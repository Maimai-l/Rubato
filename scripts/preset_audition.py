"""
预设试听套件 —— 混响/噪底的数值由【用户的耳朵】定,不由代码拍脑袋。

背景(用户实听):背景 IR 糊、吵,混响太大。两个来源已在代码层确认:
  ① apply_preset 旧混音按"峰值"对齐湿声 → 同一 wet 数值听感远比标称湿(DSP bug,已修为能量归一);
  ② 预设配置本身偏湿(~57% 权重落在 wet≥0.40)+ 噪底偏响(-44~-46 dBFS)。
①已修;②的新数值需要用户听过再定 —— 本脚本产出一套对照音频:

对每个预设 × 一个参考曲段,产 3 个文件:
  <preset>__legacy.wav   旧混音(现网音频的听感基线)
  <preset>__fixed.wav    新混音(能量归一,同 wet 数值)
  <preset>__fixed_w70.wav 新混音 + RUBATO_WET_SCALE=0.7(候选整体降湿档)
用户逐组听,回复形如:"fixed 就够 / 全局 0.7 / p09 p12 p13 单独再降 / 噪底统一 -6dB"。

用法(执行端):
  python scripts/preset_audition.py                 # 用 manifest 第一首曲;或 --midi 指定
  python scripts/preset_audition.py --source salamander
输出:reports/preset_audition/ ;跑完把文件夹给用户听。
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl

ROOT = Path(r"D:\vscode_projects\ee_download")
REPO_ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="逐预设产 legacy/fixed/fixed_w70 对照音频,供用户实听定数")
    ap.add_argument("--midi", default="", help="参考 MIDI;缺省取 manifest 第一首")
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--sources", default=str(REPO_ROOT / "configs" / "sources.yaml"))
    ap.add_argument("--presets", default=str(REPO_ROOT / "configs" / "recording_presets.yaml"))
    ap.add_argument("--source", default="", help="音源 id;缺省取配置第一个")
    ap.add_argument("--seconds", type=float, default=20.0, help="试听片段长度")
    ap.add_argument("--out", default=str(ROOT / "reports" / "preset_audition"))
    args = ap.parse_args(argv)

    import numpy as np
    import soundfile as sf
    import yaml
    from rubato.render.core import render_midi_to_wav44
    from rubato.render.irgen import apply_preset

    with open(args.sources, "r", encoding="utf-8") as f:
        sources_cfg = yaml.safe_load(f)
    with open(args.presets, "r", encoding="utf-8") as f:
        presets_cfg = yaml.safe_load(f)

    midi = args.midi
    if not midi:
        for p in read_jsonl(args.manifest):
            if p.get("midi_path"):
                midi = p["midi_path"]
                break
    sid = args.source or next(iter(sources_cfg["sources"]))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"参考曲: {midi}\n音源: {sid}\n渲干声(一次)…")
    dry44 = out / "_dry44.wav"
    render_midi_to_wav44(midi, sources_cfg["sources"][sid], sources_cfg, str(dry44), utt_id="audition")
    audio, sr = sf.read(str(dry44), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    try:
        import soxr
        audio16 = soxr.resample(audio, sr, 16000)
    except Exception:
        import scipy.signal as ss
        audio16 = ss.resample_poly(audio, 16000, sr).astype(np.float32)
    audio16 = audio16[: int(args.seconds * 16000)].astype(np.float32)
    sf.write(str(out / "_00_dry.wav"), audio16, 16000)

    n = 0
    for pid, preset in presets_cfg["presets"].items():
        for tag, mode, scale in (("legacy", "legacy", "1.0"),
                                 ("fixed", "energy", "1.0"),
                                 ("fixed_w70", "energy", "0.7")):
            os.environ["RUBATO_WET_SCALE"] = scale
            y = apply_preset(audio16, preset, sr=16000, seed=7, preset_id=pid, wet_mode=mode)
            sf.write(str(out / f"{pid}__{tag}.wav"), y, 16000)
            n += 1
    os.environ.pop("RUBATO_WET_SCALE", None)
    try:
        dry44.unlink()
    except OSError:
        pass
    print(f"\n完成:{n} 个对照文件 → {out}")
    print("【给用户】每个预设听 legacy(现网基线)/ fixed(修混音)/ fixed_w70(再降湿 30%),")
    print("回复:哪个档可接受 + 哪些预设(如 p09/p12/p13)要单独再降 + 噪底要不要统一降(如 -6dB)。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
