"""
S11 训练主循环装配。规格见 SPEC.md R-S11.1~11.7 + 验收 A-S11.1。

这是"装配"不是"发明":loss 三件套(losses.py)、采样/tiling(sampling.py)、
止损(early_stop.py)都已实现并测试。本文件把它们与 dataloader、优化器、评测钩子
串成 Lightning 循环。需 GPU + 真实数据 + NeMo 模型,沙盒不跑;关键处带断言,本地跑即抓错。

装配结构:
  RubatoDataModule  — 从分片读样本,dialect 采样,tiling,collate 成 batch
  RubatoLitModule   — 封装 S10 的模型,training_step 用 batch_sequence_loss,
                      eval hook 跑 nASAP/MAESTRO
  train()           — 装 optimizer(R-S11.4)、schedule、止损回调,启动
"""
from __future__ import annotations
import gc
import os
from pathlib import Path

from rubato.model.sampling import dialect_sampler, tiling_offset, DIALECT_MIX
from rubato.model.early_stop import StopController


# ---------------------------------------------------------------- optimizer 装配(R-S11.4)

def build_optimizer(model, cfg: dict):
    """
    R-S11.4:AdamW,decoder/encoder 差分学习率(热启动 encoder 降载)。
    encoder lr=1e-4,其余 5e-4。返回 (optimizer, scheduler)。
    """
    import torch
    enc_params, other_params = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        # 声学 encoder 归组:匹配点分路径里独立的 'encoder' 段(命中 'encoder.*' 与
        # 'model.encoder.*',但不误收 'transf_encoder.*' 那个解码侧模块)。
        # 旧写法 name.startswith("encoder") 在 NeMo 把模型包一层(名字变 'model.encoder.')
        # 时会【静默】把 encoder 全划进 other_params,热启动差分 lr 失效且不报错。
        is_enc = "encoder" in name.split(".")
        (enc_params if is_enc else other_params).append(p)

    # 热启动的核心就是给 encoder 降载 lr;encoder 组为空 = 差分 lr 名存实亡,必须炸响不静默。
    if not enc_params:
        sample = [n for n, _ in model.named_parameters()][:12]
        raise ValueError(
            "build_optimizer:未匹配到任何 encoder 参数,差分学习率会退化为全模型同 lr。"
            f"请检查参数命名(样本 {sample})并调整归组规则。")
    if not other_params:
        raise ValueError(
            "build_optimizer:除 encoder 外没有任何可训练参数，decoder/output head 不会更新")

    lr_enc = float(cfg.get("lr_encoder", 1e-4))
    lr_dec = float(cfg.get("lr_decoder", 5e-4))
    betas = tuple(cfg.get("betas", (0.9, 0.98)))
    wd = float(cfg.get("wd", 0.01))
    warmup = int(cfg.get("warmup_steps", 1500))
    max_steps = int(cfg.get("max_steps", 100000))
    min_ratio = float(cfg.get("min_lr_ratio", 0.1))
    if lr_enc <= 0 or lr_dec <= 0:
        raise ValueError(f"学习率必须 >0: encoder={lr_enc} decoder={lr_dec}")
    if len(betas) != 2 or not (0 <= betas[0] < 1 and 0 <= betas[1] < 1):
        raise ValueError(f"AdamW betas 非法:{betas}")
    if wd < 0 or warmup < 0 or max_steps <= 0 or not (0 <= min_ratio <= 1):
        raise ValueError(
            f"优化器/scheduler 配置非法:wd={wd} warmup={warmup} "
            f"max_steps={max_steps} min_lr_ratio={min_ratio}")

    opt = torch.optim.AdamW([
        {"params": enc_params, "lr": lr_enc},
        {"params": other_params, "lr": lr_dec},
    ], betas=betas, weight_decay=wd)

    def lr_lambda(step):
        if step < warmup:
            return step / max(warmup, 1)
        import math
        progress = (step - warmup) / max(max_steps - warmup, 1)
        cos = 0.5 * (1 + math.cos(math.pi * min(progress, 1.0)))
        return min_ratio + (1 - min_ratio) * cos

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)
    return opt, sched


def apply_cfg_lrs(opt, sched, cfg: dict):
    """快照恢复【之后】把 cfg 的 lr 重新落到 optimizer/scheduler 上,返回各组当前 lr。
    为什么必须有:opt.load_state_dict 会把 param_groups 的 lr/initial_lr 一起还原,
    sched.load_state_dict 会还原 base_lrs —— 用 CLI 改了 lr 再续训,不重刷就被旧快照
    静默吃掉:实验以为在 3e-4 跑,实际还是 5e-4,判决整个作废。组序同 build_optimizer
    ([enc, 其余]);cfg 没改时本函数在数值上是无操作,默认续训行为不变。"""
    bases = [float(cfg.get("lr_encoder", 1e-4)), float(cfg.get("lr_decoder", 5e-4))]
    lams = getattr(sched, "lr_lambdas", None)
    for i, (g, base) in enumerate(zip(opt.param_groups, bases)):
        g["initial_lr"] = base
        g["lr"] = base * (lams[i](sched.last_epoch) if lams else 1.0)
    sched.base_lrs = [g["initial_lr"] for g in opt.param_groups]
    return [g["lr"] for g in opt.param_groups]


def group_grad_norms(param_groups):
    """各 param_group 的【裁剪前】梯度 L2 范数,顺序同 build_optimizer(enc, dec)。
    为什么单列:总 gn 只回答"裁剪吃掉多少",回答不了"梯度流向了谁"——H2(encoder
    声学→钢琴域适应不足)的直接观测就是分组范数:enc 长期 << dec 说明 encoder 几乎
    收不到信号,lr_encoder 调多大都无从谈起;enc/dec 同量级则 H2 失血。
    勾稽:gn_total² ≈ enc² + dec²(clip 与本函数覆盖同一批带 .grad 参数),
    日志里两者并排,分组遗漏会当场对不上账。"""
    import torch
    out = []
    for g in param_groups:
        norms = [p.grad.detach().norm() for p in g["params"] if p.grad is not None]
        out.append(float(torch.norm(torch.stack(norms))) if norms else 0.0)
    return out


def normalize_accumulated_gradients(parameters, n_sequences: int):
    """把 ``sum(micro_batch_mean * B)`` 的梯度归一成有效 batch 的逐序列平均。

    梯度累积的边界由音频秒数决定，但论文损失的归约单位是“序列”。旧实现再按音频秒
    缩放 micro-batch mean，会让长样本获得更大权重，且结果依赖 micro-batch 如何切分。
    """
    if n_sequences <= 0:
        raise ValueError(f"累计序列数必须 >0，得到 {n_sequences}")
    inv = 1.0 / float(n_sequences)
    for p in parameters:
        if p.grad is not None:
            p.grad.mul_(inv)


def clip_gradients(parameters, max_norm: float) -> float:
    """裁剪并在 optimizer.step 前拒绝 NaN/Inf 梯度。"""
    import math
    import torch
    max_norm = float(max_norm)
    if not math.isfinite(max_norm) or max_norm <= 0:
        raise ValueError(f"clip_norm 必须为正有限数，得到 {max_norm}")
    return float(torch.nn.utils.clip_grad_norm_(
        parameters, max_norm, error_if_nonfinite=True))


def new_step_metrics() -> dict:
    """一个 optimizer step（可含多个 micro-batch）的无偏监控累加器。"""
    return {
        "n_seq": 0, "micro_batches": 0, "audio_sec": 0.0,
        "loss_sum": 0.0,
        "sem_sum": 0.0, "n_sem": 0,
        "ts_sum": 0.0, "n_ts": 0,
        "pitch_sum": 0.0, "n_pitch": 0,
        "acoustic_aux_sum": 0.0, "acoustic_event_sum": 0.0,
        "acoustic_align_sum": 0.0, "acoustic_f1_sum": 0.0,
        "n_acoustic": 0,
        "dialect_sem": {},
    }


def accumulate_step_metrics(state: dict, parts: dict):
    """把一个 micro-batch 汇入 optimizer-step 口径；返回同一个 state。"""
    b = int(parts.get("batch_size", 0))
    if b <= 0:
        raise ValueError(f"training_step 未报告有效 batch_size: {b}")
    state["n_seq"] += b
    state["micro_batches"] += 1
    state["audio_sec"] += float(parts.get("batch_audio_sec", 0.0))
    state["loss_sum"] += float(parts["loss"].detach()) * b
    for value_key, count_key, sum_key in (
            ("semantic_loss", "n_sem", "sem_sum"),
            ("ts_loss", "n_ts", "ts_sum"),
            ("pitch_loss", "n_pitch", "pitch_sum")):
        n = int(parts.get(count_key, 0) or 0)
        value = parts.get(value_key)
        if n and value is not None:
            state[sum_key] += float(value) * n
            state[count_key] += n
    n_acoustic = int(parts.get("n_acoustic", 0) or 0)
    if n_acoustic:
        state["acoustic_aux_sum"] += float(parts["acoustic_aux_loss"]) * n_acoustic
        state["acoustic_event_sum"] += float(parts["acoustic_event_loss"]) * n_acoustic
        state["acoustic_align_sum"] += float(parts["acoustic_align_loss"]) * n_acoustic
        if parts.get("acoustic_frame_f1") is not None:
            state["acoustic_f1_sum"] += (
                float(parts["acoustic_frame_f1"]) * n_acoustic)
        state["n_acoustic"] += n_acoustic
    for d, (v, n) in (parts.get("dialect_sem") or {}).items():
        old_sum, old_n = state["dialect_sem"].get(d, (0.0, 0))
        state["dialect_sem"][d] = (old_sum + float(v) * int(n), old_n + int(n))
    return state


def finalize_step_metrics(state: dict) -> dict:
    """把累加器化成日志/止损用的完整 optimizer-step 指标。"""
    n_seq = int(state["n_seq"])
    if n_seq <= 0:
        raise ValueError("空 optimizer step 不能汇总")
    return {
        "loss": state["loss_sum"] / n_seq,
        "semantic_loss": state["sem_sum"] / max(int(state["n_sem"]), 1),
        "ts_loss": state["ts_sum"] / max(int(state["n_ts"]), 1),
        "pitch_loss": (state["pitch_sum"] / state["n_pitch"]
                       if state["n_pitch"] else None),
        "acoustic_aux_loss": (
            state["acoustic_aux_sum"] / state["n_acoustic"]
            if state["n_acoustic"] else None),
        "acoustic_event_loss": (
            state["acoustic_event_sum"] / state["n_acoustic"]
            if state["n_acoustic"] else None),
        "acoustic_align_loss": (
            state["acoustic_align_sum"] / state["n_acoustic"]
            if state["n_acoustic"] else None),
        "acoustic_frame_f1": (
            state["acoustic_f1_sum"] / state["n_acoustic"]
            if state["n_acoustic"] else None),
        "n_acoustic": int(state["n_acoustic"]),
        "dialect_sem": {d: (s / n, n) for d, (s, n) in state["dialect_sem"].items()
                        if n},
        "batch_audio_sec": float(state["audio_sec"]),
        "batch_size": n_seq,
        "micro_batches": int(state["micro_batches"]),
    }


# ---------------------------------------------------------------- CUDA memory health

_MIB = 1024 ** 2


