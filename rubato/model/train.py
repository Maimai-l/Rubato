"""
S11 训练主循环装配。规格见 SPEC.md R-S11.1~11.7 + 验收 A-S11.1。

这是"装配"不是"发明":loss 三件套(losses.py)、采样/tiling(sampling.py)、
止损(early_stop.py)都已实现并测试。本文件把它们与 dataloader、优化器、评测钩子
串成 Lightning 循环。需 GPU + 真实数据 + NeMo 模型,沙盒不跑;关键处带断言,本地跑即抓错。

装配结构:
  RubatoDataModule  — 从分片读样本,dialect 采样,tiling,collate 成 batch
  RubatoLitModule   — 封装 S10 的模型,training_step 用 combined_loss,eval hook 跑 nASAP/MAESTRO
  train()           — 装 optimizer(R-S11.4)、schedule、止损回调,启动
"""
from __future__ import annotations
from pathlib import Path

from rubato.model.losses import combined_loss, sequence_loss
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

    opt = torch.optim.AdamW([
        {"params": enc_params, "lr": cfg.get("lr_encoder", 1e-4)},
        {"params": other_params, "lr": cfg.get("lr_decoder", 5e-4)},
    ], betas=tuple(cfg.get("betas", (0.9, 0.98))), weight_decay=cfg.get("wd", 0.01))

    # cosine + warmup
    warmup = cfg.get("warmup_steps", 1500)
    max_steps = cfg.get("max_steps", 100000)
    min_ratio = cfg.get("min_lr_ratio", 0.1)

    def lr_lambda(step):
        if step < warmup:
            return step / max(warmup, 1)
        import math
        progress = (step - warmup) / max(max_steps - warmup, 1)
        cos = 0.5 * (1 + math.cos(math.pi * min(progress, 1.0)))
        return min_ratio + (1 - min_ratio) * cos

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda)
    return opt, sched


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
        d = s.get("dur_s", 0)
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
        for k in ("log_probs", "transf_log_probs", "logits"):
            if k in output:
                return output[k]
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
    if guards:
        v = guards.get("vocab")
        if v:
            mi, ml = int(input_ids.max()), int(labels.max())
            assert mi < v and ml < v, \
                f"token id 越界:input.max={mi} labels.max={ml} ≥ 词表 {v} —— tokenizer/词表替换不一致"
        p = guards.get("max_pos")
        if p:
            L = int(input_ids.shape[1])
            assert L <= p, \
                f"目标序列长 {L} > 位置表 {p} 行 —— 超长过滤没生效或上限读错(utt 见 batch 首条)"

    # 1. raw wav → mel(必须走 canary 自带 preprocessor,R-S10.3 前端一致性)
    processed, processed_len = model.preprocessor(input_signal=audio, length=audio_len)

    # 2. teacher-forcing forward。EncDecMultiTaskModel 返回
    #    (transf_log_probs, encoded_len, enc_states, enc_mask);transf_log_probs 已 log-softmax。
    output = model.forward(
        processed_signal=processed, processed_signal_length=processed_len,
        transcript=input_ids, transcript_length=input_lens,
    )
    log_probs = resolve_log_probs(output)
    assert log_probs.dim() == 3, f"log_probs 应为 (B,L,V),得 {tuple(log_probs.shape)}"
    assert log_probs.shape[:2] == labels.shape, \
        f"log_probs {tuple(log_probs.shape[:2])} 与 labels {tuple(labels.shape)} 未对齐 —— " \
        "检查 collate 是否做了 teacher-forcing 右移(input=seq[:-1], labels=seq[1:])"

    cfg = loss_cfg or {}
    parts = batch_sequence_loss(
        log_probs, labels, token_types, loss_mask, ts_bins, ts_token_ids,
        label_smoothing=cfg.get("sem_label_smooth", 0.1),
        p_center=cfg.get("p_center", 0.9), w=cfg.get("w", 5),
    )
    loss = parts["loss"]
    assert loss.requires_grad, "loss 无梯度 —— forward 图断了(检查 no_grad/detach)"
    assert torch.isfinite(loss), f"loss 非有限: {loss}"

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
    return {
        "loss": loss,
        "semantic_loss": parts["sem"],
        "ordinal_loss": parts["ts"],
        "ts_loss": parts["ts"],
        "n_sem": parts["n_sem"], "n_ts": parts["n_ts"],
        "dialect_sem": {d: (sum(v) / len(v), len(v)) for d, v in dialect_sem.items()},
        "dialect_ts": {d: (sum(v) / len(v), len(v)) for d, v in dialect_ts.items()},
        "batch_audio_sec": float(audio_len.sum().item()) / 16000.0,
        "seq_lengths": batch.get("seq_lengths", loss_mask.sum(-1)),
    }


