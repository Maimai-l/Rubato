"""S6 MAESTRO 逻辑测试(MIDI→AMT 事件,沙盒可验证部分)。运行: python tests_maestro.py"""
import sys, io
sys.path.insert(0, ".")
from rubato.data.maestro import midi_to_events

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

def make_midi(events):
    """用 mido 造测试 MIDI。events: [(type, note/cc, val, delta_ticks)]。"""
    import mido
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))  # 120 BPM
    for typ, a, b, dt in events:
        if typ == "on":
            track.append(mido.Message("note_on", note=a, velocity=b, time=dt))
        elif typ == "off":
            track.append(mido.Message("note_off", note=a, velocity=0, time=dt))
        elif typ == "cc":
            track.append(mido.Message("control_change", control=a, value=b, time=dt))
    buf = io.BytesIO()
    mid.save(file=buf)
    return buf.getvalue()

print("[1] 基本 note on/off → 事件")
# 480 ticks/beat default, 120BPM → 1 beat = 0.5s
mb = make_midi([("on", 60, 80, 0), ("off", 60, 0, 480)])
notes, pedal = midi_to_events(mb)
check("one_note", len(notes) == 1, notes)
check("pitch_correct", notes[0]["pitch"] == 60)
check("velocity_preserved", notes[0]["vel"] == 80)
check("duration_half_sec", abs(notes[0]["off"] - notes[0]["on"] - 0.5) < 0.01,
      f"{notes[0]['off'] - notes[0]['on']}")

print("[2] KeyOff 约定:velocity=0 的 note_on 算释放")
mb = make_midi([("on", 62, 70, 0), ("on", 62, 0, 240)])   # note_on vel=0 = off
notes, _ = midi_to_events(mb)
check("velzero_is_off", len(notes) == 1 and notes[0]["pitch"] == 62, notes)

print("[3] CC64 踏板阈值(≥64 = down)")
mb = make_midi([("cc", 64, 100, 0), ("cc", 64, 30, 240), ("on", 60, 80, 0), ("off", 60, 0, 240)])
notes, pedal = midi_to_events(mb, cc64_thresh=64)
check("pedal_events", len(pedal) == 2, pedal)
check("pedal_down_100", pedal[0][1] == True, pedal[0])    # 100 >= 64
check("pedal_up_30", pedal[1][1] == False, pedal[1])      # 30 < 64

print("[4] 曲末未释放的音符按曲末收尾")
mb = make_midi([("on", 64, 80, 0), ("on", 67, 80, 240)])  # 两个都不 off
notes, _ = midi_to_events(mb)
check("unreleased_closed", len(notes) == 2, notes)
check("all_have_offset", all(n["off"] > n["on"] for n in notes))

print("[5] 和弦(同时 onset)")
mb = make_midi([("on", 60, 80, 0), ("on", 64, 80, 0), ("on", 67, 80, 0),
                ("off", 60, 0, 480), ("off", 64, 0, 0), ("off", 67, 0, 0)])
notes, _ = midi_to_events(mb)
check("chord_three_notes", len(notes) == 3, len(notes))
check("chord_same_onset", len(set(n["on"] for n in notes)) == 1)
check("sorted_by_pitch", [n["pitch"] for n in notes] == [60, 64, 67])

print("[6] 事件流可喂 segment_amt")
from rubato.data.segment import segment_amt, make_amt_label
# 造一段较长的音符流
events = []
for i in range(30):
    events += [("on", 60 + i % 12, 80, 0 if i else 0), ("off", 60 + i % 12, 0, 240)]
mb = make_midi(events)
notes, pedal = midi_to_events(mb)
check("many_notes", len(notes) == 30, len(notes))
wins = segment_amt(notes, pedal)
check("segments_produced", len(wins) >= 1, len(wins))
# AMT 标签合法
if wins:
    lab, f = make_amt_label(wins[0][0], wins[0][1])
    check("amt_label_valid", "AMT" in lab, f)

print(f"\n全部通过: {PASS} 项")
print("注:zipfile 流式转 FLAC(stream_wav_to_flac)需真实 zip+ffmpeg,本地验证;")
print("    MIDI→AMT 事件逻辑(KeyOff/CC64/曲末收尾)沙盒已验证。")
