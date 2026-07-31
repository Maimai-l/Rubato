"""Strict content-leakage certificate for the active PDMX training manifests.

The certificate is bound to the exact manifest bytes.  A passing certificate
requires every ASAP reference score and every unique PDMX train score to parse,
and requires zero near-duplicates by exact Jaccard on the established
(pitch, duration) 8-grams.  Parse failures never pass open.

Run when the current training job is idle (the full scan is CPU/IO heavy):
  python scripts/certify_pdmx_leakage.py
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
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

from rubato.data.assemble import normalize_row
from rubato.data.pdmx import ir_to_pitch_dur_seq, ngram_set
from rubato.intermo.partitura_adapter import AdapterError, part_to_ir
from scripts.build_dataset import (
    ROOT, SOURCES, _file_fingerprint, _load_pdmx_eval_blacklist,
    _pdmx_row_fn, active_pdmx_filter_paths, active_pdmx_manifest_paths,
    pdmx_source_manifest_paths)


_CERT_REFS: tuple[frozenset, ...] = ()
_CERT_INDEX: dict[tuple, tuple[int, ...]] = {}
_CERT_THRESHOLD = 0.7


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


def _load_without_display_notation(path: Path):
    """Parse a temporary XML copy without unsupported display-only notation.

    PDMX includes SMuFL names such as ``slash-flat`` that older Partitura
    versions do not recognize and raise ``KeyError`` for.  The sounding pitch
    is carried by ``<pitch>/<alter>``; ``<accidental>`` only controls the
    engraved glyph.  Likewise, ``<type>512th</type>`` is a display value while
    the performed duration is carried by ``<duration>`` and ``<divisions>``.
    Removing these tags in a temporary copy preserves pitch/duration semantics
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
    cleaned = re.sub(
        rb"<(?:\w+:)?type\b[^>]*>.*?</(?:\w+:)?type\s*>",
        b"", cleaned, flags=re.DOTALL)
    if cleaned == data:
        raise ValueError("no display notation tags available to sanitize")
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
            _load_without_display_notation):
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


def _score_grams(path: Path, n: int = 8) -> frozenset:
    return ngram_set(ir_to_pitch_dur_seq(_score_ir(path)), n)


def _build_ref_index(ref_grams: list[frozenset]) -> dict[tuple, tuple[int, ...]]:
    index: dict[tuple, list[int]] = {}
    for ref_id, grams in enumerate(ref_grams):
        for gram in grams:
            index.setdefault(gram, []).append(ref_id)
    return {gram: tuple(ids) for gram, ids in index.items()}


def _cert_worker_init(ref_grams: list[frozenset], threshold: float) -> None:
    global _CERT_REFS, _CERT_INDEX, _CERT_THRESHOLD
    _CERT_REFS = tuple(ref_grams)
    _CERT_INDEX = _build_ref_index(ref_grams)
    _CERT_THRESHOLD = float(threshold)


def _is_leaked_grams(grams: frozenset) -> bool:
    """Exact Jaccard gate, with an exact inverted-index candidate reduction."""
    candidates: set[int] = set()
    for gram in grams:
        candidates.update(_CERT_INDEX.get(gram, ()))
    for ref_id in candidates:
        ref = _CERT_REFS[ref_id]
        union = len(grams | ref)
        score = len(grams & ref) / union if union else 1.0
        if score > _CERT_THRESHOLD:
            return True
    return False


