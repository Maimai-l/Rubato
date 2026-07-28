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
import re
import sys
import tempfile
import time
import zipfile
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import partitura

from rubato.data.pdmx import near_dup_ids, piece_signature
from rubato.intermo.partitura_adapter import AdapterError, part_to_ir
from scripts.build_dataset import (
    ROOT, SOURCES, _file_fingerprint, active_pdmx_manifest_paths)


def _quarter_fraction(value) -> Fraction:
    """Partitura's quarter-map float → exact-enough whole-note fraction."""
    return Fraction(str(float(value))).limit_denominator(1_000_000) / 4


def _signature_only_ir(part):
    """Minimal IR for MinHash when strict training serialization is inapplicable.

    Training serialization deliberately rejects changing divisions because its
    measure/time assumptions are stricter; it also requires a time signature
    before the first measure. Leakage detection consumes only pitch/duration,
    so use Partitura's normalized quarter map and reproduce the adapter's
    tied-note/strict-overlap merge without weakening any training rule.
    """
    grouped: dict[tuple[int, int], list[list[Fraction]]] = {}
    for note in part.notes_tied:
        staff = int(getattr(note, "staff", None) or 1)
        pitch = int(note.midi_pitch)
        on = _quarter_fraction(part.quarter_map(note.start.t))
        off = _quarter_fraction(part.quarter_map(note.end_tied.t))
        if off > on:
            grouped.setdefault((staff, pitch), []).append([on, off])
    notes = []
    for (_staff, pitch), intervals in grouped.items():
        intervals.sort()
        current = intervals[0]
        for interval in intervals[1:]:
            if interval[0] < current[1]:
                current[1] = max(current[1], interval[1])
            else:
                notes.append(SimpleNamespace(
                    pitch=pitch, onset=current[0],
                    dur=current[1] - current[0]))
                current = interval
        notes.append(SimpleNamespace(
            pitch=pitch, onset=current[0], dur=current[1] - current[0]))
    if not notes:
        raise AdapterError("没有可用于泄漏签名的音符")
    return SimpleNamespace(notes=notes)


def _load_without_display_accidentals(path: Path):
    """Parse a temporary XML copy without ``<accidental>`` display glyphs.

    PDMX includes SMuFL names such as ``slash-flat`` that older Partitura
    versions do not recognize and raise ``KeyError`` for.  The sounding pitch
    is carried by ``<pitch>/<alter>``; ``<accidental>`` only controls the
    engraved glyph.  Removing it in a temporary copy preserves pitch semantics
    and never mutates the dataset.
    """
    path = Path(path)
    if path.suffix.lower() == ".mxl":
        with zipfile.ZipFile(path) as archive:
            candidates = [
                name for name in archive.namelist()
                if name.lower().endswith((".xml", ".musicxml"))
                and not name.replace("\\", "/").startswith("META-INF/")
            ]
            if not candidates:
                raise ValueError("MXL contains no score XML")
            data = archive.read(candidates[0])
    else:
        data = path.read_bytes()
    cleaned = re.sub(
        rb"<(?:\w+:)?accidental\b[^>]*>.*?</(?:\w+:)?accidental\s*>",
        b"", data, flags=re.DOTALL)
    if cleaned == data:
        raise ValueError("no display accidental tags available to sanitize")
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
                suffix=".musicxml", delete=False) as handle:
            handle.write(cleaned)
            tmp_name = handle.name
        return partitura.load_musicxml(tmp_name)
    finally:
        if tmp_name:
            Path(tmp_name).unlink(missing_ok=True)


def _score_ir(path: Path):
    """Parse MusicXML/MXL using both Partitura entrypoints, then select a part."""
    errors = []
    for loader in (
            partitura.load_score, partitura.load_musicxml,
            _load_without_display_accidentals):
        try:
            score = loader(str(path))
            if hasattr(score, "parts") and score.parts:
                part = score.parts[0]
            elif hasattr(score, "notes"):
                part = score
            else:
                raise ValueError("score has neither parts nor notes")
            try:
                return part_to_ir(part)
            except AdapterError:
                return _signature_only_ir(part)
        except Exception as e:
            errors.append(f"{getattr(loader, '__name__', type(loader).__name__)}:"
                          f"{type(e).__name__}: {e}")
    raise RuntimeError(
        " | ".join(errors[:3]))


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
            print(f"REF_FAIL {path}: {type(e).__name__}: {e}", flush=True)
        if i % 25 == 0:
            print(f"refs {i}/{len(refs)} failed={len(ref_fail)}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if ref_fail or len(ref_sigs) != len(refs):
        cert = {
            "schema": 1,
            "status": "fail",
            "reason": "reference_parse_failure",
            "method": "MinHash Jaccard on 8-gram (pitch,duration)",
            "threshold": args.threshold,
            "manifests": manifest_records,
            "target_unique_train": len(targets),
            "target_signatures": 0,
            "target_parse_failed": 0,
            "target_failures": [],
            "target_scan_skipped": True,
            "reference_root": str(Path(args.asap_root).resolve()),
            "reference_scores": len(refs),
            "reference_signatures": len(ref_sigs),
            "reference_parse_failed": len(ref_fail),
            "reference_failures": ref_fail,
            "leaked_count": 0,
            "leaked_piece_ids": [],
            "elapsed_s": 0.0,
        }
        out.write_text(json.dumps(cert, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"DONE status=fail leaked=0 target_fail=0 "
              f"ref_fail={len(ref_fail)} → {out}", flush=True)
        return 2

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
            if len(target_fail) <= 20:
                print(f"TARGET_FAIL {row['piece_id']} {row['xml_raw']}: "
                      f"{type(e).__name__}: {e}", flush=True)
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
    out.write_text(json.dumps(cert, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"DONE status={cert['status']} leaked={len(leaked)} "
          f"target_fail={len(target_fail)} ref_fail={len(ref_fail)} → {out}",
          flush=True)
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
