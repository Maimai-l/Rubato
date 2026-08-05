"""
decoder 形式语言预训练(D91;round-3 起点部件,不碰主线训练)。

做什么:只训 transf_decoder + log_softmax(其余全冻结),在 gen_formal_corpus 的
合法 InterMo 文本上做纯 LM(交叉注意力喂零上下文 = decoder-only)。目标是在
decoder 见到音频之前,把 Dyck 开闭配对与小节算术刻进电路(Hu et al. 2025 配方,
论文 §2 暗示)。产出 decoder_init.pt,由 build_model(decoder_init=) 在 round-3
启动时载入(--decoder-init 旗标)。

格式零漂移:目标序列经【生产同一个】encode_target 构造(prompt+标签+eot、
loss_mask、右移全同正训),不存在第二套实现。

用法(执行端;GPU 空闲窗跑,或 --device cpu 冒烟):
  python scripts/pretrain_decoder.py --corpus D:\\vscode_projects\\ee_download\\work\\formal_corpus.jsonl ^
      --steps 20000 --out D:\\vscode_projects\\ee_download\\work\\decoder_init.pt
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("RUBATO_WORK")
            or (ROOT.parent / "work" if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download\work"))


def default_nemo_path(repo_root: Path = ROOT) -> Path:
    """Match build_dataset's layout while retaining a repo-local fallback."""
    candidates = (repo_root.parent / "canary-180m-flash.nemo",
                  repo_root / "canary-180m-flash.nemo")
    return next((p for p in candidates if p.exists()), candidates[0])


def classify_health(avg50: float, *, is_smoke: bool, free_ok: bool,
                    dyck_ok: bool = True) -> tuple[str, bool]:
    """Return the registered loss class and whether the artifact is usable."""
    loss_class = "PASS" if avg50 <= 1.5 else ("GRAY" if avg50 <= 3.0 else "FAIL")
    # D92/D93: random pitch contributes an irreducible CE floor, so the numeric
    # CE class is diagnostic only.  Formal free continuation is the admission
    # gate; NaN/Inf remains fatal in every mode.
    health_pass = (math.isfinite(avg50) if is_smoke
                   else (math.isfinite(avg50) and free_ok and dyck_ok))
    return loss_class, health_pass


def load_corpus(path: str, max_rows: int | None = None) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("text") and r.get("dialect"):
                rows.append({"utt_id": r.get("utt_id", f"row_{len(rows)}"),
                             "dialect": r["dialect"], "text": r["text"],
                             "n_atoms": r.get("n_atoms")})
            if max_rows and len(rows) >= max_rows:
                break
    if not rows:
        raise RuntimeError(f"语料为空: {path}")
    return rows


def rows_to_batch(rows: list[dict], tokenizer, max_len: int = 1022,
                  domain: str = "synth"):
    """行 → 张量批。encode_target 与正训同一构造器;超长行跳过(返回 skipped 数)。"""
    import torch
    from rubato.data.dataset import encode_target
    encs, skipped = [], 0
    for r in rows:
        e = encode_target(tokenizer, r["dialect"], r["text"],
                          sample=False, domain=domain)
        if len(e["input_ids"]) > max_len:
            skipped += 1
            continue
        encs.append(e)
    if not encs:
        return None, skipped
    L = max(len(e["input_ids"]) for e in encs)
    B = len(encs)
    ids = torch.zeros(B, L, dtype=torch.long)
    labels = torch.zeros(B, L, dtype=torch.long)
    mask = torch.zeros(B, L, dtype=torch.bool)
    lens = torch.zeros(B, dtype=torch.long)
    for i, e in enumerate(encs):
        n = len(e["input_ids"])
        ids[i, :n] = torch.tensor(e["input_ids"], dtype=torch.long)
        labels[i, :n] = torch.tensor(e["labels"], dtype=torch.long)
        mask[i, :n] = torch.tensor(e["loss_mask"], dtype=torch.bool)
        lens[i] = n
    return {"input_ids": ids, "labels": labels, "loss_mask": mask,
            "input_lens": lens}, skipped


