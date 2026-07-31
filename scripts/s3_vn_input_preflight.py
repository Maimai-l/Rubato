"""Preflight PDMX MusicXML inputs for VirtuosoNet.

VirtuosoNet crashes with ``IndexError`` before inference when a MusicXML score
contains no explicit ``<time>`` declaration.  This tool performs that cheap,
lossless input gate before S5: it never edits a score or invents a meter.

It writes a compatible manifest plus an auditable JSONL of rejected pieces.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


TIME_TAG = re.compile(br"<time(?:\s|>)", re.I)


def check_piece(piece: dict) -> tuple[dict, str | None]:
    path_s = piece.get("xml_norm") or piece.get("xml_raw")
    if not path_s:
        return piece, "missing_xml_path"
    path = Path(path_s)
    if not path.is_file():
        return piece, "missing_xml_file"
    try:
        if path.suffix.casefold() == ".mxl":
            with zipfile.ZipFile(path) as archive:
                names = [
                    name for name in archive.namelist()
                    if name.casefold().endswith((".xml", ".musicxml"))
                    and not name.casefold().startswith("meta-inf/")
                ]
                if not names:
                    return piece, "mxl_without_score_xml"
                data = archive.read(names[0])
        else:
            data = path.read_bytes()
    except zipfile.BadZipFile:
        return piece, "bad_mxl_zip"
    except OSError as exc:
        return piece, f"read_error:{type(exc).__name__}"
    return piece, None if TIME_TAG.search(data) else "no_time_signature"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out-manifest", type=Path, required=True)
    ap.add_argument("--out-rejects", type=Path, required=True)
    ap.add_argument("--out-report", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4,
                    help="Small I/O pool; keep conservative on a busy disk.")
    args = ap.parse_args()

    pieces = [json.loads(line) for line in args.manifest.open(encoding="utf-8") if line.strip()]
    args.out_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.out_rejects.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    kept = 0
    with args.out_manifest.open("w", encoding="utf-8") as out, \
            args.out_rejects.open("w", encoding="utf-8") as rejects, \
            ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for index, (piece, reason) in enumerate(pool.map(check_piece, pieces), 1):
            if reason is None:
                out.write(json.dumps(piece, ensure_ascii=False) + "\n")
                kept += 1
            else:
                counts[reason] += 1
                rejects.write(json.dumps({
                    "piece_id": piece.get("piece_id"),
                    "xml_path": piece.get("xml_norm") or piece.get("xml_raw"),
                    "reason": reason,
                }, ensure_ascii=False) + "\n")
            if index % 1000 == 0:
                print(f"[preflight] {index}/{len(pieces)} kept={kept} rejected={index-kept}", flush=True)

    report = {
        "input_pieces": len(pieces),
        "kept_for_vn": kept,
        "rejected": len(pieces) - kept,
        "reasons": dict(sorted(counts.items())),
        "rule": "keep only inputs with an explicit MusicXML <time> declaration; do not invent meter",
    }
    args.out_report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("DONE", json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
