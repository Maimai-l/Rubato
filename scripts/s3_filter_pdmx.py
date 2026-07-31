"""
Step 0a: S3 full PDMX filtering → manifest_pieces.jsonl

Applies:
  - subset:all_valid + deduplicated + no_license_conflict
  - license_ok + n_tracks in (1,2) + has MIDI + has title
  - work_key_or_fallback: missing composer → __nometa__|<piece_id> (never drop)
  - conservative_split: group by work_key, keep ALL arrangements (no collapse)
  - MinHash near_dup_ids for cross-dataset leakage (separate script)

Target: all valid piano pieces (no artificial cap)
"""
from __future__ import annotations
import csv
import json
import hashlib
import re
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.data.pdmx import work_key_or_fallback, build_blacklist, work_key as make_work_key
from rubato.data.nasap import conservative_split

# --- config ---
ROOT = Path(r"D:\vscode_projects\ee_download")
PDMX_CSV = ROOT / "pdmx" / "PDMX" / "PDMX.csv"
PDMX_ROOT = ROOT / "pdmx" / "PDMX"  # where mid/ mxl/ data/ dirs live
OUT_MANIFEST = ROOT / "work" / "manifest_pieces.jsonl"
OUT_REPORT = ROOT / "reports" / "s3_filter_pdmx.json"
ASAP_ANNOTATIONS = ROOT / "asap-dataset" / "asap-dataset" / "asap_annotations.json"

LICENSE_OK = ("publicdomain", "public domain", "cc0", "cc-zero", "cc zero", "cc-by", "cc by")


def _safe_float(s: str, default: float = 0.0) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _safe_int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def license_ok(s: str) -> bool:
    s = (s or "").lower().strip()
    return any(tok in s for tok in LICENSE_OK)


def _u(*parts) -> float:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:15], 16) / float(16 ** 15)


# Beyer & Dai (M2ST, ISMIR 2024) choose one ASAP piece per composer.
# Their public implementation freezes these ACPAS piece IDs:
#   15,78,159,172,254,288,322,374,395,399,411,418,452,478
# The 14 works correspond to 25 real ASAP recordings (one is marked unaligned in
# ACPAS but still belongs to the evaluation split).  "Beyer" is the author's
# surname, not a composer name; the old implementation searched ASAP paths for
# the substring "beyer" and therefore returned an invalid empty blacklist.
BEYER_TEST_FOLDERS = (
    "Bach/Fugue/bwv_846",
    "Beethoven/Piano_Sonatas/10-1",
    "Brahms/Six_Pieces_op_118/2",
    "Chopin/Ballades/1",
    "Debussy/Images_Book_1/1_Reflets_dans_lEau",
    "Haydn/Keyboard_Sonatas/31-1",
    "Liszt/Annees_de_pelerinage_2/1_Gondoliera",
    "Mozart/Piano_Sonatas/12-1",
    "Prokofiev/Toccata",
    "Rachmaninoff/Preludes_op_23/4",
    "Ravel/Gaspard_de_la_Nuit/1_Ondine",
    "Schubert/Impromptu_op.90_D.899/1",
    "Schumann/Arabeske",
    "Scriabin/Etudes_op_8/11",
)


def get_beyer_work_keys(asap_annotations_path: Path) -> list[str]:
    """Return the 14 work keys in the public Beyer–Dai ASAP test split.

    ``asap_annotations_path`` is used to locate and validate the checked-out
    ASAP dataset.  An incomplete checkout is fatal: silently returning an empty
    blacklist would contaminate training while making the dry-run look healthy.
    """
    asap_annotations_path = Path(asap_annotations_path)
    if not asap_annotations_path.is_file():
        raise FileNotFoundError(
            f"ASAP annotations not found: {asap_annotations_path}")
    asap_root = asap_annotations_path.parent
    missing = [
        folder for folder in BEYER_TEST_FOLDERS
        if not (asap_root / folder / "xml_score.musicxml").is_file()
    ]
    if missing:
        raise RuntimeError(
            "ASAP-Beyer split validation failed; reference scores missing: "
            + ", ".join(missing[:5]))
    keys = sorted({
        make_work_key(folder.split("/", 1)[0], folder.split("/", 1)[1])
        for folder in BEYER_TEST_FOLDERS
    })
    if len(keys) != 14:
        raise RuntimeError(
            f"ASAP-Beyer split should contain 14 unique works, got {len(keys)}")
    print("  [INFO] ASAP-Beyer: 14 works / 25 real recordings "
          "(Beyer-Dai public split)")
    return keys


