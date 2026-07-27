"""Strict content-leakage certificate for the active PDMX training manifests.

The certificate is bound to the exact manifest bytes.  A passing certificate
requires every ASAP reference score and every unique PDMX train score to parse,
and requires zero MinHash near-duplicates.  Parse failures never pass open.

Run when the current training job is idle (the full scan is CPU/IO heavy):
  python scripts/certify_pdmx_leakage.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import partitura

from rubato.data.pdmx import near_dup_ids, piece_signature
from rubato.intermo.partitura_adapter import part_to_ir
from scripts.build_dataset import (
    ROOT, SOURCES, _file_fingerprint, active_pdmx_manifest_paths)


def _score_ir(path: Path):
    """Parse MusicXML/MXL using both Partitura entrypoints, then select a part."""
    first_error = None
    for loader in (partitura.load_score, partitura.load_musicxml):
        try:
            score = loader(str(path))
            if hasattr(score, "parts") and score.parts:
                part = score.parts[0]
            elif hasattr(score, "notes"):
                part = score
            else:
                raise ValueError("score has neither parts nor notes")
            return part_to_ir(part)
        except Exception as e:
            first_error = first_error or e
    raise RuntimeError(
        f"{type(first_error).__name__}: {first_error}") from first_error


def _read_manifests(paths: list[Path]) -> tuple[list[dict], list[dict]]:
    records = []
    train_by_id: dict[str, dict] = {}
    for path in paths:
        sha, rows = _file_fingerprint(path)
        train_rows = 0
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("split") != "train":
                    continue
                train_rows += 1
                pid = str(row.get("piece_id") or "")
                xml = str(row.get("xml_raw") or "")
                if not pid or not xml:
                    raise ValueError(
                        f"{path}:{line_no} train row missing piece_id/xml_raw")
                old = train_by_id.get(pid)
                if old and Path(old["xml_raw"]).resolve() != Path(xml).resolve():
                    raise ValueError(
                        f"piece_id {pid} maps to conflicting XML paths")
                train_by_id[pid] = {"piece_id": pid, "xml_raw": xml}
        records.append({"path": str(path.resolve()), "sha256": sha,
                        "rows": rows, "train_rows": train_rows})
    return records, [train_by_id[k] for k in sorted(train_by_id)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", action="append", default=[],
                    help="Manifest to certify; repeat. Default = active build_dataset manifests.")
    ap.add_argument(
        "--asap-root",
        default=str(ROOT / "asap-dataset" / "asap-dataset"))
    ap.add_argument(
        "--out",
        default=str(ROOT / "reports" / "pdmx_leakage_certificate.json"))
    ap.add_argument("--threshold", type=float, default=0.7)
    args = ap.parse_args(argv)
    paths = ([Path(p).resolve() for p in args.manifest]
             if args.manifest else active_pdmx_manifest_paths(SOURCES))
    if not paths or any(not p.is_file() for p in paths):
        missing = [str(p) for p in paths if not p.is_file()]
        raise FileNotFoundError(f"active PDMX manifests missing:{missing}")
    if not 0.0 < args.threshold < 1.0:
        raise ValueError("--threshold must be between 0 and 1")

    manifest_records, targets = _read_manifests(paths)
    refs = sorted(Path(args.asap_root).glob("**/xml_score.musicxml"))
    if not refs:
        raise FileNotFoundError(f"no ASAP reference scores under {args.asap_root}")
    print(f"certificate scope: manifests={len(paths)} "
          f"unique_train={len(targets)} refs={len(refs)}", flush=True)

    ref_sigs, ref_fail = [], []
    for i, path in enumerate(refs, 1):
        try:
            ref_sigs.append(piece_signature(_score_ir(path)))
        except Exception as e:
            ref_fail.append({"path": str(path), "error": f"{type(e).__name__}: {e}"})
        if i % 25 == 0:
            print(f"refs {i}/{len(refs)} failed={len(ref_fail)}", flush=True)

    target_sigs, target_fail = {}, []
    started = time.time()
    for i, row in enumerate(targets, 1):
        try:
            target_sigs[row["piece_id"]] = piece_signature(
                _score_ir(Path(row["xml_raw"])))
        except Exception as e:
            target_fail.append({
                "piece_id": row["piece_id"], "xml_raw": row["xml_raw"],
                "error": f"{type(e).__name__}: {e}"})
        if i % 500 == 0:
            rate = i / max(time.time() - started, 1e-6)
            eta = (len(targets) - i) / max(rate, 1e-6)
            print(f"targets {i}/{len(targets)} sigs={len(target_sigs)} "
                  f"failed={len(target_fail)} rate={rate:.1f}/s "
                  f"ETA={eta/60:.1f}m", flush=True)

    leaked = (near_dup_ids(target_sigs, ref_sigs, threshold=args.threshold)
              if ref_sigs and target_sigs else set())
    passed = not ref_fail and not target_fail and not leaked \
        and len(ref_sigs) == len(refs) and len(target_sigs) == len(targets)
    cert = {
        "schema": 1,
        "status": "pass" if passed else "fail",
        "reason": ("all_active_train_scores_checked_zero_near_duplicates"
                   if passed else "parse_failure_or_leak_detected"),
        "method": "MinHash Jaccard on 8-gram (pitch,duration)",
        "threshold": args.threshold,
        "manifests": manifest_records,
        "target_unique_train": len(targets),
        "target_signatures": len(target_sigs),
        "target_parse_failed": len(target_fail),
        "target_failures": target_fail[:100],
        "reference_root": str(Path(args.asap_root).resolve()),
        "reference_scores": len(refs),
        "reference_signatures": len(ref_sigs),
        "reference_parse_failed": len(ref_fail),
        "reference_failures": ref_fail,
        "leaked_count": len(leaked),
        "leaked_piece_ids": sorted(leaked),
        "elapsed_s": round(time.time() - started, 1),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cert, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"DONE status={cert['status']} leaked={len(leaked)} "
          f"target_fail={len(target_fail)} ref_fail={len(ref_fail)} → {out}",
          flush=True)
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
