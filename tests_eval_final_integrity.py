"""正式终评范围/清单完整性回归。"""
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.eval_final import (
    PAPER_ASAP_BENCHMARK,
    official_omr_complete,
    performance_benchmark_status,
    validate_performance_pairs,
)


def test_official_omr_requires_full_original_scope():
    good = {"complete": True, "n_pairs": 2, "n_scores_parsed": 2,
            "omr_ned_mean": 64.3}
    assert official_omr_complete("test", 0, False, 2, 0, good)
    assert not official_omr_complete("test", 1, False, 2, 0, good)
    assert not official_omr_complete("val", 0, False, 2, 0, good)
    assert not official_omr_complete("test", 0, True, 2, 0, good)
    assert not official_omr_complete("test", 0, False, 2, 1, good)
    assert not official_omr_complete(
        "test", 0, False, 3, 0, good)  # LEGATO 批次完整，但原始清单少一首


def test_manifest_rejects_duplicates_wrong_split_and_missing_paths():
    with TemporaryDirectory() as td:
        root = Path(td)
        audio = root / "x.flac"
        ref = root / "x.musicxml"
        audio.write_bytes(b"x")
        ref.write_text("<score-partwise/>", encoding="utf-8")
        row = {"perf_id": "p0", "flac": str(audio), "ref_xml": str(ref),
               "split": "test"}
        validate_performance_pairs([row], expected_split="test")
        try:
            validate_performance_pairs([row, row], expected_split="test")
            raise AssertionError("duplicate perf_id was accepted")
        except ValueError as e:
            assert "duplicate perf_id" in str(e)
        bad = {**row, "perf_id": "p1", "split": "val",
               "flac": str(root / "missing.flac")}
        try:
            validate_performance_pairs([bad], expected_split="test")
            raise AssertionError("wrong split/missing file was accepted")
        except ValueError as e:
            assert "expected='test'" in str(e) and "missing.flac" in str(e)


def test_paper_scope_requires_explicit_identity_and_exact_102_rows():
    local = [{"perf_id": f"p{i}", "benchmark": "local_holdout",
              "benchmark_expected_count": 34} for i in range(34)]
    assert not performance_benchmark_status(local)["paper_exact"]
    unidentified = [{"perf_id": f"p{i}"} for i in range(102)]
    assert not performance_benchmark_status(unidentified)["paper_exact"]
    paper = [{"perf_id": f"p{i}", "benchmark": PAPER_ASAP_BENCHMARK,
              "benchmark_expected_count": 102} for i in range(102)]
    assert performance_benchmark_status(paper)["paper_exact"]
    assert not performance_benchmark_status(paper[:-1])["paper_exact"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print(f"全部通过: {len(tests)} 项")
