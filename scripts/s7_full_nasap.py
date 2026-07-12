"""
S7 nASAP full dataset processing script.
Processes all 519 ASAP performances with maestro_audio_performance set.
Runs the nASAP pipeline: MusicXML -> IR -> alignment -> TimeMap -> segments -> labels.
"""
from __future__ import annotations
import json
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import partitura
import pandas as pd

from rubato.intermo.partitura_adapter import part_to_ir
from rubato.data.nasap_timemap import parse_alignment_tsv, build_timemap, build_xmlid_map
from rubato.data.nasap import segment_score_overlap
from rubato.data.segment import make_labels


ASAP_ROOT = Path(r"D:\vscode_projects\ee_download\asap-dataset\asap-dataset")
METADATA_CSV = ASAP_ROOT / "metadata.csv"
REPORT_PATH = Path(r"D:\vscode_projects\ee_download\reports\s7_full_nasap.json")


def loader(p):
    """Load MusicXML and return first part, or the score if no parts attribute."""
    s = partitura.load_musicxml(p)
    return s.parts[0] if hasattr(s, 'parts') else s


def read_tsv_rows(path: str) -> list[dict]:
    """Read a TSV file into a list of dicts."""
    import csv
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def process_piece(xml_path: str, alignment_rows: list[dict]) -> tuple[list[dict], dict]:
    """
    Process a single nASAP piece. Mirrors process_nasap_piece but without the
    maestro_flac_path guard, so it runs on alignment-only data.

    Returns (label_rows, stats).
    """
    stats = {"xml": xml_path, "has_audio": False}

    # 1. Load score via partitura
    try:
        part = loader(xml_path)
    except Exception as e:
        stats["skipped"] = f"load_musicxml_failed:{type(e).__name__}:{str(e)[:100]}"
        return [], stats

    # 2. Convert to IR
    try:
        ir = part_to_ir(part)
    except Exception as e:
        stats["skipped"] = f"part_to_ir_failed:{type(e).__name__}:{str(e)[:100]}"
        return [], stats

    # 3. Parse alignment TSV
    try:
        alignment = parse_alignment_tsv(alignment_rows)
        stats["alignment_rows"] = len(alignment_rows)
        stats["alignment_parsed"] = len(alignment)
    except Exception as e:
        stats["skipped"] = f"parse_alignment_failed:{type(e).__name__}:{str(e)[:100]}"
        return [], stats

    # 4. Build xml_id map from partitura Part
    try:
        xmlid_map = build_xmlid_map(part)
        stats["xmlid_map_size"] = len(xmlid_map)
    except Exception as e:
        stats["skipped"] = f"build_xmlid_map_failed:{type(e).__name__}:{str(e)[:100]}"
        return [], stats

    # 5. Build TimeMap from alignment + xml_id map
    try:
        tmap, tm_stats = build_timemap(alignment, xmlid_map)
        stats["timemap"] = tm_stats
    except Exception as e:
        stats["skipped"] = f"build_timemap_failed:{type(e).__name__}:{str(e)[:100]}"
        return [], stats

    if tmap is None:
        stats["skipped"] = "timemap_failed"
        return [], stats

    # 6. Overlap segmentation
    try:
        segs = segment_score_overlap(ir, tmap)
        stats["n_segments"] = len(segs)
    except Exception as e:
        stats["skipped"] = f"segment_failed:{type(e).__name__}:{str(e)[:100]}"
        return [], stats

    # 7. Make labels for each segment
    # 段起点在原曲的乐谱位置(Fraction),供 make_labels 平移局部 tmap:
    # sub_ir 已归零,但 tmap 建在原曲坐标系,不传 offset 则 TAST 时间戳全部映射到曲首(错)。
    bounds = [m.start for m in ir.measures] + [ir.score_end]
    label_rows = []
    for si, (sub_ir, (a, b)) in enumerate(segs):
        try:
            score_offset = bounds[a] if a < len(bounds) else bounds[-1]
            labels, fails = make_labels(sub_ir, "nasap", tmap=tmap, score_offset=score_offset)
            if labels:
                label_rows.append({
                    "utt_id": f"nasap_{Path(xml_path).stem}_{si:03d}",
                    "measure_range": [a, b],
                    **{k: labels.get(k) for k in ("A2S", "A2S_lite", "TAST")},
                    "AMT": None,
                })
        except Exception as e:
            stats.setdefault("label_fails", []).append(f"seg_{si}:{type(e).__name__}")

    stats["labels_produced"] = len(label_rows)
    return label_rows, stats


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-labels", type=str, default="")
    ap.add_argument("--out-corpus", type=str, default="")
    args = ap.parse_args()

    # 输出句柄只开一次(在循环外)。append 模式:配合 --offset/--limit 分块累积;
    # 整轮重跑前请先删旧文件,否则会二次追加。
    label_fh = open(args.out_labels, "a", encoding="utf-8") if args.out_labels else None
    corpus_fh = open(args.out_corpus, "a", encoding="utf-8") if args.out_corpus else None

    print("=" * 70)
    print("S7 nASAP Full Dataset Processing")
    print("=" * 70)

    # Read metadata
    print(f"\nReading metadata: {METADATA_CSV}")
    df = pd.read_csv(str(METADATA_CSV))

    # Filter to rows with maestro_audio_performance set
    has_maestro = df["maestro_audio_performance"].notna() & (df["maestro_audio_performance"] != "")
    pieces = df[has_maestro].copy()
    print(f"Total rows: {len(df)}")
    print(f"Rows with maestro_audio_performance: {len(pieces)}")

    # Apply offset/limit for parallel chunking
    if args.offset or args.limit:
        start = args.offset
        end = args.offset + args.limit if args.limit else len(pieces)
        pieces = pieces.iloc[start:end]
        print(f"Chunk: rows {start}-{end} ({len(pieces)} pieces)")

    # Results tracking
    results = {
        "total_attempted": len(pieces),
        "successful": 0,
        "failed": 0,
        "total_segments": 0,
        "total_a2s_chars": 0,
        "per_composer": defaultdict(lambda: {"attempted": 0, "successful": 0, "segments": 0, "a2s_chars": 0}),
        "failures": [],
        "skipped_reasons": Counter(),
        "timemap_stats": {"total_aligned": 0, "matched_xmlid": 0, "anchors": 0, "dropped_no_scorepos": 0, "dropped_nonmonotone": 0},
        "pieces_without_align_tsv": 0,
    }

    t_start = time.time()

    for idx, (_, row) in enumerate(pieces.iterrows()):
        piece_id = f"{row['composer']}/{row['title']}/{row.get('midi_performance', '?')}"
        if idx % 20 == 0 or idx == len(pieces) - 1:
            elapsed = time.time() - t_start
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            print(f"\n[{idx+1}/{len(pieces)}] ({rate:.1f} pieces/s) Processing {piece_id}")

        composer = str(row["composer"])
        results["per_composer"][composer]["attempted"] += 1

        # Build paths
        xml_rel = str(row["xml_score"])
        xml_path = str(ASAP_ROOT / xml_rel)

        # Check for note_alignment TSV
        alignment_rows = []
        note_align_rel = row.get("note_alignments", "")
        if not note_align_rel or (isinstance(note_align_rel, float) and pd.isna(note_align_rel)):
            results["pieces_without_align_tsv"] += 1
            results["failed"] += 1
            reason = "no_note_alignments_path"
            results["skipped_reasons"][reason] += 1
            results["failures"].append({"piece_id": piece_id, "composer": composer, "reason": reason})
            continue

        align_path = str(ASAP_ROOT / note_align_rel)

        # Check if alignment file exists
        if not Path(align_path).exists():
            results["pieces_without_align_tsv"] += 1
            results["failed"] += 1
            reason = f"alignment_file_not_found"
            results["skipped_reasons"][reason] += 1
            results["failures"].append({"piece_id": piece_id, "composer": composer, "reason": reason,
                                       "path": align_path})
            continue

        # Read alignment TSV
        try:
            alignment_rows = read_tsv_rows(align_path)
        except Exception as e:
            results["failed"] += 1
            reason = f"read_tsv_failed:{type(e).__name__}"
            results["skipped_reasons"][reason] += 1
            results["failures"].append({"piece_id": piece_id, "composer": composer, "reason": reason})
            continue

        # Check XML exists
        if not Path(xml_path).exists():
            results["failed"] += 1
            reason = "xml_file_not_found"
            results["skipped_reasons"][reason] += 1
            results["failures"].append({"piece_id": piece_id, "composer": composer, "reason": reason,
                                       "path": xml_path})
            continue

        # Process piece
        try:
            label_rows, stats = process_piece(xml_path, alignment_rows)

            # Aggregate timemap stats
            if "timemap" in stats:
                tm = stats["timemap"]
                for k in results["timemap_stats"]:
                    if k in tm:
                        results["timemap_stats"][k] += tm[k]

            # 【配对必需,修 no_audio=11526 全灭】行内带演奏音频引用(resolve_audio 据此配
            # work/maestro_audio/<base>.flac);utt_id 加演奏号 —— 同曲多演奏不再撞名互踢;
            # split 沿用 metadata(无则留空,assemble 默认 train)。
            _perf_ref = str(row.get("maestro_audio_performance") or "")
            _perf_stem = Path(str(row.get("midi_performance") or _perf_ref or "p")).stem
            for lr in label_rows:
                lr["perf_audio"] = _perf_ref
                lr["utt_id"] = lr["utt_id"].replace("nasap_", f"nasap_{_perf_stem}_", 1)
                if row.get("split"):
                    lr["split"] = str(row["split"])
            if label_rows and len(label_rows) > 0:
                results["successful"] += 1
                results["total_segments"] += len(label_rows)

                # Write labels
                if label_fh:
                    for lr in label_rows:
                        label_fh.write(json.dumps(lr, ensure_ascii=False) + "\n")

                # Write corpus (A2S + A2S_lite only — tokenizer 语料按论文 §3.2)
                if corpus_fh:
                    for lr in label_rows:
                        for d in ("A2S", "A2S_lite"):
                            t = lr.get(d)
                            if t and t.strip():
                                corpus_fh.write(t.strip() + "\n")

                # Count A2S chars
                for lr in label_rows:
                    a2s = lr.get("A2S", "")
                    if a2s:
                        results["total_a2s_chars"] += len(a2s)

                results["per_composer"][composer]["successful"] += 1
                results["per_composer"][composer]["segments"] += len(label_rows)
                for lr in label_rows:
                    a2s = lr.get("A2S", "")
                    if a2s:
                        results["per_composer"][composer]["a2s_chars"] += len(a2s)
            else:
                results["failed"] += 1
                reason = stats.get("skipped", "unknown")
                results["skipped_reasons"][reason] += 1
                results["failures"].append({"piece_id": piece_id, "composer": composer, "reason": reason})

        except Exception as e:
            results["failed"] += 1
            reason = f"process_exception:{type(e).__name__}:{str(e)[:100]}"
            results["skipped_reasons"][reason] += 1
            results["failures"].append({"piece_id": piece_id, "composer": composer, "reason": reason,
                                       "traceback": traceback.format_exc()[:300]})

    t_elapsed = time.time() - t_start

    # Build summary report
    composer_breakdown = {}
    for comp, data in sorted(results["per_composer"].items()):
        composer_breakdown[comp] = {
            "attempted": data["attempted"],
            "successful": data["successful"],
            "segments": data["segments"],
            "a2s_chars": data["a2s_chars"],
        }

    top5_failures = results["skipped_reasons"].most_common(5)

    report = {
        "report_type": "s7_full_nasap",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": round(t_elapsed, 1),
        "total_attempted": results["total_attempted"],
        "successful": results["successful"],
        "failed": results["failed"],
        "total_segments": results["total_segments"],
        "total_a2s_chars": results["total_a2s_chars"],
        "pieces_without_align_tsv": results["pieces_without_align_tsv"],
        "per_composer": composer_breakdown,
        "top5_failure_reasons": [{"reason": r, "count": c} for r, c in top5_failures],
        "aggregate_timemap_stats": results["timemap_stats"],
        "failure_details": results["failures"][:50],  # first 50 for debugging
    }

    # Write report
    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(str(REPORT_PATH), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n" + "=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)
    print(f"  Total pieces attempted:            {results['total_attempted']}")
    print(f"  Successfully processed:            {results['successful']}")
    print(f"  Failed (0 segments or exception):  {results['failed']}")
    print(f"  Total segments produced:           {results['total_segments']}")
    print(f"  Total A2S chars produced:          {results['total_a2s_chars']}")
    print(f"  Pieces without alignment TSV:      {results['pieces_without_align_tsv']}")
    print(f"  Elapsed time:                      {t_elapsed:.1f}s")
    print()
    print("Per-composer breakdown:")
    for comp, data in sorted(composer_breakdown.items()):
        success_pct = (data["successful"] / max(data["attempted"], 1)) * 100
        print(f"  {comp:20s}: {data['successful']:3d}/{data['attempted']:3d} successful "
              f"({success_pct:5.1f}%), {data['segments']:4d} segments, "
              f"{data['a2s_chars']:>8,d} A2S chars")
    print()
    print("Top 5 failure reasons:")
    for i, (reason, count) in enumerate(top5_failures, 1):
        print(f"  {i}. [{count:3d}] {reason}")
    print()
    print(f"Timemap aggregate: matched {results['timemap_stats']['matched_xmlid']}/{results['timemap_stats']['total_aligned']} "
          f"(dropped_nomap={results['timemap_stats']['dropped_no_scorepos']}, "
          f"nonmonotone={results['timemap_stats']['dropped_nonmonotone']}, "
          f"anchors={results['timemap_stats']['anchors']})")
    # Close file handles
    if label_fh:
        label_fh.close()
    if corpus_fh:
        corpus_fh.close()

    print(f"\nReport written to: {REPORT_PATH}")
    if args.out_labels:
        print(f"Labels written to: {args.out_labels}  (successful={results['successful']}, "
              f"segments={results['total_segments']})")
    if args.out_corpus:
        print(f"Corpus (A2S+A2S_lite) written to: {args.out_corpus}")


if __name__ == "__main__":
    main()