def cuda_memory_snapshot(torch_module=None) -> dict | None:
    """Return allocator + driver counters without synchronizing the device."""
    if torch_module is None:
        import torch as torch_module
    cuda = torch_module.cuda
    if not cuda.is_available():
        return None
    stats = cuda.memory_stats()
    try:
        free_b, total_b = cuda.mem_get_info()
    except (RuntimeError, AttributeError):
        free_b, total_b = None, None
    try:
        backend = cuda.get_allocator_backend()
    except (RuntimeError, AttributeError):
        backend = "unknown"
    return {
        "allocated": int(cuda.memory_allocated()),
        "reserved": int(cuda.memory_reserved()),
        "peak_allocated": int(cuda.max_memory_allocated()),
        "peak_reserved": int(cuda.max_memory_reserved()),
        "inactive_split": int(
            stats.get("inactive_split_bytes.all.current", 0)),
        "alloc_retries": int(stats.get("num_alloc_retries", 0)),
        "ooms": int(stats.get("num_ooms", 0)),
        "driver_free": int(free_b) if free_b is not None else None,
        "driver_total": int(total_b) if total_b is not None else None,
        # Global driver usage minus this process's PyTorch reservation.  It can
        # include cuDNN/third-party allocations and other GPU processes, so do
        # not mislabel it as a Python leak.
        "driver_untracked": (
            max(int(total_b) - int(free_b) - int(cuda.memory_reserved()), 0)
            if free_b is not None and total_b is not None else None),
        "backend": str(backend),
    }


def maintain_cuda_memory(reason: str, *, force: bool = False,
                         min_free_mb: float = 1024,
                         min_reclaimable_mb: float = 512,
                         torch_module=None, collect_cycles=None) -> dict | None:
    """Observe memory and release unused cache only at a caller-safe boundary.

    ``empty_cache`` cannot release live tensors and is therefore gated by both
    low driver headroom and allocator cache.  Evaluation may force a release
    because its temporary allocation shapes differ substantially from training.
    The caller must first drop its batch/loss references.
    """
    if torch_module is None:
        import torch as torch_module
    before = cuda_memory_snapshot(torch_module)
    if before is None:
        return None
    free_b = before["driver_free"]
    low_free = free_b is not None and free_b < float(min_free_mb) * _MIB
    # A full Python GC walk is expensive with the 700k+ sample object graph.
    # Only scan when pressure is real or when eval has just created a distinct
    # set of temporary objects.
    if force or low_free:
        (gc.collect if collect_cycles is None else collect_cycles)()
        after_gc = cuda_memory_snapshot(torch_module)
    else:
        after_gc = before
    cached_b = max(after_gc["reserved"] - after_gc["allocated"], 0)
    enough_cache = cached_b >= float(min_reclaimable_mb) * _MIB
    release = bool((force or low_free) and enough_cache)
    if release:
        torch_module.cuda.empty_cache()
    after = cuda_memory_snapshot(torch_module)
    try:
        torch_module.cuda.reset_peak_memory_stats()
    except (RuntimeError, AttributeError):
        pass
    return {
        "reason": str(reason),
        "action": "empty_cache" if release else "observe",
        "low_free": low_free,
        "cached_before_release": cached_b,
        "before": before,
        "after_gc": after_gc,
        "after": after,
    }


def format_cuda_memory_event(event: dict | None) -> str | None:
    """Compact, grep-friendly production log line for memory maintenance."""
    if event is None:
        return None
    before, after = event["after_gc"], event["after"]

    def mb(value):
        return "?" if value is None else f"{value / _MIB:.0f}"

    released = max(before["reserved"] - after["reserved"], 0)
    return (
        f"CUDA_MEM reason={event['reason']} action={event['action']} "
        f"alloc={mb(after['allocated'])}MiB reserved={mb(after['reserved'])}MiB "
        f"cached={mb(max(after['reserved'] - after['allocated'], 0))}MiB "
        f"inactive_split={mb(after['inactive_split'])}MiB "
        f"driver_free={mb(after['driver_free'])}MiB "
        f"driver_untracked={mb(after['driver_untracked'])}MiB "
        f"peak_reserved={mb(before['peak_reserved'])}MiB "
        f"released={mb(released)}MiB retries={after['alloc_retries']} "
        f"ooms={after['ooms']} backend={after['backend']}")


# ---------------------------------------------------------------- 动态 bucketing(R-S11.4)

def bucket_batches(samples: list[dict], max_batch_sec: float = 560.0,
                   max_attn_sq: int | None = None):
    """
    R-S11.4:动态 bucketing,每 batch 音频总时长 ≤max_batch_sec。
    samples 按时长排序后贪心装桶。返回 [[sample,...], ...]。

    【必须喂"补零后"的时长】(执行端 29.5GB OOM 实测):tiling 会把音频前置补零到
    t0+dur(最长 40s),按补零前时长记账会让 2s 样本装 30 个、实际膨胀到上千秒。
    调用方(train_batches)负责把 dur_s 换算成有效时长。
    max_attn_sq:第二预算 B×Lmax²(decoder 自注意力显存 ∝ 批内条数×最长文本²;
    短音频长文本的批会从这个口子爆)。sample 带 "tok"=目标 token 数时生效。
    """
    ordered = sorted(samples, key=lambda s: s.get("dur_s", 0))
    batches, cur, cur_sec, cur_lmax = [], [], 0.0, 0
    for s in ordered:
        d = float(s.get("dur_s", 0))
        if d > max_batch_sec:
            raise ValueError(
                f"单样本 {s.get('utt_id', '?')}/{s.get('dialect', '?')} 时长 {d:.3f}s "
                f"> max_batch_sec={max_batch_sec:.3f}s；调用方必须先显式隔离并记账")
        L = int(s.get("tok", 0) or 0)
        new_lmax = max(cur_lmax, L)
        over_sec = cur and cur_sec + d > max_batch_sec
        over_attn = (cur and max_attn_sq
                     and (len(cur) + 1) * new_lmax * new_lmax > max_attn_sq)
        if over_sec or over_attn:
            batches.append(cur)
            cur, cur_sec, cur_lmax = [], 0.0, 0
            new_lmax = L
        cur.append(s)
        cur_sec += d
        cur_lmax = new_lmax
    if cur:
        batches.append(cur)
    return batches


# ---------------------------------------------------------------- 训练步(R-S11.1 装配)

def resolve_log_probs(output):
    """
    从 NeMo forward 的返回值中取出 log_probs,形态不认识就【抛错】。
    EncDecMultiTaskModel.forward(..., transcript=input_ids, transcript_length=...)
    返回 4 元组 (transf_log_probs, encoded_len, enc_states, enc_mask)。
    旧实现按 dict/Tensor 判断、判不中就静默用 0.0 当 loss —— 训练会"跑通但学不到任何东西"。
    这里绝不静默:未知形态直接 TypeError。
    """
    import torch
    if isinstance(output, (tuple, list)):
        lp = output[0]
        if not isinstance(lp, torch.Tensor):
            raise TypeError(f"forward 返回元组但首元素非 Tensor: {type(lp)}")
        return lp
    if isinstance(output, dict):
        for k in ("log_probs", "transf_log_probs"):
            if k in output:
                return output[k]
        if "logits" in output:
            return torch.log_softmax(output["logits"], dim=-1)
        raise TypeError(f"forward 返回 dict 但无 log_probs/logits 键: {list(output)}")
    if isinstance(output, torch.Tensor):
        return output
    raise TypeError(f"无法从 forward 输出提取 log_probs: {type(output)}")