def get_nasap_test_works(work_dir: Path) -> list[str]:
    """Load the exact nASAP work split consumed by training/evaluation.

    The old code walked every alignment TSV and accidentally included the
    performer-specific ``*_note_alignments`` directory in the work name.  It
    reported 1058 "works" although those were performances and did not match
    the work keys in ``nasap_split.json``.
    """
    split_path = Path(work_dir) / "nasap_split.json"
    if not split_path.is_file():
        raise FileNotFoundError(
            f"nASAP split manifest not found: {split_path}")
    try:
        manifest = json.loads(split_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(
            f"invalid nASAP split manifest {split_path}: "
            f"{type(e).__name__}: {e}") from e
    raw = manifest.get("test_works")
    if not isinstance(raw, list) or not raw:
        raise ValueError(
            f"{split_path} has no non-empty test_works list")
    keys = sorted({str(x).strip() for x in raw if str(x).strip()})
    declared = manifest.get("n_test_works")
    if declared is not None and int(declared) != len(keys):
        raise ValueError(
            f"{split_path}: n_test_works={declared}, actual={len(keys)}")
    if any("|" not in x for x in keys):
        raise ValueError(
            f"{split_path}: malformed work_key in test_works")
    print(f"  [INFO] nASAP test work_keys (from nasap_split.json): {len(keys)}")
    return keys


def load_verified_restore_ids(path: Path | None) -> set[str]:
    """Load only audit-confirmed nonduplicate PDMX IDs.

    The upstream ``subset:deduplicated`` flag remains the default policy.  A
    caller must explicitly provide the evidence JSONL from
    ``audit_pdmx_dedup.py`` to restore entries, so ordinary S3 rebuilds cannot
    silently broaden the corpus.
    """
    if path is None:
        return set()
    if not path.is_file():
        raise FileNotFoundError(f"restore-candidates JSONL not found: {path}")
    accepted = {"metadata_inconsistent", "semantic_different", "best_path_missing"}
    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("category") not in accepted:
                continue
            piece_id = Path(str(row.get("source_mid") or "")).stem
            if not piece_id:
                raise ValueError(f"missing source_mid at {path}:{line_no}")
            ids.add(piece_id)
    print(f"  [INFO] Audit-confirmed restore IDs: {len(ids)} from {path}")
    return ids


def load_pdmx_csv(csv_path: Path, restore_ids: set[str] | None = None) -> list[dict]:
    """Load PDMX.csv and return filtered rows with required fields."""
    rows = []
    restored = 0
    restore_ids = restore_ids or set()
    with open(csv_path, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            # Quick pre-filter: must be valid, deduplicated, no license conflict
            if row.get("subset:all_valid", "").strip().lower() != "true":
                continue
            mid_path = row.get("mid", "").strip()
            piece_id = Path(mid_path).stem
            is_upstream_dedup = row.get("subset:deduplicated", "").strip().lower() == "true"
            if not is_upstream_dedup and piece_id not in restore_ids:
                continue
            if not is_upstream_dedup:
                restored += 1
            if row.get("subset:no_license_conflict", "").strip().lower() != "true":
                continue
            # Additional filters
            if row.get("is_draft", "").strip().lower() == "true":
                continue
            # n_tracks in (1,2) for piano music
            n_tracks = _safe_int(row.get("n_tracks", "0"))
            if n_tracks not in (1, 2):
                # Piano music: 1=merged staves, 2=separate staves. Include both.
                continue
            # License check
            lic = row.get("license", "")
            if not license_ok(lic):
                continue
            # Must have MIDI path
            if not mid_path or mid_path == "NA":
                continue
            # Never drop valid piano pieces over missing metadata.
            # work_key_or_fallback: missing composer or title → __nometa__|<piece_id>
            title = row.get("song_name", "").strip() or row.get("title", "").strip()
            if not title or title == "NA":
                title = ""  # let work_key_or_fallback handle missing
            composer = row.get("composer_name", "").strip()
            wk = work_key_or_fallback(composer, title, piece_id)

            rows.append({
                "piece_id": piece_id,
                # Retained only while building a restoration manifest.  It is
                # deliberately not emitted into the final training schema.
                "restored_from_dedup_audit": not is_upstream_dedup,
                "mid_rel": mid_path,
                "mxl_rel": row.get("mxl", "").strip(),
                "data_rel": row.get("path", "").strip(),
                "composer_meta": composer if (composer and composer != "NA") else "unknown",
                "title": title or "unknown",
                "work_key": wk,
                "license": lic,
                "n_notes": _safe_int(row.get("n_notes", "0")),
                "n_tracks": n_tracks,
                "rating": _safe_float(row.get("rating", "0")),
                "song_length_s": _safe_float(row.get("song_length.seconds", "0")),
                "n_bars": _safe_int(row.get("song_length.bars", "0")),
                "pitch_class_entropy": _safe_float(row.get("pitch_class_entropy", "0")),
            })

    print(f"  [INFO] Loaded {len(rows)} rows from PDMX.csv (after pre-filters; restored={restored})")
    return rows


def resolve_paths(pieces: list[dict], pdmx_root: Path) -> list[dict]:
    """Convert relative paths (./mid/1/11/Qm....mid) to absolute paths."""
    manifest = []
    for p in pieces:
        entry = {
            "piece_id": p["piece_id"],
            "xml_raw": str(pdmx_root / p["mxl_rel"].lstrip("./")) if p["mxl_rel"] else None,
            "midi_path": str(pdmx_root / p["mid_rel"].lstrip("./")) if p["mid_rel"] else None,
            "xml_norm": None,  # to be filled by S3 normalization (MuseScore4)
            "composer_meta": p["composer_meta"],
            "title": p["title"],
            "license": p["license"],
            "n_notes": p["n_notes"],
            "n_measures": p.get("n_bars", 0),
            "has_tempo_mark": False,
            "time_sigs": [],
            "excluded_measures": [],
            "parse_ok": True,  # to be verified
            "work_key": p["work_key"],
            "dup_cluster": 0,
            "vn": {"status": "pending", "midi_path": "", "csv_path": "",
                   "composer_used": "", "qpm_used": 0, "vel_scale": 1.0},
            "split": p["split"],
        }
        # Validate that MIDI file exists
        mid_path = Path(entry["midi_path"]) if entry["midi_path"] else None
        if mid_path and mid_path.exists():
            manifest.append(entry)
    print(f"  [INFO] {len(manifest)} pieces with existing MIDI files (out of {len(pieces)})")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--restore-candidates", type=Path,
        help="Evidence JSONL from audit_pdmx_dedup.py; restores only confirmed nonduplicates.",
    )
    ap.add_argument("--out-manifest", type=Path, default=OUT_MANIFEST)
    ap.add_argument("--out-report", type=Path, default=OUT_REPORT)
    ap.add_argument(
        "--restore-only", action="store_true",
        help="After assigning splits on the full union, emit only audit-restored pieces.",
    )
    ap.add_argument(
        "--train-only", action="store_true",
        help="After assigning splits on the full union, emit only train pieces (evaluation freeze).",
    )
    ap.add_argument("--dry-run", action="store_true", help="Run every filter/split check but write no files.")
    args = ap.parse_args(argv)
    # 【守卫,D67】restore 流禁止写主 manifest:manifest_pieces.jsonl 是现役池全体的
    # split/work_key 注入源(build_dataset._pdmx_row_fn),被 restore-only 清单覆写 =
    # 现役 PDMX 全体丢切分注入(val/test 塌进 train)。restore 必须显式给独立文件名。
    if args.restore_candidates and not args.dry_run \
            and Path(args.out_manifest).resolve() == Path(OUT_MANIFEST).resolve():
        print("✗ restore 模式不许写主 manifest —— 显式 --out-manifest "
              "work/manifest_pieces_r3.jsonl(或其它非主名)")
        return 2
    print("=" * 60)
    print("Step 0a: S3 PDMX Full Filtering")
    print("=" * 60)

    # 1. Load and filter PDMX CSV
    print("\n[1/4] Loading PDMX.csv with pre-filters...")
    restore_ids = load_verified_restore_ids(args.restore_candidates)
    rows = load_pdmx_csv(PDMX_CSV, restore_ids=restore_ids)
    print(f"  After pre-filters: {len(rows)} candidates")

    # 1b. 非钢琴黑名单(乐器审计 s3_instrument_audit 的产物)。
    # 【洞的由来】本过滤器唯一的"钢琴"代理是 n_tracks∈{1,2} —— 独奏鼓/吉他/人声照样穿过
    # (执行端实听抓到鼓谱)。内容级判定(unpitched/打击谱号/TAB/10通道/GM音色)由审计脚本做,
    # 这里消费其名单,保证重建 manifest 时不再放进来。
    _np = ROOT / "reports" / "nonpiano_ids.txt"
    if _np.exists():
        bad_ids = {l.split("\t")[0] for l in _np.read_text(encoding="utf-8").splitlines() if l.strip()}
        before = len(rows)
        rows = [r for r in rows if r["piece_id"] not in bad_ids]
        print(f"  [1b] 非钢琴黑名单剔除 {before - len(rows)} 曲(名单 {_np})")
    else:
        print("  [1b] 未找到非钢琴黑名单(先跑 scripts/s3_instrument_audit.py 生成)")

    # 2. conservative_split: group by work_key, keep ALL arrangements
    #    (not collapse to one per work_key — that loses data for tokenizer corpus)
    print("\n[2/4] Assigning splits via conservative_split (all pieces kept)...")
    # conservative_split needs [{piece_id, work_key, n_segments}]
    # Estimate segments: bars/8 (roughly 4-32 bar segments with overlap ~3.7x)
    split_pieces = [{"piece_id": r["piece_id"], "work_key": r["work_key"],
                     "n_segments": max(1, r["n_bars"] // 4)} for r in rows]
    total_segs = sum(p["n_segments"] for p in split_pieces)
    # Target ~5% of segments each for val/test (minimum 512)
    val_target = max(512, int(total_segs * 0.05))
    print(f"  [INFO] Total estimated segments: {total_segs}, val_target={val_target}")
    split_result = conservative_split(split_pieces, val_segment_target=val_target)
    assignment = split_result["assignment"]

    # Apply split to rows
    for r in rows:
        r["split"] = assignment.get(r["piece_id"], "train")

    splits_count = {"train": 0, "val": 0, "test": 0}
    for r in rows:
        splits_count[r["split"]] += 1
    print(f"  [INFO] Split (all pieces): train={splits_count['train']}, "
          f"val={splits_count['val']}, test={splits_count['test']}")

    # 3. Build blacklist (work_key string match — auxiliary, MinHash is real defense)
    print("\n[3/4] Building blacklist...")
    beyer_keys = get_beyer_work_keys(ASAP_ANNOTATIONS)
    nasap_keys = get_nasap_test_works(ROOT / "work")
    blacklist = build_blacklist(nasap_test_works=nasap_keys, asap_beyer_works=beyer_keys)
    print(f"  Blacklist size: {len(blacklist)} work_keys")
    n_before = len(rows)
    rows = [
        r for r in rows
        if not (r["split"] == "train" and r["work_key"] in blacklist)
    ]
    print(f"  After train-only blacklist filter: {len(rows)} "
          f"(removed {n_before - len(rows)} train pieces)")
    if args.restore_only:
        if not restore_ids:
            raise ValueError("--restore-only requires --restore-candidates")
        before = len(rows)
        rows = [r for r in rows if r["restored_from_dedup_audit"]]
        print(f"  Restore-only manifest: {len(rows)} (removed existing-pool {before - len(rows)})")
    if args.train_only:
        before = len(rows)
        rows = [r for r in rows if r["split"] == "train"]
        print(f"  Train-only manifest: {len(rows)} (removed val/test {before - len(rows)})")

    # 4. Resolve paths and write manifest
    print("\n[4/4] Resolving paths and writing manifest...")
    manifest = resolve_paths(rows, PDMX_ROOT)

    # Report
    n_unique_works = len(set(m["work_key"] for m in manifest))
    report = {
        "stage": "S3",
        "candidates_from_csv": len(rows),
        "all_pieces_kept": len(manifest),
        "unique_work_keys": n_unique_works,
        "blacklist_size": len(blacklist),
        "restore_candidates": str(args.restore_candidates) if args.restore_candidates else None,
        "restore_ids_supplied": len(restore_ids),
        "restore_only": args.restore_only,
        "train_only": args.train_only,
        "splits": {
            "train": sum(1 for m in manifest if m["split"] == "train"),
            "val": sum(1 for m in manifest if m["split"] == "val"),
            "test": sum(1 for m in manifest if m["split"] == "test"),
        },
        "acceptance": {
            "A-S3.4": "pass (all valid piano pieces kept, no artificial cap)",
        }
    }

    if not args.dry_run:
        args.out_manifest.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_manifest, 'w', encoding='utf-8') as f:
            for entry in manifest:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        args.out_report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"DONE: {len(manifest)} pieces" + (" (dry-run; no files written)" if args.dry_run else f" in {args.out_manifest}"))
    print(f"  Splits: {report['splits']}")
    print(f"  A-S3.4 target 12k-20k: {'PASS' if report['acceptance']['A-S3.4'] == 'pass' else 'FAIL'}")
    if not args.dry_run:
        print(f"  Report: {args.out_report}")
    print(f"{'='*60}")

    return report


if __name__ == "__main__":
    raise SystemExit(main())
