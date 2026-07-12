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

def bucket_batches(samples: list[dict], max_batch_sec: float = 560.0):
    """
    R-S11.4:动态 bucketing,每 batch 音频总时长 ≤max_batch_sec。
    samples 按时长排序后贪心装桶。返回 [[sample,...], ...]。
    """
    ordered = sorted(samples, key=lambda s: s.get("dur_s", 0))
    batches, cur, cur_sec = [], [], 0.0
    for s in ordered:
        d = s.get("dur_s", 0)
        if cur and cur_sec + d > max_batch_sec:
            batches.append(cur)
            cur, cur_sec = [], 0.0
        cur.append(s)
        cur_sec += d
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


def training_step_logic(model, batch, tokenizer, ts_token_ids=None, loss_cfg=None):
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

    return {
        "loss": loss,
        "semantic_loss": parts["sem"],
        "ordinal_loss": parts["ts"],
        "ts_loss": parts["ts"],
        "n_sem": parts["n_sem"], "n_ts": parts["n_ts"],
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
                   legato_omr_fn=None, eval_max: int = 128) -> dict:
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
    n_ok, n_total, n_empty = 0, 0, 0
    omr_scores = []
    for sample in _eval_subset(nasap_val, eval_max):
        audio = _sample_audio(sample)
        if audio is None:
            continue
        pred = infer_a2s(model, audio, tokenizer)
        n_total += 1
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
    if omr_scores:
        metrics["val_omr_ned"] = sum(omr_scores) / len(omr_scores)

    # MAESTRO val:AMT note F1(mir_eval)。R-S11.7 的"步≥8000 且 AMT F1<70 → 停训"
    # 依赖它;参照音符从该窗的真值 AMT 文本反解。无参照样本跳过(不打 0 分)。
    f1s = []
    for sample in _eval_subset(maestro_val, eval_max):
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
    if torch.cuda.is_available():
        model = model.cuda()
    opt, sched = build_optimizer(model, cfg)
    stopper = StopController()
    ckpt_dir = Path(cfg.get("ckpt_dir", "outputs/ckpt"))
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    step = 0
    max_steps = cfg.get("max_steps", 100000)
    log_every = int(cfg.get("log_every", 50))
    ckpt_ring = []      # 滚动保留 6
    best_omr = float("inf")
    recent, recent_sem, recent_ts = [], [], []      # 近 50 步窗口(日志 + final_* 判据)
    report = {"stop_events": [], "eval_history": []}

    def _finish(tag: str):
        report["final"] = tag
        report["final_loss"] = round(sum(recent) / len(recent), 4) if recent else None
        report["final_sem"] = round(sum(recent_sem) / len(recent_sem), 4) if recent_sem else None
        report["final_ts"] = round(sum(recent_ts) / len(recent_ts), 4) if recent_ts else None
        return report

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
    for epoch in range(cfg.get("max_epochs", 1000)):
        for batch in datamodule.train_batches(epoch):
            with autocast():
                parts = training_step_logic(model, batch, tokenizer,
                                            ts_token_ids=ts_token_ids, loss_cfg=loss_cfg)
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
            if step % log_every == 0 or step == 1:
                print(f"step {step} loss={recent[-1]:.4f} avg50={sum(recent)/len(recent):.4f} "
                      f"sem={recent_sem[-1]:.4f} ts={recent_ts[-1]:.4f} "
                      f"lr={opt.param_groups[0]['lr']:.2e} audio={batch_sec:.0f}s", flush=True)

            # 评测 + 止损
            if step % eval_every_steps == 0:
                model.eval()
                with torch.no_grad():
                    m = run_eval_hooks(model, datamodule.nasap_val,
                                       getattr(datamodule, "maestro_val", []),
                                       tokenizer,
                                       labels=getattr(datamodule, "labels", None),
                                       legato_omr_fn=legato_omr_fn,
                                       eval_max=int(cfg.get("eval_max", 128)))
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
                if act in ("pause_unparseable", "stop_bad_labels"):
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