def pretrain_step(model, batch, enc_dim: int, device):
    """零上下文 decoder-only 前向 + 纯 CE(仅 loss_mask 位)。返回 (loss, n_tok)。"""
    import torch
    ids = batch["input_ids"].to(device)
    labels = batch["labels"].to(device)
    mask = batch["loss_mask"].to(device)
    lens = batch["input_lens"].to(device)
    B, L = ids.shape
    valid = torch.arange(L, device=device).unsqueeze(0) < lens.unsqueeze(1)
    enc = torch.zeros(B, 1, enc_dim, device=device)
    enc_mask = torch.ones(B, 1, dtype=torch.long, device=device)
    h = model.transf_decoder(input_ids=ids, decoder_mask=valid.long(),
                             encoder_embeddings=enc, encoder_mask=enc_mask)
    lp = model.log_softmax(hidden_states=h)
    if isinstance(lp, (tuple, list)):
        lp = lp[0]
    if lp.shape[:2] != labels.shape:
        raise RuntimeError(f"log_probs {tuple(lp.shape[:2])} != labels "
                           f"{tuple(labels.shape)} —— decoder 前向契约变了")
    nll = -lp.gather(-1, labels.unsqueeze(-1)).squeeze(-1)
    scored = mask & valid
    if not bool(scored.any()):
        raise RuntimeError("批内零计分 token")
    loss = nll[scored].mean()
    if not bool(loss.requires_grad):
        raise RuntimeError("loss 无梯度 —— decoder 参数没解冻或图断了")
    return loss, int(scored.sum())


def freeze_except_decoder(model) -> tuple[int, int]:
    """冻结全部,再解冻 transf_decoder+log_softmax。返回 (可训, 冻结) 参数量。"""
    for p in model.parameters():
        p.requires_grad = False
    n_train = 0
    for part in ("transf_decoder", "log_softmax"):
        mod = getattr(model, part, None)
        if mod is None:
            raise RuntimeError(f"模型缺 {part} —— 与 infer/训练同一成员名,不能继续")
        for p in mod.parameters():
            p.requires_grad = True
            n_train += p.numel()
    n_frozen = sum(p.numel() for p in model.parameters() if not p.requires_grad)
    return n_train, n_frozen


def reset_decoder_parameters(model) -> int:
    """Reset every decoder/output module once, removing Canary text priors."""
    seen, n = set(), 0
    for part in (model.transf_decoder, model.log_softmax):
        for module in part.modules():
            if id(module) in seen:
                continue
            seen.add(id(module))
            reset = getattr(module, "reset_parameters", None)
            if callable(reset):
                reset()
                n += 1
    if not n:
        raise RuntimeError("decoder scratch 初始化未匹配到任何 reset_parameters")
    return n


def atomic_torch_save(payload, out_path: str):
    """Write a torch artifact durably, then atomically replace its final path."""
    import torch
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f"{out.name}.tmp.{os.getpid()}")
    with open(tmp, "xb") as fh:
        torch.save(payload, fh)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, out)


def save_decoder_init(model, out_path: str, meta: dict):
    atomic_torch_save(
        {"transf_decoder": model.transf_decoder.state_dict(),
         "log_softmax": model.log_softmax.state_dict(),
         "meta": meta}, out_path)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_signature(args) -> dict:
    """Fields that must not change across an exact optimizer/RNG resume."""
    return {
        "corpus": str(Path(args.corpus).resolve()),
        "corpus_sha256": _sha256(args.corpus),
        "tokenizer": str(Path(args.tokenizer).resolve()),
        "tokenizer_sha256": _sha256(args.tokenizer),
        "lr": float(args.lr), "warmup": int(args.warmup),
        "batch_rows": int(args.batch_rows), "enc_dim": int(args.enc_dim),
        "seed": int(args.seed), "init_mode": args.init_mode,
        "precision": args.precision,
    }


def save_resume_state(model, opt, out_path: str, *, step: int, recent: list,
                      rng: random.Random, n_skipped: int, signature: dict,
                      last_free_eval: dict | None = None):
    import torch
    payload = {
        "snapshot_version": 1,
        "transf_decoder": model.transf_decoder.state_dict(),
        "log_softmax": model.log_softmax.state_dict(),
        "optimizer": opt.state_dict(),
        "step": int(step), "recent": list(recent),
        "batch_rng_state": rng.getstate(),
        "torch_rng_state": torch.get_rng_state(),
        "cuda_rng_state": (torch.cuda.get_rng_state_all()
                           if torch.cuda.is_available() else None),
        "n_skipped_total": int(n_skipped),
        "signature": signature,
        "last_free_eval": last_free_eval,
    }
    atomic_torch_save(payload, out_path)