# ---------------------------------------------------------------- 评测钩子(R-S11.5)

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
                   legato_omr_fn=None, eval_max: int = 128,
                   time_budget_s: float = 1200.0) -> dict:
    """
    R-S11.5:nASAP val 跑 可解析率/OMR-NED;MAESTRO val 跑 AMT F1。
    样本 = assemble 的 utt dict(audio_path/win/dur_s)或预载 {audio, ...};音频按需窗读。
    labels: {utt_id: {A2S..AMT}} —— 参照标签的唯一来源:AMT F1 的 ref_notes 由参照 AMT
      文本反解(amt_text_to_notes),OMR-NED 无 LEGATO 时用 A2S 文本 NED 代理(text_ned)。
      【无参照的样本跳过、不打 0 分】—— 旧版把缺 ref_notes 记 F1=0,会在 8000 步被
      StopController 误判"标签管线有 bug"停训。
    legato_omr_fn: LEGATO OMR-NED(执行端注入);缺省用 text_ned 代理,保证 best.pt
      挑选与收敛判定始终有指标。
    返回指标 dict(含诊断量 empty_rate/n_eval),喂给 StopController。
    """
    from rubato.model.infer import infer_a2s, infer_amt, _EMPTY_A2S   # S12
    from rubato.intermo.core import text_to_units, validate_units
    from rubato.model.evaluate import note_f1, amt_text_to_notes, text_ned

    labels = labels or {}
    metrics = {"parseable_rate": 0.0, "val_omr_ned": None,
               "a2s_note_f1": None, "maestro_amt_f1": None,
               "empty_rate": None, "n_eval_nasap": 0, "n_eval_maestro": 0}

    # nASAP val:生成 + 可解析率。
    # 注意:infer_a2s 失败时兜底返回 _EMPTY_A2S(合法空谱)—— 若把它算"可解析",
    # 可解析率会被结构性钉在 ~1.0,R-S11.7 的 <80% 止损永远不触发。空谱按不可解析计。
    # empty_rate 单列:≈1.0 说明是解码 API 胶水没接上(NeMo generate 签名),不是模型烂 ——
    # 两者都表现为 pause_unparseable,诊断量必须能区分。
    import time as _time
    t_eval0 = _time.time()
    n_ok, n_total, n_empty = 0, 0, 0
    truncated = False
    omr_scores = []
    sample_preds: list[str] = []
    subset = _eval_subset(nasap_val, eval_max)
    for si, sample in enumerate(subset):
        # 时限 + 心跳:eval 是逐 token 生成,慢是常态 —— 没有这两样,"慢"和"卡死"
        # 在执行端不可区分(实测 30 分钟无输出被当成 hang)。超时截断,按已评样本出指标。
        if _time.time() - t_eval0 > time_budget_s:
            truncated = True
            print(f"  eval 时限 {time_budget_s:.0f}s 用尽,截断于 {si}/{len(subset)}(指标按已评样本)",
                  flush=True)
            break
        if si % 8 == 0:
            print(f"  eval nasap {si}/{len(subset)}({_time.time() - t_eval0:.0f}s)", flush=True)
        audio = _sample_audio(sample)
        if audio is None:
            continue
        pred = infer_a2s(model, audio, tokenizer)
        n_total += 1
        if len(sample_preds) < 2:              # 模型实际吐了什么 —— 定性"胶水坏/模型早"的直接证据
            sample_preds.append(pred[:160])
        viol = validate_units(text_to_units(pred)) if pred else ["empty"]
        if pred == _EMPTY_A2S:
            n_empty += 1
            viol = viol or ["empty_fallback"]
        if not viol:
            n_ok += 1
            ref_a2s = labels.get(sample.get("utt_id"), {}).get("A2S")
            if legato_omr_fn and sample.get("ref_xml"):
                omr_scores.append(legato_omr_fn(pred, sample["ref_xml"]))
            elif ref_a2s:
                omr_scores.append(text_ned(pred, ref_a2s))    # 代理指标,见 evaluate.text_ned
    metrics["parseable_rate"] = n_ok / max(n_total, 1)
    metrics["empty_rate"] = (n_empty / n_total) if n_total else None
    metrics["n_eval_nasap"] = n_total
    metrics["eval_truncated"] = truncated
    for k, p in enumerate(sample_preds):
        print(f"  eval 样本预测[{k}]: {p!r}", flush=True)
    if omr_scores:
        metrics["val_omr_ned"] = sum(omr_scores) / len(omr_scores)

    # MAESTRO val:AMT note F1(mir_eval)。R-S11.7 的"步≥8000 且 AMT F1<70 → 停训"
    # 依赖它;参照音符从该窗的真值 AMT 文本反解。无参照样本跳过(不打 0 分)。
    f1s = []
    for si, sample in enumerate(_eval_subset(maestro_val, eval_max)):
        if _time.time() - t_eval0 > 2 * time_budget_s:     # AMT 共享总时限(nasap 用掉一份)
            print(f"  eval 总时限用尽,AMT 截断于 {si}", flush=True)
            break
        if si % 8 == 0:
            print(f"  eval maestro {si}({_time.time() - t_eval0:.0f}s)", flush=True)
        ref_text = labels.get(sample.get("utt_id"), {}).get("AMT")
        if not ref_text:
            continue
        try:
            ref_notes = amt_text_to_notes(ref_text)
        except Exception:
            continue
        if not ref_notes:
            continue
        audio = _sample_audio(sample)
        if audio is None:
            continue
        pred_text = infer_amt(model, audio, tokenizer)
        try:
            est_notes = amt_text_to_notes(pred_text)
        except Exception:
            est_notes = []
        f1s.append(note_f1(ref_notes, est_notes)["f1"])
    metrics["n_eval_maestro"] = len(f1s)
    if f1s:
        metrics["maestro_amt_f1"] = 100.0 * sum(f1s) / len(f1s)

    return metrics


