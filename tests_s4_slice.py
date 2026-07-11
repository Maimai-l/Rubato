"""S4 真实速度图切割 + 离谱速度钳制 回归测试。
用 mido 造带变速/变拍号的 MIDI + soundfile 造整曲音频,验证:时间图、网格、切割、钳制全链。
运行: python tests_s4_slice.py
"""
import json
import sys
import tempfile
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, ".")
import mido
import numpy as np
import soundfile as sf

from rubato.data.midi_time import midi_time, tempo_outliers, clamp_midi_tempo
import scripts.s4_slice_segments as slicer
import scripts.s4_fix_tempo as fixer

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


def make_midi(path, first_tempo_bpm=60.0):
    """2 小节 4/4 @first_tempo,再 2 小节 3/4 @120bpm。ppq=480。总长 3.5 全音符。"""
    mid = mido.MidiFile(ticks_per_beat=480)
    tr = mido.MidiTrack(); mid.tracks.append(tr)
    tr.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(first_tempo_bpm), time=0))
    tr.append(mido.Message("note_on", note=60, velocity=64, time=0))
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(120.0), time=3840))  # 2 全音符处
    tr.append(mido.MetaMessage("time_signature", numerator=3, denominator=4, time=0))
    tr.append(mido.Message("note_off", note=60, velocity=0, time=2880))               # 再 1.5 全音符
    mid.save(str(path))
    return path


print("[1] midi_time:变速(60→120bpm)+ 变拍号(4/4→3/4)的时间图与小节网格")
m = make_midi(tmp / "p.mid")
tmap, measures, total = midi_time(m)
check("measures", measures == [F(0), F(1), F(2), F(11, 4)], measures)
check("total", total == F(7, 2), total)
for pos, want in [(F(0), 0.0), (F(1), 4.0), (F(2), 8.0), (F(11, 4), 9.5), (F(7, 2), 11.0)]:
    check(f"tmap({pos})={want}", abs(tmap(pos) - want) < 1e-6, tmap(pos))

print("[2] 离谱速度检测与钳制(MXL 编辑错误:四分音符=4 → 80;MIDI set_tempo 最慢只能存 ~3.6bpm)")
bad_mid = make_midi(tmp / "bad.mid", first_tempo_bpm=4.0)      # "四分音符=1"式编辑错误(可表示下限附近)
check("outlier_detected", tempo_outliers(bad_mid) == [4.0], tempo_outliers(bad_mid))
check("normal_clean", tempo_outliers(m) == [], tempo_outliers(m))
n = clamp_midi_tempo(bad_mid, fallback_bpm=80.0)
check("clamped_one_event", n == 1, n)
check("backup_exists", (tmp / "bad.tempo_orig.mid").exists())
check("clamped_now_clean", tempo_outliers(bad_mid) == [], tempo_outliers(bad_mid))
t2, _, _ = midi_time(bad_mid)
check("clamped_map_80bpm", abs(t2(F(2)) - 6.0) < 1e-6, t2(F(2)))   # 2全音符=8拍@80bpm=6s(不再480s)

