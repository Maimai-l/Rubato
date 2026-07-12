"""文本标签管线回归:真速度分段、巨曲守卫、score_range、以及【导入路径调用 run() 无 NameError】
(执行端 658c48b 曾加 --no-midi-tempo 开关,在 run() 里引用 __main__ 的 args ——
 经 s5_parallel 导入调用时每曲必 NameError 被吞成 failure,P4 全灭。已撤,此测试防复发。)
运行: python tests_text_labels.py
"""
import json
import os
import sys
import tempfile
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, ".")
import mido

import scripts.s5_pdmx_a2s_labels as tl
from rubato.intermo.core import SPitch, Note, Measure, ScoreIR

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


tmp = Path(tempfile.mkdtemp())

# 假谱面加载(绕开 partitura):2 小节 4/4,总长 2 全音符
FAKE_IR = ScoreIR([Note("PR", SPitch("C", 0, 4), F(0), F(1))],
                  [Measure(F(0), 4, 4, 0), Measure(F(1), 4, 4, 0)], F(2))
tl.load_musicxml_part = lambda p: "fake_part"
tl.part_to_ir = lambda part: FAKE_IR

# 与 IR 结构匹配的真 MIDI(2 整小节 4/4 @60bpm)→ 速度图守卫应放行
mid = mido.MidiFile(ticks_per_beat=480)
tr = mido.MidiTrack(); mid.tracks.append(tr)
tr.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(60.0), time=0))
tr.append(mido.Message("note_on", note=60, velocity=64, time=0))
tr.append(mido.Message("note_off", note=60, velocity=0, time=3840))
mid.save(str(tmp / "p.mid"))

piece = {"piece_id": "T", "xml_raw": str(tmp / "fake.xml"), "midi_path": str(tmp / "p.mid")}

print("[1] 正常曲:真速度图放行(无 tempo_fallback),行带 score_range")
os.environ.pop("S5_TEMPO_MIDI_MAX_MB", None)
rows, stats = tl.process_piece(piece, tmp, 1, None, 40.0, True, overlap=False)
check("no_fallback", not stats.get("tempo_fallback"), stats)
check("rows_made", len(rows) >= 1, stats)
check("score_range_present", rows[0].get("score_range") == [0.0, 2.0], rows[0])

print("[2] 巨曲守卫:超过阈值只该曲回退恒速并计数(不再有全局开关)")
os.environ["S5_TEMPO_MIDI_MAX_MB"] = "0.000001"      # 任何文件都算"巨曲"
rows2, stats2 = tl.process_piece(piece, tmp, 1, None, 40.0, True, overlap=False)
check("guard_fires", stats2.get("tempo_fallback") == "midi_too_big", stats2)
check("still_produces", len(rows2) >= 1, stats2)     # 回退恒速仍产标签,不是失败
os.environ.pop("S5_TEMPO_MIDI_MAX_MB", None)

print("[3]【防复发】经导入路径调用 run()(s5_parallel 的方式)无 NameError,report 聚合 tempo_fallback")
mani = tmp / "m.jsonl"
with open(mani, "w", encoding="utf-8") as f:
    f.write(json.dumps(piece) + "\n")
rep = tl.run(str(mani), str(tmp), str(tmp / "l.jsonl"), str(tmp / "c.txt"),
             str(tmp / "r.json"), blacklist=set(), overlap=False)
check("run_no_nameerror", rep["processed"] == 1 and not rep["failures"], rep)
os.environ["S5_TEMPO_MIDI_MAX_MB"] = "0.000001"
rep2 = tl.run(str(mani), str(tmp), str(tmp / "l2.jsonl"), str(tmp / "c2.txt"),
              str(tmp / "r2.json"), blacklist=set(), overlap=False)
check("report_aggregates_fallback", rep2.get("tempo_fallback", {}).get("midi_too_big") == 1, rep2)
os.environ.pop("S5_TEMPO_MIDI_MAX_MB", None)

print(f"\n全部通过: {PASS} 项")