def training_step_logic(model, batch, tokenizer, ts_token_ids=None, loss_cfg=None,
                        guards: dict | None = None):
    """
    单训练步。返回 {loss(带梯度), semantic_loss, ordinal_loss, ...}。

    batch 契约(rubato/data/dataset.py 的 collate 产出):
      audio          (B, S)  原始波形(16k mono,tiling 补齐后)
      audio_lens     (B,)    有效采样点数
      input_ids      (B, L)  decoder 输入 = [prompt + 标签 + eot] 去掉最后一位(teacher forcing 右移)
      input_lens     (B,)    input_ids 有效长度
      labels         (B, L)  目标 = 完整序列去掉第一位(与 input_ids 错一位对齐)
      token_types    (B, L)  0=语义 1=时间戳(与 labels 对齐)
      loss_mask      (B, L)  bool,prompt 位置 False(R-S10.4)
      ts_bins        (B, L)  时间戳位置的 bin 编号(其余位置 0,被 mask 忽略)

    loss 路径(修复:三件套现在真正进 backward,不再只是监控指标):
      NeMo preprocessor → encoder/decoder forward(teacher forcing)→ transf_log_probs
      → batch_sequence_loss(语义 label-smooth + 时间戳序数平滑 + 1/√|T| 序列归一)
    """
    import torch
    from rubato.model.losses import batch_sequence_loss, build_ts_token_ids

    device = next(model.parameters()).device
    audio = batch["audio"].to(device)
    audio_len = batch["audio_lens"].to(device)
    input_ids = batch["input_ids"].to(device)
    input_lens = batch["input_lens"].to(device)
    labels = batch["labels"].to(device)
    token_types = batch["token_types"].to(device)
    loss_mask = batch["loss_mask"].to(device)
    ts_bins = batch["ts_bins"].to(device)

    if ts_token_ids is None:
        ts_token_ids = build_ts_token_ids(tokenizer)
    ts_token_ids = ts_token_ids.to(device)

    # 【前置守卫】索引越界在 GPU 上是异步 device assert,栈指向随机后续 kernel(执行端三次
    # 崩溃三个不同栈)。在 forward 之前用精确断言拦下,报错自带肇事数字。
    if audio.ndim != 2 or input_ids.ndim != 2 or labels.shape != input_ids.shape:
        raise ValueError(
            f"batch 形状错误:audio={tuple(audio.shape)} input={tuple(input_ids.shape)} "
            f"labels={tuple(labels.shape)}")
    for name, value in (("token_types", token_types), ("loss_mask", loss_mask),
                        ("ts_bins", ts_bins)):
        if value.shape != labels.shape:
            raise ValueError(
                f"{name} 形状 {tuple(value.shape)} != labels {tuple(labels.shape)}")
    if bool((audio_len <= 0).any()) or bool((audio_len > audio.shape[1]).any()):
        raise ValueError(
            f"audio_lens 越界:min={int(audio_len.min())} max={int(audio_len.max())} "
            f"padded={audio.shape[1]}")
    if bool((input_lens <= 0).any()) or bool((input_lens > input_ids.shape[1]).any()):
        raise ValueError(
            f"input_lens 越界:min={int(input_lens.min())} max={int(input_lens.max())} "
            f"padded={input_ids.shape[1]}")
    if bool((loss_mask.sum(-1) <= 0).any()):
        raise ValueError("batch 含零有效目标 token 的序列")
    positions = torch.arange(labels.shape[1], device=device).unsqueeze(0)
    valid_positions = positions < input_lens.unsqueeze(1)
    if bool((loss_mask & ~valid_positions).any()):
        raise ValueError("loss_mask 在 input_lens 之外仍为 True，padding 会污染 loss")
    scored_types = token_types[loss_mask]
    if bool(((scored_types != 0) & (scored_types != 1)).any()):
        bad = torch.unique(scored_types[(scored_types != 0) & (scored_types != 1)])
        raise ValueError(f"计分 token_types 只能为 0/1，得到 {bad[:10].tolist()}")
    ts_positions = loss_mask & (token_types == 1)
    if bool(ts_positions.any()):
        ts_values = ts_bins[ts_positions]
        if bool((ts_values < 0).any()) or bool((ts_values >= len(ts_token_ids)).any()):
            raise ValueError(
                f"ts_bins 越界:min={int(ts_values.min())} max={int(ts_values.max())} "
                f"合法=[0,{len(ts_token_ids) - 1}]")
        expected_ts_labels = ts_token_ids[ts_values]
        if not bool(torch.equal(labels[ts_positions], expected_ts_labels)):
            raise ValueError(
                "时间戳 label id 与 ts_bins→tokenizer 映射不一致；"
                "token_types/右移或 tokenizer 已损坏")
    if guards:
        v = guards.get("vocab")
        if v:
            ni, nl = int(input_ids.min()), int(labels.min())
            mi, ml = int(input_ids.max()), int(labels.max())
            if ni < 0 or nl < 0 or mi >= v or ml >= v:
                raise ValueError(
                    f"token id 越界:input=[{ni},{mi}] labels=[{nl},{ml}] "
                    f"词表=[0,{v - 1}] —— tokenizer/词表替换不一致")
        p = guards.get("max_pos")
        if p and int(input_ids.shape[1]) > p:
            raise ValueError(
                f"目标序列长 {input_ids.shape[1]} > 位置表 {p} 行 —— "
                "超长过滤没生效或上限读错")

    # 1. raw wav → mel(必须走 canary 自带 preprocessor,R-S10.3 前端一致性)
    processed, processed_len = model.preprocessor(input_signal=audio, length=audio_len)

    # 2. teacher-forcing forward。EncDecMultiTaskModel 返回
    #    (transf_log_probs, encoded_len, enc_states, enc_mask);transf_log_probs 已 log-softmax。
    output = model.forward(
        processed_signal=processed, processed_signal_length=processed_len,
        transcript=input_ids, transcript_length=input_lens,
    )
    log_probs = resolve_log_probs(output)
    if log_probs.dim() != 3:
        raise ValueError(f"log_probs 应为 (B,L,V),得 {tuple(log_probs.shape)}")
    if log_probs.shape[:2] != labels.shape:
        raise ValueError(
            f"log_probs {tuple(log_probs.shape[:2])} 与 labels {tuple(labels.shape)} "
            "未对齐 —— 检查 teacher-forcing 右移")
    if guards and guards.get("vocab") \
            and int(log_probs.shape[-1]) != int(guards["vocab"]):
        raise ValueError(
            f"模型输出词表 {log_probs.shape[-1]} != tokenizer {guards['vocab']}；"
            "词表替换函数可能写了但未真正接入输出头")
    if not bool(torch.isfinite(log_probs).all()):
        raise FloatingPointError("模型 forward 产生 NaN/Inf log_probs")

    cfg = loss_cfg or {}
    parts = batch_sequence_loss(
        log_probs, labels, token_types, loss_mask, ts_bins, ts_token_ids,
        label_smoothing=cfg.get("sem_label_smooth", 0.1),
        p_center=cfg.get("p_center", 0.9), w=cfg.get("w", 5),
        pitch_weight=float(cfg.get("pitch_weight", 1.0)),
        pitch_mask=cfg.get("pitch_mask"),
    )
    loss = parts["loss"]
    aux_report = None
    aux_cfg = dict(cfg.get("acoustic_aux") or {})
    aux_weight = float(aux_cfg.get("weight", 0.0))
    if aux_weight > 0:
        if not isinstance(output, (tuple, list)) or len(output) < 4:
            raise TypeError(
                "AMT auxiliary loss requires Canary forward tuple "
                "(log_probs, encoded_len, enc_states, enc_mask)")
        encoded_len, enc_states = output[1], output[2]
        if not isinstance(enc_states, torch.Tensor) or enc_states.dim() != 3:
            raise ValueError(
                f"AMT auxiliary encoder states must be (B,T,D), got "
                f"{type(enc_states)} "
                f"{getattr(enc_states, 'shape', None)}")
        if not isinstance(encoded_len, torch.Tensor) \
                or encoded_len.shape != audio_len.shape:
            raise ValueError(
                f"AMT auxiliary encoded lengths invalid: "
                f"{getattr(encoded_len, 'shape', None)} vs "
                f"{tuple(audio_len.shape)}")
        refs = batch.get("acoustic_refs")
        if refs is None or len(refs) != int(audio.shape[0]):
            raise ValueError(
                "AMT auxiliary enabled but batch has no aligned acoustic_refs; "
                "construct RubatoDataset(acoustic_targets=True)")
        head = getattr(model, "rubato_amt_aux_head", None)
        if head is None:
            raise RuntimeError(
                "AMT auxiliary enabled but model.rubato_amt_aux_head is absent")
        from rubato.model.acoustic_aux import (
            acoustic_auxiliary_loss, build_acoustic_targets)
        targets = build_acoustic_targets(
            refs, encoded_len, int(enc_states.shape[1]), audio_len,
            sample_rate=int(aux_cfg.get("sample_rate", 16000)),
            onset_radius=int(aux_cfg.get("onset_radius", 1)))
        aux_logits = head(enc_states)
        aux_report = acoustic_auxiliary_loss(
            aux_logits, targets,
            alignment_weight=float(aux_cfg.get("alignment_weight", 0.25)),
            alignment_margin=float(aux_cfg.get("alignment_margin", 0.10)))
        # Main loss is a mean over B sequences.  Auxiliary loss is a mean over
        # the supervised subset, so multiply by n_aux/B before the outer
        # accumulation code multiplies the whole loss by B.
        supervised_ratio = (
            float(aux_report["n_supervised"]) / max(int(audio.shape[0]), 1))
        loss = loss + aux_weight * aux_report["loss"] * supervised_ratio
    if not loss.requires_grad:
        raise RuntimeError("loss 无梯度 —— forward 图断了(检查 no_grad/detach)")
    if not bool(torch.isfinite(loss)):
        raise FloatingPointError(f"loss 非有限: {loss}")

    # 按 dialect 聚合逐序列 sem/ts(用户建议:四方言各自的学习曲线,别混成一个总数)
    dialect_sem: dict = {}
    dialect_ts: dict = {}
    ds = batch.get("dialects")
    if ds and "seq_sem" in parts:
        for i, d in enumerate(ds):
            if not d:
                continue
            dialect_sem.setdefault(d, []).append(float(parts["seq_sem"][i]))
            if bool(parts["seq_has_ts"][i]):
                dialect_ts.setdefault(d, []).append(float(parts["seq_ts"][i]))
    result = {
        "loss": loss,
        "semantic_loss": parts["sem"],
        "ordinal_loss": parts["ts"],
        "ts_loss": parts["ts"],
        "pitch_loss": parts.get("pitch"), "n_pitch": parts.get("n_pitch", 0),
        "n_sem": parts["n_sem"], "n_ts": parts["n_ts"],
        "dialect_sem": {d: (sum(v) / len(v), len(v)) for d, v in dialect_sem.items()},
        "dialect_ts": {d: (sum(v) / len(v), len(v)) for d, v in dialect_ts.items()},
        "batch_audio_sec": float(audio_len.sum().item()) / 16000.0,
        "batch_size": int(labels.shape[0]),
        "seq_lengths": batch.get("seq_lengths", loss_mask.sum(-1)),
    }
    if aux_report is not None:
        result.update({
            "acoustic_aux_loss": aux_report["loss"].detach(),
            "acoustic_event_loss": aux_report["event_loss"].detach(),
            "acoustic_align_loss": aux_report["alignment_loss"].detach(),
            "acoustic_frame_f1": aux_report["frame_f1"],
            "n_acoustic": aux_report["n_supervised"],
        })
    return result


# ---------------------------------------------------------------- 评测钩子(R-S11.5)

def viol_tally(entries: list) -> dict:
    """
    eval 拒因直方图(D43,执行端提议采纳):entries = [(is_fallback, viol_list)]。
    回答"parseable 卡在哪类校验"——兜底样本只记「兜底」(其 viol 是对兜底常量的校验,
    非模型产物);其余按违规类别记样本数(一样本可入多类);零违规记「通过」。
    """
    out: dict = {}

    def _add(c):
        out[c] = out.get(c, 0) + 1

    for fb, viols in entries:
        if fb:
            _add("兜底")
            continue
        if not viols:
            _add("通过")
            continue
        cats = set()
        for v in viols:
            s = str(v)
            if s.startswith("DYCK"):
                cats.add("DYCK")
            elif s.startswith("MEASURE"):
                cats.add("MEASURE")
            elif s.startswith("TERMINAL_BAR"):
                cats.add("TERMINAL")
            elif s.startswith("empty"):
                cats.add("兜底")
            else:
                cats.add(s.split(":", 1)[0][:16] or "OTHER")
        for c in cats:
            _add(c)
    return out


def _eval_subset(samples: list[dict], eval_max: int) -> list[dict]:
    """确定性抽 eval 子集(按 utt_id 哈希排序取前 N)—— nasap/maestro val 可达数千段,
    每 3000 步全量跑 beam 解码要小时级;子集稳定(与步数/epoch 无关),指标可跨 eval 对比。"""
    if eval_max <= 0 or len(samples) <= eval_max:
        return samples
    import hashlib
    return sorted(samples, key=lambda s: hashlib.sha256(
        str(s.get("utt_id", id(s))).encode()).hexdigest())[:eval_max]


def _sample_audio(sample: dict):
    """eval 样本音频:既收预载数组(sample["audio"]),也收 assemble 的 utt dict
    (audio_path + 可选 win —— build_dataset 传进来的就是这种,旧版直接 KeyError)。"""
    if sample.get("audio") is not None:
        return sample["audio"]
    path = sample.get("audio_path")
    if not path:
        return None
    from rubato.data.dataset import load_audio
    try:
        return load_audio(path, win=sample.get("win"))
    except Exception:
        return None