def load_resume_state(model, opt, path: str, signature: dict, device):
    import torch
    snap = torch.load(path, map_location=device)
    if snap.get("snapshot_version") != 1:
        raise RuntimeError(f"未知 pretrain resume 版本: {snap.get('snapshot_version')}")
    if snap.get("signature") != signature:
        raise RuntimeError(
            "pretrain resume 配置/语料不一致，拒绝近似恢复:\n"
            f"saved={snap.get('signature')}\nnow={signature}")
    model.transf_decoder.load_state_dict(snap["transf_decoder"], strict=True)
    model.log_softmax.load_state_dict(snap["log_softmax"], strict=True)
    opt.load_state_dict(snap["optimizer"])
    if snap.get("torch_rng_state") is not None:
        torch.set_rng_state(snap["torch_rng_state"].cpu())
    if torch.cuda.is_available() and snap.get("cuda_rng_state") is not None:
        torch.cuda.set_rng_state_all([s.cpu() for s in snap["cuda_rng_state"]])
    rng = random.Random()
    rng.setstate(snap["batch_rng_state"])
    return {
        "step": int(snap["step"]), "recent": list(snap.get("recent") or []),
        "rng": rng, "n_skipped_total": int(snap.get("n_skipped_total", 0)),
        "last_free_eval": snap.get("last_free_eval"),
    }


def decoder_only_generate(model, tokenizer, row: dict, enc_dim: int, device,
                          prefix_tokens: int = 12, max_new: int = 256) -> dict:
    """Greedy continuation with the same decoder and a zero audio context.

    A short reference prefix creates varied, sometimes-open Dyck states.  The
    continuation itself is entirely model-generated; production validation of
    the combined text therefore measures recovery/closure rather than another
    teacher-forced proxy.
    """
    import torch
    from rubato.model.build import DIALECT_PROMPT, build_target_sequence
    dialect = row["dialect"]
    label_pieces = tokenizer.encode(row["text"], out_type=str)
    pieces, _ = build_target_sequence(dialect, label_pieces, domain="synth")
    prompt_n = len(DIALECT_PROMPT[dialect]) + 1
    n_seed = min(max(1, int(prefix_tokens)), len(label_pieces))
    ids = [tokenizer.piece_to_id(p) for p in pieces[:prompt_n + n_seed]]
    eot = tokenizer.piece_to_id("<|eot|>")
    stop = "cap"
    with torch.no_grad():
        for _ in range(max_new):
            if len(ids) >= 1023:
                stop = "poslimit"
                break
            t = torch.tensor([ids], dtype=torch.long, device=device)
            enc = torch.zeros(1, 1, enc_dim, device=device)
            enc_mask = torch.ones(1, 1, dtype=torch.long, device=device)
            h = model.transf_decoder(
                input_ids=t, decoder_mask=torch.ones_like(t),
                encoder_embeddings=enc, encoder_mask=enc_mask)
            lp = model.log_softmax(hidden_states=h)
            if isinstance(lp, (tuple, list)):
                lp = lp[0]
            nxt = int(lp[0, -1].argmax())
            if nxt == eot:
                stop = "eot"
                break
            ids.append(nxt)
    text = tokenizer.decode(ids[prompt_n:]).strip()
    return {"text": text, "stop": stop, "n_seed": n_seed,
            "n_new": len(ids) - prompt_n - n_seed}