# ---------------------------------------------------------------- 断点续训(长跑生死线)

def save_snapshot(path, model, opt, sched, step: int, epoch: int):
    """全状态快照(模型+优化器+调度器+进度),原子替换写。为什么必须有:执行端 16GB 卡
    余量 45MiB,数周长跑必然中途崩;只存模型权重的 ckpt 恢复不了 Adam 动量和 lr 进度,
    崩一次等于从头再来。"""
    import torch
    from pathlib import Path as _P
    path = _P(path)
    tmp = path.with_suffix(".tmp")
    torch.save({"model": model.state_dict(), "optimizer": opt.state_dict(),
                "scheduler": sched.state_dict(), "step": step, "epoch": epoch}, tmp)
    tmp.replace(path)                          # 原子:写一半崩不会毁掉上一份


def load_snapshot(path, model, opt, sched):
    """恢复快照 → (step, epoch);文件不存在/损坏 → None(从头开始,打印原因)。"""
    import torch
    from pathlib import Path as _P
    path = _P(path)
    if not path.exists():
        return None
    try:
        snap = torch.load(str(path), map_location="cpu")
        model.load_state_dict(snap["model"])
        opt.load_state_dict(snap["optimizer"])     # state 张量随参数设备自动就位
        sched.load_state_dict(snap["scheduler"])
        return int(snap.get("step", 0)), int(snap.get("epoch", 0))
    except Exception as e:
        print(f"⚠ 快照恢复失败({type(e).__name__}: {e}),从头开始")
        return None


