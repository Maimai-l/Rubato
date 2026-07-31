"""Gate normalized PDMX MusicXML by the parser VirtuosoNet actually uses.

MuseScore re-save fixes many raw-MXL issues, but a score can still be valid
MusicXML while ``virtuoso.pyScoreParser.ScoreData`` rejects it (for example,
an incomplete terminal measure raises ``IndexError`` in beat construction).
This preflight runs only that parser with ``read_xml_only=True``: it loads no
checkpoint, performs no GPU inference, and never modifies a score.

The output manifest is therefore the exact input set eligible for S5
rendering.  Rejections are JSONL with the concrete exception class for audit.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def check_piece(piece: dict) -> tuple[dict, str | None]:
    path_s = piece.get("xml_norm") or piece.get("xml_raw")
    if not path_s:
        return piece, "missing_xml_path"
    path = Path(path_s)
    if not path.is_file():
        return piece, "missing_xml_file"
    try:
        # Composer affects the model's style embedding, not score parsing.
        # Bach is the established, data-rich fallback used by S5.
        from virtuoso.pyScoreParser.data_class import ScoreData
        score = ScoreData(str(path), None, "Bach", read_xml_only=True)
        if not score.xml_notes:
            return piece, "empty_xml_notes"
    except Exception as exc:
        return piece, f"scoredata:{type(exc).__name__}"
    return piece, None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out-manifest", type=Path, required=True)
    ap.add_argument("--out-rejects", type=Path, required=True)
    ap.add_argument("--out-report", type=Path, required=True)
    ap.add_argument("--virtuoso-root", type=Path,
                    default=Path(r"D:\vscode_projects\virtuso\virtuosoNet"))
    ap.add_argument("--workers", type=int, default=8,
                    help="Thread count; use 8-16 on the shared SSD, not a large I/O storm.")
    ap.add_argument("--limit", type=int, default=0,
                    help="For a safe canary; 0 means all input rows.")
    args = ap.parse_args()
    if not args.virtuoso_root.is_dir():
        raise SystemExit(f"Virtuoso source root not found: {args.virtuoso_root}")
    sys.path.insert(0, str(args.virtuoso_root))

    pieces = [json.loads(line) for line in args.manifest.open(encoding="utf-8") if line.strip()]
    if args.limit:
        pieces = pieces[:args.limit]
    for target in (args.out_manifest, args.out_rejects, args.out_report):
        target.parent.mkdir(parents=True, exist_ok=True)

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
                print(f"[scoredata] {index}/{len(pieces)} kept={kept} rejected={index-kept}", flush=True)

    report = {
        "input_pieces": len(pieces),
        "kept_for_vn": kept,
        "rejected": len(pieces) - kept,
        "reasons": dict(sorted(counts.items())),
        "rule": "ScoreData(read_xml_only=True) must parse and yield at least one XML note; no model or inference",
    }
    args.out_report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("DONE", json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