def run_eval_hooks(model, nasap_val, maestro_val, tokenizer, labels: dict | None = None,
                   eval_max: int = 128,
                   time_budget_s: float = 1200.0,
                   autolog: str | None = None, step: int | None = None,
                   probe_utts: list | None = None,
                   decode_legs: bool = True) -> dict:
    """
    R-S11.5:nASAP val 跑可解析率/文本 NED 代理；MAESTRO val 跑 AMT F1。
    样本 = assemble 的 utt dict(audio_path/win/dur_s)或预载 {audio, ...};音频按需窗读。
    labels: {utt_id: {A2S..AMT}} —— 参照标签的唯一来源:AMT F1 的 ref_notes 由参照 AMT
      文本反解(amt_text_to_notes)。没有 LEGATO 时只计算明确标名的 A2S 文本代理
      text_ned_proxy，绝不写成 OMR-NED。有参照但缺音频/解码失败的样本必须留在分母；
      无参照样本不属于该指标的评测集合。
    正式 LEGATO 只能在 scripts/eval_final.py 对整曲预测和原始参考 XML 运行。训练窗
      既不是整曲也没有等价参考版面，不能通过“可选回调”伪装成论文 OMR-NED。
    返回指标 dict(含诊断量 empty_rate/n_eval),喂给 StopController。
    """
    from rubato.model.infer import infer_a2s, infer_amt, _EMPTY_A2S   # S12
    from rubato.intermo.core import text_to_units, validate_units
    from rubato.model.evaluate import note_f1, amt_text_to_notes, text_ned

    labels = labels or {}
    metrics = {"parseable_rate": 0.0, "val_text_ned_proxy": None,
               "a2s_note_f1": None, "maestro_amt_f1": None,
               "empty_rate": None, "n_eval_nasap": 0, "n_eval_maestro": 0,
               "n_text_proxy_scored": 0, "text_proxy_coverage": 0.0,
               "n_audio_missing": 0, "amt_eval_truncated": False,
               "eval_complete": False}

    # 证据行:打印 + 缓存,eval 末尾原样追加进 autolog 文件(git 里的报告由代码写,
    # 执行端只 commit 不编辑 —— 人肉摘录三次丢失/删改证据后,把这一步从人手里拿走)。
    _lines: list[str] = []

    def _p(s: str):
        print(s, flush=True)
        _lines.append(s)

    # nASAP val:生成 + 可解析率。
    # 注意:infer_a2s 失败时兜底返回 _EMPTY_A2S(合法空谱)—— 若把它算"可解析",
    # 可解析率会被结构性钉在 ~1.0,R-S11.7 的 <80% 止损永远不触发。空谱按不可解析计。
    # empty_rate 单列:≈1.0 说明是解码 API 胶水没接上(NeMo generate 签名),不是模型烂 ——
    # 两者都表现为 pause_unparseable,诊断量必须能区分。
    import time as _time
    from rubato.model import infer as _inf
    _inf.LAST_INFER_ERROR = None          # 吞错现场:本轮 eval 只看本轮的
    _inf.LAST_DECODE_DEBUG = None
    t_eval0 = _time.time()
    n_ok, n_total, n_empty = 0, 0, 0
    truncated = False
    proxy_scores = []                    # 训练监控代理；永不冒充 OMR-NED
    viol_entries: list = []              # (is_fallback, viol_list) → viol_tally 拒因直方图
    sample_preds: list[str] = []
    ok_pred = ok_utt = ok_ref = None     # 首个过校验的预测(展示偏差修复:别只看失败样本)
    probe: dict = {}
    n_probed = 0
    _probe0 = None                       # 样本0 的 (参照, 方言, domain),供错配对照
    if probe_utts:
        # 多源 Δsem 探针(固定池,逐 eval 可比):每源一条,真音频 vs 静音的语义命中率差
        # = "模型的音频阅读能力"进度表 —— 单源探针曾两次把全局判决带偏(D27/D28)。
        n_probed = 99                    # 停用循环内单源探针,以本池为准
        from rubato.model.infer import teacher_forced_probe as _tfp
        import numpy as _np
        _fmt2 = lambda v: "-" if v is None else f"{v:.2f}"
        for u in probe_utts:
            _lab = labels.get(u.get("utt_id"), {}) or {}
            _dia = next((x for x in ("TAST", "A2S", "AMT") if _lab.get(x)), None)
            aud = _sample_audio(u)
            if not _dia or aud is None:
                _p(f"  eval 多源探针 {u.get('kind')}[{u.get('utt_id')}]: 缺标签/音频,跳过")
                continue
            try:
                pr = _tfp(model, aud, _lab[_dia], _dia, tokenizer, domain=u.get("domain"))
                mu = _tfp(model, _np.zeros_like(_np.asarray(aud, dtype=_np.float32)),
                          _lab[_dia], _dia, tokenizer, domain=u.get("domain"))
                ds = (pr["acc_sem"] - mu["acc_sem"]) \
                    if (pr.get("acc_sem") is not None and mu.get("acc_sem") is not None) else None
                dt = (pr["acc_ts"] - mu["acc_ts"]) \
                    if (pr.get("acc_ts") is not None and mu.get("acc_ts") is not None) else None
                dpit = (pr["acc_pitch"] - mu["acc_pitch"]) \
                    if (pr.get("acc_pitch") is not None and mu.get("acc_pitch") is not None) else None
                _p(f"  eval 多源探针 {u.get('kind')}/{_dia}[{u.get('utt_id')}]: "
                   f"Δsem={_fmt2(ds) if ds is None else f'{ds:+.2f}'} "
                   f"Δts={_fmt2(dt) if dt is None else f'{dt:+.2f}'} "
                   f"Δpitch={_fmt2(dpit) if dpit is None else f'{dpit:+.2f}'} "
                   f"真sem={_fmt2(pr.get('acc_sem'))} 静sem={_fmt2(mu.get('acc_sem'))} "
                   f"真pitch={_fmt2(pr.get('acc_pitch'))} "
                   f"acc={pr['acc']:.2f} n={pr['n_scored']}")
                if not probe:
                    probe = pr
            except Exception as e:
                _p(f"  eval 多源探针 {u.get('kind')}[{u.get('utt_id')}] 失败: "
                   f"{type(e).__name__}: {e}")
    # 【D77】双节奏评测:探针(教师强制,秒级)每次都跑 —— 试验主判据只靠它;
    # 解码腿(48×逐 token 生成,~25 分钟)按 --eval-decode-every 稀疏跑。
    # decode_legs=False 时到此为止:落盘探针证据,返回 probe_only 标记
    # (调用侧据此跳过 stopper/best.pt,这不是一次"指标为 0 的坏 eval")。
    if not decode_legs:
        _p("  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)")
        if autolog and _lines:
            try:
                from pathlib import Path as _P
                fp = _P(autolog)
                fp.parent.mkdir(parents=True, exist_ok=True)
                with open(fp, "a", encoding="utf-8") as fh:
                    fh.write(f"\n## eval @ step {step if step is not None else '?'} "
                             f"({_time.strftime('%Y-%m-%d %H:%M:%S')})\n")
                    fh.write("\n".join(_lines) + "\n")
                print(f"  eval 证据已落盘 {fp}(git add + commit + push 即完成上报,勿编辑)",
                      flush=True)
            except Exception as e:
                print(f"  ⚠ eval 证据落盘失败({type(e).__name__}: {e})—— 贴回本行", flush=True)
        return {"probe_only": True, "probe": probe}

    subset = _eval_subset(nasap_val, eval_max)
    for si, sample in enumerate(subset):
        # 时限 + 心跳:eval 是逐 token 生成,慢是常态 —— 没有这两样,"慢"和"卡死"
        # 在执行端不可区分(实测 30 分钟无输出被当成 hang)。超时截断,按已评样本出指标。
        if _time.time() - t_eval0 > time_budget_s:
            truncated = True
            _p(f"  eval 时限 {time_budget_s:.0f}s 用尽,截断于 {si}/{len(subset)}(指标按已评样本)")
            break
        if si % 8 == 0:
            print(f"  eval nasap {si}/{len(subset)}({_time.time() - t_eval0:.0f}s)", flush=True)
        n_total += 1
        audio = _sample_audio(sample)
        if audio is None:
            metrics["n_audio_missing"] += 1
            viol_entries.append((True, ["audio_missing"]))
            if len(sample_preds) < 2:
                sample_preds.append("<AUDIO_MISSING>")
            continue
        pred = infer_a2s(model, audio, tokenizer, domain=sample.get("domain"))
        infer_stats = dict(getattr(_inf, "LAST_INFER_STATS", {}) or {})
        if len(sample_preds) < 2:              # 模型实际吐了什么 —— 定性"胶水坏/模型早"的直接证据
            sample_preds.append(pred[:160])
        if n_probed < 2:
            # 教师强制探针(每次 eval 前两个有参照的样本,~秒级):自由生成塌缩的病因分诊,
            # 命中率还是比 parseable 灵敏得多的进度表。失败不许影响 eval 主流程。
            # 三组对照回答"decoder 有没有在从音频读内容":
            #   样本0 真音频 vs 静音(Δsem);样本1 到位后再加【错配】= 样本0 的谱 × 样本1 的
            #   音频(比静音更严:静音可能只是超纲输入,错配是分布内的真钢琴声)。
            # 每行带 rms=音频能量 —— 对照输入确实不同,由日志自证(22000 步三指标全同引发过怀疑)。
            _lab = labels.get(sample.get("utt_id"), {}) or {}
            _dia = "TAST" if _lab.get("TAST") else ("A2S" if _lab.get("A2S") else None)
            if _dia:
                try:
                    import numpy as _np
                    from rubato.model.infer import teacher_forced_probe
                    _fmt = lambda v: "-" if v is None else f"{v:.2f}"
                    _rms = lambda a: float(_np.sqrt(_np.mean(_np.square(
                        _np.asarray(a, dtype=_np.float32)))))
                    pr = teacher_forced_probe(model, audio, _lab[_dia], _dia,
                                              tokenizer, domain=sample.get("domain"))
                    _p(f"  eval 探针[{sample.get('utt_id', '?')}/{_dia}]: "
                          f"acc={pr['acc']:.2f} 前缀acc={pr['acc_prefix']:.2f} "
                          f"sem={_fmt(pr.get('acc_sem'))} ts={_fmt(pr.get('acc_ts'))} "
                          f"eotP@首位={pr['eot_p_first']:.4f} n={pr['n_scored']} "
                          f"rms={_rms(audio):.4f} enc帧={pr.get('enc_frames', '-')} "
                          f"enc_std={_fmt(pr.get('enc_std'))}"
                          + (f" 截断至{pr['truncated_to']}" if pr.get('truncated_to') else ""))
                    if n_probed == 0:
                        probe = pr
                        _probe0 = (_lab[_dia], _dia, sample.get("domain"))
                        _p(f"  eval 探针argmax: {pr.get('argmax_prefix', '')!r}")
                        _p(f"  eval 探针参照:   {pr.get('ref_prefix', '')!r}")
                        muted = _np.zeros_like(_np.asarray(audio, dtype=_np.float32))
                        mu = teacher_forced_probe(model, muted, _lab[_dia], _dia,
                                                  tokenizer, domain=sample.get("domain"))
                        d_sem = (pr["acc_sem"] - mu["acc_sem"]) \
                            if (pr.get("acc_sem") is not None and mu.get("acc_sem") is not None) else None
                        _p(f"  eval 探针(静音对照): acc={mu['acc']:.2f} "
                              f"sem={_fmt(mu.get('acc_sem'))} ts={_fmt(mu.get('acc_ts'))} "
                              f"rms={_rms(muted):.4f} enc_std={_fmt(mu.get('enc_std'))} "
                              f"Δsem={_fmt(d_sem) if d_sem is None else f'{d_sem:+.2f}'}"
                              f"(真音频语义命中 − 静音;≈0 = decoder 没在读音频内容)")
                    elif _probe0 is not None:
                        # 错配对照:样本0 的参照谱 × 本样本(样本1)的音频。
                        # 与样本0 真音频行同参照可直接比:一致 → 音频换成谁都一样 = 没在读。
                        r0, d0, dom0 = _probe0
                        wp = teacher_forced_probe(model, audio, r0, d0, tokenizer, domain=dom0)
                        _p(f"  eval 探针(错配音频): acc={wp['acc']:.2f} "
                              f"sem={_fmt(wp.get('acc_sem'))} ts={_fmt(wp.get('acc_ts'))} "
                              f"rms={_rms(audio):.4f}"
                              f"(样本0 的谱 × 本样本音频;与样本0行一致 = 没在读音频)")
                    n_probed += 1
                except Exception as e:
                    if not probe:
                        probe = {"error": f"{type(e).__name__}: {e}"}
                    n_probed += 1
                    _p(f"  eval 探针失败({type(e).__name__}: {e})—— 贴回本行")
        viol = validate_units(text_to_units(pred)) if pred else ["empty"]
        is_fallback = bool(infer_stats.get("fallback")) or pred == _EMPTY_A2S
        is_partial = infer_stats.get("status") == "partial"
        if is_fallback:
            n_empty += 1
            viol = viol or ["empty_fallback"]
        if is_partial:
            viol = list(viol) + [
                f"partial_windows:{infer_stats.get('n_failed_windows', 0)}"]
        # 拒因直方图 v2(D44):v1 拿 pred 复验 —— 但校验拒绝发生在 infer 层内部,eval 只
        # 见兜底常量,直方图退化成 empty 率(58000-61000 实测全是"兜底=4x")。真实违规
        # 由 infer.LAST_VIOLS 带出:有真实违规 = 模型输出被校验拦下(按类计);无 = 异常/空路径。
        _tv = list(getattr(_inf, "LAST_VIOLS", []) or [])
        # 通过样本无条件记「通过」:beam 首试失败、greedy 复活的样本,LAST_VIOLS 留有首试
        # 残留,不清会把通过样本计进拒类(abtest 首跑实测 通过=3 vs parseable=5)
        if not viol and not is_fallback and not is_partial:
            viol_entries.append((False, []))
        else:
            viol_entries.append((is_fallback and not _tv, _tv or viol))
        if not viol:
            n_ok += 1
            if ok_pred is None and not is_fallback:
                # 首个真正通过校验的预测:样本预测[0]/[1] 是确定性子集的前两个样本,
                # 它们长期失败 → 显示的永远是兜底常量,通过的样本反而从未被看见(展示偏差)
                ok_pred = pred[:160]
                ok_utt = sample.get("utt_id", "?")
                ok_ref = (labels.get(ok_utt, {}) or {}).get("A2S") or ""
            ref_a2s = labels.get(sample.get("utt_id"), {}).get("A2S")
            if ref_a2s:
                proxy_scores.append(text_ned(pred, ref_a2s))
    metrics["parseable_rate"] = n_ok / max(n_total, 1)
    metrics["empty_rate"] = (n_empty / n_total) if n_total else None
    metrics["n_eval_nasap"] = n_total
    metrics["eval_truncated"] = truncated
    metrics["n_text_proxy_scored"] = len(proxy_scores)
    metrics["text_proxy_coverage"] = len(proxy_scores) / max(n_total, 1)
    for k, p in enumerate(sample_preds):
        _p(f"  eval 样本预测[{k}]: {p!r}")
    if ok_pred is not None:
        _p(f"  eval 样本预测[首个通过 {ok_utt}]: {ok_pred!r}")
        _p(f"  eval 同样本参照:              {ok_ref[:160]!r}")
    # 兜底 ≠ 模型输出:'|4/4k0' 是异常/拒绝的兜底常量(执行端 6 轮 eval 被它蒙蔽)。
    # 只要出现兜底,把吞错现场打出来 —— 模型真实输出/违规项/异常栈,三选一必有。
    if n_empty:
        if _inf.LAST_DECODE_DEBUG:
            _p(f"  eval 解码现场: {_inf.LAST_DECODE_DEBUG}")
        if _inf.LAST_INFER_ERROR:
            _p(f"  eval 兜底异常: {_inf.LAST_INFER_ERROR[:600]}")
        if not (_inf.LAST_DECODE_DEBUG or _inf.LAST_INFER_ERROR):
            _p("  eval 兜底但无现场记录 —— 空谱来自非异常路径,贴回本行")
    if proxy_scores:
        metrics["val_text_ned_proxy"] = sum(proxy_scores) / len(proxy_scores)
    if viol_entries:
        _vt = viol_tally(viol_entries)
        _p("  eval 拒因(样本数): "
           + " ".join(f"{k}={v}" for k, v in sorted(_vt.items(), key=lambda kv: (-kv[1], kv[0])))
           + f" /共{len(viol_entries)}")
    # 一行汇总:把判读必需的全部证据压进单行 —— 执行端按行摘录日志时,丢哪行都不致盲
    _p0 = sample_preds[0][:60] if sample_preds else ""
    _pr = (f"探针acc={probe['acc']:.2f}/前缀{probe['acc_prefix']:.2f}"
           f" eotP0={probe['eot_p_first']:.4f}") if probe.get("n_scored") else \
          (f"探针err={probe.get('error', '无参照')}" if probe else "探针=未跑")
    # 【D72】n 太小的 parseable 没有统计力(n=2 全空的概率在真率 0.10 下高达 81%)——
    # 印成 NA 防误判读;r2 试验就是被 n=2 的 0.00 错杀的。
    _pv = (f"{metrics['parseable_rate']:.2f}" if n_total >= 12
           else f"NA(n={n_total}<12勿判读)")
    _p(f"  eval 汇总: parseable={_pv} "
          f"empty={metrics['empty_rate']} n={n_total} 样本0={_p0!r} {_pr}")

    # MAESTRO val:AMT note F1(mir_eval)。R-S11.7 的"步≥8000 且 AMT F1<70 → 停训"
    # 依赖它;参照音符从该窗的真值 AMT 文本反解。无参照样本跳过(不打 0 分)。
    f1s = []
    maestro_subset = _eval_subset(maestro_val, eval_max)
    n_amt_expected = sum(
        1 for s in maestro_subset if labels.get(s.get("utt_id"), {}).get("AMT"))
    n_amt_ref_invalid = 0
    n_amt_audio_missing = 0
    amt_truncated = False
    for si, sample in enumerate(maestro_subset):
        if _time.time() - t_eval0 > 2 * time_budget_s:     # AMT 共享总时限(nasap 用掉一份)
            _p(f"  eval 总时限用尽,AMT 截断于 {si}")
            amt_truncated = True
            break
        if si % 8 == 0:
            print(f"  eval maestro {si}({_time.time() - t_eval0:.0f}s)", flush=True)
        ref_text = labels.get(sample.get("utt_id"), {}).get("AMT")
        if not ref_text:
            continue
        try:
            ref_notes = amt_text_to_notes(ref_text)
        except Exception:
            n_amt_ref_invalid += 1
            continue
        if not ref_notes:
            n_amt_ref_invalid += 1
            continue
        audio = _sample_audio(sample)
        if audio is None:
            n_amt_audio_missing += 1
            f1s.append(0.0)               # 有参照却读不到音频：不能从分母消失
            continue
        pred_text = infer_amt(model, audio, tokenizer,
                              domain=sample.get("domain"))
        try:
            est_notes = amt_text_to_notes(pred_text)
        except Exception:
            est_notes = []
        f1s.append(note_f1(ref_notes, est_notes)["f1"])
    metrics["n_eval_maestro"] = len(f1s)
    metrics["n_eval_maestro_expected"] = n_amt_expected
    metrics["n_amt_ref_invalid"] = n_amt_ref_invalid
    metrics["n_amt_audio_missing"] = n_amt_audio_missing
    metrics["amt_eval_truncated"] = amt_truncated
    metrics["eval_complete"] = (
        (len(subset) > 0 or n_amt_expected > 0)
        and not truncated and not amt_truncated
        and n_total == len(subset)
        and metrics["n_audio_missing"] == 0
        and n_amt_ref_invalid == 0
        and len(f1s) == n_amt_expected)
    if f1s:
        metrics["maestro_amt_f1"] = 100.0 * sum(f1s) / len(f1s)
    _p(f"  eval 指标: parseable={metrics['parseable_rate']:.2f} "
       f"amt_f1={metrics['maestro_amt_f1']} "
       f"text_ned_proxy={metrics['val_text_ned_proxy']} "
       f"proxy_scored={metrics['n_text_proxy_scored']}/{metrics['n_eval_nasap']} "
       f"n_maestro={metrics['n_eval_maestro']}/{n_amt_expected} "
       f"complete={metrics['eval_complete']}")

    # 证据自动落盘(追加,不覆盖):报告由代码写,执行端只 commit —— 摘录/删改这一步收走
    if autolog and _lines:
        try:
            from pathlib import Path as _P
            fp = _P(autolog)
            fp.parent.mkdir(parents=True, exist_ok=True)
            with open(fp, "a", encoding="utf-8") as fh:
                fh.write(f"\n## eval @ step {step if step is not None else '?'} "
                         f"({_time.strftime('%Y-%m-%d %H:%M:%S')})\n")
                fh.write("\n".join(_lines) + "\n")
            print(f"  eval 证据已落盘 {fp}(git add + commit + push 即完成上报,勿编辑)",
                  flush=True)
        except Exception as e:
            print(f"  ⚠ eval 证据落盘失败({type(e).__name__}: {e})—— 贴回本行", flush=True)

    return metrics


