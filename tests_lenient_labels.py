"""
lenient_measures 回退(执行端 2b65f4d 接线,D60 追认)的判决性测试。

背景:ir_to_units/validate_units 的宽松模式是初始提交就有的休眠设计(D45 类),
执行端为 PDMX 华彩/超长小节接上了 make_labels 的回退,但没配测试 —— 本文件补上:
① 华彩 IR:严格模式必须报"长度"类 SerializeError,宽松模式必须出合法标签;
② make_labels 对华彩段走回退产出 A2S(不再整段丢弃);
③ 回退只对"长度"类错误开门 —— 其它 SerializeError 不得触发宽松重试(语义闸)。
"""
from __future__ import annotations

import sys
import time
from fractions import Fraction as F

from rubato.intermo.core import (
    Note, Measure, ScoreIR, SPitch, SerializeError,
    project, text_to_units, validate_units,
)
import rubato.data.segment as seg

# 华彩夹具:小节 0 实际跨 1/2,声明 1/4 —— 内部小节长度 != 声明,严格模式必炸
IR_CADENZA = ScoreIR(
    notes=[
        Note("PR", SPitch("C", 0, 4), F(0), F(1, 2)),
        Note("PR", SPitch("D", 0, 4), F(1, 2), F(1, 4)),
    ],
    measures=[Measure(F(0), 1, 4, 0), Measure(F(1, 2), 1, 4, 0)],
    score_end=F(3, 4),
)


def test_strict_raises_length_and_lenient_projects():
    try:
        project(IR_CADENZA, "A2S")
        raise AssertionError("严格模式对华彩小节应报 SerializeError")
    except SerializeError as e:
        assert "长度" in str(e), f"错误文本应是长度类(回退门依赖它): {e}"
    text = project(IR_CADENZA, "A2S", lenient_measures=True)
    assert text and "|" in text
    viol = validate_units(text_to_units(text), lenient_measures=True)
    assert viol == [], f"宽松模式产物必须仍过校验(Dyck/自洽不放松): {viol}"


def test_make_labels_falls_back_for_cadenza():
    labels, fails = seg.make_labels(IR_CADENZA, "flat")
    assert "A2S" in labels and "A2S_lite" in labels, (labels, fails)
    assert not any(f["dialect"] in ("A2S", "A2S_lite") for f in fails), fails


def test_fallback_gate_only_length_errors():
    calls = []
    orig = seg.project

    def fake_project(ir, d, *a, **k):
        calls.append(k.get("lenient_measures", False))
        raise SerializeError("布局折叠失败(与小节尺寸无关的另一类错)")

    try:
        seg.project = fake_project
        labels, fails = seg.make_labels(IR_CADENZA, "flat")
    finally:
        seg.project = orig
    assert labels == {}, "非长度错不得产出标签"
    assert True not in calls, "非长度类 SerializeError 触发了宽松重试 —— 语义闸失守"
    assert all("SerializeError" in f["reason"] for f in fails), fails


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        t0 = time.time()
        try:
            fn()
            print(f"  ok {fn.__name__} ({time.time()-t0:.1f}s)")
        except Exception as e:
            bad += 1
            import traceback
            print(f"  FAIL {fn.__name__}: {e}")
            traceback.print_exc(limit=4)
    print(("PASS" if not bad else "FAIL") + f" {len(fns)-bad}/{len(fns)}")
    sys.exit(1 if bad else 0)
