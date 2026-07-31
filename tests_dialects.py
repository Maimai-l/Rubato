"""补齐的方言(TAST_lite / AMT_lite / DBD / DBD_lite)+ PDMX→AMT 桥。运行: python tests_dialects.py"""
import sys
import re
from fractions import Fraction as F
sys.path.insert(0, ".")
from rubato.intermo.core import (
    SPitch, Note, Measure, ScoreIR, TimeMap, project, perf_to_amt,
    text_to_units, units_to_ir, validate_units, score_ir_to_events,
    ir_to_dbd_units, _derive_beats,
)

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)


# 一段 2 小节 4/4:C4 全音符 + D4 全音符
ir = ScoreIR(
    [Note("PR", SPitch("C", 0, 4), F(0), F(1)),
     Note("PR", SPitch("D", 0, 4), F(1), F(1))],
    [Measure(F(0), 4, 4, 0), Measure(F(1), 4, 4, 0)], F(2))
tmap = TimeMap([(F(0), 0.0), (F(2), 16.0)])          # 每小节 8s

print("[1] TAST_lite = A2S_lite + 时间戳,MIDI 音高")
tast_lite = project(ir, "TAST_lite", tmap)
check("tast_lite_midi_pitch", "N60" in tast_lite and "N62" in tast_lite, tast_lite)
check("tast_lite_has_ts", "<|0.00|>" in tast_lite, tast_lite)
# 去戳后 == A2S_lite(时间戳不改切分)
stripped = re.sub(r" <\|\d+\.\d{2}\|>", "", tast_lite)
check("tast_lite_strip_eq_a2s_lite", stripped == project(ir, "A2S_lite"), f"\n{stripped}\n{project(ir,'A2S_lite')}")
check("tast_lite_no_spelling", "C4" not in tast_lite and "PR:" in tast_lite, tast_lite)

print("[2] AMT_lite = 音高事件 + 时间戳,无力度/踏板")
notes = [{"pitch": 60, "on": 0.50, "off": 1.20, "vel": 82},
         {"pitch": 64, "on": 0.50, "off": 1.20, "vel": 78}]
pedal = [(0.50, True), (1.25, False)]
amt_full, _ = perf_to_amt(notes, pedal)
amt_lite, _ = perf_to_amt(notes, pedal, lite=True)
check("amt_full_has_vel", "<|vel:82|>" in amt_full, amt_full)
check("amt_lite_no_vel", "<|vel:" not in amt_lite, amt_lite)
check("amt_lite_no_pedal", "<|CC64:" not in amt_lite, amt_lite)
check("amt_lite_has_pitch_ts", "N60" in amt_lite and "<|0.50|>" in amt_lite, amt_lite)
# AMT/AMT_lite 无小节线是设计(纯 moment),只查 Dyck 平衡,不查 TERMINAL_BAR
check("amt_lite_dyck_ok", not [x for x in validate_units(text_to_units(amt_lite)) if "DYCK" in x],
      validate_units(text_to_units(amt_lite)))

print("[3] DBD:拍点网格 + 小节线 + 时间戳,无音高")
dbd = project(ir, "DBD", tmap)
check("dbd_has_barline", "|4/4k0" in dbd, dbd)
check("dbd_has_beat_marker", "*" in dbd, dbd)
check("dbd_no_pitch", not re.search(r"[A-Ga-gNn]\d", dbd), dbd)   # 无任何音高字形
check("dbd_has_ts", "<|0.00|>" in dbd and "<|8.00|>" in dbd, dbd)
# 4/4 每小节 4 拍:下拍(小节线)+ 3 个 '*';两小节共 6 个 '*'
check("dbd_beat_count", dbd.count("*") == 6, f"{dbd.count('*')} in {dbd}")
check("dbd_valid", not validate_units(text_to_units(dbd)), validate_units(text_to_units(dbd)))
# 拍点网格推导:2 小节 × 4 拍 = 8 个拍点,含 2 个下拍
beats = _derive_beats(ir)
check("derive_beats_count", len(beats) == 8, len(beats))
check("derive_beats_downbeats", sum(1 for _, d in beats if d) == 2, beats)

print("[4] DBD round-trip(拍点标记解析回来)")
u = text_to_units(dbd)
check("dbd_parse_beat_flag", any(x.beat for x in u), [x.beat for x in u])
# 再序列化应幂等
from rubato.intermo.core import units_to_text, ir_to_dbd_units, stamp_units
u2 = ir_to_dbd_units(ir); stamp_units(u2, tmap)
check("dbd_idempotent", units_to_text(u2, with_ts=True) == dbd, f"\n{units_to_text(u2, with_ts=True)}\n{dbd}")

print("[5] DBD_lite:纯拍流,无小节线签名")
dbd_lite = project(ir, "DBD_lite", tmap)
check("dbd_lite_no_barline", "k0" not in dbd_lite, dbd_lite)
check("dbd_lite_all_beats", dbd_lite.count("*") >= 6, dbd_lite)
check("dbd_lite_valid_dyck", not [x for x in validate_units(text_to_units(dbd_lite)) if "DYCK" in x],
      validate_units(text_to_units(dbd_lite)))

print("[6] PDMX→AMT 桥:乐谱恒速 → 演奏事件 → AMT")
ev = score_ir_to_events(ir, sec_per_whole=2.0, default_vel=64)
check("events_count", len(ev) == 2, ev)
check("events_seconds", ev[0]["on"] == 0.0 and ev[0]["off"] == 2.0, ev[0])   # C4 全音符=1 whole=2s
check("events_midi_pitch", ev[0]["pitch"] == 60 and ev[1]["pitch"] == 62, ev)
amt_from_score, st = perf_to_amt(ev)
check("pdmx_amt_dyck_ok", not [x for x in validate_units(text_to_units(amt_from_score)) if "DYCK" in x],
      validate_units(text_to_units(amt_from_score)))
check("pdmx_amt_has_notes", "N60" in amt_from_score and "N62" in amt_from_score, amt_from_score)
# lite 桥
amt_lite_from_score, _ = perf_to_amt(ev, lite=True)
check("pdmx_amt_lite_no_vel", "<|vel:" not in amt_lite_from_score, amt_lite_from_score)

print(f"\n全部通过: {PASS} 项")
print("注:DBD_lite 的 full/lite 精确切分依论文 Fig.2 图示,当前取『下拍+拍号 vs 纯拍流』的合理解读。")
