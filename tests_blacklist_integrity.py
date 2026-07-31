"""Evaluation-blacklist regression tests.

Runs without the large local datasets:
  python tests_blacklist_integrity.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from scripts.build_dataset import _pdmx_row_fn
from scripts.s3_filter_pdmx import (
    BEYER_TEST_FOLDERS,
    get_beyer_work_keys,
    get_nasap_test_works,
)


PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


print("[1] nASAP blacklist comes from the consumed split manifest")
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    split = {
        "test_works": ["bach|fugue", "mozart|sonata"],
        "n_test_works": 2,
    }
    (root / "nasap_split.json").write_text(
        json.dumps(split), encoding="utf-8")
    got = get_nasap_test_works(root)
    check("exact_nasap_test_works",
          got == ["bach|fugue", "mozart|sonata"], got)

    split["n_test_works"] = 3
    (root / "nasap_split.json").write_text(
        json.dumps(split), encoding="utf-8")
    try:
        get_nasap_test_works(root)
        mismatch_rejected = False
    except ValueError:
        mismatch_rejected = True
    check("declared_count_mismatch_rejected", mismatch_rejected)


print("[2] Beyer-Dai split is 14 works, not composer-name matching")
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    annotations = root / "asap_annotations.json"
    annotations.write_text("{}", encoding="utf-8")
    for folder in BEYER_TEST_FOLDERS:
        score = root / folder / "xml_score.musicxml"
        score.parent.mkdir(parents=True, exist_ok=True)
        score.write_text("<score-partwise/>", encoding="utf-8")
    got = get_beyer_work_keys(annotations)
    check("beyer_has_14_unique_works", len(got) == len(set(got)) == 14, got)
    check("beyer_not_fake_composer",
          all(not key.startswith("beyer|") for key in got), got)


print("[3] external-eval blacklist filters train only")
with tempfile.TemporaryDirectory() as td:
    manifest = Path(td) / "manifest.jsonl"
    rows = [
        {"piece_id": "train_leak", "split": "train",
         "work_key": "bach|fugue"},
        {"piece_id": "val_overlap", "split": "val",
         "work_key": "bach|fugue"},
        {"piece_id": "safe", "split": "train",
         "work_key": "other|piece"},
    ]
    manifest.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    row_fn = _pdmx_row_fn(
        manifest, blacklist={"bach|fugue"})
    check("train_overlap_filtered",
          row_fn({"utt_id": "a", "piece_id": "train_leak"}) is None)
    val = row_fn({"utt_id": "b", "piece_id": "val_overlap"})
    check("val_overlap_retained",
          val is not None and val["split"] == "val", val)
    safe = row_fn({"utt_id": "c", "piece_id": "safe"})
    check("safe_train_retained",
          safe is not None and safe["split"] == "train", safe)


print("[4] malformed manifest cannot silently become train")
with tempfile.TemporaryDirectory() as td:
    manifest = Path(td) / "bad.jsonl"
    manifest.write_text(
        json.dumps({"piece_id": "x", "split": None,
                    "work_key": "x|y"}) + "\n",
        encoding="utf-8")
    try:
        _pdmx_row_fn(manifest, blacklist={"x|y"})
        invalid_split_rejected = False
    except ValueError:
        invalid_split_rejected = True
    check("invalid_split_rejected", invalid_split_rejected)


print(f"\n全部通过: {PASS} 项")
