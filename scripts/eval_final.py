"""
论文级终评驱动(S13)—— 拿 ckpt 扫 test 集,产 outputs/eval_report.md + 全部审计产物。

指标(对照论文数字,gap_annotation 自动标"训练可缩/结构性"):
  nASAP test:可解析率、OMR-NED(musicdiff/LEGATO 契约;文本 NED 代理并列供对照)、
             TAST note F1(mir_eval,onset 与 onset+offset 双口径)、失败三分类归因。
  MAESTRO test:AMT note F1(双口径)+ bootstrap 95% CI。

产物(--out 目录):preds.jsonl(逐 utt 预测/参照/判定,全量审计)、metrics.json、
eval_report.md、omr_ned/(musicdiff 输入输出,首次运行把 stdout_tail 贴回钉解析)。

用法(执行端,训练出像样的 ckpt 之后):
  python scripts/eval_final.py --limit 20        # 冒烟:20 utt/源,先看跑通+样张
  python scripts/eval_final.py                   # 全量 test(小时级,心跳可见)
  python scripts/eval_final.py --split val       # 训练途中看水位也行
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout

ROOT = Path(r"D:\vscode_projects\ee_download")
WORK = ROOT / "work"


def load_ckpt_state(path: Path):
    import torch
    snap = torch.load(str(path), map_location="cpu")
    return snap["model"] if isinstance(snap, dict) and "model" in snap else snap


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="论文级终评:ckpt 扫 test 集,产报告(缺省全量)")
    ap.add_argument("--ckpt", default="", help="缺省 outputs/ckpt/best.pt,无则 last.pt")
    ap.add_argument("--nemo", default=str(ROOT / "canary-180m-flash.nemo"))
    ap.add_argument("--tokenizer", default=str(WORK / "rubato_spm.model"))
    ap.add_argument("--vocab-spec", default="configs/vocab_spec.json")
    ap.add_argument("--split", default="test", choices=("test", "val"))
    ap.add_argument("--limit", type=int, default=0, help="每源 utt 上限(冒烟);0=全量")
    ap.add_argument("--out", default=str(ROOT / "reports" / "eval_final"))
    ap.add_argument("--skip-omr", action="store_true", help="跳过 musicdiff(没装/太慢时)")
    ap.add_argument("--skip-tast", action="store_true", help="跳过 nASAP 的 TAST 二次解码")
    args = ap.parse_args(argv)

    import torch
    import sentencepiece as spm
    from scripts.build_dataset import SOURCES, resolve_audio, _pdmx_row_fn
    from rubato.data.assemble import assemble, partition_by_split
    from rubato.data.dataset import load_audio
    from rubato.model.build import build_model, DIALECT_PROMPT
    from rubato.model.infer import infer_a2s, infer_amt, autoregressive_decode, _EMPTY_A2S
    from rubato.model.evaluate import (note_f1, amt_text_to_notes, text_ned, bootstrap_ci,
                                       classify_failure, build_eval_report)
    from rubato.intermo.core import text_to_units, validate_units

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 装配 test 集(与训练同一条装配路,split 字段同源)----
    pdmx_fn = _pdmx_row_fn()
    for src in SOURCES:
        if src["kind"] == "pdmx":
            src["row_fn"] = pdmx_fn
    utts, labels, _stats = assemble(SOURCES, resolve_audio)
    part = partition_by_split(utts)
    pool = part[args.split]
    nasap = [u for u in pool if u["kind"] == "nasap"]
    maestro = [u for u in pool if u["kind"] == "maestro"]
    if args.limit:
        nasap, maestro = nasap[:args.limit], maestro[:args.limit]
    print(f"终评 split={args.split}: nasap={len(nasap)} maestro={len(maestro)}")

    # ---- 建模 + 载 ckpt ----
    ckpt = Path(args.ckpt) if args.ckpt else (ROOT / "outputs" / "ckpt" / "best.pt")
    if not ckpt.exists():
        ckpt = ROOT / "outputs" / "ckpt" / "last.pt"
    if not ckpt.exists():
        print(f"✗ 找不到 ckpt({ckpt})")
        return 1
    tok = spm.SentencePieceProcessor(model_file=args.tokenizer)
    model, _rep = build_model(args.nemo, args.tokenizer, args.vocab_spec)
    model.load_state_dict(load_ckpt_state(ckpt))
    if torch.cuda.is_available():
        model = model.cuda()
    model.eval()
    print(f"ckpt = {ckpt}")

    preds_fh = open(out_dir / "preds.jsonl", "w", encoding="utf-8")
    t0 = time.time()

    # ---- nASAP:A2S(可解析率/NED/归因/OMR 对)+ TAST note F1 ----
    n_ok = 0
    ned_proxy: list[float] = []
    tast_f1, tast_f1_off = [], []
    triage = []
    xml_pairs: list[tuple[str, str]] = []
    export_fail = 0
    for i, u in enumerate(nasap):
        if i % 8 == 0:
            print(f"nasap {i}/{len(nasap)}({time.time() - t0:.0f}s)", flush=True)
        audio = load_audio(u["audio_path"], win=u.get("win"))
        ref_a2s = labels[u["utt_id"]].get("A2S") or ""
        with torch.no_grad():
            pred = infer_a2s(model, audio, tok)
        try:
            viol = validate_units(text_to_units(pred)) if pred else ["empty"]
        except Exception as e:
            viol = [f"parse:{type(e).__name__}"]
        if pred == _EMPTY_A2S:
            viol = viol or ["empty_fallback"]
        parseable = not viol
        n_ok += int(parseable)
        row = {"utt_id": u["utt_id"], "kind": "nasap", "pred_a2s": pred,
               "ref_a2s": ref_a2s, "parseable": parseable}
        if parseable and ref_a2s:
            row["ned_proxy"] = text_ned(pred, ref_a2s)
            ned_proxy.append(row["ned_proxy"])
            triage.append({"utt_id": u["utt_id"],
                           "category": classify_failure(pred, ref_a2s, row["ned_proxy"])})
            if not args.skip_omr:
                try:
                    from rubato.model.omr_ned import a2s_to_musicxml
                    xml_pairs.append((a2s_to_musicxml(pred), a2s_to_musicxml(ref_a2s)))
                except Exception:
                    export_fail += 1
        else:
            triage.append({"utt_id": u["utt_id"], "category": "parse_fail"})
        if not args.skip_tast and labels[u["utt_id"]].get("TAST"):
            with torch.no_grad():
                pred_tast = autoregressive_decode(model, audio, tok,
                                                  list(DIALECT_PROMPT["TAST"]))
            try:
                f = note_f1(amt_text_to_notes(labels[u["utt_id"]]["TAST"]),
                            amt_text_to_notes(pred_tast))
                tast_f1.append(f["f1"])
                tast_f1_off.append(f["f1_off"])
                row["tast_f1"] = f["f1"]
            except Exception as e:
                row["tast_f1_err"] = type(e).__name__
        preds_fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---- MAESTRO:AMT note F1 双口径 ----
    amt_f1, amt_f1_off = [], []
    for i, u in enumerate(maestro):
        if i % 8 == 0:
            print(f"maestro {i}/{len(maestro)}({time.time() - t0:.0f}s)", flush=True)
        ref_text = labels[u["utt_id"]].get("AMT")
        if not ref_text:
            continue
        audio = load_audio(u["audio_path"], win=u.get("win"))
        with torch.no_grad():
            pred_text = infer_amt(model, audio, tok)
        try:
            est = amt_text_to_notes(pred_text)
        except Exception:
            est = []
        f = note_f1(amt_text_to_notes(ref_text), est)
        amt_f1.append(f["f1"])
        amt_f1_off.append(f["f1_off"])
        preds_fh.write(json.dumps({"utt_id": u["utt_id"], "kind": "maestro",
                                   "pred_amt": pred_text[:2000], "f1": f["f1"],
                                   "f1_off": f["f1_off"]}, ensure_ascii=False) + "\n")
    preds_fh.close()

    # ---- OMR-NED(musicdiff,LEGATO 契约)----
    omr = {"skipped": True}
    if not args.skip_omr and xml_pairs:
        from rubato.model.omr_ned import omr_ned_musicdiff
        print(f"musicdiff:{len(xml_pairs)} 对(导出失败 {export_fail})…", flush=True)
        omr = omr_ned_musicdiff(xml_pairs, out_dir / "omr_ned")
        print(f"musicdiff rc={omr['returncode']} parsed={omr['n_scores_parsed']} "
              f"mean={omr['omr_ned_mean']}")
        if omr["omr_ned_mean"] is None:
            print("  ⚠ 未能从输出解析出分数 —— 把 stdout_tail 和 output_files 贴回规划端钉解析")

    # ---- 汇总 + 报告 ----
    metrics = {
        "split": args.split, "ckpt": str(ckpt),
        "nasap_n": len(nasap), "maestro_n": len(maestro),
        "parseable_rate": round(n_ok / max(len(nasap), 1), 4),
        "ned_proxy_ci": bootstrap_ci(ned_proxy),
        "nasap_tast_note_f1": (100 * sum(tast_f1) / len(tast_f1)) if tast_f1 else None,
        "nasap_tast_note_f1_off": (100 * sum(tast_f1_off) / len(tast_f1_off)) if tast_f1_off else None,
        "maestro_amt_f1": (100 * sum(amt_f1) / len(amt_f1)) if amt_f1 else None,
        "maestro_amt_f1_ci": bootstrap_ci(amt_f1),
        "maestro_amt_f1_off": (100 * sum(amt_f1_off) / len(amt_f1_off)) if amt_f1_off else None,
        "omr_ned": omr, "xml_export_fail": export_fail,
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    named = {k: v for k, v in (("maestro_amt_f1", metrics["maestro_amt_f1"]),
                               ("nasap_tast_note_f1", metrics["nasap_tast_note_f1"]))
             if v is not None}
    if omr.get("omr_ned_mean") is not None:
        named["nasap_omr_ned"] = omr["omr_ned_mean"]
    report_md = build_eval_report(named, triage)
    (out_dir / "eval_report.md").write_text(report_md, encoding="utf-8")
    print(f"\n完成 → {out_dir}(preds.jsonl / metrics.json / eval_report.md)")
    print("【贴回给用户】metrics.json 全文 + eval_report.md 全文 + musicdiff stdout_tail(若有)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