def proxy_metric_eligible(metrics: dict, min_scored: int = 12,
                          min_coverage: float = 0.80) -> bool:
    """训练监控的文本代理是否完整；字段与正式 LEGATO OMR-NED 永久分离。"""
    return (
        metrics.get("val_text_ned_proxy") is not None
        and metrics.get("eval_complete", False)
        and not metrics.get("eval_truncated", False)
        and not metrics.get("amt_eval_truncated", False)
        and int(metrics.get("n_text_proxy_scored", 0)) >= min_scored
        and float(metrics.get("text_proxy_coverage", 0.0)) >= min_coverage)


# ---------------------------------------------------------------- 断点续训(长跑生死线)

def _mp_producer(dm, epoch, start_batch, q):
    """预取子进程入口(必须模块级:Windows spawn 按引用导入)。纯 CPU,永不碰 CUDA。"""
    try:
        import os
        import pickle as _pk
        os.environ["CUDA_VISIBLE_DEVICES"] = ""     # 防御:子进程绝不许抢显存/初始化 CUDA
        for b in dm.train_batches(epoch, start_batch=start_batch):
            # 按值序列化:mp 队列对 torch 张量默认走共享内存【引用】,子进程一死引用即失效
            # (实测 ConnectionReset/FileNotFound)。显式 pickle 成字节 = 生命周期完全解耦。
            q.put(("batch", _pk.dumps(b, protocol=4)))
        q.put(("end", None))
    except BaseException:
        import traceback
        try:
            q.put(("error", traceback.format_exc()))
        except Exception:
            pass


def prefetch_batches(dm, epoch: int, depth: int = 3, start_batch: int = 0,
                     first_timeout_s: float = 1800.0, steady_timeout_s: float = 600.0):
    """
    【进程级】预取:子进程跑同一个 train_batches 生成器,批经进程队列传回,主进程只喂 GPU。

    为什么是进程不是线程(D40):线程版实测把 GPU 利用率从 ~50% 打到 ~20% —— 装批线程与
    主线程共享 GIL/CPU 线程池,kernel 发射节奏被卡死;这正是官方 DataLoader 用进程的原因。
    语义保证不变:同一生成器、同一调用顺序,批内容/顺序与串行逐字节相同(tests_prefetch)。

    无人值守兜底(27h 约束):启动失败(不可 pickle)/子进程死亡/超时/异常 → 打印完整现场
    (行首统一「预取:」,贴回可 grep),【自动退回串行装批】从尚未消费的 cursor 继续，
    不重复训练已消费批。depth<=0 = 串行。
    """
    if depth <= 0:
        yield from dm.train_batches(epoch, start_batch=start_batch)
        return
    import multiprocessing as _mp
    import queue as _q
    import time as _time
    ctx = _mp.get_context("spawn")                  # 与执行端 Windows 同语义;沙盒测的就是它
    q = ctx.Queue(maxsize=max(1, int(depth)))
    try:
        p = ctx.Process(target=_mp_producer, args=(dm, epoch, start_batch, q),
                        daemon=True, name="batch-producer")
        p.start()
    except Exception as e:
        print(f"预取: 进程起不来({type(e).__name__}: {e})→ 本 epoch 串行装批", flush=True)
        yield from dm.train_batches(epoch, start_batch=start_batch)
        return
    import pickle as _pk
    n = 0
    deadline = _time.time() + first_timeout_s
    try:
        while True:
            try:
                kind, payload = q.get(timeout=5.0)
                if kind == "batch":
                    payload = _pk.loads(payload)
            except _q.Empty:
                if not p.is_alive():                # 静默死亡(pickle 失败/被杀/OOM):秒级发现
                    print(f"预取: 子进程死亡且队列已空(已收 {n} 批)→ 从 "
                          f"batch_cursor={start_batch + n} 串行续跑", flush=True)
                    yield from dm.train_batches(epoch, start_batch=start_batch + n)
                    return
                if _time.time() > deadline:         # 活着但卡死:超时止损
                    print(f"预取: 子进程超时(已收 {n} 批)→ 杀之，从 "
                          f"batch_cursor={start_batch + n} 串行续跑", flush=True)
                    yield from dm.train_batches(epoch, start_batch=start_batch + n)
                    return
                continue
            except Exception as e:                  # 主侧接收/反序列化故障:同样不许停训
                print(f"预取: 主侧接收异常({type(e).__name__}: {e},已收 {n} 批)"
                      f"→ 从 batch_cursor={start_batch + n} 串行续跑", flush=True)
                yield from dm.train_batches(epoch, start_batch=start_batch + n)
                return
            deadline = _time.time() + steady_timeout_s
            if kind == "batch":
                n += 1
                yield payload
            elif kind == "end":
                return
            else:                                   # "error":子进程完整栈带回
                print(f"预取: 子进程异常(已收 {n} 批)→ 从 "
                      f"batch_cursor={start_batch + n} 串行续跑;现场:\n"
                      f"{payload}", flush=True)
                yield from dm.train_batches(epoch, start_batch=start_batch + n)
                return
    finally:
        try:
            p.terminate()
        except Exception:
            pass


