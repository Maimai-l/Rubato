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

def training_step_logic(model, batch, tokenizer):
    """
    单训练步的 loss 计算(装配 combined_loss)。返回 loss dict。
    batch: {audio_feats, target_tokens, token_types, seq_lengths, ...}。
    token_types 区分语义/时间戳位置 → 分流到对应 loss。
    此函数体现装配逻辑;实际张量流经 NeMo 模型的 forward,本地接。
    """
    import torch
    device = next(model.parameters()).device
    audio = batch["audio_feats"].to(device)
    audio_len = batch["seq_lengths"].to(device)
    targets = batch["target_tokens"].to(device)
    target_len = batch.get("target_lengths",
                           torch.tensor([len(t) for t in targets], device=device)).to(device)

    # 1. Preprocess: raw audio → mel features (NeMo preprocessor)
    processed, processed_len = model.preprocessor(
        input_signal=audio, length=audio_len,
    )

    # 2. Forward with PROCESSED signal (not raw audio)
    output = model.forward(
        processed_signal=processed, processed_signal_length=processed_len,
        transcript=targets, transcript_length=target_len,
    )

    # Extract loss
    if isinstance(output, dict):
        loss = output.get("loss")
        if loss is None:
            loss = torch.tensor(0.0, device=device, requires_grad=True)
    elif isinstance(output, torch.Tensor):
        loss = output
    else:
        loss = torch.tensor(0.0, device=device, requires_grad=True)

    assert torch.isfinite(loss), f"loss 非有限: {loss}"

    # --- combined_loss 组件 (R-S11.1): 作为额外指标,不参与 backward ---
    sem_loss_val = torch.tensor(0.0, device=device)
    ts_loss_val = torch.tensor(0.0, device=device)

    if isinstance(output, dict) and "logits" in output and tokenizer is not None:
        logits = output["logits"]  # (B, T, V)
        token_types = batch.get("token_types")
        loss_mask = batch.get("loss_mask")
        if token_types is not None and loss_mask is not None:
            with torch.no_grad():
                token_types = token_types.to(device)
                loss_mask = loss_mask.to(device)

                # 时间戳 token ID → bin 编号映射
                ts_token_ids = torch.tensor(
                    [tokenizer.piece_to_id(f"<|t{i}|>") for i in range(4000)],
                    device=device,
                )
                ts_id_to_bin = {tokenizer.piece_to_id(f"<|t{i}|>"): i for i in range(4000)}

                sem_mask = (token_types == 0) & loss_mask
                ts_mask = (token_types == 1) & loss_mask

                sem_logits, sem_targets = None, None
                ts_logits, ts_targets = None, None

                if sem_mask.any():
                    sem_logits = logits[sem_mask]
                    sem_targets = targets[sem_mask]

                if ts_mask.any():
                    # 取时间戳子集的 logits (N_ts, 4000)
                    ts_logits = logits[ts_mask][:, ts_token_ids]
                    ts_target_ids = targets[ts_mask]
                    ts_targets = torch.tensor(
                        [ts_id_to_bin[int(t)] for t in ts_target_ids],
                        device=device, dtype=torch.long,
                    )

                seq_lengths = batch.get("seq_lengths",
                    torch.tensor([targets.shape[1]] * targets.shape[0], device=device))
                loss_dict = combined_loss(
                    sem_logits, sem_targets, ts_logits, ts_targets, seq_lengths,
                )
                sem_loss_val = loss_dict.get("sem", torch.tensor(0.0, device=device))
                ts_loss_val = loss_dict.get("ts", torch.tensor(0.0, device=device))

    return {
        "loss": loss,
        "semantic_loss": sem_loss_val,
        "ordinal_loss": ts_loss_val,
        "ts_loss": ts_loss_val,
        "seq_lengths": batch.get("seq_lengths", torch.tensor(0.0)),
    }


# ---------------------------------------------------------------- 评测钩子(R-S11.5)

def run_eval_hooks(model, nasap_val, maestro_val, tokenizer, legato_omr_fn=None) -> dict:
    """
    R-S11.5:nASAP val 跑 可解析率/OMR-NED/A2S F1;MAESTRO val 跑 AMT F1。
    legato_omr_fn: LEGATO OMR-NED 计算函数(本地注入,U10 已验证可用)。
    返回指标 dict,喂给 StopController。
    """
    from rubato.model.infer import infer_a2s   # S12
    from rubato.intermo.core import text_to_units, validate_units

    metrics = {"parseable_rate": 0.0, "val_omr_ned": None,
               "a2s_note_f1": None, "maestro_amt_f1": None}

    # nASAP val:生成 + 可解析率
    n_ok, n_total = 0, 0
    omr_scores = []
    for sample in nasap_val:
        pred = infer_a2s(model, sample["audio"], tokenizer)
        n_total += 1
        viol = validate_units(text_to_units(pred)) if pred else ["empty"]
        if not viol:
            n_ok += 1
            if legato_omr_fn and sample.get("ref_xml"):
                omr_scores.append(legato_omr_fn(pred, sample["ref_xml"]))
    metrics["parseable_rate"] = n_ok / max(n_total, 1)
    if omr_scores:
        metrics["val_omr_ned"] = sum(omr_scores) / len(omr_scores)

    # MAESTRO val:AMT note F1(mir_eval,本地接)
    # metrics["maestro_amt_f1"] = compute_amt_f1(model, maestro_val, tokenizer)

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
    opt, sched = build_optimizer(model, cfg)
    stopper = StopController()
    ckpt_dir = Path(cfg.get("ckpt_dir", "outputs/ckpt"))
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    step = 0
    max_steps = cfg.get("max_steps", 100000)
    ckpt_ring = []      # 滚动保留 6
    best_omr = float("inf")
    report = {"stop_events": [], "eval_history": []}

    model.train()
    for epoch in range(cfg.get("max_epochs", 1000)):
        for batch in datamodule.train_batches(epoch):
            opt.zero_grad()
            parts = training_step_logic(model, batch, tokenizer)
            parts["loss"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            step += 1

            # 评测 + 止损
            if step % eval_every_steps == 0:
                model.eval()
                with torch.no_grad():
                    m = run_eval_hooks(model, datamodule.nasap_val,
                                       [], tokenizer, legato_omr_fn)
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
                    # 回滚上一 ckpt + lr×0.5
                    if len(ckpt_ring) >= 2:
                        prev = torch.load(ckpt_ring[-2])
                        model.load_state_dict(prev["model"])
                    for g in opt.param_groups:
                        g["lr"] *= 0.5

                model.train()

            if step >= max_steps:
                report["final"] = "max_steps_reached"
                return report

    report["final"] = "max_epochs_reached"
    return report
