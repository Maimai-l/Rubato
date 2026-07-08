"""
Generate AMT labels from ALL 1276 MAESTRO MIDI files.
Reads MIDI from zip, parses with mido (via rubato.data.maestro.midi_to_events),
converts to AMT text (via rubato.intermo.core.perf_to_amt),
writes JSONL output, and produces a statistics report.
"""
import json
import sys
import time
import zipfile
from pathlib import Path

# Add rubato-repl to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.data.maestro import midi_to_events
from rubato.intermo.core import perf_to_amt


def load_csv_rows(csv_path: str) -> list[dict]:
    """Load MAESTRO CSV with UTF-8 encoding."""
    import csv
    with open(csv_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resolve_zip_member(zf: zipfile.ZipFile, csv_midi_name: str) -> str | None:
    """Find the actual zip member path for a CSV midi_filename entry."""
    names = set(zf.namelist())
    # Direct match
    if csv_midi_name in names:
        return csv_midi_name
    # Try with maestro-v3.0.0/ prefix (as seen in the zip)
    prefixed = f"maestro-v3.0.0/{csv_midi_name}"
    if prefixed in names:
        return prefixed
    # Fallback: any member ending with this filename
    for n in names:
        if n.endswith(csv_midi_name):
            return n
    return None


def process_all(midi_zip_path: str, csv_path: str, out_jsonl: str) -> dict:
    """Process all MIDI files and produce AMT labels."""
    rows = load_csv_rows(csv_path)
    total = len(rows)
    print(f"Loaded {total} entries from CSV.")

    # Statistics accumulators
    split_counts: dict[str, int] = {}
    total_notes = 0
    total_floored = 0
    total_units = 0
    failures: list[dict] = []
    processed = 0
    label_rows: list[dict] = []

    zf = zipfile.ZipFile(midi_zip_path)
    t0 = time.time()

    for i, row in enumerate(rows):
        split = row["split"]
        split_counts[split] = split_counts.get(split, 0) + 1
        csv_midi = row["midi_filename"]
        midi_file_id = csv_midi  # use CSV path as identifier

        # Resolve member name in zip
        member = resolve_zip_member(zf, csv_midi)
        if member is None:
            failures.append({"midi_file": midi_file_id, "reason": "not_found_in_zip"})
            print(f"  [{i+1}/{total}] FAIL (not found): {csv_midi}")
            continue

        # Parse MIDI
        try:
            midi_bytes = zf.read(member)
            notes, pedal = midi_to_events(midi_bytes)
        except Exception as e:
            err_msg = str(e)[:100]
            failures.append({"midi_file": midi_file_id, "reason": f"parse_error:{type(e).__name__}:{err_msg}"})
            print(f"  [{i+1}/{total}] FAIL (parse): {csv_midi} -> {type(e).__name__}")
            continue

        # Convert to AMT
        try:
            amt_text, stats = perf_to_amt(notes, pedal)
        except Exception as e:
            err_msg = str(e)[:100]
            failures.append({"midi_file": midi_file_id, "reason": f"amt_error:{type(e).__name__}:{err_msg}"})
            print(f"  [{i+1}/{total}] FAIL (amt): {csv_midi} -> {type(e).__name__}")
            continue

        n_notes = len(notes)
        total_notes += n_notes
        total_floored += stats.get("min_dur_floored", 0)
        total_units += stats.get("n_units", 0)
        processed += 1

        label_rows.append({
            "midi_file": midi_file_id,
            "amt_text": amt_text,
            "split": split,
            "n_notes": n_notes,
        })

        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate
            print(f"  [{i+1}/{total}] processed={processed} fail={len(failures)} "
                  f"rate={rate:.1f} files/s eta={eta:.0f}s")

    zf.close()
    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s. {processed} processed, {len(failures)} failures.")

    # Write JSONL
    out_path = Path(out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for row in label_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(label_rows)} lines to {out_jsonl}")

    # Build report
    report = {
        "total_csv_entries": total,
        "processed": processed,
        "failures": len(failures),
        "split_distribution": split_counts,
        "total_notes": total_notes,
        "avg_notes_per_file": round(total_notes / processed, 1) if processed else 0,
        "total_min_dur_floored": total_floored,
        "total_amt_units": total_units,
        "elapsed_seconds": round(elapsed, 1),
        "failure_details": failures,
        "output_jsonl": str(out_path.resolve()),
        "output_lines": len(label_rows),
    }
    return report


if __name__ == "__main__":
    MIDI_ZIP = r"D:\vscode_projects\ee_download\maestro-v3.0.0-midi.zip"
    CSV_PATH = r"D:\vscode_projects\ee_download\maestro-v3.0.0.csv"
    OUT_JSONL = r"D:\vscode_projects\ee_download\work\maestro_amt_labels.jsonl"
    OUT_REPORT = r"D:\vscode_projects\ee_download\reports\s6_amt_labels.json"

    report = process_all(MIDI_ZIP, CSV_PATH, OUT_JSONL)

    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport written to {OUT_REPORT}")
    print(json.dumps({k: v for k, v in report.items() if k != "failure_details"}, indent=2))
