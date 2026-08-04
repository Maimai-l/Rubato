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
import json
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


def load_corpus(path: str, max_rows: int | None = None) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("text") and r.get("dialect"):
                rows.append({"dialect": r["dialect"], "text": r["text"]})
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


def save_decoder_init(model, out_path: str, meta: dict):
    import torch
    torch.save({"transf_decoder": model.transf_decoder.state_dict(),
                "log_softmax": model.log_softmax.state_dict(),
                "meta": meta}, out_path)


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
    ap.add_argument("--seed", type=int, default=20260804)
    ap.add_argument("--save-every", type=int, default=2000)
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--tokenizer", default=str(WORK / "rubato_spm.model"))
    ap.add_argument("--nemo", default=str(ROOT / "canary-180m-flash.nemo"))
    ap.add_argument("--vocab-spec",
                    default=str(ROOT / "configs" / "vocab_spec.json"),
                    help="与 build_dataset 同一缺省(configs/vocab_spec.json)")
    args = ap.parse_args(argv)
    if args.steps <= 0 or args.batch_rows <= 0 or args.lr <= 0:
        raise ValueError("steps/batch_rows/lr 必须为正")

    import torch
    import sentencepiece as spm
    from rubato.model.build import build_model
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    rows = load_corpus(args.corpus)
    print(f"语料 {len(rows)} 条 ← {args.corpus}", flush=True)
    tok = spm.SentencePieceProcessor(model_file=args.tokenizer)

    model, _ = build_model(args.nemo, args.tokenizer, args.vocab_spec)
    model = model.to(device)
    model.train()
    n_train, n_frozen = freeze_except_decoder(model)
    print(f"预训练配置回显: 可训参数={n_train:,}(decoder+softmax) "
          f"冻结={n_frozen:,} lr={args.lr:g} warmup={args.warmup} "
          f"steps={args.steps} batch_rows={args.batch_rows} enc_dim={args.enc_dim} "
          f"device={device}", flush=True)

    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=args.lr, betas=(0.9, 0.98), weight_decay=0.01)
    rng = random.Random(args.seed)
    t0 = time.time()
    recent = []
    step = 0
    n_skipped_total = 0
    while step < args.steps:
        batch_rows = [rows[rng.randrange(len(rows))]
                      for _ in range(args.batch_rows)]
        batch, skipped = rows_to_batch(batch_rows, tok)
        n_skipped_total += skipped
        if batch is None:
            continue
        for g in opt.param_groups:
            g["lr"] = args.lr * min(1.0, (step + 1) / max(args.warmup, 1))
        loss, n_tok = pretrain_step(model, batch, args.enc_dim, device)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            [p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
        step += 1
        recent.append(float(loss.detach()))
        if len(recent) > 50:
            recent.pop(0)
        if step % args.log_every == 0 or step == 1:
            print(f"step {step} loss={recent[-1]:.4f} "
                  f"avg50={sum(recent) / len(recent):.4f} tok={n_tok} "
                  f"lr={opt.param_groups[0]['lr']:.2e} "
                  f"{(time.time() - t0) / step:.2f}s/步", flush=True)
        if step % args.save_every == 0 or step == args.steps:
            meta = {"steps": step, "corpus": str(args.corpus),
                    "loss_avg50": sum(recent) / len(recent),
                    "lr": args.lr, "seed": args.seed,
                    "skipped_overlong": n_skipped_total}
            save_decoder_init(model, args.out, meta)
            print(f"  已存 {args.out} (step {step})", flush=True)
    print(f"完成: {args.steps} 步, 末 avg50={sum(recent) / len(recent):.4f}, "
          f"超长跳过 {n_skipped_total} 行, 用时 {(time.time() - t0) / 60:.1f} 分钟")
    print("下一步: round-3 启动命令加 --decoder-init 指向本产物(见 EXECUTOR 追加 31)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
