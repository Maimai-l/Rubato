"""MAESTRO AMT 切窗管线回归测试:s6_amt_windows 端到端 + assemble win 直通 + load_audio 按窗读。
运行: python tests_amt_windows.py
"""
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, ".")
import mido
import numpy as np
import soundfile as sf

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

print("[1] load_audio 按窗读:只取整曲的 [t0,t1],不载全曲")
from rubato.data.dataset import load_audio
whole = tmp / "w.flac"
sig = (np.arange(5 * 8000, dtype="float32") / (5 * 8000)) * 0.8   # 单调爬升的可识别信号
sf.write(str(whole), sig, 8000)
a = load_audio(str(whole), sr_target=8000, win=[1.0, 3.0])
check("win_len", abs(len(a) - 2 * 8000) <= 2, len(a))
check("win_content", abs(float(a[0]) - float(sig[8000])) < 1e-3, (a[0], sig[8000]))
full = load_audio(str(whole), sr_target=8000)
check("no_win_full", abs(len(full) - 5 * 8000) <= 2, len(full))

print("[2] assemble:行带 win → utt 带 win 且 dur_s=窗长(不是整曲时长)")
from rubato.data.assemble import assemble
lbl = tmp / "m.jsonl"
with open(lbl, "w", encoding="utf-8") as f:
    f.write(json.dumps({"utt_id": "maestro_x_000", "midi_file": "a/b.midi",
                        "win": [10.0, 28.5], "AMT": "(A)a", "split": "train"}) + "\n")
    f.write(json.dumps({"utt_id": "maestro_x_001", "midi_file": "a/b.midi",
                        "AMT": "(A)a", "split": "train"}) + "\n")   # 无 win:整曲行为不变
utts, labels, stats = assemble([{"path": str(lbl), "kind": "maestro", "domain": "real"}],
                               lambda uid, kind, row: ("whole.flac", 300.0))
u0 = next(u for u in utts if u["utt_id"] == "maestro_x_000")
u1 = next(u for u in utts if u["utt_id"] == "maestro_x_001")
check("win_passthrough", u0.get("win") == [10.0, 28.5], u0)
check("win_dur", abs(u0["dur_s"] - 18.5) < 1e-6, u0["dur_s"])
check("no_win_whole_dur", u1["dur_s"] == 300.0 and "win" not in u1, u1)

print("[3] s6_amt_windows 端到端:zip 里的演奏 MIDI → 12–25s 窗 AMT 行")
mid = mido.MidiFile(ticks_per_beat=480)
tr = mido.MidiTrack(); mid.tracks.append(tr)
tr.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))     # 120bpm:0.5s/拍
for i in range(60):                                                # 60 音,每 0.5s 一个,共 30s
    tr.append(mido.Message("note_on", note=60 + (i % 12), velocity=70, time=0 if i == 0 else 480))
    tr.append(mido.Message("note_off", note=60 + (i % 12), velocity=0, time=384))
    tr.append(mido.Message("note_on", note=60 + (i % 12), velocity=0, time=0))   # 占位不发声
buf = io.BytesIO(); mid.save(file=buf)
zpath = tmp / "maestro.zip"
with zipfile.ZipFile(zpath, "w") as z:
    z.writestr("maestro-v3.0.0/2018/perf1.midi", buf.getvalue())
csvp = tmp / "maestro.csv"
csvp.write_text("midi_filename,audio_filename,split\n"
                "2018/perf1.midi,2018/perf1.wav,train\n", encoding="utf-8")
import scripts.s6_amt_windows as s6w
out = tmp / "win.jsonl"
rc = s6w.main(["--zip", str(zpath), "--csv", str(csvp), "--out", str(out)])
check("s6w_rc0", rc == 0)
rows = [json.loads(l) for l in open(out, encoding="utf-8") if l.strip()]
check("windows_made", len(rows) >= 2, len(rows))
check("amt_nonempty", all(r["AMT"] for r in rows), rows[:1])
check("win_bounds_valid", all(0 <= r["win"][0] < r["win"][1] for r in rows), rows[:1])
check("win_len_in_range", all(5.0 <= r["win"][1] - r["win"][0] <= 40.0 for r in rows),
      [(r["win"][1] - r["win"][0]) for r in rows])
check("utt_ids_unique", len({r["utt_id"] for r in rows}) == len(rows))
check("consecutive_windows", all(abs(rows[i + 1]["win"][0] - rows[i]["win"][1]) < 1e-6
                                 for i in range(len(rows) - 1)), [r["win"] for r in rows])

print(f"\n全部通过: {PASS} 项")