def formal_free_eval(model, rows: list[dict], tokenizer, enc_dim: int, device,
                     n: int = 4, prefix_tokens: int = 12,
                     max_new: int = 256) -> dict:
    """Free-continuation legality gauge; no target token is fed after prefix."""
    from rubato.intermo.core import text_to_units, validate_units
    was_training = model.training
    model.eval()
    per = max(1, int(n) // 2)
    chosen = []
    for dialect in ("A2S", "TAST"):
        pool = sorted((r for r in rows if r["dialect"] == dialect),
                      key=lambda r: (int(r["n_atoms"])
                                     if r.get("n_atoms") is not None else 10 ** 9,
                                     r.get("utt_id", "")))
        chosen.extend(pool[:per])
    chosen = chosen[:max(1, int(n))]
    entries, tally, n_ok, n_eot = [], {}, 0, 0
    for row in chosen:
        g = decoder_only_generate(model, tokenizer, row, enc_dim, device,
                                  prefix_tokens=prefix_tokens, max_new=max_new)
        try:
            viol = validate_units(text_to_units(g["text"])) if g["text"] else ["empty"]
        except Exception as e:
            viol = [f"parse_error:{type(e).__name__}"]
        ok = not viol
        n_ok += int(ok)
        n_eot += int(g["stop"] == "eot")
        cats = set()
        for v in viol:
            s = str(v)
            if s.startswith("DYCK"):
                cats.add("DYCK")
            elif s.startswith("MEASURE"):
                cats.add("MEASURE")
            elif s.startswith("TERMINAL_BAR"):
                cats.add("TERMINAL")
            else:
                cats.add(s.split(":", 1)[0])
        for c in cats:
            tally[c] = tally.get(c, 0) + 1
        entries.append({"utt_id": row.get("utt_id"), "dialect": row["dialect"],
                        "parseable": ok, "violations": viol[:10],
                        "stop": g["stop"], "n_seed": g["n_seed"],
                        "n_new": g["n_new"], "prediction_prefix": g["text"][:240]})
    if was_training:
        model.train()
    return {"n": len(entries), "n_parseable": n_ok,
            "parseable_rate": n_ok / max(len(entries), 1),
            "n_eot": n_eot, "violation_tally": tally, "samples": entries}


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="decoder 形式语言预训练(零音频纯 LM)")
    ap.add_argument("--corpus", default=str(WORK / "formal_corpus.jsonl"))
    ap.add_argument("--out", default=str(WORK / "decoder_init.pt"))
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--batch-rows", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--warmup", type=int, default=500)
    ap.add_argument("--enc-dim", type=int, default=1024,
                    help="交叉注意力零上下文的维度;须等于 encoder 输出维(canary=1024),"
                         "错了首步就形状崩,fail loud")
    ap.add_argument("--device", default=None, help="缺省自动:有 CUDA 用 CUDA")
    ap.add_argument("--precision", choices=("auto", "bf16", "fp32"), default="auto",
                    help="缺省 CUDA 用 bf16、CPU 用 fp32；写入续跑签名")
    ap.add_argument("--seed", type=int, default=20260804)
    ap.add_argument("--save-every", type=int, default=2000)
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--init-mode", choices=("scratch", "canary"), default="scratch",
                    help="decoder 初始层；缺省 scratch，与实验卡/论文语义一致")
    ap.add_argument("--resume-state", default=None,
                    help="精确续跑状态；缺省为 <out>.resume.pt")
    ap.add_argument("--no-resume", action="store_true",
                    help="禁止读取 resume；已有 out/resume 时仍拒绝覆盖")
    ap.add_argument("--free-eval-every", type=int, default=2000,
                    help="每 N 步跑一次 decoder-only 自由续写合法率；0=仅终点")
    ap.add_argument("--free-eval-n", type=int, default=4)
    ap.add_argument("--free-eval-prefix", type=int, default=12)
    ap.add_argument("--free-eval-max-new", type=int, default=256)
    ap.add_argument("--min-free-parseable", type=float, default=None,
                    help="终产物自由续写健康门；缺省 steps<2000 为0，否则0.5")
    ap.add_argument("--max-free-dyck", type=int, default=None,
                    help="终产物自由续写中允许含 DYCK 违规的样本数；缺省不设此门")
    ap.add_argument("--tokenizer", default=str(WORK / "rubato_spm.model"))
    ap.add_argument("--nemo", default=str(default_nemo_path()))
    ap.add_argument("--vocab-spec",
                    default=str(ROOT / "configs" / "vocab_spec.json"),
                    help="与 build_dataset 同一缺省(configs/vocab_spec.json)")
    args = ap.parse_args(argv)
    if args.steps <= 0 or args.batch_rows <= 0 or args.lr <= 0:
        raise ValueError("steps/batch_rows/lr 必须为正")
    if args.save_every <= 0 or args.log_every <= 0 or args.free_eval_every < 0:
        raise ValueError("save/log every 必须为正，free-eval-every 必须非负")
    if args.free_eval_n <= 0 or args.free_eval_prefix <= 0 or args.free_eval_max_new <= 0:
        raise ValueError("free-eval 参数必须为正")
    if args.min_free_parseable is not None \
            and not (0.0 <= args.min_free_parseable <= 1.0):
        raise ValueError("--min-free-parseable 必须在 0..1")
    if args.max_free_dyck is not None and args.max_free_dyck < 0:
        raise ValueError("--max-free-dyck 必须为非负整数")

    import torch
    import sentencepiece as spm
    from rubato.model.build import build_model
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    is_cuda = str(device).startswith("cuda")
    if args.precision == "auto":
        args.precision = "bf16" if is_cuda and torch.cuda.is_bf16_supported() else "fp32"
    if args.precision == "bf16" and not is_cuda:
        raise ValueError("--precision bf16 当前只支持 CUDA；CPU 冒烟请用 auto/fp32")
    autocast = (lambda: torch.autocast("cuda", dtype=torch.bfloat16)) \
        if args.precision == "bf16" else contextlib.nullcontext

    # Reproducibility starts before build_model: vocabulary replacement itself
    # initializes trainable tensors, so seeding only the row sampler is too late.
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    rows = load_corpus(args.corpus)
    print(f"语料 {len(rows)} 条 ← {args.corpus}", flush=True)
    tok = spm.SentencePieceProcessor(model_file=args.tokenizer)

    model, _ = build_model(args.nemo, args.tokenizer, args.vocab_spec)
    n_reset = reset_decoder_parameters(model) if args.init_mode == "scratch" else 0
    model = model.to(device)
    model.train()
    n_train, n_frozen = freeze_except_decoder(model)
    print(f"预训练配置回显: 可训参数={n_train:,}(decoder+softmax) "
          f"冻结={n_frozen:,} lr={args.lr:g} warmup={args.warmup} "
          f"steps={args.steps} batch_rows={args.batch_rows} enc_dim={args.enc_dim} "
          f"device={device} precision={args.precision} init={args.init_mode} "
          f"reset_modules={n_reset}", flush=True)

    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.lr, betas=(0.9, 0.98), weight_decay=0.01)
    signature = _run_signature(args)
    resume_path = args.resume_state or (str(args.out) + ".resume.pt")
    if args.no_resume and (Path(args.out).exists() or Path(resume_path).exists()):
        raise FileExistsError(
            f"--no-resume 但产物已存在，拒绝覆盖: out={args.out} resume={resume_path}")
    rng = random.Random(args.seed)
    t0 = time.time()
    recent = []
    step = 0
    n_skipped_total = 0
    last_free_eval = None
    if not args.no_resume and Path(resume_path).exists():
        state = load_resume_state(model, opt, resume_path, signature, device)
        step, recent, rng = state["step"], state["recent"], state["rng"]
        n_skipped_total = state["n_skipped_total"]
        last_free_eval = state["last_free_eval"]
        if step > args.steps:
            raise RuntimeError(f"resume step={step} > 目标 steps={args.steps}")
        print(f"预训练精确恢复: step={step} ← {resume_path} "
              "(decoder/optimizer/RNG/recent 全恢复)", flush=True)
    elif Path(args.out).exists():
        raise FileExistsError(
            f"最终产物已存在但无 resume，拒绝覆盖: {args.out}")
    run_start_step = step
    if is_cuda:
        torch.cuda.reset_peak_memory_stats(device)

    while step < args.steps:
        batch_rows = [rows[rng.randrange(len(rows))]
                      for _ in range(args.batch_rows)]
        batch, skipped = rows_to_batch(batch_rows, tok)
        n_skipped_total += skipped
        if batch is None:
            continue
        for g in opt.param_groups:
            g["lr"] = args.lr * min(1.0, (step + 1) / max(args.warmup, 1))
        with autocast():
            loss, n_tok = pretrain_step(model, batch, args.enc_dim, device)
        if not torch.isfinite(loss):
            raise FloatingPointError(f"step {step + 1} loss 非有限: {float(loss)}")
        opt.zero_grad(set_to_none=True)
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(
            [p for p in model.parameters() if p.requires_grad], 1.0)
        if not torch.isfinite(grad_norm):
            raise FloatingPointError(
                f"step {step + 1} gradient norm 非有限: {float(grad_norm)}")
        opt.step()
        step += 1
        recent.append(float(loss.detach()))
        if len(recent) > 50:
            recent.pop(0)
        if step % args.log_every == 0 or step == 1:
            ran = max(1, step - run_start_step)
            shape = tuple(batch["input_ids"].shape)
            cuda_mem = (f" cuda={torch.cuda.memory_allocated(device)/2**20:.0f}MiB"
                        f" peak={torch.cuda.max_memory_allocated(device)/2**20:.0f}MiB"
                        if is_cuda else "")
            print(f"step {step} loss={recent[-1]:.4f} "
                  f"avg50={sum(recent) / len(recent):.4f} tok={n_tok} "
                  f"rows={shape[0]} seq={shape[1]} gn={float(grad_norm):.2f} "
                  f"lr={opt.param_groups[0]['lr']:.2e} "
                  f"{(time.time() - t0) / ran:.2f}s/步{cuda_mem}", flush=True)
        save_now = step % args.save_every == 0 or step == args.steps
        if save_now:
            save_resume_state(
                model, opt, resume_path, step=step, recent=recent, rng=rng,
                n_skipped=n_skipped_total, signature=signature,
                last_free_eval=last_free_eval)
            print(f"  断点已原子存 {resume_path} (step {step})", flush=True)
        eval_now = (step == args.steps or
                    (args.free_eval_every and step % args.free_eval_every == 0))
        if eval_now:
            last_free_eval = formal_free_eval(
                model, rows, tok, args.enc_dim, device, n=args.free_eval_n,
                prefix_tokens=args.free_eval_prefix,
                max_new=args.free_eval_max_new)
            print(f"  free-eval step={step}: parseable="
                  f"{last_free_eval['n_parseable']}/{last_free_eval['n']} "
                  f"eot={last_free_eval['n_eot']}/{last_free_eval['n']} "
                  f"拒因={last_free_eval['violation_tally']}", flush=True)

    avg50 = sum(recent) / len(recent)
    min_free = (args.min_free_parseable if args.min_free_parseable is not None
                else (0.0 if args.steps < 2000 else 0.5))
    free_ok = bool(last_free_eval) and \
        last_free_eval["parseable_rate"] >= min_free
    dyck_count = ((last_free_eval or {}).get("violation_tally") or {}).get("DYCK", 0)
    dyck_ok = (args.max_free_dyck is None
               or (bool(last_free_eval) and dyck_count <= args.max_free_dyck))
    is_smoke = args.steps < 2000
    loss_class, health_pass = classify_health(
        avg50, is_smoke=is_smoke, free_ok=free_ok, dyck_ok=dyck_ok)
    meta = {"steps": step, "target_steps": args.steps,
            "complete": step == args.steps, "corpus": str(args.corpus),
            "corpus_sha256": signature["corpus_sha256"],
            "loss_avg50": avg50, "loss_class": loss_class,
            "free_eval": last_free_eval, "min_free_parseable": min_free,
            "max_free_dyck": args.max_free_dyck,
            "free_dyck_count": dyck_count, "free_dyck_ok": dyck_ok,
            "health_pass": health_pass,
            "artifact_role": "smoke" if is_smoke else "decoder_init",
            "format_version": 2, "lr": args.lr, "seed": args.seed,
            "init_mode": args.init_mode, "skipped_overlong": n_skipped_total}
    save_decoder_init(model, args.out, meta)
    save_resume_state(model, opt, resume_path, step=step, recent=recent, rng=rng,
                      n_skipped=n_skipped_total, signature=signature,
                      last_free_eval=last_free_eval)
    print(f"  最终产物已原子存 {args.out} "
          f"(health={'PASS' if health_pass else 'FAIL'})", flush=True)
    print(f"完成: {args.steps} 步, 末 avg50={avg50:.4f}({loss_class}), "
          f"超长跳过 {n_skipped_total} 行, 用时 {(time.time() - t0) / 60:.1f} 分钟")
    if is_cuda:
        print(f"CUDA 峰值: allocated="
              f"{torch.cuda.max_memory_allocated(device)/2**20:.0f}MiB "
              f"reserved={torch.cuda.max_memory_reserved(device)/2**20:.0f}MiB")
    if is_smoke:
        print(f"自由续写诊断(smoke 不设准入门): "
              f"{last_free_eval['n_parseable']}/{last_free_eval['n']}")
        print("下一步: 只可继续正式 pretrain；本 smoke 产物禁止用于 round-3")
    else:
        print(f"自由续写门: {last_free_eval['n_parseable']}/{last_free_eval['n']} "
              f">= {min_free:.0%} → {'PASS' if free_ok else 'FAIL'}")
        if args.max_free_dyck is not None:
            print(f"DYCK 门: {dyck_count} <= {args.max_free_dyck} → "
                  f"{'PASS' if dyck_ok else 'FAIL'}")
        print("下一步: 仅健康门通过时，round-3 可加 --decoder-init 指向本产物")
    return 0 if health_pass else 2


if __name__ == "__main__":
    sys.exit(main())
