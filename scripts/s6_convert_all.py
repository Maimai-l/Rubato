"""
S6 MAESTRO Full Batch: stream all 1276 WAVs from zip to 16kHz mono FLAC.
Streaming only -- no extraction.  Resumable: skips valid existing FLACs.
"""
import json
import os
import sys
import time
import zipfile
from pathlib import Path

# Ensure rubato is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rubato.data.maestro import load_maestro_csv, stream_wav_to_flac, flac_duration

# ------------------------------------------------------------------- Config
WAV_ZIP = r"D:/vscode_projects/ee_download/maestro-v3.0.0.zip"
CSV_PATH = r"D:/vscode_projects/ee_download/maestro-v3.0.0.csv"
OUTPUT_DIR = r"D:/vscode_projects/ee_download/work/maestro_audio/"
REPORT_PATH = r"D:/vscode_projects/ee_download/reports/s6_full_convert.json"
ZIP_PREFIX = "maestro-v3.0.0/"
LOG_INTERVAL = 100  # report progress every N files

# ------------------------------------------------------------------- Helpers
def fmt_size(n: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def get_all_zip_members(zip_path: str) -> set:
    """Read all member names from zip once (avoids re-seeking 101 GB)."""
    with zipfile.ZipFile(zip_path) as zf:
        return set(zf.namelist())


def resolve_member_fast(audio_fn: str, all_names: set) -> str | None:
    """Resolve audio_filename to full zip member path using cached name set."""
    candidate = ZIP_PREFIX + audio_fn
    if candidate in all_names:
        return candidate
    # fallback: scan for any member ending with audio_fn
    for n in all_names:
        if n.endswith(audio_fn):
            return n
    return None


def flac_valid(path: str) -> float | None:
    """Return duration (s) if FLAC exists and is valid, else None."""
    if not os.path.isfile(path):
        return None
    dur = flac_duration(path)
    if dur is not None and dur > 0:
        return dur
    return None


def main():
    t_start = time.time()

    # 1. Load CSV
    print("Loading CSV ...")
    rows = load_maestro_csv(CSV_PATH)
    total = len(rows)
    print(f"  {total} rows loaded.")

    # 2. Pre-cache zip member names (one seek, not 1276)
    print("Reading zip central directory ...")
    t0 = time.time()
    all_members = get_all_zip_members(WAV_ZIP)
    print(f"  {len(all_members)} members found ({time.time()-t0:.1f}s).")

    # 3. Pre-resolve all member paths
    member_map: dict[str, str | None] = {}
    unresolved = []
    print("Resolving member paths ...")
    for row in rows:
        afn = row["audio_filename"]
        m = resolve_member_fast(afn, all_members)
        member_map[afn] = m
        if m is None:
            unresolved.append(afn)
    if unresolved:
        print(f"  WARNING: {len(unresolved)} files could not be resolved in zip!")
        for u in unresolved[:10]:
            print(f"    {u}")
    else:
        print(f"  All {total} paths resolved successfully.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 4. Batch convert
    stats = {
        "converted": 0, "skipped": 0, "failures": 0,
        "total_flac_size": 0, "total_dur_s": 0.0,
        "failure_details": [],
    }

    for i, row in enumerate(rows):
        audio_fn = row["audio_filename"]
        base = os.path.splitext(os.path.basename(audio_fn))[0]
        out_flac = os.path.join(OUTPUT_DIR, base + ".flac")
        member = member_map.get(audio_fn)

        if member is None:
            stats["failures"] += 1
            stats["failure_details"].append({
                "id": audio_fn, "index": i, "reason": "not_in_zip"
            })
            _log_interval(i, total, stats, t_start)
            continue

        # ---- Skip valid existing FLACs (resumability) ----
        existing_dur = flac_valid(out_flac)
        if existing_dur is not None:
            stats["skipped"] += 1
            stats["total_dur_s"] += existing_dur
            stats["total_flac_size"] += os.path.getsize(out_flac)
            _log_interval(i, total, stats, t_start)
            continue

        # ---- Convert ----
        result = stream_wav_to_flac(WAV_ZIP, member, out_flac, sr_target=16000)
        if result.get("ok"):
            dur = result.get("dur_s", 0.0) or 0.0
            fsize = os.path.getsize(out_flac)
            stats["converted"] += 1
            stats["total_dur_s"] += dur
            stats["total_flac_size"] += fsize
        else:
            stats["failures"] += 1
            stats["failure_details"].append({
                "id": audio_fn, "index": i, "reason": "wav_convert",
                "detail": result.get("error", "")[:200],
                "out": out_flac
            })

        _log_interval(i, total, stats, t_start)

    t_elapsed = time.time() - t_start

    # 5. Verify on-disk state
    flac_files = sorted([
        f for f in os.listdir(OUTPUT_DIR) if f.endswith(".flac")
    ])
    actual_count = len(flac_files)
    actual_size = sum(
        os.path.getsize(os.path.join(OUTPUT_DIR, f)) for f in flac_files
    )
    # Sum durations from all valid FLACs
    verified_dur = 0.0
    dur_errors = 0
    for f in flac_files:
        d = flac_duration(os.path.join(OUTPUT_DIR, f))
        if d is not None:
            verified_dur += d
        else:
            dur_errors += 1

    # 6. Build report
    report = {
        "task": "s6_full_convert",
        "status": "completed",
        "total_csv_rows": total,
        "converted": stats["converted"],
        "skipped_existing": stats["skipped"],
        "failures": stats["failures"],
        "failure_details": stats["failure_details"],
        "actual_flac_count": actual_count,
        "actual_flac_size_bytes": actual_size,
        "actual_flac_size_gb": round(actual_size / 1e9, 4),
        "total_audio_duration_s": round(verified_dur, 2),
        "total_audio_duration_h": round(verified_dur / 3600, 2),
        "duration_verify_errors": dur_errors,
        "elapsed_s": round(t_elapsed, 2),
        "elapsed_min": round(t_elapsed / 60, 2),
        "wav_zip": WAV_ZIP,
        "csv": CSV_PATH,
        "output_dir": OUTPUT_DIR,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    # 7. Summary
    print("\n" + "=" * 60)
    print("  S6 FULL CONVERT -- COMPLETE")
    print("=" * 60)
    print(f"  CSV rows:         {total}")
    print(f"  Converted:        {stats['converted']}")
    print(f"  Skipped (exists): {stats['skipped']}")
    print(f"  Failures:         {stats['failures']}")
    print(f"  ---")
    print(f"  FLACs on disk:    {actual_count}")
    print(f"  Total size:       {fmt_size(actual_size)}")
    print(f"  Total duration:   {verified_dur/3600:.2f} h")
    print(f"  Duration errs:    {dur_errors}")
    print(f"  Elapsed:          {t_elapsed/60:.1f} min")
    print(f"  Report:           {REPORT_PATH}")
    print("=" * 60)

    if stats["failures"]:
        print("\nFAILURES:")
        for f in stats["failure_details"]:
            print(f"  [{f['index']}] {f['id']}: {f.get('detail', f['reason'])}")

    return report


def _log_interval(i: int, total: int, stats: dict, t_start: float):
    """Print progress at interval boundaries."""
    idx = i + 1  # 1-based
    if idx % LOG_INTERVAL == 0 or idx == total:
        elapsed = time.time() - t_start
        done = stats["converted"] + stats["skipped"]
        print(
            f"  [{idx:5d}/{total}] "
            f"done={done} "
            f"ok={stats['converted']} "
            f"skip={stats['skipped']} "
            f"fail={stats['failures']} "
            f"flac={fmt_size(stats['total_flac_size'])} "
            f"elapsed={elapsed//60:.0f}m{elapsed%60:.0f}s"
        )


if __name__ == "__main__":
    main()