def timed_iter(gen, stat: dict):
    """
    装批/计算时间分账(D41:两次提速尝试都建立在"GPU 利用率 52% ⇒ 48% 时间在等数据"
    这个【未经测量的换算】上,双双负收益 —— 计算阶段内部利用率本就可以远低于 100%,
    利用率不是时间份额)。本计时器把每步真实拆成两个数:
      stat["data"] += 等 __next__ 返回的墙钟(装批);stat["comp"] += 两次取批之间的墙钟(计算)。
    损失标量在日志缓冲处已隐式同步 CUDA,step 粒度的分账是诚实的。开销 = 每 micro-batch
    两次 perf_counter,可忽略。提速决策树(预登记)只认这两个数。
    """
    import time as _time
    it = iter(gen)
    last_out = None
    while True:
        t0 = _time.perf_counter()
        if last_out is not None:
            stat["comp"] = stat.get("comp", 0.0) + (t0 - last_out)
        try:
            b = next(it)
        except StopIteration:
            return
        last_out = _time.perf_counter()
        stat["last_data"] = last_out - t0
        stat["data"] = stat.get("data", 0.0) + stat["last_data"]
        yield b


def save_snapshot(path, model, opt, sched, step: int, epoch: int,
                  batch_cursor: int = 0):
    """全状态快照(模型+优化器+调度器+进度),原子替换写。为什么必须有:执行端 16GB 卡
    余量 45MiB,数周长跑必然中途崩;只存模型权重的 ckpt 恢复不了 Adam 动量和 lr 进度,
    崩一次等于从头再来。"""
    import torch
    import random
    import numpy as np
    from pathlib import Path as _P
    path = _P(path)
    tmp = path.with_suffix(".tmp")
    has_cuda_params = any(p.is_cuda for p in model.parameters())
    np_state = np.random.get_state()
    rng = {
        "python": random.getstate(),
        # PyTorch 2.6 默认 weights_only=True；NumPy ndarray 不是安全白名单类型。
        # 转成纯容器，保持快照可由安全加载器读取。
        "numpy": {
            "bit_generator": np_state[0],
            "keys": np_state[1].tolist(),
            "pos": int(np_state[2]),
            "has_gauss": int(np_state[3]),
            "cached_gaussian": float(np_state[4]),
        },
        "torch": torch.get_rng_state(),
        "cuda": (torch.cuda.get_rng_state_all()
                 if has_cuda_params and torch.cuda.is_available() else None),
    }
    torch.save({"model": model.state_dict(), "optimizer": opt.state_dict(),
                "scheduler": sched.state_dict(), "step": step, "epoch": epoch,
                "batch_cursor": int(batch_cursor), "rng_state": rng,
                "snapshot_version": 3}, tmp)
    tmp.replace(path)                          # 原子:写一半崩不会毁掉上一份


def _load_optimizer_allowing_appended_params(opt, saved_state: dict,
                                             allow_append: bool = False) -> int:
    """Load Adam state while allowing new parameters appended to an old group.

    An auxiliary head added after a checkpoint has no Adam moments yet.  PyTorch
    normally rejects the whole restore because the parameter count differs.
    The base parameter order is unchanged and the head is registered last, so
    extending the saved group's id list preserves every existing state exactly;
    Adam initializes only the new tensors lazily on their first step.
    """
    import copy

    current = opt.state_dict()
    saved = copy.deepcopy(saved_state)
    old_groups = saved.get("param_groups") or []
    new_groups = current.get("param_groups") or []
    if len(old_groups) != len(new_groups):
        raise ValueError(
            f"optimizer group count changed: {len(old_groups)} -> "
            f"{len(new_groups)}")
    appended = 0
    for i, (old, new) in enumerate(zip(old_groups, new_groups)):
        old_ids = list(old.get("params") or [])
        new_ids = list(new.get("params") or [])
        if len(old_ids) > len(new_ids):
            raise ValueError(
                f"optimizer group {i} shrank: {len(old_ids)} -> "
                f"{len(new_ids)}")
        extra = len(new_ids) - len(old_ids)
        if extra:
            if not allow_append or i != len(new_groups) - 1:
                raise ValueError(
                    f"optimizer group {i} gained {extra} parameters")
            old["params"] = old_ids + new_ids[len(old_ids):]
            appended += extra
    opt.load_state_dict(saved)
    return appended


def load_snapshot(path, model, opt, sched, allow_legacy_cursor: bool = False,
                  allow_new_model_prefixes: tuple[str, ...] = (),
                  allow_optimizer_param_append: bool = False):
    """恢复快照 → (step, epoch, next_batch_cursor)。

    文件不存在才返回 None；存在但损坏必须中止，绝不能伪装成“从头训练”。v1 快照没有
    epoch 内 cursor，只有显式 ``allow_legacy_cursor`` 才允许从该 epoch 头重放。
    """
    import torch
    from pathlib import Path as _P
    path = _P(path)
    if not path.exists():
        return None
    try:
        import random
        import numpy as np
        snap = torch.load(str(path), map_location="cpu")
        if "batch_cursor" not in snap and not allow_legacy_cursor:
            raise RuntimeError(
                "旧版快照缺 batch_cursor，无法保证不重复训练整个 epoch。"
                "如确认接受一次从 epoch 开头重放，请显式加 "
                "--allow-legacy-resume-from-epoch-start")
        incompatible = model.load_state_dict(snap["model"], strict=False)
        missing = list(incompatible.missing_keys)
        unexpected = list(incompatible.unexpected_keys)
        bad_missing = [
            k for k in missing
            if not any(k.startswith(prefix)
                       for prefix in allow_new_model_prefixes)]
        if bad_missing or unexpected:
            raise RuntimeError(
                f"model state mismatch: missing={bad_missing[:10]} "
                f"unexpected={unexpected[:10]}")
        appended = _load_optimizer_allowing_appended_params(
            opt, snap["optimizer"],
            allow_append=allow_optimizer_param_append)
        if missing and appended != len(missing):
            raise RuntimeError(
                f"new model parameters and optimizer append differ: "
                f"missing={len(missing)} appended={appended}")
        if not missing and appended:
            raise RuntimeError(
                f"optimizer gained {appended} parameters without new model keys")
        sched.load_state_dict(snap["scheduler"])
        if missing:
            print(
                f"  实验续训:旧快照无新模块参数 {len(missing)} 个，"
                f"已随机初始化；旧 optimizer 状态完整恢复，新增参数 {appended} 个"
                "由 Adam 首步初始化",
                flush=True)
        rng = snap.get("rng_state")
        if rng:
            random.setstate(rng["python"])
            ns = rng["numpy"]
            if isinstance(ns, dict):
                np.random.set_state((
                    ns["bit_generator"], np.asarray(ns["keys"], dtype=np.uint32),
                    int(ns["pos"]), int(ns["has_gauss"]),
                    float(ns["cached_gaussian"])))
            else:
                # 兼容开发期短暂写出的 v3 草案（需显式非安全加载才可能读到）。
                np.random.set_state(ns)
            torch.set_rng_state(rng["torch"])
            if rng.get("cuda") is not None and torch.cuda.is_available():
                torch.cuda.set_rng_state_all(rng["cuda"])
        else:
            print("⚠ 旧版快照无 RNG 状态：权重/优化器可续训，但 dropout/随机采样轨迹"
                  "无法逐位复现；下一次保存将升级为 v3", flush=True)
        cursor = int(snap.get("batch_cursor", 0))
        if "batch_cursor" not in snap:
            print("⚠ 显式允许旧版快照：本次将从保存 epoch 的开头重放", flush=True)
        return int(snap.get("step", 0)), int(snap.get("epoch", 0)), cursor
    except Exception as e:
        raise RuntimeError(
            f"快照存在但恢复失败，已中止以防静默从 step 0 重训：{path} "
            f"({type(e).__name__}: {e})") from e


