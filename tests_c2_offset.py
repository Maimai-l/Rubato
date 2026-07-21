"""
C2 偏移窗(shift_events + 切窗机组合)的判决性测试(EXPERIMENT_ACOUSTIC)。
钉死四件事:事件平移语义、踏板保持状态带入、窗坐标回写、与原窗系确实错开。
"""
import time

from rubato.data.segment import segment_amt, shift_events


def _mknotes(onsets, dur=0.5, pitch=60, vel=64):
    return [{"pitch": pitch + i % 12, "on": float(t), "off": float(t) + dur, "vel": vel}
            for i, t in enumerate(onsets)]


def test_shift_drops_and_shifts():
    notes = _mknotes([0.0, 5.0, 9.9, 10.0, 15.0, 30.0])
    pedal = [(2.0, True), (12.0, False), (20.0, True)]
    n2, p2 = shift_events(notes, pedal, 10.0)
    assert [round(n["on"], 3) for n in n2] == [0.0, 5.0, 20.0]   # <10s 的三个丢弃
    assert all(n["off"] - n["on"] == 0.5 for n in n2)            # 时值不变
    # 踏板:offset=10 时刻状态 = 踩下(2.0 True 且 12.0 才抬)→ 合成 t=0 初始事件
    assert p2[0] == (0.0, True)
    assert (2.0, False) in p2 and (10.0, True) in p2             # 12s/20s 事件平移到 2s/10s


def test_shift_pedal_state_up():
    notes = _mknotes([11.0])
    n2, p2 = shift_events(notes, [(2.0, True), (8.0, False)], 10.0)
    assert p2[0] == (0.0, False)                                 # 10s 时刻已抬起


def test_shift_zero_is_identity():
    notes = _mknotes([1.0, 2.0])
    pedal = [(0.5, True)]
    n2, p2 = shift_events(notes, pedal, 0.0)
    assert n2 == notes and p2 == pedal


def test_offset_windows_interleave_and_map_back():
    # 60s 均匀音流:原窗系从 0 起,偏移窗系从 10 起 —— 回写坐标后两组窗界应互不重合
    notes = _mknotes([i * 0.5 for i in range(120)])
    pedal: list = []
    base = segment_amt(notes, pedal, target_lo=12.0, target_hi=25.0)
    n2, p2 = shift_events(notes, pedal, 10.0)
    off = segment_amt(n2, p2, target_lo=12.0, target_hi=25.0)
    assert base and off
    base_cuts = {round(t0, 2) for _n, _p, (t0, _t1) in base}
    off_cuts = {round(t0 + 10.0, 2) for _n, _p, (t0, _t1) in off}   # 回写 = +offset
    assert off_cuts and base_cuts
    assert 0.0 in base_cuts and 10.0 in off_cuts
    # 错开性:偏移窗起点不与原窗起点全同(哪怕部分撞上,至少首窗错开 10s)
    assert off_cuts != base_cuts
    # 窗内事件是相对时间且非空
    for wn, _wp, (t0, t1) in off:
        assert wn and all(0 <= n["on"] < (t1 - t0) + 1e-6 for n in wn)


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
