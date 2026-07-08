"""
S6 MAESTRO(R-S6.1~6.4)。MIDI → AMT 事件 + 流式 zip→FLAC。

【论文明确】offset 用 KeyOff 约定(键释放,非踏板延长);CC64 以 64 为阈值二值化,力度原值。
"""
from __future__ import annotations
import io
from pathlib import Path


def midi_to_events(midi_bytes: bytes, cc64_thresh: int = 64):
    """
    MIDI 字节 → (notes, pedal)。
      notes: [{pitch, on, off, vel}](秒),按 (onset, pitch) 排序。
      pedal: [(sec, bool)],bool=踏板是否踩下(CC64 >= 阈值)。

    KeyOff 约定【论文明确】:note_off 或 note_on(vel=0) 都算键释放。
    曲末仍 open 的音符按曲末时刻收尾(R-S6:不丢音)。
    """
    import mido
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))

    # 绝对秒:逐 tick 累加,tempo 变化实时生效(mido 的 tick2second 需 tempo)
    tempo = 500000                      # 默认 120 BPM
    tpq = mid.ticks_per_beat or 480
    abs_sec = 0.0
    events = []                          # (sec, type, a, b)
    # 合并所有轨到单一时间线(MAESTRO 单轨,但稳妥起见合并)
    for msg in mido.merge_tracks(mid.tracks):
        abs_sec += mido.tick2second(msg.time, tpq, tempo)
        if msg.type == "set_tempo":
            tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            events.append((abs_sec, "on", msg.note, msg.velocity))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            events.append((abs_sec, "off", msg.note, 0))
        elif msg.type == "control_change" and msg.control == 64:
            events.append((abs_sec, "cc64", msg.value, 0))

    notes = []
    open_notes: dict[int, tuple[float, int]] = {}     # pitch -> (on_sec, vel)
    pedal = []
    end_sec = events[-1][0] if events else 0.0
    for sec, typ, a, b in events:
        if typ == "on":
            if a in open_notes:                        # 同音重叠:先收前一个(KeyOff)
                on, vel = open_notes.pop(a)
                notes.append({"pitch": a, "on": on, "off": sec, "vel": vel})
            open_notes[a] = (sec, b)
        elif typ == "off":
            if a in open_notes:
                on, vel = open_notes.pop(a)
                notes.append({"pitch": a, "on": on, "off": sec, "vel": vel})
        elif typ == "cc64":
            pedal.append((sec, a >= cc64_thresh))
    for pitch, (on, vel) in open_notes.items():        # 曲末收尾
        notes.append({"pitch": pitch, "on": on, "off": max(end_sec, on + 0.001), "vel": vel})

    notes.sort(key=lambda n: (n["on"], n["pitch"]))
    return notes, pedal


# ---------------------------------------------------------------- 流式 zip → FLAC(R-S6.1,本地)

def stream_wav_to_flac(zip_path: str, out_dir: str, sr_target: int = 16000,
                       members: list[str] | None = None,
                       progress_every: int = 50):
    """
    R-S6.1【不变量,禁解压全包】:逐成员流式读 wav → 16k mono FLAC 落盘。
    peak 磁盘 = zip + FLAC(~10GB),不落中间 wav。需 soundfile+soxr,本地跑。
    返回 {converted, failures, total_dur_s}。
    """
    import zipfile
    import numpy as np
    import soundfile as sf
    try:
        import soxr
        def _resample(x, sr): return soxr.resample(x, sr, sr_target)
    except Exception:
        import scipy.signal as ss
        def _resample(x, sr):
            return ss.resample(x, int(round(len(x) * sr_target / sr))).astype("float32")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stats = {"converted": 0, "failures": [], "total_dur_s": 0.0}
    with zipfile.ZipFile(zip_path) as zf:
        wavs = members or [n for n in zf.namelist() if n.lower().endswith(".wav")]
        for i, name in enumerate(wavs):
            try:
                with zf.open(name) as f:                # 流式,不解压全包
                    audio, sr = sf.read(io.BytesIO(f.read()), dtype="float32")
                if audio.ndim > 1:
                    audio = audio.mean(axis=1)          # → mono
                if sr != sr_target:
                    audio = _resample(audio, sr)
                rel = Path(name).with_suffix(".flac").name
                dst = out / rel
                sf.write(str(dst), audio, sr_target, format="FLAC")
                stats["converted"] += 1
                stats["total_dur_s"] += len(audio) / sr_target
            except Exception as e:
                stats["failures"].append({"member": name, "reason": f"{type(e).__name__}:{str(e)[:80]}"})
            if progress_every and (i + 1) % progress_every == 0:
                print(f"  [{i+1}/{len(wavs)}] converted={stats['converted']} fail={len(stats['failures'])}")
    return stats
