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
        (enc_params if name.startswith("encoder") else other_params).append(p)

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

def run_eval_hooks(model, nasap_val, maestro_val, tokenizer, legato_omr_fn=None) -> dict:
    """
    R-S11.5:nASAP val 跑 可解析率/OMR-NED/A2S F1;MAESTRO val 跑 AMT F1。
    legato_omr_fn: LEGATO OMR-NED 计算函数(本地注入,U10 已验证可用)。
    返回指标 dict,喂给 StopController。
    """
    from rubato.model.infer import infer_a2s, infer_amt   # S12
    from rubato.intermo.core import text_to_units, validate_units

    metrics = {"parseable_rate": 0.0, "val_omr_ned": None,
               "a2s_note_f1": None, "maestro_amt_f1": None}

    # nASAP val:生成 + 可解析率。
    # 注意:infer_a2s 失败时兜底返回 _EMPTY_A2S(合法空谱)—— 若把它算"可解析",
    # 可解析率会被结构性钉在 ~1.0,R-S11.7 的 <80% 止损永远不触发。空谱按不可解析计。
    from rubato.model.infer import _EMPTY_A2S
    n_ok, n_total = 0, 0
    omr_scores = []
    for sample in nasap_val:
        pred = infer_a2s(model, sample["audio"], tokenizer)
        n_total += 1
        viol = validate_units(text_to_units(pred)) if pred else ["empty"]
        if pred == _EMPTY_A2S:
            viol = viol or ["empty_fallback"]
        if not viol:
            n_ok += 1
            if legato_omr_fn and sample.get("ref_xml"):
                omr_scores.append(legato_omr_fn(pred, sample["ref_xml"]))
    metrics["parseable_rate"] = n_ok / max(n_total, 1)
    if omr_scores:
        metrics["val_omr_ned"] = sum(omr_scores) / len(omr_scores)

    # MAESTRO val:AMT note F1(mir_eval)。此前只有注释 —— 但 R-S11.7 的
    # "步≥8000 且 AMT F1<70 → 停训" 依赖它,不算等于止损规则永不触发。
    if maestro_val:
        from rubato.model.evaluate import note_f1, amt_text_to_notes
        f1s = []
        for sample in maestro_val:
            pred_text = infer_amt(model, sample["audio"], tokenizer)
            try:
                est_notes = amt_text_to_notes(pred_text)
            except Exception:
                est_notes = []
            ref_notes = sample.get("ref_notes") or []
            f1s.append(note_f1(ref_notes, est_notes)["f1"])
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
    opt, sched = build_optimizer(model, cfg)
    stopper = StopController()
    ckpt_dir = Path(cfg.get("ckpt_dir", "outputs/ckpt"))
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    step = 0
    max_steps = cfg.get("max_steps", 100000)
    ckpt_ring = []      # 滚动保留 6
    best_omr = float("inf")
    report = {"stop_events": [], "eval_history": []}

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

            # 评测 + 止损
            if step % eval_every_steps == 0:
                model.eval()
                with torch.no_grad():
                    m = run_eval_hooks(model, datamodule.nasap_val,
                                       getattr(datamodule, "maestro_val", []),
                                       tokenizer, legato_omr_fn)
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
                    report["final"] = f"stopped:{act}:{action['reason']}"
                    return report
                if act == "converged":
                    report["final"] = f"converged:{action['reason']}"
                    return report
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
                report["final"] = "max_steps_reached"
                return report

    report["final"] = "max_epochs_reached"
    return report
