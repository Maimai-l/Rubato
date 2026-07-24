"""Normalize a PDMX manifest with MuseScore4 for VirtuosoNet compatibility.

Raw PDMX MXL files can make VirtuosoNet hang even when their MusicXML is
otherwise valid.  Re-saving through MuseScore4 produces the canonical XML
that VirtuosoNet accepts.  This tool is resumable: existing non-empty outputs
are reused and the input manifest is never changed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def destination(piece: dict, out_root: Path) -> Path:
    raw = Path(piece.get("xml_raw") or piece.get("xml_norm") or "")
    # Preserve PDMX's numeric two-level shard where available, so output
    # directories remain small even for the full 128k restoration manifest.
    shard = raw.parent.parent.name if len(raw.parents) >= 2 else "misc"
    leaf = raw.parent.name if raw.parent.name else "misc"
    return out_root / shard / leaf / f"{piece.get('piece_id', raw.stem)}.musicxml"


def normalize_one(args: tuple[dict, str, str, int]) -> tuple[dict, str | None, str]:
    piece, exe, out_root_s, timeout_s = args
    source = Path(piece.get("xml_norm") or piece.get("xml_raw") or "")
    output = destination(piece, Path(out_root_s))
    if not source.is_file():
        return piece, "missing_input", ""
    if output.is_file() and output.stat().st_size > 0:
        return piece, None, str(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        cp = subprocess.run(
            [exe, "-o", str(output), str(source)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout_s, check=False,
        )
    except subprocess.TimeoutExpired:
        return piece, "musescore_timeout", ""
    except OSError as exc:
        return piece, f"musescore_oserror:{type(exc).__name__}", ""
    if cp.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        return piece, f"musescore_exit:{cp.returncode}", ""
    return piece, None, str(output)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out-manifest", type=Path, required=True)
    ap.add_argument("--out-rejects", type=Path, required=True)
    ap.add_argument("--out-report", type=Path, required=True)
    ap.add_argument("--out-xml-root", type=Path, required=True)
    ap.add_argument("--musescore", default=r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--limit", type=int, default=0, help="For a safe canary; 0 means all input rows.")
    args = ap.parse_args()
    if not Path(args.musescore).is_file():
        raise SystemExit(f"MuseScore executable not found: {args.musescore}")

    pieces = [json.loads(line) for line in args.manifest.open(encoding="utf-8") if line.strip()]
    if args.limit:
        pieces = pieces[:args.limit]
    for p in (args.out_manifest, args.out_rejects, args.out_report):
        p.parent.mkdir(parents=True, exist_ok=True)
    args.out_xml_root.mkdir(parents=True, exist_ok=True)

    kept = 0
    reasons: dict[str, int] = {}
    work = ((p, args.musescore, str(args.out_xml_root), args.timeout) for p in pieces)
    with args.out_manifest.open("w", encoding="utf-8") as out, \
            args.out_rejects.open("w", encoding="utf-8") as rejects, \
            ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for index, (piece, reason, xml_norm) in enumerate(pool.map(normalize_one, work), 1):
            if reason is None:
                piece = dict(piece)
                piece["xml_norm"] = xml_norm
                out.write(json.dumps(piece, ensure_ascii=False) + "\n")
                kept += 1
            else:
                reasons[reason] = reasons.get(reason, 0) + 1
                rejects.write(json.dumps({
                    "piece_id": piece.get("piece_id"),
                    "xml_path": piece.get("xml_norm") or piece.get("xml_raw"),
                    "reason": reason,
                }, ensure_ascii=False) + "\n")
            if index % 100 == 0:
                print(f"[ms4] {index}/{len(pieces)} kept={kept} rejected={index-kept}", flush=True)

    report = {
        "input_pieces": len(pieces), "normalized": kept,
        "rejected": len(pieces) - kept, "reasons": dict(sorted(reasons.items())),
        "out_xml_root": str(args.out_xml_root),
        "rule": "MuseScore4 re-save; original manifest and raw MXL are untouched",
    }
    args.out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DONE", json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
