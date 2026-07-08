"""
Step 0a-fix: MinHash near-duplicate leakage defense (#14 real fix).

work_key string matching failed (0 removed) because ASAP folder names
(Bach/Fugue) ≠ PDMX metadata (johann sebastian bach|fugue c major).

Real defense: near_dup_ids via MinHash on (pitch, dur) n-grams —
content-based, naming-agnostic (R-S3.6).

Reference: EXECUTOR_CORRECTIONS.md §5b.
"""
from __future__ import annotations
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import warnings
warnings.filterwarnings("ignore")

import partitura
from rubato.intermo.partitura_adapter import part_to_ir
from rubato.data.pdmx import piece_signature, near_dup_ids

ROOT = Path(r"D:\vscode_projects\ee_download")
MANIFEST_IN = ROOT / "work" / "manifest_pieces.jsonl"
MANIFEST_OUT = ROOT / "work" / "manifest_pieces.jsonl"  # overwrite with cleaned
MANIFEST_LEAKED = ROOT / "work" / "manifest_leaked_minhash.jsonl"
ASAP_DATASET = ROOT / "asap-dataset" / "asap-dataset"
REPORT_OUT = ROOT / "reports" / "s3_minhash_leakage.json"


def find_asap_scores(asap_root: Path) -> list[Path]:
    """Find all xml_score.musicxml files in ASAP dataset (reference scores)."""
    scores = sorted(asap_root.glob("**/xml_score.musicxml"))
    print(f"  [INFO] Found {len(scores)} ASAP reference scores")
    return scores


def compute_ref_signatures(score_paths: list[Path]) -> list:
    """Parse ASAP scores → IR → MinHash signatures. Skip failures."""
    ref_sigs = []
    failed = 0
    for i, sp in enumerate(score_paths):
        try:
            score = partitura.load_musicxml(str(sp))
            part = score.parts[0] if hasattr(score, "parts") and score.parts else score
            ir = part_to_ir(part)
            ref_sigs.append(piece_signature(ir))
        except Exception:
            failed += 1
        if (i + 1) % 50 == 0:
            print(f"  [REF] {i+1}/{len(score_paths)} ({failed} failed)")
    print(f"  [REF] Done: {len(ref_sigs)} signatures ({failed} failed)")
    return ref_sigs


def process_pdmx_pieces(manifest: list[dict], ref_sigs: list) -> tuple[list[dict], set]:
    """
    Parse PDMX MXL files → IR → MinHash signature → check vs refs.
    Returns (cleaned_manifest, leaked_piece_ids).
    """
    target_sigs = {}
    failed = 0
    t0 = time.time()

    for i, p in enumerate(manifest):
        xml_path = p.get("xml_raw")
        if not xml_path:
            failed += 1
            continue
        try:
            # .mxl files use load_score (not load_musicxml)
            score = partitura.load_score(xml_path)
            # partitura may return a Part, PartGroup, or Score
            if hasattr(score, "parts") and score.parts:
                part = score.parts[0]
            elif hasattr(score, "notes"):
                part = score
            else:
                failed += 1
                continue
            ir = part_to_ir(part)
            target_sigs[p["piece_id"]] = piece_signature(ir)
        except Exception:
            failed += 1

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(manifest) - i - 1) / rate if rate > 0 else 0
            print(f"  [PDMX] {i+1}/{len(manifest)} sigs={len(target_sigs)} "
                  f"failed={failed} rate={rate:.1f}/s ETA={eta/60:.1f}m")

    elapsed = time.time() - t0
    print(f"  [PDMX] Done: {len(target_sigs)} signatures from {len(manifest)} "
          f"({failed} failed) in {elapsed/60:.1f}m")

    # Run near_dup_ids
    print(f"  [MINHASH] Checking {len(target_sigs)} targets vs {len(ref_sigs)} refs...")
    t1 = time.time()
    leaked = near_dup_ids(target_sigs, ref_sigs, threshold=0.7)
    print(f"  [MINHASH] Leaked: {len(leaked)} piece_ids in {time.time()-t1:.1f}s")

    cleaned = [p for p in manifest if p["piece_id"] not in leaked]
    return cleaned, leaked


def main():
    print("=" * 60)
    print("Step 0a-fix: MinHash Near-Duplicate Leakage Defense (#14)")
    print("=" * 60)

    # 1. Load manifest
    print("\n[1/4] Loading manifest...")
    manifest = []
    with open(MANIFEST_IN, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                manifest.append(json.loads(line))
    print(f"  Loaded {len(manifest)} pieces")

    # 2. Compute ASAP reference signatures
    print("\n[2/4] Computing ASAP reference signatures...")
    asap_scores = find_asap_scores(ASAP_DATASET)
    ref_sigs = compute_ref_signatures(asap_scores)

    if not ref_sigs:
        print("  [FAIL] No reference signatures — cannot compute leakage")
        return

    # 3. Process PDMX pieces and find near-duplicates
    print("\n[3/4] Processing PDMX pieces and checking vs references...")
    cleaned, leaked = process_pdmx_pieces(manifest, ref_sigs)

    # 4. Write cleaned manifest and report
    print(f"\n[4/4] Writing results...")
    with open(MANIFEST_OUT, 'w', encoding='utf-8') as f:
        for entry in cleaned:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    # Save leaked pieces for audit
    leaked_entries = [p for p in manifest if p["piece_id"] in leaked]
    with open(MANIFEST_LEAKED, 'w', encoding='utf-8') as f:
        for entry in leaked_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    splits_after = {"train": 0, "val": 0, "test": 0}
    for p in cleaned:
        splits_after[p["split"]] += 1

    report = {
        "stage": "S3-MinHash",
        "method": "near_dup_ids (Jaccard>0.7 on 8-gram (pitch,dur) sequences)",
        "ref_scores": len(asap_scores),
        "ref_signatures": len(ref_sigs),
        "target_pieces": len(manifest),
        "target_signatures": len(manifest) - sum(1 for p in manifest if p["piece_id"] not in
            {pp["piece_id"] for pp in cleaned}),
        "leaked_count": len(leaked),
        "leaked_piece_ids": sorted(leaked)[:50],
        "leaked_work_keys": [p["work_key"] for p in leaked_entries[:50]],
        "splits_after": splits_after,
        "acceptance": {
            "A-S3.6": "pass" if len(leaked) > 0 else "fail (0 removed — defense not working)",
        }
    }

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_OUT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"RESULT: {len(leaked)} pieces removed via MinHash near-duplicate detection")
    print(f"  Before: {len(manifest)} → After: {len(cleaned)}")
    print(f"  Splits: {splits_after}")
    print(f"  Leaked work_keys (sample): {report['leaked_work_keys'][:10]}")
    print(f"  A-S3.6: {'PASS' if report['acceptance']['A-S3.6'] == 'pass' else 'FAIL'}")
    print(f"  Report: {REPORT_OUT}")
    print(f"  Leaked manifest: {MANIFEST_LEAKED}")
    print(f"{'='*60}")

    return report


if __name__ == "__main__":
    main()
