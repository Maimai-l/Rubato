"""S5 humanize 兜底测试(补齐 PDMX-TAST 的时序来源)。运行: python tests_humanize.py"""
import sys
import re
from fractions import Fraction as F
sys.path.insert(0, ".")
from rubato.intermo.core import (
    SPitch, Note, Measure, ScoreIR, project, text_to_units, validate_units,
)
from rubato.render.humanize import humanize_timemap, humanize_events, _ou_tempo, _seeded_rng

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

# 3 小节 4/4,PR 每小节一个全音符
ir = ScoreIR(
    [Note("PR", SPitch("C", 0, 4), F(0), F(1)),
     Note("PR", SPitch("D", 0, 4), F(1), F(1)),
     Note("PR", SPitch("E", 0, 4), F(2), F(1))],
    [Measure(F(0), 4, 4, 0), Measure(F(1), 4, 4, 0), Measure(F(2), 4, 4, 0)], F(3))

print("[1] OU 速度因子在 [0.90,1.10] 内")
rng = _seeded_rng(1, "p1")
phis = _ou_tempo(50, rng)
check("ou_bounded", all(0.90 <= p <= 1.10 for p in phis), (min(phis), max(phis)))
check("ou_length", len(phis) == 50)

print("[2] humanize_timemap:单调递增 + 覆盖全曲")
tm = humanize_timemap(ir, base_sec_per_whole=2.0, seed=7, piece_id="pdmx_1")
t0 = float(tm(F(0))); tend = float(tm(F(3)))
check("tmap_starts_0", abs(t0) < 1e-9, t0)
check("tmap_end_positive", tend > 0, tend)
# 单调:采样若干乐谱位置,演奏时间递增
prev = -1.0
mono = True
for k in range(0, 13):
    s = float(tm(F(k, 4)))
    if s < prev - 1e-9: mono = False
    prev = s
check("tmap_monotone", mono, "演奏时间应随乐谱位置单调不降")
# 名义总时长 3 whole × 2s = 6s;OU 抖动后应在合理区间(±10%)
check("tmap_tempo_reasonable", 6.0 * 0.90 <= tend <= 6.0 * 1.10, tend)

print("[3] 确定性:同 (seed, piece) 一致,不同 piece 不同")
tm_a = humanize_timemap(ir, seed=7, piece_id="pdmx_1")
tm_b = humanize_timemap(ir, seed=7, piece_id="pdmx_1")
tm_c = humanize_timemap(ir, seed=7, piece_id="pdmx_2")
check("deterministic_same", float(tm_a(F(3))) == float(tm_b(F(3))))
check("varies_by_piece", float(tm_a(F(3))) != float(tm_c(F(3))))

print("[4] 用 humanize tmap 投影 PDMX → TAST(此前恒 null 的路)")
tast = project(ir, "TAST", tm)
check("pdmx_tast_has_ts", re.search(r"<\|\d+\.\d{2}\|>", tast) is not None, tast)
check("pdmx_tast_valid", not validate_units(text_to_units(tast)), validate_units(text_to_units(tast)))
# 去戳 == A2S(时间戳不改切分)
stripped = re.sub(r" <\|\d+\.\d{2}\|>", "", tast)
check("pdmx_tast_strip_eq_a2s", stripped == project(ir, "A2S"), f"\n{stripped}\n{project(ir,'A2S')}")

print("[5] humanize_events:抖动在界内 + 时值保持 + 与 tmap 同源")
events, pedal, tm2 = humanize_events(ir, base_sec_per_whole=2.0, seed=7, piece_id="pdmx_1")
check("events_count", len(events) == 3, len(events))
check("vel_in_range", all(20 <= e["vel"] <= 120 for e in events), [e["vel"] for e in events])
check("onset_nonneg_ordered", all(e["off"] > e["on"] >= 0 for e in events), events)
# onset 抖动幅度 ≤ 35ms 相对无抖版
base_on = float(tm2(F(0)))
check("jitter_bounded", abs(events[0]["on"] - base_on) <= 0.035 + 1e-9, (events[0]["on"], base_on))

print(f"\n全部通过: {PASS} 项")
print("注:humanize 是 VN 的 CPU 兜底,产 PDMX-TAST + 时序多样性;VN 主路径在执行端 py312 跑。")