print("[3] 切割器端到端:按真实速度图切段,越界段跳过,结构不匹配整曲跳过")
audio_dir = tmp / "aud"; audio_dir.mkdir()
sf.write(str(audio_dir / "pdmx_P.flac"), np.zeros(11 * 8000, dtype="float32"), 8000)
sf.write(str(audio_dir / "pdmx_Q.flac"), np.zeros(11 * 8000, dtype="float32"), 8000)
labels = tmp / "labels.jsonl"
rows = [
    {"utt_id": "pdmx_P_000", "piece_id": "P", "measure_range": [0, 2], "A2S": "x"},   # 0..8s ✓
    {"utt_id": "pdmx_P_001", "piece_id": "P", "measure_range": [2, 4], "A2S": "x"},   # 8..11s ✓
    {"utt_id": "pdmx_P_002", "piece_id": "P", "measure_range": [0, 4], "A2S": "x"},   # 11s > max=10 ✗
    {"utt_id": "pdmx_Q_000", "piece_id": "Q", "measure_range": [0, 10], "A2S": "x"},  # 超网格 → 整曲跳
    {"utt_id": "pdmxperf_R_000", "piece_id": "R", "measure_range": [0, 2], "A2S": "x",
     "audio_path": "already.wav"},                                                    # VN 行:不属此管线
]
with open(labels, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
manifest = tmp / "manifest.jsonl"
with open(manifest, "w", encoding="utf-8") as f:
    f.write(json.dumps({"piece_id": "P", "midi_path": str(m)}) + "\n")
    f.write(json.dumps({"piece_id": "Q", "midi_path": str(m)}) + "\n")
rc = slicer.main(["--labels", str(labels), "--manifest", str(manifest),
                  "--audio-dir", str(audio_dir), "--min-sec", "1.0",
                  "--max-sec", "10.0", "--slack", "0"])
check("slicer_rc0", rc == 0)
d0 = sf.info(str(audio_dir / "pdmx_P_000.flac")).duration
d1 = sf.info(str(audio_dir / "pdmx_P_001.flac")).duration
check("seg0_8s", abs(d0 - 8.0) < 0.01, d0)
check("seg1_3s", abs(d1 - 3.0) < 0.01, d1)
check("too_long_skipped", not (audio_dir / "pdmx_P_002.flac").exists())
check("mismatch_skipped", not (audio_dir / "pdmx_Q_000.flac").exists())

print("[4] 续跑:重跑切割器,已有段不重切(seg_resumed 计数)")
rc = slicer.main(["--labels", str(labels), "--manifest", str(manifest),
                  "--audio-dir", str(audio_dir), "--min-sec", "1.0",
                  "--max-sec", "10.0", "--slack", "0"])
check("resume_rc0", rc == 0)

print("[5] s4_fix_tempo 脚本:干跑报告、--apply 钳制+删旧整曲音频")
bad2 = make_midi(tmp / "bad2.mid", first_tempo_bpm=999.0)      # 过快的一样钳
sf.write(str(audio_dir / "pdmx_B.flac"), np.zeros(8000, dtype="float32"), 8000)
mani2 = tmp / "mani2.jsonl"
with open(mani2, "w", encoding="utf-8") as f:
    f.write(json.dumps({"piece_id": "B", "midi_path": str(bad2)}) + "\n")
    f.write(json.dumps({"piece_id": "P", "midi_path": str(m)}) + "\n")
rc = fixer.main(["--manifest", str(mani2), "--audio-dir", str(audio_dir)])
check("fixer_dry_rc0", rc == 0)
check("dry_no_change", tempo_outliers(bad2) == [999.0] and (audio_dir / "pdmx_B.flac").exists())
rc = fixer.main(["--manifest", str(mani2), "--audio-dir", str(audio_dir), "--apply"])
check("fixer_apply_rc0", rc == 0)
check("fast_clamped", tempo_outliers(bad2) == [], tempo_outliers(bad2))
check("stale_audio_deleted", not (audio_dir / "pdmx_B.flac").exists())
check("normal_piece_untouched", tempo_outliers(m) == [] and (audio_dir / "pdmx_P_000.flac").exists())

print("[6]【弱起免疫】anacrusis 曲:score_range 直达速度图,切割正确(网格路径会静默错位)")
# 弱起 1 拍(0.25 全音符)+ 2 个整 4/4 小节,60bpm:IR 小节起点 [0, 0.25, 1.25],总长 2.25 全音符 = 9s。
# 算术网格会给 [0,1,2](整小节假设)且 len/total 双守卫恰好都过 —— 这正是静默毒药;
# score_range 携带 IR 真实位置,免疫此问题。
mp6 = mido.MidiFile(ticks_per_beat=480)
tr6 = mido.MidiTrack(); mp6.tracks.append(tr6)
tr6.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
tr6.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(60.0), time=0))
tr6.append(mido.Message("note_on", note=60, velocity=64, time=0))
tr6.append(mido.Message("note_off", note=60, velocity=0, time=4320))     # 2.25 全音符
mp6.save(str(tmp / "pickup.mid"))
sf.write(str(audio_dir / "pdmx_PU.flac"), np.zeros(9 * 8000, dtype="float32"), 8000)
lb6 = tmp / "l6.jsonl"
with open(lb6, "w", encoding="utf-8") as f:
    f.write(json.dumps({"utt_id": "pdmx_PU_000", "piece_id": "PU", "measure_range": [1, 3],
                        "score_range": [0.25, 2.25], "A2S": "x"}) + "\n")
mani6 = tmp / "m6.jsonl"
with open(mani6, "w", encoding="utf-8") as f:
    f.write(json.dumps({"piece_id": "PU", "midi_path": str(tmp / "pickup.mid")}) + "\n")
rc = slicer.main(["--labels", str(lb6), "--manifest", str(mani6),
                  "--audio-dir", str(audio_dir), "--min-sec", "1.0",
                  "--max-sec", "40.0", "--slack", "0"])
check("pickup_rc0", rc == 0)
d6 = sf.info(str(audio_dir / "pdmx_PU_000.flac")).duration
check("pickup_slice_correct_8s", abs(d6 - 8.0) < 0.01, d6)   # 0.25→2.25 全音符 @60bpm = 1s..9s

print("[7] 同 tick 重复 meta 事件去重(双轨 merge 后拍号/速度各带一份不再插重复小节)")
mp7 = mido.MidiFile(ticks_per_beat=480)
t1 = mido.MidiTrack(); t2 = mido.MidiTrack(); mp7.tracks += [t1, t2]
for tr in (t1, t2):                                          # 两轨都带同样的 meta(常见导出)
    tr.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    tr.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
t1.append(mido.Message("note_on", note=60, velocity=64, time=0))
t1.append(mido.Message("note_off", note=60, velocity=0, time=3840))      # 2 整小节
mp7.save(str(tmp / "dup.mid"))
_, meas7, tot7 = midi_time(tmp / "dup.mid")
check("dup_meta_dedup", meas7 == [F(0), F(1)] and tot7 == F(2), (meas7, tot7))

print(f"\n全部通过: {PASS} 项")