def _cert_target_worker(row: dict) -> dict:
    try:
        grams = _score_grams(Path(row["xml_raw"]))
        return {
            "piece_id": row["piece_id"], "ok": True,
            "leaked": _is_leaked_grams(grams), "error": None,
        }
    except Exception as exc:
        return {
            "piece_id": row["piece_id"], "xml_raw": row["xml_raw"],
            "ok": False, "leaked": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


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


def _manifest_xml_map(paths: list[Path]) -> dict[str, str]:
    """Load the source-local piece→XML mapping with conflict checks."""
    mapping: dict[str, str] = {}
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                pid = str(row.get("piece_id") or "")
                xml = str(row.get("xml_raw") or "")
                if not pid:
                    raise ValueError(f"{path}:{line_no} missing piece_id")
                if not xml:
                    raise ValueError(f"{path}:{line_no} missing xml_raw")
                old = mapping.get(pid)
                if old and Path(old).resolve() != Path(xml).resolve():
                    raise ValueError(
                        f"piece_id {pid} maps to conflicting XML paths")
                mapping[pid] = xml
    return mapping


def _read_active_training_scope(
        sources: list[dict], manifest_paths: list[Path],
        blacklist: set[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Select only score pieces referenced by labels that can enter train.

    This deliberately reuses ``_pdmx_row_fn`` and ``normalize_row`` so the
    certificate cannot silently drift from assembly split/blacklist/quarantine
    rules.  Audio availability is not part of score leakage, so a referenced
    piece is conservatively certified even if its current audio is absent.
    """
    manifest_records, _unused_all_train = _read_manifests(manifest_paths)
    if blacklist is None:
        blacklist = _load_pdmx_eval_blacklist()
    targets: dict[str, dict] = {}
    label_records = []
    seen_label_paths: set[str] = set()
    for src in sources:
        if src.get("kind") != "pdmx":
            continue
        label_path = Path(src["path"]).resolve()
        label_key = str(label_path).lower()
        if label_key in seen_label_paths:
            raise ValueError(f"duplicate PDMX label source:{label_path}")
        seen_label_paths.add(label_key)
        if not label_path.is_file():
            raise FileNotFoundError(f"active PDMX labels missing:{label_path}")
        source_manifests = pdmx_source_manifest_paths(src)
        xml_by_id = _manifest_xml_map(source_manifests)
        row_filter = _pdmx_row_fn(
            source_manifests,
            quarantine_unmapped=bool(src.get("quarantine_unmapped", False)),
            blacklist=blacklist)
        sha, rows = _file_fingerprint(label_path)
        train_label_rows = 0
        train_piece_ids: set[str] = set()
        with label_path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                row = row_filter(row)
                if row is None:
                    continue
                normalized = normalize_row(row, "pdmx")
                if normalized is None or not normalized[1]:
                    continue
                if (normalized[2] or "train").lower() != "train":
                    continue
                pid = str(row.get("piece_id") or "")
                xml = xml_by_id.get(pid)
                if not pid or not xml:
                    raise ValueError(
                        f"{label_path}:{line_no} train row has no mapped XML")
                train_label_rows += 1
                train_piece_ids.add(pid)
                old = targets.get(pid)
                if old and Path(old["xml_raw"]).resolve() != Path(xml).resolve():
                    raise ValueError(
                        f"piece_id {pid} maps to conflicting XML paths")
                targets[pid] = {"piece_id": pid, "xml_raw": xml}
        label_records.append({
            "path": str(label_path),
            "sha256": sha,
            "rows": rows,
            "train_label_rows": train_label_rows,
            "train_piece_ids": len(train_piece_ids),
            "manifests": [str(path) for path in source_manifests],
            "quarantine_unmapped": bool(
                src.get("quarantine_unmapped", False)),
        })
    if not label_records:
        raise RuntimeError("no active PDMX label sources")
    return (
        manifest_records,
        label_records,
        [targets[pid] for pid in sorted(targets)],
    )


def _fingerprint_records(paths: list[Path]) -> list[dict]:
    records = []
    for path in paths:
        sha, rows = _file_fingerprint(path)
        records.append({
            "path": str(path.resolve()), "sha256": sha, "rows": rows})
    return records


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
    ap.add_argument(
        "--workers", type=int, default=min(8, os.cpu_count() or 4),
        help="Parallel MusicXML parsers; default min(8, logical CPUs).")
    args = ap.parse_args(argv)
    paths = ([Path(p).resolve() for p in args.manifest]
             if args.manifest else active_pdmx_manifest_paths(SOURCES))
    if not paths or any(not p.is_file() for p in paths):
        missing = [str(p) for p in paths if not p.is_file()]
        raise FileNotFoundError(f"active PDMX manifests missing:{missing}")
    if not 0.0 < args.threshold < 1.0:
        raise ValueError("--threshold must be between 0 and 1")
    if args.workers <= 0:
        raise ValueError("--workers must be positive")

    if args.manifest:
        manifest_records, targets = _read_manifests(paths)
        label_records = []
        filter_records = []
        scope = "all_manifest_train"
    else:
        manifest_records, label_records, targets = \
            _read_active_training_scope(SOURCES, paths)
        filter_records = _fingerprint_records(active_pdmx_filter_paths())
        scope = "active_label_referenced_train"
    refs = sorted(Path(args.asap_root).glob("**/xml_score.musicxml"))
    if not refs:
        raise FileNotFoundError(f"no ASAP reference scores under {args.asap_root}")
    print(f"certificate scope: {scope} manifests={len(paths)} "
          f"labels={len(label_records)} "
          f"unique_train={len(targets)} refs={len(refs)}", flush=True)

    ref_grams, ref_fail = [], []
    for i, path in enumerate(refs, 1):
        try:
            ref_grams.append(_score_grams(path))
        except Exception as e:
            ref_fail.append({"path": str(path), "error": f"{type(e).__name__}: {e}"})
            print(f"REF_FAIL {path}: {type(e).__name__}: {e}", flush=True)
        if i % 25 == 0:
            print(f"refs {i}/{len(refs)} failed={len(ref_fail)}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if ref_fail or len(ref_grams) != len(refs):
        cert = {
            "schema": 1,
            "status": "fail",
            "reason": "reference_parse_failure",
            "method": "Exact Jaccard on 8-gram (pitch,duration), inverted reference index",
            "threshold": args.threshold,
            "scope": scope,
            "manifests": manifest_records,
            "label_sources": label_records,
            "filter_files": filter_records,
            "target_unique_train": len(targets),
            "target_signatures": 0,
            "target_parse_failed": 0,
            "target_failures": [],
            "target_scan_skipped": True,
            "reference_root": str(Path(args.asap_root).resolve()),
            "reference_scores": len(refs),
            "reference_signatures": len(ref_grams),
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

    target_ok = 0
    target_fail = []
    leaked: set[str] = set()
    started = time.time()
    print(f"targets: workers={args.workers} exact_jaccard "
          f"ref_index_grams={sum(len(g) for g in ref_grams)}", flush=True)

    def consume(results):
        nonlocal target_ok
        for i, result in enumerate(results, 1):
            if result["ok"]:
                target_ok += 1
                if result["leaked"]:
                    leaked.add(result["piece_id"])
            else:
                target_fail.append({
                    "piece_id": result["piece_id"],
                    "xml_raw": result["xml_raw"],
                    "error": result["error"],
                })
                if len(target_fail) <= 20:
                    print(f"TARGET_FAIL {result['piece_id']} "
                          f"{result['xml_raw']}: {result['error']}", flush=True)
            if i % 500 == 0:
                rate = i / max(time.time() - started, 1e-6)
                eta = (len(targets) - i) / max(rate, 1e-6)
                print(f"targets {i}/{len(targets)} sigs={target_ok} "
                      f"failed={len(target_fail)} leaked={len(leaked)} "
                      f"rate={rate:.1f}/s ETA={eta/60:.1f}m", flush=True)

    if args.workers == 1:
        _cert_worker_init(ref_grams, args.threshold)
        consume(map(_cert_target_worker, targets))
    else:
        context = mp.get_context("spawn")
        with context.Pool(
                processes=args.workers,
                initializer=_cert_worker_init,
                initargs=(ref_grams, args.threshold),
                maxtasksperchild=250) as pool:
            consume(pool.imap_unordered(
                _cert_target_worker, targets, chunksize=4))

    passed = not ref_fail and not target_fail and not leaked \
        and len(ref_grams) == len(refs) and target_ok == len(targets)
    cert = {
        "schema": 1,
        "status": "pass" if passed else "fail",
        "reason": ("all_active_train_scores_checked_zero_near_duplicates"
                   if passed else "parse_failure_or_leak_detected"),
        "method": "Exact Jaccard on 8-gram (pitch,duration), inverted reference index",
        "threshold": args.threshold,
        "scope": scope,
        "manifests": manifest_records,
        "label_sources": label_records,
        "filter_files": filter_records,
        "target_unique_train": len(targets),
        "target_signatures": target_ok,
        "target_parse_failed": len(target_fail),
        "target_failures": target_fail[:100],
        "reference_root": str(Path(args.asap_root).resolve()),
        "reference_scores": len(refs),
        "reference_signatures": len(ref_grams),
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
