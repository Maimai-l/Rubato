"""
C3 音色副本纯逻辑的判决性测试:选曲确定性/train-only、第二源绝不重复、行变换、_s2 命名兼容。
(渲染本体走 s4 同一 render_midi_to_wav44/finalize,沙盒无渲染引擎,不在此测。)
"""
import tempfile
import time
from pathlib import Path

from scripts.c3_timbre_copies import choose_second, pick_subset, transform_rows

SCFG = {"sources": {"S1": {"ratio": 0.4}, "S2": {"ratio": 0.3},
                    "S3": {"ratio": 0.2}, "S4": {"ratio": 0.1}}}
PCFG = {"seed": 7, "weights": {"p1": 0.5, "p2": 0.3, "p3": 0.2},
        "presets": {"p1": {}, "p2": {}, "p3": {}}}


def test_pick_subset_train_only_and_deterministic():
    rows = {
        "a": [{"split": "train"}, {"split": "train"}],
        "b": [{"split": "train"}, {"split": "val"}],      # 混入 val → 整曲出局
        "c": [{}],                                        # 缺 split = train
        "d": [{"split": "test"}],
        "e": [{"split": "train"}],
    }
    got = pick_subset(rows, 10)
    assert set(got) == {"a", "c", "e"}
    assert got == pick_subset(rows, 10)                   # 确定性
    assert len(pick_subset(rows, 2)) == 2                 # n 截断


def test_choose_second_never_original_and_deterministic():
    from rubato.render.core import assign_source_and_preset
    for pid in (f"p{i}" for i in range(60)):
        orig, src2, preset2 = choose_second(pid, SCFG, PCFG)
        orig2 = assign_source_and_preset(f"pdmx_{pid}", SCFG, PCFG)[0]
        assert orig == orig2
        assert src2 != orig, f"{pid}: 第二源撞回原源 {src2}"
        assert src2 in SCFG["sources"] and preset2 in PCFG["weights"]
        assert (orig, src2, preset2) == choose_second(pid, SCFG, PCFG)   # 确定性


def test_transform_rows_suffix_and_preserve():
    rows = [{"utt_id": "pdmx_X_000", "split": "train", "A2S": "|4/4k0", "score_range": [0, 4]}]
    out = transform_rows(rows)
    assert out[0]["utt_id"] == "pdmx_X_000_s2"
    assert out[0]["A2S"] == "|4/4k0" and out[0]["score_range"] == [0, 4]
    assert rows[0]["utt_id"] == "pdmx_X_000"              # 原行不动


def test_s2_whole_naming_compatible_with_slicer():
    from scripts.s4_slice_segments import _find_whole
    tmp = Path(tempfile.mkdtemp(prefix="c3_"))
    (tmp / "pdmx_ABC_s2.opus").write_bytes(b"x")
    assert _find_whole(tmp, "ABC_s2") is not None          # pid 传 "{pid}_s2" 即命中
    assert _find_whole(tmp, "ABC") is None                 # 不污染原名空间


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            t0 = time.time()
            try:
                fn()
                print(f"  ok {name} ({time.time() - t0:.1f}s)")
            except Exception as e:
                fails += 1
                print(f"  FAIL {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if fails else 0)
