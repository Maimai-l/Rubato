#!/usr/bin/env python3
"""Audit records excluded by PDMX's upstream ``subset:deduplicated`` flag.

This is deliberately read-only with respect to the dataset and the training
manifest.  It compares every dropped record to the CSV row named by its
``best_path`` and writes an evidence report plus a JSONL list of records whose
pair is not actually identical by the checks below.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

try:
    from rubato.platform import harden_stdout

    harden_stdout()
except Exception:
    pass


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT.parent
DEFAULT_CSV = DATA_ROOT / "PDMX" / "PDMX" / "PDMX.csv"
DEFAULT_REPORT = ROOT / "reports" / "PDMX_DEDUP_AUDIT.md"
DEFAULT_CANDIDATES = DATA_ROOT / "work" / "pdmx_dedup_restore_candidates.jsonl"

METADATA_FIELDS = (
    "n_notes",
    "song_length",
    "song_length.seconds",
    "song_length.bars",
    "n_tracks",
)


@dataclass(frozen=True)
class MidiSignature:
    raw_sha256: str
    note_sha256: str
    note_count: int
    end_beat: str
    dangling_note_ons: int


def clean(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    return clean(value).lower() == "true"


def shown(row: dict[str, str]) -> str:
    composer = clean(row.get("composer_name"))
    title = clean(row.get("song_name")) or clean(row.get("title"))
    return f"{title or '(untitled)'}" + (f" — {composer}" if composer else "")

def resolve_mid(row: dict[str, str], pdmx_root: Path) -> Path:
    raw = clean(row.get("mid"))
    return pdmx_root / raw.lstrip("./\\").replace("/", "\\")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def midi_signature(path: Path) -> MidiSignature:
    """Hash musical note events independent of track layout, velocity, and MIDI bytes."""
    import mido

    raw = file_sha256(path)
    midi = mido.MidiFile(path)
    ticks_per_beat = midi.ticks_per_beat
    notes: list[tuple[int, int, int, int, int]] = []
    dangling = 0

    for track in midi.tracks:
        absolute = 0
        active: defaultdict[tuple[int, int], list[int]] = defaultdict(list)
        for message in track:
            absolute += message.time
            if message.type == "note_on" and message.velocity > 0:
                active[(message.channel, message.note)].append(absolute)
            elif message.type == "note_off" or (
                message.type == "note_on" and message.velocity == 0
            ):
                key = (message.channel, message.note)
                if active[key]:
                    start = active[key].pop(0)
                    # The channel is intentionally omitted: it is arrangement,
                    # not pitch/rhythm content, for this identity check.
                    start_beat = Fraction(start, ticks_per_beat)
                    duration_beat = Fraction(absolute - start, ticks_per_beat)
                    notes.append(
                        (
                            message.note,
                            start_beat.numerator,
                            start_beat.denominator,
                            duration_beat.numerator,
                            duration_beat.denominator,
                        )
                    )
        dangling += sum(len(starts) for starts in active.values())

    notes.sort()
    encoded = "\n".join(
        f"{pitch}:{start_num}/{start_den}:{dur_num}/{dur_den}"
        for pitch, start_num, start_den, dur_num, dur_den in notes
    ).encode("ascii")
    note_hash = hashlib.sha256(encoded).hexdigest()
    max_end = Fraction(0, 1)
    for pitch, start_num, start_den, dur_num, dur_den in notes:
        max_end = max(
            max_end,
            Fraction(start_num, start_den) + Fraction(dur_num, dur_den),
        )
    return MidiSignature(
        raw_sha256=raw,
        note_sha256=note_hash,
        note_count=len(notes),
        end_beat=f"{max_end.numerator}/{max_end.denominator}",
        dangling_note_ons=dangling,
    )


def comparable_metadata(left: dict[str, str], right: dict[str, str]) -> list[str]:
    return [field for field in METADATA_FIELDS if clean(left.get(field)) != clean(right.get(field))]


def sample_dict(
    source: dict[str, str], target: dict[str, str], category: str, differing: list[str]
) -> dict[str, Any]:
    return {
        "category": category,
        "source_path": clean(source.get("path")),
        "source_mid": clean(source.get("mid")),
        "source_title": shown(source),
        "best_path": clean(target.get("path")),
        "best_mid": clean(target.get("mid")),
        "best_title": shown(target),
        "different_metadata_fields": differing,
        "source_metadata": {field: clean(source.get(field)) for field in METADATA_FIELDS},
        "best_metadata": {field: clean(target.get(field)) for field in METADATA_FIELDS},
    }


def format_sample(sample: dict[str, Any]) -> list[str]:
    lines = [
        f"- `{sample['category']}`: **{sample['source_title']}** → **{sample['best_title']}**",
        f"  - source: `{sample['source_path']}`; best_path: `{sample['best_path']}`",
    ]
    if sample["different_metadata_fields"]:
        lines.append("  - differs: " + ", ".join(f"`{x}`" for x in sample["different_metadata_fields"]))
        for field in sample["different_metadata_fields"]:
            lines.append(
                f"    - `{field}`: {sample['source_metadata'][field]!r} vs {sample['best_metadata'][field]!r}"
            )
    if "midi_comparison" in sample:
        lines.append("  - MIDI: " + sample["midi_comparison"])
    return lines


def write_report(
    report: Path,
    total_rows: int,
    all_valid: int,
    dedup_kept: int,
    dedup_dropped: int,
    counts: Counter[str],
    examples: dict[str, list[dict[str, Any]]],
) -> None:
    metadata_bad = counts["metadata_inconsistent"]
    candidate_total = metadata_bad + counts["semantic_different"]
    lines = [
        "# PDMX upstream deduplication audit",
        "",
        "Generated by `scripts/audit_pdmx_dedup.py`. This is an evidence-only audit: it does **not** change the PDMX filter, generated manifests, or any training pool.",
        "",
        "## Scope and method",
        "",
        f"- CSV rows: **{total_rows:,}**",
        f"- `subset:all_valid=true`: **{all_valid:,}**",
        f"- upstream `subset:deduplicated=true`: **{dedup_kept:,}**",
        f"- upstream `subset:deduplicated!=true` audited: **{dedup_dropped:,}**",
        "- Each dropped row is compared with the CSV row at its `best_path`.",
        "- First pass checks note count, symbolic length, seconds, bars, and track count. A mismatch in any of those fields means the pair cannot be an identical MIDI file.",
        "- For pairs whose five fields all agree, the audit compares raw MIDI SHA-256 and a content hash of sorted `(pitch, onset in beats, duration in beats)` events. The latter intentionally ignores MIDI byte layout, track layout, channel, velocity, and metadata.",
        "",
        "## Result",
        "",
        f"- **{metadata_bad:,} / {dedup_dropped:,} ({metadata_bad / dedup_dropped:.2%})** have a metadata mismatch with their declared `best_path`. These are strong false-dedup candidates; they were excluded upstream but are not identical under PDMX's own basic music statistics.",
        f"- **{counts['metadata_equal']:,} / {dedup_dropped:,} ({counts['metadata_equal'] / dedup_dropped:.2%})** have all five fields equal and received MIDI-level comparison.",
        f"  - byte-identical: **{counts['byte_identical']:,}**",
        f"  - same note-event content but different MIDI bytes: **{counts['semantic_equal_nonbyte']:,}**",
        f"  - different note-event content: **{counts['semantic_different']:,}**",
        f"  - unavailable / parse error: **{counts['midi_unavailable']:,}**",
        f"- Total candidates that are demonstrably non-identical by this audit: **{candidate_total:,}**. This number is a review/restoration candidate count, not an instruction to reintroduce them automatically.",
        "",
        "## Examples: metadata-inconsistent pairs",
        "",
    ]
    for sample in examples.get("metadata_inconsistent", []):
        lines.extend(format_sample(sample))
    lines.extend(["", "## Examples: MIDI-level residual pairs", ""])
    residual = []
    for category in ("byte_identical", "semantic_equal_nonbyte", "semantic_different", "midi_unavailable"):
        residual.extend(examples.get(category, []))
    if residual:
        for sample in residual:
            lines.extend(format_sample(sample))
    else:
        lines.append("No metadata-equal residual pairs were available for a sample.")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The upstream flag is not a safe proxy for strict duplicate removal: most dropped rows point at `best_path` rows with obviously different basic musical statistics. Before changing the production filter, review the candidate JSONL and decide on a replacement deduplication policy (for example, only exclude exact content duplicates, or keep all valid PDMX records with a group-aware split policy).",
            "",
        ]
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--candidate-out", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--limit", type=int, help="Audit only the first N dropped rows (smoke test only).")
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()

    if not args.csv.is_file():
        raise SystemExit(f"PDMX CSV not found: {args.csv}")
    pdmx_root = args.csv.parent
    with args.csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_path = {clean(row.get("path")): row for row in rows if clean(row.get("path"))}
    all_valid_rows = [row for row in rows if truthy(row.get("subset:all_valid"))]
    dropped = [row for row in all_valid_rows if not truthy(row.get("subset:deduplicated"))]
    if args.limit is not None:
        dropped = dropped[: args.limit]

    counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    candidates: list[dict[str, Any]] = []
    signature_cache: dict[Path, MidiSignature | Exception] = {}

    def remember(category: str, item: dict[str, Any]) -> None:
        if len(examples[category]) < args.samples:
            examples[category].append(item)

    def signature_for(row: dict[str, str]) -> MidiSignature:
        path = resolve_mid(row, pdmx_root)
        cached = signature_cache.get(path)
        if cached is None:
            if not path.is_file():
                cached = FileNotFoundError(str(path))
            else:
                try:
                    cached = midi_signature(path)
                except Exception as exc:  # Retain per-file failure and continue the audit.
                    cached = exc
            signature_cache[path] = cached
        if isinstance(cached, Exception):
            raise cached
        return cached

    print(f"[INFO] CSV rows={len(rows):,}; all_valid={len(all_valid_rows):,}; dropped to audit={len(dropped):,}")
    for index, source in enumerate(dropped, start=1):
        target = by_path.get(clean(source.get("best_path")))
        if target is None:
            counts["best_path_missing"] += 1
            item = sample_dict(source, {}, "best_path_missing", [])
            item["reason"] = "best_path is not present in PDMX.csv"
            candidates.append(item)
            remember("best_path_missing", item)
            continue

        differing = comparable_metadata(source, target)
        if differing:
            counts["metadata_inconsistent"] += 1
            item = sample_dict(source, target, "metadata_inconsistent", differing)
            candidates.append(item)
            remember("metadata_inconsistent", item)
            continue

        counts["metadata_equal"] += 1
        item = sample_dict(source, target, "metadata_equal", [])
        try:
            source_sig = signature_for(source)
            target_sig = signature_for(target)
            item["source_midi_signature"] = asdict(source_sig)
            item["best_midi_signature"] = asdict(target_sig)
            if source_sig.raw_sha256 == target_sig.raw_sha256:
                category = "byte_identical"
                item["midi_comparison"] = "raw MIDI SHA-256 equal"
            elif source_sig.note_sha256 == target_sig.note_sha256:
                category = "semantic_equal_nonbyte"
                item["midi_comparison"] = "raw bytes differ; normalized pitch/onset/duration events equal"
            else:
                category = "semantic_different"
                item["midi_comparison"] = "normalized pitch/onset/duration events differ"
                candidates.append(item)
            # The initial sample is constructed before the MIDI comparison;
            # persist the final category in JSONL so downstream restoration
            # consumes semantic_different rather than the provisional label.
            item["category"] = category
            counts[category] += 1
            remember(category, item)
        except Exception as exc:
            counts["midi_unavailable"] += 1
            item["category"] = "midi_unavailable"
            item["midi_comparison"] = f"unavailable: {type(exc).__name__}: {exc}"
            candidates.append(item)
            remember("midi_unavailable", item)

        if index % 200 == 0:
            print(f"[INFO] processed {index:,}/{len(dropped):,}; metadata_equal={counts['metadata_equal']:,}")

    args.candidate_out.parent.mkdir(parents=True, exist_ok=True)
    with args.candidate_out.open("w", encoding="utf-8", newline="") as handle:
        for item in candidates:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

    dedup_kept = sum(truthy(row.get("subset:deduplicated")) for row in all_valid_rows)
    write_report(
        args.report,
        total_rows=len(rows),
        all_valid=len(all_valid_rows),
        dedup_kept=dedup_kept,
        dedup_dropped=len(dropped),
        counts=counts,
        examples=examples,
    )
    print(
        "DONE: "
        + " ".join(
            f"{key}={counts[key]:,}"
            for key in (
                "metadata_inconsistent",
                "metadata_equal",
                "byte_identical",
                "semantic_equal_nonbyte",
                "semantic_different",
                "midi_unavailable",
                "best_path_missing",
            )
        )
    )
    print(f"[INFO] report={args.report}")
    print(f"[INFO] candidates={args.candidate_out} rows={len(candidates):,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
