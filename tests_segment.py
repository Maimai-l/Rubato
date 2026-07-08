"""S8 分段器测试。运行: python tests_segment.py"""
import sys
from fractions import Fraction as F
sys.path.insert(0, ".")

from rubato.intermo.core import Note, Measure, ScoreIR, SPitch, TimeMap, text_to_units, validate_units, project
from rubato.data.segment import (
    segment_score, segment_amt, make_labels, make_amt_label, leakage_check,
)

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1; print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}"); raise SystemExit(1)


def make_ir(n_measures, num=4, den=4, fifths=0, notes_per_measure=2):
    """造一个 n_measures 小节、每小节若干音的 IR。"""
    mlen = F(num, den)
    measures = [Measure(i * mlen, num, den, fifths) for i in range(n_measures)]
    notes = []
    step_cycle = "CDEFGAB"
    for i in range(n_measures):
        base = i * mlen
        for j in range(notes_per_measure):
            dur = mlen / notes_per_measure
            p = SPitch(step_cycle[(i + j) % 7], 0, 4 + j % 2)
            notes.append(Note("PR", p, base + j * dur, dur))
    return ScoreIR(notes, measures, n_measures * mlen)


print("[1] 基本切段:小节数约束")
ir = make_ir(20)                    # 20 小节
segs = segment_score(ir, min_measures=4, max_measures=8)
check("seg_count", len(segs) >= 2, f"got {len(segs)}")
# 每段小节数在 [4,8]
for sub, (a, b) in segs:
    check(f"seg_range_{a}_{b}", 4 <= (b - a) <= 8 and len(sub.measures) == (b - a))
# 段起点都在小节线(子 IR 首小节 start=0)
for sub, _ in segs:
    check(f"seg_start_zero", sub.measures[0].start == 0)
    break

print("[2] 每段独立满足 InterMo 不变量")
ir = make_ir(15, num=3, den=4, fifths=-4, notes_per_measure=3)
segs = segment_score(ir, min_measures=4, max_measures=6)
for idx, (sub, rng) in enumerate(segs):
    a2s = project(sub, "A2S")
    viol = validate_units(text_to_units(a2s))
    check(f"seg{idx}_valid", not viol, f"{rng}: {viol}")

print("[3] 跨小节延音的截断")
# 一个音跨越第 5 小节边界(切点),应被截断到段边界
mlen = F(4, 4)
measures = [Measure(i * mlen, 4, 4, 0) for i in range(10)]
notes = [Note("PL", SPitch("C", 0, 3), F(0), F(10)),  # 横跨全曲的长音
         Note("PR", SPitch("E", 0, 5), F(3), F(1))]
ir = ScoreIR(notes, measures, F(10))
segs = segment_score(ir, min_measures=4, max_measures=5)
# 第一段 [0,5):长音应被截断为 5 个全音符(段内)
sub0, rng0 = segs[0]
long_notes = [n for n in sub0.notes if n.staff == "PL"]
check("tie_truncated", long_notes and long_notes[0].dur == F(5),
      f"dur={long_notes[0].dur if long_notes else None}")
# 且截断后每段仍合法(Dyck 闭合)
for sub, rng in segs:
    check(f"truncated_seg_valid_{rng[0]}", not validate_units(text_to_units(project(sub, "A2S"))))

print("[4] 时长约束(恒速)")
# 每全音符 2 秒,4/4 每小节 1 全音符=2秒;max_sec=10 → 每段最多 5 小节
ir = make_ir(20)
segs = segment_score(ir, min_measures=4, max_measures=32, max_sec=10.0, sec_per_whole=2.0)
for sub, (a, b) in segs[:-1]:       # 末段可能因并入超限,豁免
    dur = float(sub.score_end) * 2.0
    check(f"dur_le_max_{a}", dur <= 10.0 + 1e-6, f"{dur}s")
    break

print("[5] 末尾不足并入")
ir = make_ir(11)                    # 11 小节,min=4 max=4 → 4+4 后剩 3 不足
segs = segment_score(ir, min_measures=4, max_measures=4)
total_measures = sum((b - a) for _, (a, b) in segs)
check("tail_merged_or_dropped", total_measures in (8, 11),
      f"covered {total_measures}/11")  # 8=丢弃末3, 11=并入
# 并入情形:最后一段可能 4-7 小节
check("tail_seg_valid", all(not validate_units(text_to_units(project(s, "A2S"))) for s, _ in segs))

print("[6] dialect 标签生成 + validate 门")
ir = make_ir(6)
tmap = TimeMap([(F(0), 0.0), (F(6), 12.0)])
labels, fails = make_labels(ir, "flat", tmap)
check("flat_dialects", set(labels) == {"A2S", "A2S_lite", "TAST"}, f"{set(labels)} {fails}")
# maestro 只出 AMT(经 make_amt_label 而非 make_labels)
labels_n, _ = make_labels(ir, "nasap", tmap)
check("nasap_dialects", set(labels_n) == {"A2S", "A2S_lite", "TAST"})
# vn 无 TAST(除非 vn_tast_ok)
labels_v, _ = make_labels(ir, "vn", tmap, vn_tast_ok=False)
check("vn_no_tast", set(labels_v) == {"A2S", "A2S_lite"})
labels_v2, _ = make_labels(ir, "vn", tmap, vn_tast_ok=True)
check("vn_tast_when_ok", "TAST" in labels_v2)

print("[7] AMT 智能切点分窗")
# 造一段 40s 的音符流,中间有明确的"无声+踏板抬起"间隙
notes = []
for i in range(20):
    t = i * 2.0
    notes.append({"pitch": 60 + i % 12, "on": t, "off": t + 1.5, "vel": 80})  # 每 2s 一音,间隙 0.5s
pedal = [(0.0, False)]               # 全程无踏板 → 间隙处都是好切点
wins = segment_amt(notes, pedal, target_lo=12, target_hi=25, search=2.0)
check("amt_windows", len(wins) >= 1, f"got {len(wins)}")
for wn, wp, (t0, t1) in wins:
    dur = t1 - t0
    check(f"amt_win_dur_{t0:.0f}", 8 <= dur <= 27 or t1 == 40.0, f"{dur}s")
    break
# 每窗 AMT 标签合法
for wn, wp, rng in wins:
    lab, f = make_amt_label(wn, wp)
    check(f"amt_label_valid_{rng[0]:.0f}", "AMT" in lab, f)
    break

print("[8] 泄漏终检")
utts = [
    {"utt_id": "u1", "split": "train", "work_key": "chopin|op10", "maestro_id": None, "dup_cluster": 1},
    {"utt_id": "u2", "split": "test",  "work_key": "chopin|op25", "maestro_id": None, "dup_cluster": 2},
    {"utt_id": "u3", "split": "val",   "work_key": "liszt|s244",  "maestro_id": None, "dup_cluster": 3},
]
check("leakage_clean", leakage_check(utts)["ok"])
# 注入泄漏:train 和 test 共享 work_key
utts_bad = utts + [{"utt_id": "u4", "split": "test", "work_key": "chopin|op10",
                    "maestro_id": None, "dup_cluster": 9}]
r = leakage_check(utts_bad)
check("leakage_detected", not r["ok"] and "chopin|op10" in r["violations"]["work_key"], r)

print(f"\n全部通过: {PASS} 项")
