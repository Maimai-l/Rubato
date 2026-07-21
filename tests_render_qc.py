"""
audit_render_qc 的判决性测试:合成一正常曲 + 一截断曲,脚本必须抓到截断、写出报告。
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np


def _make_midi(path: Path, dur_s: float):
    import mido
    mid = mido.MidiFile()
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.Message("note_on", note=60, velocity=64, time=0))
    # 500000 us/beat 缺省,480 tick/beat → dur_s 秒 = dur_s*960 tick
    tr.append(mido.Message("note_off", note=60, velocity=0, time=int(dur_s * 960)))
    mid.save(str(path))


def _make_flac(path: Path, dur_s: float):
    import soundfile as sf
    t = np.zeros(int(dur_s * 16000), dtype=np.float32)
    sf.write(str(path), t, 16000)


def test_truncation_caught_and_report_written():
    tmp = Path(tempfile.mkdtemp(prefix="qc_"))
    whole = tmp / "whole"
    whole.mkdir()
    rows = []
    for pid, midi_s, audio_s in (("okpiece", 10.0, 10.3), ("cutpiece", 30.0, 12.0)):
        _make_midi(tmp / f"{pid}.mid", midi_s)
        _make_flac(whole / f"pdmx_{pid}.flac", audio_s)
        rows.append({"piece_id": pid, "midi_path": str(tmp / f"{pid}.mid")})
    man = tmp / "man.jsonl"
    man.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    # 报告写进真实 repo reports/?不行 —— 测试要隔离:用环境把 ROOT 指走不现实,
    # 改为直接跑脚本后检查 stdout(报告行同样打印)。
    out = subprocess.run(
        [sys.executable, "scripts/audit_render_qc.py",
         "--manifest", str(man), "--whole-dir", str(whole),
         "--maestro-dir", str(tmp / "nope")],
        capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    text = out.stdout
    assert "疑似截断" in text and "1 曲" in text, text
    assert "cutpiece" in text, "截断曲没被点名"
    assert "okpiece" not in text.split("疑似截断")[1][:400], "正常曲被误报"
    assert "查=2" in text
    assert "maestro_audio 目录不存在" in text


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            t0 = time.time()
            try:
                fn()
                print(f"  ok {name} ({time.time() - t0:.1f}s)")
            except Exception as e:
                fails += 1
                print(f"  FAIL {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if fails else 0)
