"""
论文级终评驱动(S13)—— 拿 ckpt 扫 test 集,产 outputs/eval_report.md + 全部审计产物。

指标(对照论文数字,gap_annotation 自动标"训练可缩/结构性"):
  nASAP test:整曲可解析率、官方 LEGATO OMR-NED(原始人工 MusicXML 参考)、
             TAST note F1(mir_eval,onset 与 onset+offset 双口径)、失败三分类归因。
  MAESTRO test:AMT note F1(双口径)+ bootstrap 95% CI。

产物(--out 目录):preds.jsonl(逐 utt 预测/参照/判定,全量审计)、metrics.json、
eval_report.md、omr_ned/output.csv(LEGATO 官方逐曲结果)。

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
REPO_ROOT = Path(__file__).resolve().parent.parent
PAPER_ASAP_BENCHMARK = "rubato_paper_asap_standard_maestro_test_v1"
PAPER_ASAP_COUNT = 102


def validate_performance_pairs(pairs: list[dict], expected_split: str | None = None,
                               check_paths: bool = True) -> None:
    """在加载模型前硬校验整曲清单，避免数小时后才发现错配/缺文件。"""
    required = ("perf_id", "flac", "ref_xml")
    errors = []
    seen = set()
    for i, row in enumerate(pairs):
        if not isinstance(row, dict):
            errors.append(f"row {i}: not an object")
            continue
        missing = [k for k in required if not row.get(k)]
        if missing:
            errors.append(f"row {i}: missing {','.join(missing)}")
            continue
        perf_id = str(row["perf_id"])
        if perf_id in seen:
            errors.append(f"row {i}: duplicate perf_id={perf_id}")
        seen.add(perf_id)
        if expected_split and row.get("split") not in (None, expected_split):
            errors.append(
                f"row {i}: split={row.get('split')!r}, expected={expected_split!r}")
        if check_paths:
            for key in ("flac", "ref_xml"):
                if not Path(row[key]).is_file():
                    errors.append(f"row {i}: {key} missing: {row[key]}")
    if not pairs:
        errors.append("manifest is empty")
    declared = {row.get("benchmark") for row in pairs if isinstance(row, dict)}
    if len(declared) > 1:
        errors.append(f"mixed benchmark identities: {sorted(map(str, declared))}")
    expected_counts = {
        row.get("benchmark_expected_count") for row in pairs
        if isinstance(row, dict) and row.get("benchmark_expected_count") is not None}
    if len(expected_counts) > 1:
        errors.append(
            f"mixed benchmark_expected_count values: {sorted(map(str, expected_counts))}")
    if errors:
        preview = "\n  ".join(errors[:20])
        suffix = f"\n  ... {len(errors) - 20} more" if len(errors) > 20 else ""
        raise ValueError(f"invalid performance manifest:\n  {preview}{suffix}")


def performance_benchmark_status(pairs: list[dict]) -> dict:
    """Distinguish a complete local LEGATO run from the paper's exact ASAP scope.

    Merely running the official metric on every row does not make an arbitrary
    holdout comparable to Table 2.  The paper scope is 102 recordings; manifests
    without an explicit identity remain useful local evaluations but fail closed
    for paper-number comparisons.
    """
    identities = {row.get("benchmark") for row in pairs}
    identity = next(iter(identities)) if len(identities) == 1 else None
    declared = {row.get("benchmark_expected_count") for row in pairs}
    expected = next(iter(declared)) if len(declared) == 1 else None
    paper_exact = (
        identity == PAPER_ASAP_BENCHMARK
        and expected == PAPER_ASAP_COUNT
        and len(pairs) == PAPER_ASAP_COUNT
    )
    if paper_exact:
        reason = "exact_paper_asap_manifest"
    elif identity is None:
        reason = "manifest_has_no_benchmark_identity"
    elif identity != PAPER_ASAP_BENCHMARK:
        reason = f"different_benchmark:{identity}"
    else:
        reason = (
            f"paper_manifest_count_mismatch:"
            f"rows={len(pairs)} declared={expected} expected={PAPER_ASAP_COUNT}")
    return {"identity": identity or "unidentified",
            "declared_count": expected, "row_count": len(pairs),
            "paper_exact": paper_exact, "reason": reason}


def official_omr_complete(split: str, limit: int, skipped: bool, perf_n: int,
                          export_fail: int, omr: dict) -> bool:
    """论文 OMR 可发布门：全量 test + 原始清单逐项出分，任何条件均值都失败关闭。"""
    return (
        split == "test" and limit == 0 and not skipped and perf_n > 0
        and export_fail == 0 and bool(omr.get("complete"))
        and int(omr.get("n_pairs", -1)) == perf_n
        and int(omr.get("n_scores_parsed", -1)) == perf_n
        and omr.get("omr_ned_mean") is not None
    )


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
    ap.add_argument(
        "--vocab-spec",
        default=str(REPO_ROOT / "configs" / "vocab_spec.json"))
    ap.add_argument("--split", default="test", choices=("test", "val"))
    ap.add_argument("--limit", type=int, default=0, help="每源 utt 上限(冒烟);0=全量")
    ap.add_argument("--out", default=str(ROOT / "reports" / "eval_final"))
    ap.add_argument("--skip-omr", action="store_true", help="显式跳过官方 LEGATO OMR-NED")
    ap.add_argument("--skip-tast", action="store_true", help="跳过 nASAP 的 TAST 二次解码")
    ap.add_argument("--beam-size", type=int, default=4,
                    help="正式终评 beam size；训练监控可用1，论文对照缺省4")
    ap.add_argument("--pairs", default=str(WORK / "calib_pairs.jsonl"),
                    help="完整 nASAP test performance→整曲音频/原始参考 XML 清单")
    ap.add_argument("--legato-script", default=None,
                    help="LEGATO compute_OMR-NED.py；缺省按已校准路径自动找")
    ap.add_argument("--legato-python", default=sys.executable,
                    help="运行 LEGATO 官方脚本的 Python")
    ap.add_argument("--musicdiff-source",
                    default=str(WORK / "efficient-musicdiff"),
                    help="LEGATO 指定的 efficient-musicdiff 源码根；加入子进程 PYTHONPATH")
    args = ap.parse_args(argv)
    if args.limit < 0:
        ap.error("--limit must be >= 0")

    import torch
    import sentencepiece as spm
    from scripts.build_dataset import SOURCES, resolve_audio, attach_pdmx_row_fns
    from rubato.data.assemble import assemble, partition_by_split
    from rubato.data.dataset import load_audio
    from rubato.model.build import build_model
    from rubato.model.infer import infer_a2s, infer_amt, single_window_tast
    from rubato.model.evaluate import (note_f1, amt_text_to_notes, bootstrap_ci,
                                       build_eval_report)
    from rubato.intermo.core import text_to_units, validate_units

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 装配 test 集(与训练同一条装配路,split 字段同源)----
    attach_pdmx_row_fns(SOURCES)
    utts, labels, _stats = assemble(SOURCES, resolve_audio)
    part = partition_by_split(utts)
    pool = part[args.split]
    nasap = [u for u in pool if u["kind"] == "nasap"]
    maestro = [u for u in pool if u["kind"] == "maestro"]
    if args.limit:
        nasap, maestro = nasap[:args.limit], maestro[:args.limit]
    perf_pairs = []
    perf_benchmark = performance_benchmark_status([])
    if args.split == "test" and Path(args.pairs).exists():
        with open(args.pairs, encoding="utf-8") as fh:
            perf_pairs = [json.loads(line) for line in fh if line.strip()]
        try:
            validate_performance_pairs(perf_pairs, expected_split="test")
        except ValueError as e:
            print(f"✗ {e}")
            return 2
        perf_benchmark = performance_benchmark_status(perf_pairs)
        if args.limit:
            perf_pairs = perf_pairs[:args.limit]
    print(f"终评 split={args.split}: nasap_segments={len(nasap)} "
          f"nasap_performances={len(perf_pairs)} maestro={len(maestro)}")
    if args.split == "test":
        print("  performance benchmark="
              f"{perf_benchmark['identity']} rows={perf_benchmark['row_count']} "
              f"paper_exact={perf_benchmark['paper_exact']} "
              f"({perf_benchmark['reason']})")
    if args.split == "test" and not perf_pairs and not args.skip_omr:
        print("✗ 正式 test OMR 缺完整 performance 配对清单；拒绝退回片段代理。"
              f"请先生成 {args.pairs}，或显式 --skip-omr。")
        return 2

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

    # ---- nASAP 正式 OMR：按完整 performance 跑长音频，参考使用原始人工 MusicXML ----
    from rubato.model import infer as _inf
    from rubato.model.omr_ned import a2s_to_musicxml
    performance_rows = []
    xml_pairs: list[tuple[str, str]] = []
    xml_row_indices: list[int] = []
    export_fail = 0
    for i, p in enumerate(perf_pairs):
        if i % 2 == 0:
            print(f"nasap performance {i}/{len(perf_pairs)}"
                  f"({time.time() - t0:.0f}s)", flush=True)
        row = {"utt_id": p["perf_id"], "kind": "nasap_performance",
               "parseable": False, "infer_status": "not_run"}
        try:
            audio = load_audio(p["flac"])
            with torch.no_grad():
                pred = infer_a2s(model, audio, tok, domain="real",
                                 beam_size=args.beam_size)
            ist = dict(getattr(_inf, "LAST_INFER_STATS", {}) or {})
            row.update(pred_a2s=pred, infer_status=ist.get("status"),
                       failed_windows=ist.get("n_failed_windows", 0),
                       n_windows=ist.get("n_windows", 0),
                       window_failures=ist.get("window_failures", []))
            try:
                viol = validate_units(text_to_units(pred)) if pred else ["empty"]
            except Exception as e:
                viol = [f"parse:{type(e).__name__}"]
            if ist.get("fallback"):
                viol = list(viol) + ["fallback"]
            if ist.get("status") == "partial":
                viol = list(viol) + [
                    f"partial_windows:{ist.get('n_failed_windows', 0)}"]
            row["parseable"] = not viol
            row["violations"] = viol
            if not viol:
                try:
                    pred_xml = a2s_to_musicxml(pred)
                    ref_xml = Path(p["ref_xml"]).read_text(encoding="utf-8")
                    xml_row_indices.append(len(performance_rows))
                    xml_pairs.append((pred_xml, ref_xml))
                except Exception as e:
                    export_fail += 1
                    row["export_error"] = f"{type(e).__name__}: {e}"
        except Exception as e:
            row["infer_status"] = "audio_or_infer_error"
            row["error"] = f"{type(e).__name__}: {e}"
        performance_rows.append(row)

    # ---- nASAP TAST note F1：片段级辅助指标；任何失败都按 0，绝不从分母消失 ----
    tast_f1, tast_f1_off = [], []
    tast_expected = tast_decode_ok = 0
    if not args.skip_tast:
        for i, u in enumerate(nasap):
            ref_tast = labels.get(u["utt_id"], {}).get("TAST")
            if not ref_tast:
                continue
            tast_expected += 1
            row = {"utt_id": u["utt_id"], "kind": "nasap_tast_segment"}
            try:
                audio = load_audio(u["audio_path"], win=u.get("win"))
                with torch.no_grad():
                    pred_tast = single_window_tast(
                        model, audio, 16000, tok, beam_size=args.beam_size,
                        truncate=False, domain=u.get("domain"))
                if not pred_tast:
                    raise ValueError("decode_or_validation_failed")
                f = note_f1(amt_text_to_notes(ref_tast),
                            amt_text_to_notes(pred_tast))
                tast_decode_ok += 1
                row.update(pred_tast=pred_tast[:4000], f1=f["f1"],
                           f1_off=f["f1_off"])
            except Exception as e:
                f = {"f1": 0.0, "f1_off": 0.0}
                row["error"] = f"{type(e).__name__}: {e}"
            tast_f1.append(f["f1"])
            tast_f1_off.append(f["f1_off"])
            preds_fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---- MAESTRO:AMT note F1 双口径；有参照的每一项都进分母 ----
    amt_f1, amt_f1_off = [], []
    amt_expected = amt_decode_ok = 0
    for i, u in enumerate(maestro):
        if i % 8 == 0:
            print(f"maestro {i}/{len(maestro)}({time.time() - t0:.0f}s)", flush=True)
        ref_text = labels.get(u["utt_id"], {}).get("AMT")
        if not ref_text:
            continue
        amt_expected += 1
        row = {"utt_id": u["utt_id"], "kind": "maestro"}
        try:
            audio = load_audio(u["audio_path"], win=u.get("win"))
            with torch.no_grad():
                pred_text = infer_amt(model, audio, tok, beam_size=args.beam_size,
                                      domain=u.get("domain"))
            est = amt_text_to_notes(pred_text)
            f = note_f1(amt_text_to_notes(ref_text), est)
            amt_decode_ok += int(bool(pred_text))
            row.update(pred_amt=pred_text[:2000], f1=f["f1"], f1_off=f["f1_off"])
        except Exception as e:
            f = {"f1": 0.0, "f1_off": 0.0}
            row["error"] = f"{type(e).__name__}: {e}"
        amt_f1.append(f["f1"])
        amt_f1_off.append(f["f1_off"])
        preds_fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---- OMR-NED：统一走已外部校准的 LEGATO 官方 JSON 接口 ----
    omr = {"skipped": True, "reason": "disabled_or_no_evaluable_pairs",
           "n_pairs": len(xml_pairs), "n_scores_parsed": 0,
           "omr_ned_mean": None, "scores": [], "complete": False}
    if not args.skip_omr and xml_pairs:
        from rubato.model.omr_ned import omr_ned_legato
        from scripts.calib_score import find_legato_script
        legato_script = (Path(args.legato_script) if args.legato_script
                         else find_legato_script())
        if legato_script is None:
            omr.update(reason="legato_script_not_found", returncode=-1)
        else:
            print(f"LEGATO:{len(xml_pairs)} 对(导出失败 {export_fail})…", flush=True)
            omr = omr_ned_legato(
                xml_pairs, out_dir / "omr_ned", legato_script,
                python_exe=args.legato_python,
                musicdiff_source=args.musicdiff_source)
        print(f"LEGATO rc={omr.get('returncode')} parsed={omr['n_scores_parsed']} "
              f"mean={omr['omr_ned_mean']}")
        if not omr.get("complete"):
            print("  ⚠ LEGATO 正式指标不完整，已拒绝发布条件均值；"
                  "检查 stdout_tail / output.csv / 覆盖率")
    for row_i, score in zip(xml_row_indices, omr.get("scores", [])):
        performance_rows[row_i]["omr_ned"] = score
    # 归因必须在 LEGATO 分数回填后做。旧实现提前把每个可解析样本都无条件算作
    # content_error，导致“总失败”恒等于总作品数。
    from rubato.model.evaluate import classify_failure
    triage = []
    for row in performance_rows:
        if not row.get("parseable"):
            category = ("merge_artifact"
                        if row.get("infer_status") == "partial" else "parse_fail")
        elif row.get("export_error"):
            category = "parse_fail"
        elif row.get("omr_ned") is None:
            category = "metric_unavailable"
        else:
            category = classify_failure(
                row.get("pred_a2s", ""), omr_ned=float(row["omr_ned"]))
        row["triage_category"] = category
        triage.append({"utt_id": row["utt_id"], "category": category})
    for row in performance_rows:
        preds_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    preds_fh.close()

    # ---- 汇总 + 报告 ----
    n_perf_ok = sum(1 for r in performance_rows if r.get("parseable"))
    perf_n = len(performance_rows)
    omr_official_complete = official_omr_complete(
        args.split, args.limit, args.skip_omr, perf_n, export_fail, omr)
    omr["scope"] = ("official_full_test" if omr_official_complete else
                    ("limited_smoke" if args.limit else args.split))
    omr["official_complete"] = omr_official_complete
    omr["benchmark"] = perf_benchmark
    # Current MAESTRO/TAST helpers macro-average generated windows rather than
    # the paper's certified recording-level protocol. Only exact ASAP OMR may
    # be compared, and only after both manifest identity and LEGATO completeness pass.
    paper_comparable_metrics = []
    if omr_official_complete and perf_benchmark["paper_exact"]:
        paper_comparable_metrics.append("nasap_omr_ned")
    metrics = {
        "split": args.split, "ckpt": str(ckpt),
        "limit": args.limit, "paper_comparable_scope": (
            bool(paper_comparable_metrics)),
        "paper_comparable_metrics": paper_comparable_metrics,
        "paper_comparison_blockers": ([] if paper_comparable_metrics else [
            perf_benchmark["reason"],
            "maestro_and_tast_are_window_macro_metrics_not_certified_paper_protocol",
        ]),
        "nasap_segment_n": len(nasap), "nasap_performance_n": perf_n,
        "maestro_n": len(maestro),
        "parseable_rate": (round(n_perf_ok / perf_n, 4) if perf_n else None),
        "nasap_performance_fail": perf_n - n_perf_ok,
        "nasap_tast_note_f1": (100 * sum(tast_f1) / len(tast_f1)) if tast_f1 else None,
        "nasap_tast_note_f1_off": (100 * sum(tast_f1_off) / len(tast_f1_off)) if tast_f1_off else None,
        "nasap_tast_expected": tast_expected,
        "nasap_tast_decode_ok": tast_decode_ok,
        "nasap_tast_coverage": (tast_decode_ok / tast_expected if tast_expected else None),
        "maestro_amt_f1": (100 * sum(amt_f1) / len(amt_f1)) if amt_f1 else None,
        # 主指标是百分制，CI 必须同量纲；旧代码把 0–1 CI 与 0–100 F1 并列。
        "maestro_amt_f1_ci": bootstrap_ci([100.0 * x for x in amt_f1]),
        "maestro_amt_f1_off": (100 * sum(amt_f1_off) / len(amt_f1_off)) if amt_f1_off else None,
        "maestro_amt_expected": amt_expected,
        "maestro_amt_decode_ok": amt_decode_ok,
        "maestro_amt_coverage": (amt_decode_ok / amt_expected if amt_expected else None),
        "omr_ned": omr, "xml_export_fail": export_fail,
        "omr_coverage": (omr.get("n_scores_parsed", 0) / perf_n if perf_n else None),
        "official_omr_complete": omr_official_complete,
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    named = {k: v for k, v in (("maestro_amt_f1", metrics["maestro_amt_f1"]),
                               ("nasap_tast_note_f1", metrics["nasap_tast_note_f1"]))
             if v is not None}
    if omr_official_complete:
        named["nasap_omr_ned"] = omr["omr_ned_mean"]
    report_md = build_eval_report(
        named, triage,
        paper_comparable_metrics=set(paper_comparable_metrics))
    (out_dir / "eval_report.md").write_text(report_md, encoding="utf-8")
    print(f"\n完成 → {out_dir}(preds.jsonl / metrics.json / eval_report.md)")
    print("【贴回给用户】metrics.json 全文 + eval_report.md 全文 + LEGATO stdout_tail(若有)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