def save_train_control(path, step: int, best_eval_metric: dict,
                       stopper: StopController) -> None:
    """原子保存小型训练决策状态，避免恢复后 best/平台历史失忆。"""
    import json
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    payload = {
        "version": 1, "step": int(step),
        "best_eval_metric": {
            str(k): (None if v == float("inf") else float(v))
            for k, v in best_eval_metric.items()},
        "stopper": stopper.state_dict(),
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(path)


def load_train_control(path, snapshot_step: int, best_eval_metric: dict,
                       stopper: StopController) -> bool:
    """恢复训练决策状态；损坏或时间线领先都硬失败，不静默重置。"""
    import json
    path = Path(path)
    if not path.exists():
        return False
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        control_step = int(state["step"])
        if control_step > int(snapshot_step):
            raise ValueError(
                f"control step {control_step} 领先 snapshot step {snapshot_step}")
        for k, v in (state.get("best_eval_metric") or {}).items():
            if k in best_eval_metric and v is not None:
                best_eval_metric[k] = float(v)
        stopper.load_state_dict(state.get("stopper") or {})
        return True
    except Exception as e:
        raise RuntimeError(
            f"训练控制状态损坏，拒绝在 best/早停历史失忆后续训：{path} "
            f"({type(e).__name__}: {e})") from e


# ---------------------------------------------------------------- 主循环(R-S11.6/11.7)

def train(model, datamodule, cfg: dict, tokenizer,
          eval_every_steps: int = 3000):
    """
    主训练循环。装 optimizer + 止损 + checkpoint。需 GPU,本地跑。
    R-S11.6:每 eval 存 ckpt,滚动保留 6,选完整 val 文本 NED 代理最低。
    论文可比的 LEGATO OMR-NED 只由 scripts/eval_final.py 对整曲计算。
    R-S11.7:StopController 四触发。
    """
    import torch
    from rubato.model.losses import build_ts_token_ids
    acoustic_cfg = dict(cfg.get("acoustic_aux") or {})
    acoustic_enabled = float(acoustic_cfg.get("weight", 0.0)) > 0
    acoustic_head_report = None
    if acoustic_enabled:
        from rubato.model.acoustic_aux import attach_amt_aux_head
        acoustic_head_report = attach_amt_aux_head(
            model,
            hidden_dim=int(acoustic_cfg.get("hidden_dim", 0)),
            dropout=float(acoustic_cfg.get("dropout", 0.0)))
    # 【必须在建 optimizer 前搬 GPU】build_model 是 map_location="cpu" 恢复的,谁都不搬的话
    # 整套训练【静默】跑 CPU(batch 张量跟着模型设备走,不报错,只是慢百倍)。
    # cfg["device"]="cpu" 是诊断模式:CUDA 的 device assert 是异步的、栈不可信,
    # CPU 上同一越界会给出精确 Python 栈 + 肇事索引(--smoke N --cpu 用)。
    if torch.cuda.is_available() and cfg.get("device") != "cpu":
        model = model.cuda()
    opt, sched = build_optimizer(model, cfg)
    stopper = StopController()
    ckpt_dir = Path(cfg.get("ckpt_dir", "outputs/ckpt"))
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    step = 0
    start_epoch = 0
    max_steps = int(cfg.get("max_steps", 100000))
    stop_after_step = int(cfg.get("stop_after_step") or max_steps)
    if stop_after_step <= 0 or stop_after_step > max_steps:
        raise ValueError(
            f"stop_after_step 必须在 (0, max_steps] 内:"
            f"{stop_after_step} vs {max_steps}")
    stop_tag = ("max_steps_reached"
                if stop_after_step == max_steps
                else "stop_after_step_reached")
    log_every = int(cfg.get("log_every", 50))
    save_every = int(cfg.get("save_every_steps", 200))
    memory_cfg = dict(cfg.get("cuda_memory") or {})
    memory_check_every = int(memory_cfg.get("check_every_steps", save_every))
    memory_min_free_mb = float(memory_cfg.get("min_free_mb", 1024))
    memory_min_reclaimable_mb = float(
        memory_cfg.get("min_reclaimable_mb", 512))
    memory_cleanup_after_eval = bool(
        memory_cfg.get("cleanup_after_eval", True))
    if (memory_check_every <= 0 or memory_min_free_mb <= 0
            or memory_min_reclaimable_mb <= 0):
        raise ValueError(
            "CUDA memory 配置非法:"
            f"check_every={memory_check_every} min_free={memory_min_free_mb} "
            f"min_reclaimable={memory_min_reclaimable_mb}")
    selection_metric = str(cfg.get("selection_metric", "text_ned_proxy"))
    if selection_metric != "text_ned_proxy":
        raise ValueError(
            f"不支持的训练期 checkpoint 选择指标:{selection_metric}")
    best_eval_metric = {selection_metric: float("inf")}
    recent, recent_sem, recent_ts = [], [], []      # 近 50 步窗口(日志 + final_* 判据)
    recent_pv: list = []                            # 音高 CE 滚动窗(D82,训练侧"听没听"直读)
    recent_aux: list = []                           # encoder AMT auxiliary BCE
    recent_aux_align: list = []                     # correct-vs-mismatched margin
    recent_aux_f1: list = []                        # encoder frame occupancy F1
    recent_gn: list = []                            # 裁剪前梯度范数(有效 lr 是否被裁剪吃掉)
    recent_td: list = []                            # 完整 optimizer-step 的装批等待
    recent_tc: list = []                            # 完整 optimizer-step 的计算墙钟
    recent_dia: dict = {}                           # {dialect: [近 200 条 seq sem]}(各自学习曲线)
    report = {"stop_events": [], "eval_history": []}

    def _dia_line() -> str:
        return " ".join(f"{d}={sum(v) / len(v):.2f}" for d, v in sorted(recent_dia.items()) if v)

    def _finish(tag: str):
        report["final"] = tag
        report["final_loss"] = round(sum(recent) / len(recent), 4) if recent else None
        report["final_sem"] = round(sum(recent_sem) / len(recent_sem), 4) if recent_sem else None
        report["final_ts"] = round(sum(recent_ts) / len(recent_ts), 4) if recent_ts else None
        report["final_acoustic_aux"] = (
            round(sum(recent_aux) / len(recent_aux), 4)
            if recent_aux else None)
        report["final_acoustic_frame_f1"] = (
            round(sum(recent_aux_f1) / len(recent_aux_f1), 4)
            if recent_aux_f1 else None)
        report["final_sem_by_dialect"] = {d: round(sum(v) / len(v), 4)
                                          for d, v in recent_dia.items() if v}
        return report

    # 【配置回显,必须在一切训练输出之前】指令经人转发,"跑的是不是那份配置"必须能从
    # 日志自证 —— H1 实验首份贴回就无法确认 --clip-norm 是否生效,判决差点悬空。
    # 此行进贴回清单:没有它 = 旧代码,先 git pull。
    print(f"训练配置回显: clip_norm={float(cfg.get('clip_norm', 1.0))} "
          f"config={cfg.get('train_config', '<programmatic>')} "
          f"lr_enc={float(cfg.get('lr_encoder', 1e-4)):.1e} "
          f"lr_dec={float(cfg.get('lr_decoder', 5e-4)):.1e} "
          f"accum={float(cfg.get('grad_accum_to_audio_sec', 2000)):.0f}s "
          f"batch_sec={getattr(datamodule, 'max_batch_sec', '?')} "
          f"precision={cfg.get('precision') or 'fp32'} max_steps={max_steps} "
          f"stop_after={stop_after_step} "
          f"eval_every={eval_every_steps} eval_max={cfg.get('eval_max', 128)} "
          f"eval_decode_every={int(cfg.get('eval_decode_every') or 0) or eval_every_steps} "
          + ("mix=D2纸面(.35/.15/.20/.30)" if not cfg.get("dialect_mix") else
             "mix=" + ",".join(f"{d}:{v:.3f}" for d, v in sorted(cfg["dialect_mix"].items())))
          + f" prefetch={'proc:' + str(int(cfg.get('prefetch_batches', 0))) if int(cfg.get('prefetch_batches', 0)) > 0 else '关'}"
          + f" aug_acoustic={'开' if getattr(getattr(datamodule, 'train_ds', None), 'acoustic_aug', False) else '关'}"
          + (f" amt_aux=w{float(acoustic_cfg.get('weight')):g}"
             f"/align{float(acoustic_cfg.get('alignment_weight', 0.25)):g}"
             f"/margin{float(acoustic_cfg.get('alignment_margin', 0.10)):g}"
             f"/params{acoustic_head_report['n_params']}"
             if acoustic_enabled else " amt_aux=关")
          + f" allocator={os.environ.get('PYTORCH_ALLOC_CONF', '<unset>')}"
          + f" mem_check={memory_check_every}step/{memory_min_free_mb:g}MiB",
          flush=True)
    # 指令随日志走(执行端只看日志不看文档的现实约束):贴回要求印在产物里
    print("【执行端贴回】① 上面的配置回显行(应含 prefetch=关) ② 续训:恢复… 行 "
          "③ 跑 1 小时后:连续 5 行带 td=/tc= 的日志(不含 eval 的窗口) "
          "④ 任务管理器→详细信息→python.exe 的「专用 GPU 内存」和「共享 GPU 内存」两个数(必贴)", flush=True)

    # 断点续训:last.pt 存在且未禁用 → 全状态 + epoch 内下一批 cursor 精确恢复。
    # (_finish 定义必须在前:曾在"续训即达 max_steps"的分支上先调后定义 → UnboundLocalError)
    last_pt = ckpt_dir / "last.pt"
    control_path = ckpt_dir / "train_control.json"
    resume_batch_cursor = 0
    if cfg.get("resume", True):
        got = load_snapshot(
            last_pt, model, opt, sched,
            allow_legacy_cursor=bool(cfg.get("allow_legacy_resume_from_epoch_start", False)),
            allow_new_model_prefixes=(
                ("rubato_amt_aux_head.",) if acoustic_enabled else ()),
            allow_optimizer_param_append=acoustic_enabled)
        if got:
            step, start_epoch, resume_batch_cursor = got
            applied = apply_cfg_lrs(opt, sched, cfg)   # CLI 改 lr 必须能穿透快照,见函数注释
            print(f"续训:恢复 step={step} epoch={start_epoch} "
                  f"batch_cursor={resume_batch_cursor}(优化器/调度器状态一并恢复;"
                  f"lr 按当前配置重刷 enc={applied[0]:.2e} dec={applied[1]:.2e})")
            if load_train_control(control_path, step, best_eval_metric, stopper):
                hist_sizes = ",".join(
                    f"{k}:{len(v)}" for k, v in stopper.metric_history.items())
                print(f"  训练控制状态已恢复:best={best_eval_metric} "
                      f"metric_histories={{{hist_sizes}}}", flush=True)
            if step >= stop_after_step:
                return _finish(stop_tag)

    # 一次性预备:时间戳 id 映射 / 梯度累积额度 / bf16
    ts_token_ids = build_ts_token_ids(tokenizer)
    accum_target_sec = float(cfg.get("grad_accum_to_audio_sec", 2000))
    loss_cfg = dict(cfg.get("loss", {}))
    loss_cfg["acoustic_aux"] = acoustic_cfg
    # 【D82】音高掩码常建(毫秒级):weight=1 时仅点亮 pv= 监控列,数值路径恒等;
    # weight≠1 时按 D82 加权(均值归一,总量级不变)。
    from rubato.model.losses import build_pitch_token_mask
    loss_cfg["pitch_weight"] = float(cfg.get("pitch_loss_weight", 1.0))
    loss_cfg["pitch_mask"] = build_pitch_token_mask(
        tokenizer, int(cfg.get("vocab_size")
                       or cfg.get("guards", {}).get("vocab")
                       or tokenizer.get_piece_size()))
    print(f"  音高 piece 掩码: {int(loss_cfg['pitch_mask'].sum())} 个 | "
          f"加权 ×{loss_cfg['pitch_weight']:g}", flush=True)
    use_bf16 = (str(cfg.get("precision", "")).startswith("bf16")
                and torch.cuda.is_available())
    autocast = (lambda: torch.autocast("cuda", dtype=torch.bfloat16)) if use_bf16 \
        else (lambda: __import__("contextlib").nullcontext())

    # 跨进程恢复现有 step ckpt；否则每次重启都从空 ring 开始，“滚动6”会越积越多。
    def _step_num(path):
        try:
            return int(path.stem.removeprefix("step"))
        except ValueError:
            return -1
    ckpt_keep = int(cfg.get("ckpt_keep", 6))
    if ckpt_keep <= 0:
        raise ValueError(f"ckpt_keep 必须 >0，得到 {ckpt_keep}")
    existing_steps = sorted(ckpt_dir.glob("step*.pt"), key=_step_num)
    for stale in existing_steps[:-ckpt_keep]:
        stale.unlink(missing_ok=True)
    ckpt_ring = existing_steps[-ckpt_keep:]

    model.train()
    opt.zero_grad(set_to_none=True)
    _memory_event = maintain_cuda_memory(
        "train_start", min_free_mb=memory_min_free_mb,
        min_reclaimable_mb=memory_min_reclaimable_mb,
        torch_module=torch)
    _memory_line = format_cuda_memory_event(_memory_event)
    if _memory_line:
        print(_memory_line, flush=True)
    accum_sec = 0.0
    step_stats = new_step_metrics()
    step_data_sec = 0.0
    step_comp_sec = 0.0
    tstat = {"data": 0.0, "comp": 0.0}
    import time as _time
    for epoch in range(start_epoch, cfg.get("max_epochs", 1000)):
        epoch_cursor = resume_batch_cursor if epoch == start_epoch else 0
        stream = prefetch_batches(datamodule, epoch,
                                  depth=int(cfg.get("prefetch_batches", 0)),
                                  start_batch=epoch_cursor)
        for batch_idx, batch in enumerate(timed_iter(stream, tstat), start=epoch_cursor):
            next_batch_cursor = batch_idx + 1
            step_data_sec += float(tstat.get("last_data", 0.0))
            _micro_t0 = _time.perf_counter()
            with autocast():
                parts = training_step_logic(model, batch, tokenizer,
                                            ts_token_ids=ts_token_ids, loss_cfg=loss_cfg,
                                            guards=cfg.get("guards"))
            batch_sec = parts.get("batch_audio_sec", accum_target_sec)
            # 累积边界按音频秒数，但损失严格按“有效 batch 内每条序列等权平均”。
            # micro-batch mean × B 先求和；到边界再除总序列数，切批方式不会改变梯度。
            batch_nseq = int(parts["batch_size"])
            (parts["loss"] * batch_nseq).backward()
            accum_sec += batch_sec
            accumulate_step_metrics(step_stats, parts)
            if accum_sec < accum_target_sec:
                step_comp_sec += _time.perf_counter() - _micro_t0
                # Do not keep the completed graph/batch alive while constructing
                # the next variable-shaped micro-batch.
                del parts, batch
                continue
            normalize_accumulated_gradients(model.parameters(), step_stats["n_seq"])
            # 裁剪前范数必须可见:论文序列损失 ΣCE×T^{-½} 的量纲 ≈65(常规逐 token 平均 ≈3),
            # 梯度天然大 ~20×;若范数长期 >> clip 阈值,每步被等比压回 = 有效 lr 缩几十倍 ——
            # "前 2000 步猛降后爬行"的头号机械嫌疑,gn 数字直接定罪或排除。
            # 注意先验修正:优化器是 AdamW,更新量 m̂/√v̂ 对【恒定比例】的梯度缩放近似不变
            # (m 与 √v 同比缩放相消),纯常数裁剪对 AdamW 的有效步长影响远小于 SGD 直觉 ——
            # 所以 H1 必须靠 --clip-norm 对照实验判决,不靠此处推理(EXPERIMENT_H1.md)。
            gn_groups = group_grad_norms(opt.param_groups)   # 分组(enc/dec)裁剪前范数,H2 观测
            gn = clip_gradients(model.parameters(), float(cfg.get("clip_norm", 1.0)))
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            step_comp_sec += _time.perf_counter() - _micro_t0
            step += 1

            # 训练可观测性:没有这几行,执行端只能对着黑屏猜收敛(冒烟判据也取自这窗口)
            step_m = finalize_step_metrics(step_stats)
            # Everything below is a safe boundary: optimizer/metrics no longer
            # need the final micro-batch or its loss graph.
            del parts, batch
            _pv = step_m.get("pitch_loss")
            for buf, v in ((recent, step_m["loss"]),
                           (recent_sem, step_m["semantic_loss"]),
                           (recent_ts, step_m["ts_loss"]),
                           (recent_pv, _pv),
                           (recent_aux, step_m.get("acoustic_aux_loss")),
                           (recent_aux_align, step_m.get("acoustic_align_loss")),
                           (recent_aux_f1, step_m.get("acoustic_frame_f1")),
                           (recent_td, step_data_sec),
                           (recent_tc, step_comp_sec)):
                if v is None:
                    continue
                buf.append(v)
                if len(buf) > 50:
                    buf.pop(0)
            for d, (v, n) in (step_m.get("dialect_sem") or {}).items():
                buf = recent_dia.setdefault(d, [])
                buf.extend([v] * n)              # 按条数计权,批间混比不歪
                if len(buf) > 200:
                    del buf[: len(buf) - 200]
            recent_gn.append(gn)
            if len(recent_gn) > 50:
                recent_gn.pop(0)
            if step % log_every == 0 or step == 1:
                # td/tc 左值=本 optimizer step（含它的全部 micro-batch），avg=近50步。
                # 不再用“下次 next() 才补记上一批”的延迟口径。
                print(f"step {step} loss={recent[-1]:.4f} avg50={sum(recent)/len(recent):.4f} "
                      f"sem={recent_sem[-1]:.4f} ts={recent_ts[-1]:.4f} "
                      + (f"pv={sum(recent_pv)/len(recent_pv):.3f} " if recent_pv else "")
                      + (f"aux={sum(recent_aux)/len(recent_aux):.3f} "
                         f"axm={sum(recent_aux_align)/len(recent_aux_align):.3f} "
                         f"af1={sum(recent_aux_f1)/len(recent_aux_f1):.3f} "
                         if recent_aux else "")
                      +
                      f"gn={gn:.1f}/avg{sum(recent_gn)/len(recent_gn):.1f} "
                      f"enc={gn_groups[0]:.1f} dec={gn_groups[1]:.1f} "
                      f"lrE={opt.param_groups[0]['lr']:.2e} lrD={opt.param_groups[-1]['lr']:.2e} "
                      f"audio={step_m['batch_audio_sec']:.0f}s "
                      f"micro={step_m['micro_batches']} seq={step_m['batch_size']} "
                      f"td={step_data_sec:.1f}s/avg{sum(recent_td)/len(recent_td):.1f} "
                      f"tc={step_comp_sec:.1f}s/avg{sum(recent_tc)/len(recent_tc):.1f}"
                      f" | {_dia_line()}", flush=True)
            if step % save_every == 0:
                save_snapshot(last_pt, model, opt, sched, step, epoch,
                              batch_cursor=next_batch_cursor)

            # 下个 optimizer step 从干净的完整-step统计开始。
            accum_sec = 0.0
            step_stats = new_step_metrics()
            step_data_sec = 0.0
            step_comp_sec = 0.0

            # 评测 + 止损(D77 双节奏:探针每 eval_every 跑;解码腿按 eval_decode_every 稀疏)
            if step % eval_every_steps == 0:
                # control 状态会记录本次 eval；必须先保证同一步模型快照存在，避免
                # control.step 领先 last.pt 而恢复出混合时间线。
                if step % save_every != 0:
                    save_snapshot(last_pt, model, opt, sched, step, epoch,
                                  batch_cursor=next_batch_cursor)
                _dec_every = int(cfg.get("eval_decode_every") or 0) or eval_every_steps
                _full = (step % _dec_every == 0)
                model.eval()
                with torch.no_grad():
                    m = run_eval_hooks(model, datamodule.nasap_val,
                                       getattr(datamodule, "maestro_val", []),
                                       tokenizer,
                                       labels=getattr(datamodule, "labels", None),
                                       eval_max=int(cfg.get("eval_max", 128)),
                                       time_budget_s=float(cfg.get("eval_time_budget_s", 1200)),
                                       autolog=cfg.get("eval_autolog"), step=step,
                                        probe_utts=getattr(datamodule, "probe_utts", None),
                                        decode_legs=_full)
                report["eval_history"].append({"step": step, **m})
                _memory_event = maintain_cuda_memory(
                    f"eval_step{step}", force=memory_cleanup_after_eval,
                    min_free_mb=memory_min_free_mb,
                    min_reclaimable_mb=memory_min_reclaimable_mb,
                    torch_module=torch)
                _memory_line = format_cuda_memory_event(_memory_event)
                if _memory_line:
                    print(_memory_line, flush=True)
                if m.get("probe_only"):
                    model.train()
                    if step >= stop_after_step:       # continue 会跳过循环尾检查,此处补上
                        return _finish(stop_tag)
                    continue               # 仅探针:不进止损器/不评 best.pt(不是坏 eval)

                proxy_eligible = proxy_metric_eligible(m)
                selection_name = selection_metric if proxy_eligible else None
                selection_value = (m.get("val_text_ned_proxy")
                                   if proxy_eligible else None)
                if not m.get("eval_complete", False):
                    action = {"action": "continue",
                              "reason": "eval不完整/超时/缺音频，不进入止损器"}
                else:
                    action = stopper.update(
                        step, m["parseable_rate"], m.get("maestro_amt_f1"),
                        selection_value, recent_loss=recent[-1],
                        selection_metric=selection_name or "none")
                report["stop_events"].append({"step": step, **action})

                # ckpt(滚动 6)
                ck = ckpt_dir / f"step{step}.pt"
                torch.save({"model": model.state_dict(), "step": step, "metrics": m}, ck)
                ckpt_ring.append(ck)
                if len(ckpt_ring) > ckpt_keep:
                    old = ckpt_ring.pop(0)
                    old.unlink(missing_ok=True)
                # 文本代理只对“可解析且有参照”的样本有定义。只有完整、样本量足够且
                # 覆盖率达标的 eval 才能刷新 best.pt；正式 OMR 不参与训练选择。
                if (selection_value is not None
                        and selection_value < best_eval_metric[selection_name]):
                    best_eval_metric[selection_name] = selection_value
                    torch.save({"model": model.state_dict(), "step": step,
                                "selection_metric": selection_name,
                                "selection_value": selection_value},
                               ckpt_dir / "best.pt")
                elif m.get("val_text_ned_proxy") is not None \
                        and selection_value is None:
                    print("  best.pt 不更新:eval 未满足完整性门槛"
                          f"(proxy={m.get('n_text_proxy_scored')}/{m.get('n_eval_nasap')}, "
                          f"complete={m.get('eval_complete')})", flush=True)

                # 评测改变了 best/平台历史后立即落几十字节的小状态文件；无需再重写
                # 2GB last.pt。恢复时要求 control.step 不领先模型快照。
                save_train_control(control_path, step, best_eval_metric, stopper)

                # 处理止损动作
                act = action["action"]
                grace = int(cfg.get("parseable_grace_steps", 4000))
                sem_gate = float(cfg.get("parseable_sem_gate", 2.0))
                sem_now = (sum(recent_sem) / len(recent_sem)) if recent_sem else 99.0
                if act == "pause_unparseable" and (step < grace or sem_now > sem_gate):
                    # 双闸:R-S11.7 的 <80% 规则是给【成熟模型】抓序列化损坏的。
                    # ① 步数宽限:全新词表头早期本就不可解析;② sem 门槛:sem 还在 >2.0
                    # (远未拟合)时不可解析是"没学会",不是"坏了" —— 执行端 step4000 实测
                    # sem=3.39 被停,按此规则应继续训,趋势才是信号。
                    print(f"  (不停训:parseable={m['parseable_rate']:.2f} 但 "
                          f"step<{grace}={step < grace} / sem={sem_now:.2f}>{sem_gate}=模型未熟;"
                          "连续多个 eval 后 sem<门槛仍 0 才算真故障)", flush=True)
                elif act in ("pause_unparseable", "stop_bad_labels"):
                    return _finish(f"stopped:{act}:{action['reason']}")
                if act == "converged":
                    return _finish(f"converged:{action['reason']}")
                if act == "rollback_lr":
                    # 旧实现只回滚模型、保留 Adam 动量/调度器，得到彼此不匹配的状态。
                    # 当前 step ring 是模型-only，不能伪造“安全回滚”；明确停下交由完整
                    # snapshot 恢复，胜过继续训练一套不可解释的混合状态。
                    return _finish(f"stopped:rollback_requires_full_snapshot:"
                                   f"{action['reason']}")

                model.train()
            elif step % memory_check_every == 0:
                _memory_event = maintain_cuda_memory(
                    f"step{step}", min_free_mb=memory_min_free_mb,
                    min_reclaimable_mb=memory_min_reclaimable_mb,
                    torch_module=torch)
                _memory_line = format_cuda_memory_event(_memory_event)
                if _memory_line:
                    print(_memory_line, flush=True)

            if step >= stop_after_step:
                # Short A/B gates often end between the production 200-step
                # save boundaries. Returning without a final snapshot makes
                # the trained arm impossible to probe and silently leaves an
                # older checkpoint behind.
                if step % save_every != 0:
                    save_snapshot(last_pt, model, opt, sched, step, epoch,
                                  batch_cursor=next_batch_cursor)
                return _finish(stop_tag)
        resume_batch_cursor = 0

    return _finish("max_epochs_reached")
