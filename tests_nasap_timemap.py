"""S7 nASAP TimeMap 修正测试。运行: python tests_nasap_timemap.py"""
import sys
from fractions import Fraction as F
sys.path.insert(0, ".")
from rubato.data.nasap_timemap import parse_alignment_tsv, build_timemap

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] TSV 解析")
rows = [
    {"xml_id": "n1-1", "midi_id": "m1", "pitch": "60", "onset": "0.5"},
    {"xml_id": "n1-2", "midi_id": "m2", "pitch": "64", "onset": "0.5"},
    {"xml_id": "*", "midi_id": "m3", "pitch": "67", "onset": "1.0"},   # 未对齐,跳过
    {"xml_id": "n2-1", "midi_id": "m4", "pitch": "60", "onset": "1.5"},
]
al = parse_alignment_tsv(rows)
check("skips_unaligned", len(al) == 3, len(al))
check("parses_onset", al[0]["perf_onset_sec"] == 0.5)

print("[2] xml_id 精确映射建 TimeMap(核心修复)")
# 关键:同音高 60 出现两次(n1-1 和 n2-1),音高匹配会错位,xml_id 不会
xmlid_pos = {"n1-1": F(0), "n1-2": F(0), "n2-1": F(1, 4)}
tmap, stats = build_timemap(al, xmlid_pos)
check("timemap_built", tmap is not None, stats)
check("all_matched", stats["matched_xmlid"] == 3, stats)
check("monotone", tmap(F(0)) <= tmap(F(1, 4)), f"{tmap(F(0))} vs {tmap(F(1,4))}")
check("slope_positive", tmap(F(1, 4)) - tmap(F(0)) > 0)

print("[3] 同音高重复不再错位(回归测试)")
# 模拟原 bug 场景:5 个同音高 C4,乐谱位置递增,演奏时间递增
al_rep = [
    {"xml_id": f"n1-{i}", "perf_onset_sec": float(i), "pitch": 60}
    for i in range(5)
]
pos_rep = {f"n1-{i}": F(i, 4) for i in range(5)}
tmap_rep, stats_rep = build_timemap(al_rep, pos_rep)
check("repeated_pitch_ok", tmap_rep is not None, stats_rep)
# 单调:每个位置的时间都应递增
prev = float("-inf")
mono = True
for i in range(5):
    t = tmap_rep(F(i, 4))
    if t < prev: mono = False
    prev = t
check("repeated_monotone", mono, "同音高序列时间应单调")
check("no_negative_duration", tmap_rep(F(4, 4)) - tmap_rep(F(0)) > 0)

print("[4] 非单调锚点被剔除(而非产坏图)")
# 演奏时间回跳(对齐错误)→ 应剔除回跳点,不产负斜率
al_bad = [
    {"xml_id": "a", "perf_onset_sec": 0.0, "pitch": 60},
    {"xml_id": "b", "perf_onset_sec": 5.0, "pitch": 62},
    {"xml_id": "c", "perf_onset_sec": 2.0, "pitch": 64},  # 回跳!
    {"xml_id": "d", "perf_onset_sec": 8.0, "pitch": 65},
]
pos_bad = {"a": F(0), "b": F(1,4), "c": F(2,4), "d": F(3,4)}
tmap_bad, stats_bad = build_timemap(al_bad, pos_bad)
check("nonmonotone_dropped", stats_bad["dropped_nonmonotone"] == 1, stats_bad)
check("still_valid_timemap", tmap_bad is not None and stats_bad.get("slope_ok"), stats_bad)

print("[5] 锚点不足返回 None(不产坏图)")
al_few = [{"xml_id": "x", "perf_onset_sec": 1.0, "pitch": 60}]
tmap_few, stats_few = build_timemap(al_few, {"x": F(0)})
check("insufficient_returns_none", tmap_few is None, stats_few)

print("[6] 缺乐谱位置的对齐被计数")
al_miss = [
    {"xml_id": "known", "perf_onset_sec": 0.0, "pitch": 60},
    {"xml_id": "unknown", "perf_onset_sec": 1.0, "pitch": 62},
    {"xml_id": "known2", "perf_onset_sec": 2.0, "pitch": 64},
]
tmap_m, stats_m = build_timemap(al_miss, {"known": F(0), "known2": F(1,4)})
check("missing_counted", stats_m["dropped_no_scorepos"] == 1, stats_m)

print(f"\n全部通过: {PASS} 项")