# ---------------------------------------------------------------- 主循环(R-S11.6/11.7)

def train(model, datamodule, cfg: dict, tokenizer,
          eval_every_steps: int = 3000, legato_omr_fn=None):
    """
    主训练循环。装 optimizer + 止损 + checkpoint。需 GPU,本地跑。
    R-S11.6:每 eval 存 ckpt,滚动保留 6,选 val OMR-NED 最低。
    R-S11.7:StopController 四触发。
    """
    import torch
    from rubato.model.losses import build_ts_token_ids
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
    max_steps = cfg.get("max_steps", 100000)
    log_every = int(cfg.get("log_every", 50))
    save_every = int(cfg.get("save_every_steps", 200))
    ckpt_ring = []      # 滚动保留 6
    best_omr = float("inf")
    recent, recent_sem, recent_ts = [], [], []      # 近 50 步窗口(日志 + final_* 判据)
    recent_dia: dict = {}                           # {dialect: [近 200 条 seq sem]}(各自学习曲线)
    report = {"stop_events": [], "eval_history": []}

    def _dia_line() -> str:
        return " ".join(f"{d}={sum(v) / len(v):.2f}" for d, v in sorted(recent_dia.items()) if v)

    def _finish(tag: str):
        report["final"] = tag
        report["final_loss"] = round(sum(recent) / len(recent), 4) if recent else None
        report["final_sem"] = round(sum(recent_sem) / len(recent_sem), 4) if recent_sem else None
        report["final_ts"] = round(sum(recent_ts) / len(recent_ts), 4) if recent_ts else None
        report["final_sem_by_dialect"] = {d: round(sum(v) / len(v), 4)
                                          for d, v in recent_dia.items() if v}
        return report

    # 断点续训:last.pt 存在且未禁用 → 全状态恢复(所在 epoch 从头重放,至多重复
    # save_every-1 步的样本 —— 每 epoch 采样确定,重复无害,远好于从 step 0 重来)
    # (_finish 定义必须在前:曾在"续训即达 max_steps"的分支上先调后定义 → UnboundLocalError)
    last_pt = ckpt_dir / "last.pt"
    if cfg.get("resume", True):
        got = load_snapshot(last_pt, model, opt, sched)
        if got:
            step, start_epoch = got
            print(f"续训:恢复 step={step} epoch={start_epoch}(优化器/调度器状态一并恢复)")
            if step >= max_steps:
                return _finish("max_steps_reached")

    # 一次性预备:时间戳 id 映射 / 梯度累积额度 / bf16
    ts_token_ids = build_ts_token_ids(tokenizer)
    accum_target_sec = float(cfg.get("grad_accum_to_audio_sec", 2000))
    loss_cfg = cfg.get("loss", {})
    use_bf16 = (str(cfg.get("precision", "")).startswith("bf16")
                and torch.cuda.is_available())
    autocast = (lambda: torch.autocast("cuda", dtype=torch.bfloat16)) if use_bf16 \
        else (lambda: __import__("contextlib").nullcontext())

    model.train()
    opt.zero_grad()
    accum_sec = 0.0
    for epoch in range(start_epoch, cfg.get("max_epochs", 1000)):
        for batch in datamodule.train_batches(epoch):
            with autocast():
                parts = training_step_logic(model, batch, tokenizer,
                                            ts_token_ids=ts_token_ids, loss_cfg=loss_cfg,
                                            guards=cfg.get("guards"))
            batch_sec = parts.get("batch_audio_sec", accum_target_sec)
            # R-S11.4:梯度累积至有效 ≈2000 audio-sec/步;按音频秒数等比缩放各 micro-batch
            scale = min(1.0, batch_sec / max(accum_target_sec, 1e-6))
            (parts["loss"] * scale).backward()
            accum_sec += batch_sec
            if accum_sec < accum_target_sec:
                continue
            accum_sec = 0.0
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            step += 1

            # 训练可观测性:没有这几行,执行端只能对着黑屏猜收敛(冒烟判据也取自这窗口)
            for buf, v in ((recent, float(parts["loss"])),
                           (recent_sem, float(parts["semantic_loss"])),
                           (recent_ts, float(parts["ts_loss"]))):
                buf.append(v)
                if len(buf) > 50:
                    buf.pop(0)
            for d, (v, n) in (parts.get("dialect_sem") or {}).items():
                buf = recent_dia.setdefault(d, [])
                buf.extend([v] * n)              # 按条数计权,批间混比不歪
                if len(buf) > 200:
                    del buf[: len(buf) - 200]
            if step % log_every == 0 or step == 1:
                print(f"step {step} loss={recent[-1]:.4f} avg50={sum(recent)/len(recent):.4f} "
                      f"sem={recent_sem[-1]:.4f} ts={recent_ts[-1]:.4f} "
                      f"lr={opt.param_groups[0]['lr']:.2e} audio={batch_sec:.0f}s"
                      f" | {_dia_line()}", flush=True)
            if step % save_every == 0:
                save_snapshot(last_pt, model, opt, sched, step, epoch)

            # 评测 + 止损
            if step % eval_every_steps == 0:
                model.eval()
                with torch.no_grad():
                    m = run_eval_hooks(model, datamodule.nasap_val,
                                       getattr(datamodule, "maestro_val", []),
                                       tokenizer,
                                       labels=getattr(datamodule, "labels", None),
                                       legato_omr_fn=legato_omr_fn,
                                       eval_max=int(cfg.get("eval_max", 128)),
                                       time_budget_s=float(cfg.get("eval_time_budget_s", 1200)))
                report["eval_history"].append({"step": step, **m})

                action = stopper.update(
                    step, m["parseable_rate"], m.get("maestro_amt_f1"),
                    m.get("val_omr_ned"), recent_loss=float(parts["loss"]))
                report["stop_events"].append({"step": step, **action})

                # ckpt(滚动 6)
                ck = ckpt_dir / f"step{step}.pt"
                torch.save({"model": model.state_dict(), "step": step, "metrics": m}, ck)
                ckpt_ring.append(ck)
                if len(ckpt_ring) > 6:
                    old = ckpt_ring.pop(0)
                    old.unlink(missing_ok=True)
                if m.get("val_omr_ned") is not None and m["val_omr_ned"] < best_omr:
                    best_omr = m["val_omr_ned"]
                    torch.save({"model": model.state_dict(), "step": step},
                               ckpt_dir / "best.pt")

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
                    # 回滚上一 ckpt + lr×0.5。
                    # 注意:LambdaLR 每步用 base_lrs×lambda(step) 重算 lr,直接改
                    # param_groups["lr"] 会在下一次 sched.step() 被覆盖 —— 必须改 base_lrs。
                    if len(ckpt_ring) >= 2:
                        prev = torch.load(ckpt_ring[-2])
                        model.load_state_dict(prev["model"])
                    sched.base_lrs = [b * 0.5 for b in sched.base_lrs]
                    for g in opt.param_groups:
                        g["lr"] *= 0.5

                model.train()

            if step >= max_steps:
                return _finish("max_steps_reached")

    return _finish("max_epochs_reached")
