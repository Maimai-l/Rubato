"""InterMo 核心测试。运行: python tests_intermo.py"""
import random
import sys
from fractions import Fraction as F

sys.path.insert(0, ".")
from rubato.intermo.core import (
    SPitch, Note, Measure, ScoreIR, ir_to_units, units_to_text,
    text_to_units, units_to_ir, validate_units, TimeMap, stamp_units,
    project, perf_to_amt, ParseError,
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


def rt(ir):
    """round trip: IR → text → IR,返回 (text, ir2)"""
    text = project(ir, "A2S")
    ir2 = units_to_ir(text_to_units(text))
    return text, ir2


# ---------------------------------------------------------------- 1. 金标:冻结字形
print("[1] 金标文本(冻结语法)")
# 3/4 拍 4 个降号(论文 Fig.1 的签名),PL: A♭2 附点二分,PR: C4 四分 + (E♭4,G4) 二分和弦
ir = ScoreIR(
    notes=[
        Note("PL", SPitch("A", -1, 2), F(0), F(3, 4)),
        Note("PR", SPitch("C", 0, 4), F(0), F(1, 4)),
        Note("PR", SPitch("E", -1, 4), F(1, 4), F(1, 2)),
        Note("PR", SPitch("G", 0, 4), F(1, 4), F(1, 2)),
    ],
    measures=[Measure(F(0), 3, 4, -4)],
    score_end=F(3, 4),
)
text = project(ir, "A2S")
expected = "|3/4k-4PL:A-2PR:C4 1/4c4E-4G4 1/2 |3/4k-4PL:a-2PR:e-4g4"
check("golden.exact", text == expected, f"\n    got:  {text}\n    want: {expected}")
# 说明:①offset 先于 onset(c4 在 E-4G4 前)②落在小节线时刻的事件归属小节线单元(D-06),
#   故终止 offset 挂在末尾小节线上,其前补一个空 moment 的 1/2 interval;与首小节线携带
#   开头 onset 对称 ③staff 标记只在切换时发出 ④和弦按音高升序 ⑤小节内 interval 和 = 3/4 ✓

# ---------------------------------------------------------------- 2. 往返:8 类边界
print("[2] 边界情形往返")

# 2.1 再触键:同 moment 同音 offset+onset
ir = ScoreIR(
    [Note("PR", SPitch("C", 0, 5), F(0), F(1, 8)),
     Note("PR", SPitch("C", 0, 5), F(1, 8), F(1, 8))],
    [Measure(F(0), 1, 4, 0)], F(1, 4))
t, ir2 = rt(ir)
check("rearticulation", ir == ir2 and "c5C5" in t, t)

# 2.2 跨小节延音(Dyck open 越过小节线)
ir = ScoreIR(
    [Note("PL", SPitch("G", 0, 2), F(0), F(2, 4)),
     Note("PR", SPitch("B", 0, 4), F(1, 4), F(1, 8))],
    [Measure(F(0), 1, 4, 0), Measure(F(1, 4), 1, 4, 0)], F(2, 4))
t, ir2 = rt(ir)
check("tie_across_bar", ir == ir2, t)

# 2.3 全休止小节(空 moment 补齐 interval)
ir = ScoreIR(
    [Note("PR", SPitch("D", 0, 5), F(1, 4), F(1, 4))],
    [Measure(F(0), 1, 4, 0), Measure(F(1, 4), 1, 4, 0)], F(2, 4))
t, ir2 = rt(ir)
check("rest_measure", ir == ir2 and t.startswith("|1/4k0 1/4 |1/4k0"), t)

# 2.4 拍号+调号中途变化
ir = ScoreIR(
    [Note("PR", SPitch("C", 0, 4), F(0), F(3, 4)),
     Note("PR", SPitch("F", 1, 4), F(3, 4), F(1, 2))],
    [Measure(F(0), 3, 4, -4), Measure(F(3, 4), 2, 4, 3)], F(5, 4))
t, ir2 = rt(ir)
check("sig_change", ir == ir2 and "|2/4k#3" in t, t)

# 2.5 弱起小节(首小节短于声明,D-10)
ir = ScoreIR(
    [Note("PR", SPitch("G", 0, 4), F(0), F(1, 8)),
     Note("PR", SPitch("C", 0, 5), F(1, 8), F(2, 4))],
    [Measure(F(0), 2, 4, 0), Measure(F(1, 8), 2, 4, 0)], F(5, 8))
t, ir2 = rt(ir)
check("pickup", ir == ir2 and not validate_units(text_to_units(t)), t)

# 2.6 双谱表同 moment(PL 先于 PR)
ir = ScoreIR(
    [Note("PL", SPitch("C", 0, 3), F(0), F(1, 4)),
     Note("PR", SPitch("E", 0, 5), F(0), F(1, 4))],
    [Measure(F(0), 1, 4, 0)], F(1, 4))
t, _ = rt(ir)
check("staff_order", t.index("PL:") < t.index("PR:"), t)

# 2.7 三连音(分数精确:1/4 三分)
tri = F(1, 12)
ir = ScoreIR(
    [Note("PR", SPitch(s, 0, 4), i * tri, tri) for i, s in enumerate("CDE")],
    [Measure(F(0), 1, 4, 0)], F(1, 4))
t, ir2 = rt(ir)
check("triplet_fraction", ir == ir2 and "1/12" in t, t)

# 2.8 重升/重降
ir = ScoreIR(
    [Note("PR", SPitch("F", 2, 4), F(0), F(1, 8)),
     Note("PR", SPitch("B", -2, 3), F(1, 8), F(1, 8))],
    [Measure(F(0), 1, 4, 0)], F(1, 4))
t, ir2 = rt(ir)
check("double_accidentals", ir == ir2 and "F##4" in t and "B--3" in t, t)

# ---------------------------------------------------------------- 3. 不变量
print("[3] 不变量")

# 3.1 canonical 幂等:parse→serialize 不动点
base = project(ScoreIR(
    [Note("PL", SPitch("A", -1, 2), F(0), F(1, 2)),
     Note("PR", SPitch("C", 0, 5), F(0), F(1, 4)),
     Note("PR", SPitch("E", -1, 5), F(1, 4), F(1, 4))],
    [Measure(F(0), 2, 4, -3)], F(1, 2)), "A2S")
again = units_to_text(ir_to_units(units_to_ir(text_to_units(base))))
check("canonical_idempotent", base == again, f"\n    {base}\n    {again}")

# 3.2 TAST 去戳 == A2S(论文不变量:时间戳不改变切分边界)
ir = ScoreIR(
    [Note("PR", SPitch("C", 0, 4), F(0), F(1, 4)),
     Note("PR", SPitch("D", 0, 4), F(1, 4), F(1, 4))],
    [Measure(F(0), 2, 4, 0)], F(2, 4))
tmap = TimeMap([(F(0), 0.0), (F(2, 4), 2.0)])
tast = project(ir, "TAST", tmap)
import re
stripped = re.sub(r" <\|t\d+\|>", "", tast)
check("tast_strip_eq_a2s", stripped == project(ir, "A2S"), f"\n    {tast}\n    {stripped}")
n_units = len(text_to_units(project(ir, "A2S")))
n_ts = len(re.findall(r"<\|t\d+\|>", tast))
check("ts_per_unit", n_ts == n_units, f"{n_ts} vs {n_units}")

# 3.3 lite 与 A2S 音高集合一致(MIDI 投影)
lite = project(ir, "A2S_lite")
check("lite_midi_glyphs", "N60" in lite and "n60" in lite and "N62" in lite, lite)
ir_l = units_to_ir(text_to_units(lite))
check("lite_roundtrip_midi",
      sorted(n.pitch for n in ir_l.notes) == sorted(n.pitch.midi for n in ir.notes)
      if all(isinstance(n.pitch, int) for n in ir_l.notes) else False, lite)

# 3.4 校验器抓坏样本
bad = base.replace("c5", "", 1) if "c5" in base else base
viol = validate_units(text_to_units("|2/4k0C4 1/4c4D4 1/4 |2/4k0"))  # D4 未闭合
check("validator_catches_unclosed", any("UNCLOSED" in x for x in viol), viol)
try:
    units_to_ir(text_to_units("|1/4k0c4 1/4 |1/4k0"))
    check("parser_rejects_orphan", False)
except ParseError:
    check("parser_rejects_orphan", True)

# 小节求和违规(需内部小节:首末有弱起豁免。中间小节 1/4 != 2/4 → 违规)
viol = validate_units(text_to_units(
    "|2/4k0C4 1/4c4D4 1/4d4 |2/4k0E4 1/4e4 |2/4k0F4 1/2f4 |2/4k0"))
check("validator_measure_sum", any("MEASURE_SUM" in x for x in viol), viol)

# ---------------------------------------------------------------- 4. AMT
print("[4] AMT dialect")
amt, stats = perf_to_amt(
    notes=[{"pitch": 60, "on": 0.50, "off": 1.20, "vel": 82},
           {"pitch": 64, "on": 0.505, "off": 1.20, "vel": 78},
           {"pitch": 60, "on": 1.30, "off": 1.302, "vel": 90}],  # 触发最短音长
    pedal=[(0.50, True), (1.25, False)])
check("amt_has_vel_ts", "<|v82|>" in amt and "<|t50|>" in amt, amt)
check("amt_pedal", "<|ped1|>" in amt and "<|ped0|>" in amt, amt)
check("amt_min_dur_floor", stats["min_dur_floored"] == 1, stats)
check("amt_dyck", not [x for x in validate_units(text_to_units(amt))
                       if "DYCK" in x], validate_units(text_to_units(amt)))

# ---------------------------------------------------------------- 5. 属性测试:随机乐谱
print("[5] 随机属性测试 (100 份)")
random.seed(20260706)
STEPS = "CDEFGAB"
for trial in range(100):
    n_meas = random.randint(2, 6)
    num, den = random.choice([(4, 4), (3, 4), (6, 8), (2, 4)])
    fifths = random.randint(-7, 7)
    mlen = F(num, den)
    measures = [Measure(i * mlen, num, den, fifths) for i in range(n_meas)]
    end = n_meas * mlen
    grid = F(1, 16)
    notes, occupied = [], set()
    for _ in range(random.randint(3, 25)):
        staff = random.choice(["PL", "PR"])
        p = SPitch(random.choice(STEPS), random.choice([-1, 0, 1]),
                   random.randint(2, 5) if staff == "PL" else random.randint(4, 6))
        start = random.randint(0, int(end / grid) - 1)
        dur = random.randint(1, min(8, int(end / grid) - start))
        cells = {(staff, p, i) for i in range(start, start + dur)}
        if cells & occupied:                       # 保证同 (staff,pitch) 不重叠
            continue
        occupied |= cells
        notes.append(Note(staff, p, start * grid, dur * grid))
    if not notes:
        continue
    ir = ScoreIR(notes, measures, end)
    t, ir2 = rt(ir)
    assert ir == ir2, f"trial {trial} roundtrip 失败\n{t}"
    assert not validate_units(text_to_units(t)), f"trial {trial} 校验失败"
    # 幂等
    assert units_to_text(ir_to_units(ir2)) == t, f"trial {trial} 非幂等"
check("property_100_random_scores", True)

print(f"\n全部通过: {PASS} 项")
