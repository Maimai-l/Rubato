"""
S3 PDMX full filtering on real data — funnel statistics.

Reads metadata.csv (streaming csv.DictReader) and applies filters from
rubato/data/pdmx.py:
  - tier_a_star check  (tier_a_star == True)
  - quality_label check (high quality or score)
  - is_duplicate check
  - is_transcription check
  - license check (white-list prefixes)
  - work_key normalization (for reference)

Reports:
  - Standard funnel (all 5 filters)
  - Relaxed funnel (tier_a_star + quality + not_dup only, per SPEC notes)
  - Per-split & per-composer distributions
  - Data quality findings
"""
import csv
import json
import unicodedata
import re
import collections
from pathlib import Path

# ---------------------------------------------------------------- normalize (from pdmx.py)
_EDITION_WORDS = re.compile(
    r"\b(op|no|nr|op\.|no\.|k|kv|bwv|d|hob|woo|s|l|rv|version|arr|arranged|transcription)\b",
    re.IGNORECASE)

LICENSE_WHITELIST_PREFIXES = ("public domain", "publicdomain", "cc0", "cc-by", "cc by")


def normalize_work(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = _EDITION_WORDS.sub(" ", s)
    s = re.sub(r"\d+", " ", s)
    return " ".join(s.split())


def work_key(composer: str, title: str) -> str:
    return f"{normalize_work(composer)}|{normalize_work(title)}"


def license_ok(license_str: str) -> bool:
    s = (license_str or "").lower().strip()
    return any(s.startswith(p) for p in LICENSE_WHITELIST_PREFIXES)


# ---------------------------------------------------------------- Main
CSV_PATH = "D:/vscode_projects/ee_download/PDMX/metadata.csv"

# Individual criterion pass counts (non-cumulative, independent)
count_total = 0
count_tier_a_star = 0
count_quality_high = 0
count_not_dup = 0
count_not_trans = 0
count_lic_ok = 0

# Cumulative funnel — strict (5-stage)
c_tier = 0
c_quality = 0
c_dup = 0
c_trans = 0
c_license = 0
final_strict = 0

# Cumulative funnel — relaxed (3-stage: tier + quality + not_dup)
r_tier = 0
r_quality = 0
r_dup = 0
final_relaxed = 0

# Drop tracking
drop_reasons = collections.Counter()

# Per-split and per-composer for final survivors
strict_split = collections.Counter()
strict_composer = collections.Counter()
relaxed_split = collections.Counter()
relaxed_composer = collections.Counter()

# Distributions
license_dist = collections.Counter()
quality_label_dist = collections.Counter()
tier_a_star_dist = collections.Counter()
tier_a_dist = collections.Counter()
tier_b_dist = collections.Counter()
is_dup_dist = collections.Counter()
is_trans_dist = collections.Counter()
split_dist_all = collections.Counter()

print("Scanning PDMX metadata.csv ...")
with open(CSV_PATH, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        count_total += 1

        # Extract values
        tier_star = str(row.get("tier_a_star", "")).strip().lower()
        tier_a    = str(row.get("tier_a", "")).strip().lower()
        tier_b    = str(row.get("tier_b", "")).strip().lower()
        ql        = str(row.get("quality_label", "")).strip().lower()
        dup       = str(row.get("is_duplicate", "")).strip().lower()
        trans     = str(row.get("is_transcription", "")).strip().lower()
        lic       = str(row.get("license", "")).strip()
        spl       = str(row.get("split", "")).strip()
        composer  = str(row.get("composer", "")).strip()

        # Track distributions
        tier_a_star_dist[tier_star] += 1
        tier_a_dist[tier_a] += 1
        tier_b_dist[tier_b] += 1
        quality_label_dist[ql] += 1
        is_dup_dist[dup] += 1
        is_trans_dist[trans] += 1
        split_dist_all[spl] += 1
        lic_short = lic[:40] if lic else "(empty)"
        license_dist[lic_short] += 1

        # 1) Independent criterion counts
        if tier_star in ("true", "1", "yes"):
            count_tier_a_star += 1
        if ql in ("high quality", "score"):
            count_quality_high += 1
        if dup not in ("true", "1", "yes"):
            count_not_dup += 1
        if trans not in ("true", "1", "yes"):
            count_not_trans += 1
        if license_ok(lic):
            count_lic_ok += 1

        # 2) Strict cumulative funnel (5 stages)
        if tier_star not in ("true", "1", "yes"):
            drop_reasons["tier_a_star_not_True"] += 1
        else:
            c_tier += 1
            if ql not in ("high quality", "score"):
                drop_reasons["quality_label_not_high_quality_or_score"] += 1
            else:
                c_quality += 1
                if dup in ("true", "1", "yes"):
                    drop_reasons["is_duplicate"] += 1
                else:
                    c_dup += 1
                    if trans in ("true", "1", "yes"):
                        drop_reasons["is_transcription"] += 1
                    else:
                        c_trans += 1
                        if not license_ok(lic):
                            drop_reasons["license_not_whitelisted"] += 1
                        else:
                            c_license += 1
                            final_strict += 1
                            strict_split[spl] += 1
                            strict_composer[composer] += 1

        # 3) Relaxed cumulative funnel (3 stages: tier + quality + not_dup)
        if tier_star in ("true", "1", "yes"):
            r_tier += 1
            if ql in ("high quality", "score"):
                r_quality += 1
                if dup not in ("true", "1", "yes"):
                    r_dup += 1
                    final_relaxed += 1
                    relaxed_split[spl] += 1
                    relaxed_composer[composer] += 1

# Top 20 composers (relaxed)
relaxed_top20 = relaxed_composer.most_common(20)
strict_top20 = strict_composer.most_common(20)

# Build report
report = {
    "stage": "S3",
    "description": "PDMX metadata filter funnel on real data",
    "csv_path": CSV_PATH,
    "csv_total_rows": count_total,
    "csv_columns": ["id","composer","composition","movement","performance_id","split","tier_b","tier_a","tier_a_star","score_dataset","score_id","score_xml_path","score_midi_path","score_note_count","score_duration","performance_dataset","performance_midi_path","performance_note_count","performance_duration","performer","is_transcription","capture_model","raw_alignment_path","raw_recall","raw_precision","raw_adjusted_alignment_ratio","is_duplicate","lead_performance","quality_label","prob_score","prob_high_quality","prob_low_quality","prob_corrupted","is_refined","refined_score_midi_path","refined_score_note_count","refined_score_duration","refined_performance_midi_path","refined_performance_note_count","refined_performance_interpolated_note_count","refined_performance_duration","refined_alignment_path","refined_recall"],

    # Strict funnel (all 5 filters from pdmx.py metadata_filter + tier/quality enhancement)
    "strict_funnel": {
        "description": "All filters: tier_a_star=True + quality_label in (high quality|score) + not is_duplicate + not is_transcription + license_ok",
        "total_pieces": count_total,
        "after_tier_a_star": c_tier,
        "after_quality_label": c_quality,
        "after_is_duplicate": c_dup,
        "after_is_transcription": c_trans,
        "after_license": c_license,
        "final_kept": final_strict,
        "retention_rate_pct": round(final_strict / count_total * 100, 4) if count_total else 0,
    },

    # Relaxed funnel (tier + quality + not_dup, relaxing is_transcription & license per SPEC)
    "relaxed_funnel": {
        "description": "Relaxed filters: tier_a_star=True + quality_label in (high quality|score) + not is_duplicate (is_transcription and license relaxed per SPEC.md notes)",
        "total_pieces": count_total,
        "after_tier_a_star": r_tier,
        "after_quality_label": r_quality,
        "after_is_duplicate_and_final": r_dup,
        "final_kept": final_relaxed,
        "retention_rate_pct": round(final_relaxed / count_total * 100, 2) if count_total else 0,
    },

    # Independent pass rates (each criterion measured on full dataset independently)
    "independent_pass_counts": {
        "tier_a_star_True": count_tier_a_star,
        "tier_a_star_True_pct": round(count_tier_a_star / count_total * 100, 2),
        "quality_label_high_quality_or_score": count_quality_high,
        "quality_label_high_quality_or_score_pct": round(count_quality_high / count_total * 100, 2),
        "is_duplicate_False": count_not_dup,
        "is_duplicate_False_pct": round(count_not_dup / count_total * 100, 2),
        "is_transcription_False": count_not_trans,
        "is_transcription_False_pct": round(count_not_trans / count_total * 100, 2),
        "license_ok": count_lic_ok,
        "license_ok_pct": round(count_lic_ok / count_total * 100, 2),
    },

    # Drop reasons for strict funnel
    "strict_drop_reasons": {
        k: {"count": v, "pct": round(v / count_total * 100, 2)}
        for k, v in drop_reasons.most_common()
    },

    # Column distributions
    "column_distributions": {
        "tier_a_star": dict(tier_a_star_dist.most_common()),
        "tier_a": dict(tier_a_dist.most_common()),
        "tier_b": dict(tier_b_dist.most_common()),
        "quality_label": dict(quality_label_dist.most_common()),
        "is_duplicate": dict(is_dup_dist.most_common()),
        "is_transcription": dict(is_trans_dist.most_common()),
        "split_all": dict(split_dist_all.most_common()),
        "license": dict(license_dist.most_common(10)),
    },

    # Split distribution (relaxed)
    "relaxed_split_distribution": {
        k: {"count": v, "pct": round(v / final_relaxed * 100, 2)}
        for k, v in relaxed_split.most_common()
    } if final_relaxed else {},

    # Top 20 composers (relaxed)
    "relaxed_top_20_composers": [
        {"composer": c.replace(",_", ", "), "count": n}
        for c, n in relaxed_top20
    ],

    # Key findings
    "findings": {
        "total_pdmx_pieces": count_total,
        "estimated_user_expected": 254035,
        "note_on_count_discrepancy": "User estimated 254,035; actual CSV has 250,046 rows (250,047 lines including header). Exact count confirmed by line count.",
        "data_quality_issues": [
            {
                "issue": "License field completely empty",
                "detail": "ALL 250,046 rows have empty license field (''). license_ok() returns False for every row, making the license filter a hard block.",
                "impact": "0 survivors under strict filtering. Blocking license stage.",
                "spec_reference": "SPEC.md R-S3.2: '训练可放宽' (can be relaxed for training).",
                "recommendation": "Relax license check for training data (as SPEC permits). For redistribution, need to determine actual license from PDMX Zenodo documentation."
            },
            {
                "issue": "99.57% rows are transcriptions",
                "detail": "248,980 of 250,046 rows have is_transcription=True. Only 1,066 (0.43%) are non-transcriptions.",
                "impact": "is_transcription filter removes 129,384 of the 130,275 tier_a_star=True candidates.",
                "spec_reference": "pdmx.py comment: '可按需放宽' (can be relaxed as needed). PDMX is primarily an alignment dataset of performance transcriptions.",
                "recommendation": "Relax is_transcription filter to retain PDMX pieces. These are the core PDMX data."
            },
            {
                "issue": "tier_a_star=True all pass quality_label and is_duplicate checks",
                "detail": "All 130,275 tier_a_star=True rows also have quality_label in ('high quality','score') AND is_duplicate=False. These three filters are perfectly correlated for tier_a_star pieces.",
                "impact": "The quality_label and is_duplicate filters don't further reduce the pool after tier_a_star.",
                "recommendation": "Consider whether tier_a_star alone is sufficient, or if combining tier_a_star = True with tier conditions produces a meaningful multi-tier pool."
            },
            {
                "issue": "No val split in PDMX",
                "detail": "PDMX only has 'train' (225,000) and 'test' (25,046) splits. No 'val' split exists.",
                "impact": "Validation set must be carved from train split or obtained from a different source.",
                "recommendation": "For S3 pipeline, hold out a subset of train as val (e.g., 5% by work_key stratification)."
            },
            {
                "issue": "Encoding issues in composer names",
                "detail": "Some composer names contain mojibake/encoding artifacts (e.g., 'Fr��d��ric', 'Alb��niz') due to ASCII normalization stripping diacritics.",
                "impact": "work_key normalization handles this (NFKD -> ASCII), but original metadata may need encoding verification.",
                "recommendation": "Verify the encoding of the CSV file. Current approach uses utf-8 which appears to read correctly but normalization drops non-ASCII characters."
            }
        ],
        "relaxed_pool_summary": {
            "total_available_if_filters_relaxed": final_relaxed,
            "pct_of_total": round(final_relaxed / count_total * 100, 2),
            "train_split": relaxed_split.get("train", 0),
            "test_split": relaxed_split.get("test", 0),
            "target_pool_size_per_spec": "12,000-20,000 pieces (R-S3.4)",
            "note": "130,275 pieces exceeds target pool of 12K-20K. After work_key dedup and random subsampling (as spec allows), target pool size is achievable.",
            "exceeds_target_by": round(final_relaxed / 20000, 1)
        }
    },

    "notes": [
        "ALL 250,046 rows have empty license field — license_ok returns False for all.",
        "99.57% of rows have is_transcription=True (transcriptions filtered out by default).",
        "PDMX is primarily an alignment dataset; most entries are transcriptions of performances.",
        "tier_a_star=True + quality_label in (high quality, score) + is_duplicate=False yields 130,275 survivors.",
        "Adding is_transcription=False reduces to 891 survivors (0.36%).",
        "Adding license_ok reduces to 0 survivors.",
        "SPEC.md R-S3.2 notes license can be relaxed for training ('训练可放宽').",
        "pdmx.py comment suggests is_transcription can be relaxed ('可按需放宽').",
        "Relaxing both gives 130,275 pieces (52.10% of PDMX), well above the 12-20K target.",
    ],
}

# Write report
reports_dir = Path("D:/vscode_projects/ee_download/reports")
reports_dir.mkdir(parents=True, exist_ok=True)
report_path = reports_dir / "s3_full_filter.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("\n" + "=" * 72)
print("S3 PDMX FULL FILTER REPORT")
print("=" * 72)

print(f"\n{'Total pieces in PDMX metadata:':45s} {count_total:>10,}")
print(f"\n--- Independent pass counts (each criterion on full dataset) ---")
print(f"  tier_a_star == True:               {count_tier_a_star:>10,}  ({count_tier_a_star/count_total*100:6.2f}%)")
print(f"  quality_label (high|score):        {count_quality_high:>10,}  ({count_quality_high/count_total*100:6.2f}%)")
print(f"  is_duplicate == False:             {count_not_dup:>10,}  ({count_not_dup/count_total*100:6.2f}%)")
print(f"  is_transcription == False:         {count_not_trans:>10,}  ({count_not_trans/count_total*100:6.2f}%)")
print(f"  license_ok:                        {count_lic_ok:>10,}  ({count_lic_ok/count_total*100:6.2f}%)")

print(f"\n--- Strict cumulative funnel (5 filters: tier + quality + dup + trans + license) ---")
print(f"  total:                             {count_total:>10,}  (100.00%)")
print(f"  after tier_a_star:                 {c_tier:>10,}  ({c_tier/count_total*100:6.2f}%)")
print(f"  after quality_label:               {c_quality:>10,}  ({c_quality/count_total*100:6.2f}%)")
print(f"  after is_duplicate:                {c_dup:>10,}  ({c_dup/count_total*100:6.2f}%)")
print(f"  after is_transcription:            {c_trans:>10,}  ({c_trans/count_total*100:6.2f}%)")
print(f"  after license:                     {c_license:>10,}  ({c_license/count_total*100:6.2f}%)")
print(f"  FINAL KEPT (strict):               {final_strict:>10,}  ({final_strict/count_total*100:6.2f}%)")

print(f"\n--- Relaxed cumulative funnel (3 filters: tier + quality + dup) ---")
print(f"  total:                             {count_total:>10,}  (100.00%)")
print(f"  after tier_a_star:                 {r_tier:>10,}  ({r_tier/count_total*100:6.2f}%)")
print(f"  after quality_label:               {r_quality:>10,}  ({r_quality/count_total*100:6.2f}%)")
print(f"  after is_duplicate (final):        {r_dup:>10,}  ({r_dup/count_total*100:6.2f}%)")
print(f"  FINAL KEPT (relaxed):              {final_relaxed:>10,}  ({final_relaxed/count_total*100:6.2f}%)")

print(f"\n--- Drop reasons (strict funnel, first reason per row) ---")
for reason, cnt in drop_reasons.most_common():
    print(f"  {reason:50s}: {cnt:>10,}  ({cnt/count_total*100:6.2f}%)")

print(f"\n--- Relaxed split distribution ---")
if final_relaxed:
    for s, c in relaxed_split.most_common():
        print(f"  {s:10s}: {c:>8,}  ({c/final_relaxed*100:5.2f}%)")

print(f"\n--- Relaxed top 20 composers ---")
for i, (c, n) in enumerate(relaxed_top20, 1):
    name = c.replace(",_", ", ")
    print(f"  {i:2d}. {name:45s} {n:>8,}")

print(f"\n--- Key findings ---")
for issue in report["findings"]["data_quality_issues"]:
    print(f"  [{issue['issue']}]")
    print(f"    Detail: {issue['detail'][:100]}...")
    print(f"    Impact: {issue['impact']}")
    print(f"    Recommendation: {issue['recommendation']}")

print(f"\nReport written to: {report_path}")
