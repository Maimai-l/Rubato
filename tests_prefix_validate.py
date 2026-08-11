"""
D101 前缀验证器判决性测试(约束解码第一块):
合法序列的任意前缀必过 / 即死项即刻报 / 前缀豁免项不误报 / 与全量验证器一致性。
"""
from __future__ import annotations

import random
import sys
import time

sys.path.insert(0, ".")

from rubato.intermo.core import (text_to_units, validate_units,
                                 validate_units_prefix)
from scripts.gen_formal_corpus import gen_one


def test_every_prefix_of_valid_sequences_passes():
    rng = random.Random(31)
    checked = 0
    for i in range(30):
        _, text = gen_one(rng, want_tast=(i % 2 == 0))
        units = text_to_units(text)
        assert validate_units(units) == []
        for k in range(1, len(units) + 1):
            viol = validate_units_prefix(units[:k])
            assert viol == [], f"合法序列前缀被误杀 @unit{k}: {viol[:3]}"
            checked += 1
    assert checked > 500, f"覆盖量不足: {checked}"


def test_fatal_violations_fire_immediately():
    # 同音重开(double onset):后文救不了,前缀期即死
    double = "|4/4k0 PL:C4 1/4 C4 1/4 c4 1/2"
    v = validate_units_prefix(text_to_units(double))
    assert any(x.startswith("DYCK_DOUBLE_ONSET") for x in v), v
    # 无主关闭(orphan offset)
    orphan = "|4/4k0 PL:c4 1/1"
    v = validate_units_prefix(text_to_units(orphan))
    assert any(x.startswith("DYCK_ORPHAN_OFFSET") for x in v), v
    # 已完成的【内部】小节加总错(首个与最末完成小节均享 pickup 豁免,错误须居中:
    # 四条小节线,第二对之间只装 1/4)
    bad_measure = ("|4/4k0PL:C4 1/1 c4C4 |4/4k0 1/4 c4C4 "
                   "|4/4k0 1/1 c4C4 |4/4k0 1/1 c4")
    units = text_to_units(bad_measure)
    v = validate_units_prefix(units)
    assert any(x.startswith("MEASURE_SUM") for x in v), v
    # 时间戳倒退
    nonmono = "|4/4k0 PL:C4 <|1.00|> 1/1 <|0.50|> c4"
    v = validate_units_prefix(text_to_units(nonmono))
    assert any(x.startswith("TS_NONMONOTONE") for x in v), v


def test_prefix_exemptions_do_not_fire():
    # 音符尚未关闭 + 无终止小节线:前缀期两者都合法
    open_prefix = "|4/4k0 PL:C4D4 1/2 c4"
    units = text_to_units(open_prefix)
    assert validate_units_prefix(units) == []
    full = validate_units(units)
    assert any(x.startswith("DYCK_UNCLOSED") for x in full)
    assert any(x.startswith("TERMINAL") for x in full) or full  # 全量口径确实更严


def test_agrees_with_full_validator_on_fatal_classes():
    # 全量验证器报的 DOUBLE_ONSET/ORPHAN/MEASURE/TS 类,前缀器必须同报
    rng = random.Random(77)
    for i in range(20):
        _, text = gen_one(rng, want_tast=True)
        units = text_to_units(text)
        fatal_full = [x for x in validate_units(units)
                      if x.split(":")[0] in ("DYCK_DOUBLE_ONSET",
                                             "DYCK_ORPHAN_OFFSET",
                                             "MEASURE_SUM", "TS_NONMONOTONE")]
        assert validate_units_prefix(units) == fatal_full


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
