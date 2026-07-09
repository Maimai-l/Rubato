"""
S5 表现性渲染驱动 —— 调【你本地的 VirtuosoNet】(不是重写它),按 VIRTUOSO_GUIDE 的 CLI/CSV。

诊断:SPEC 设计了 S5(R-S5.1-5.9)但从未落地脚本,历史上只有 S4 直排 —— 这就是"没有 VN 管线"的原因。
本脚本补上:每曲用 `virtuoso <xml> --csv` 产【表现性演奏 MIDI + 音符级 CSV】,
CSV 的 (xml_idx,start,end,pitch,velocity) 给出音符↔演奏秒(GUIDE §2.4,即 SPEC R-S5.6 主路径),
据此建 tmap;VN 的演奏 MIDI 直接渲成音频。音频与 TAST 同一 tmap ⇒ 天然对齐。

VN 主路径(默认)。humanize 只是 SPEC R-S5.9 的失败兜底(VN 超时/非零退出/无 CSV 时才用),
不是与 VN 并列的选项 —— 你有 VN,VN 就是管线。

用法(执行端,py312 环境已装 virtuoso):
  python scripts/s5_vn_render.py \
    --out-labels work/pdmx_perf_labels.jsonl --out-corpus work/a2s_corpus.txt \
    --out-audio-dir work/pdmx_audio
  # 想只在 VN 挂掉时兜底、或先干验:见 --allow-humanize-fallback / --limit。
"""
from __future__ import annotations
import argparse
import csv as _csv
import json
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from rubato.platform import read_jsonl
from rubato.intermo.partitura_adapter import part_to_ir
from rubato.data.segment import segment_score, make_labels
from rubato.data.nasap_timemap import build_timemap
from rubato.render.core import (
    render_midi_to_wav44, finalize, assign_source_and_preset,
)

ROOT = Path(r"D:\vscode_projects\ee_download")


# ---------------------------------------------------------------- VN 调用(GUIDE §2/§4)

def vn_infer(xml_path: str, composer: str, out_mid: str, timeout_s: float = 300.0) -> str | None:
    """
    调本地 virtuoso CLI 产表现性演奏 MIDI + CSV(GUIDE §2.4)。成功返回 CSV 路径,失败返回 None。
    R-S5.2:--pedal(bool_pedal) --no-plot;--csv 导出音符级时间。R-S5.9:超时/非零退出 → None。
    """
    cmd = [r"D:\ProgramData\envs\py312\Scripts\virtuoso.exe", xml_path, "-c", composer, "--pedal", "--no-plot", "--csv", "-o", out_mid]
    try:
        subprocess.run(cmd, check=True, timeout=timeout_s,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    # GUIDE §2.4:CSV 与 MIDI 同级,名为 {midi文件名}_midi_notes.csv (不剥 .mid 后缀)
    csv_path = str(out_mid) + "_midi_notes.csv"
    return csv_path if Path(csv_path).exists() and Path(out_mid).exists() else None


def csv_to_tmap(csv_path: str, part):
    """
    VN 的 CSV(xml_idx,start,end,pitch,velocity)→ 演奏 tmap(R-S5.6 主路径)。
    xml_idx = 音符在 MusicXML 的序号;对上 partitura 音符的乐谱起点(全音符单位)→ 锚点。
    复用 nasap_timemap.build_timemap(同样是"乐谱位置↔演奏秒"+单调化),含 pitch 一致性抽检。
    返回 (tmap, diag) 或 (None, diag)。
    """
    import numpy as np
    notes = list(part.notes_tied if hasattr(part, "notes_tied") else part.notes)
    qmap = np.atleast_2d(part.quarter_durations())
    dpq = int(qmap[0][1]) if qmap.size else 480
    whole = dpq * 4
    xmlid_pos, alignment = {}, []
    mismatch = 0
    with open(csv_path, encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            try:
                idx = int(r["xml_idx"]); start = float(r["start"]); pitch = int(r["pitch"])
            except (KeyError, ValueError):
                continue
            if idx < 0 or idx >= len(notes):
                continue
            n = notes[idx]
            nid = str(idx)
            xmlid_pos[nid] = Fraction(int(n.start.t), whole)
            alignment.append({"xml_id": nid, "perf_onset_sec": start, "pitch": pitch})
            npitch = n.midi_pitch if hasattr(n, "midi_pitch") else None
            if npitch is not None and npitch != pitch:
                mismatch += 1
    diag = {"anchors_in": len(alignment), "pitch_mismatch": mismatch}
    if len(alignment) < 2:
        return None, diag
    tmap, stats = build_timemap(alignment, xmlid_pos)
    diag.update(stats)
    return tmap, diag


def render_midi(midi_path: str, utt_id: str, sources_cfg, presets_cfg, out_path: str):
    """VN 演奏 MIDI → 44.1k wav → 预设链 → 16k opus 落盘(复用 S4 渲染链)。"""
    import tempfile
    src_id, preset_id = assign_source_and_preset(utt_id, sources_cfg, presets_cfg)
    source = sources_cfg["sources"][src_id]
    preset = presets_cfg["presets"][preset_id] if "presets" in presets_cfg else {"id": preset_id}
    with tempfile.TemporaryDirectory() as td:
        wav = str(Path(td) / "r.wav")
        render_midi_to_wav44(midi_path, source, sources_cfg, wav, utt_id=utt_id)
        finalize(wav, preset, sources_cfg, presets_cfg, utt_id, out_path)
    return out_path


def _slice_audio(whole_path: str, t0: float, t1: float, out_path: str) -> str | None:
    """从整曲音频切 [t0,t1] 秒(段级 utt)。返回路径或 None。"""
    import soundfile as sf
    try:
        audio, sr = sf.read(whole_path, dtype="float32")
    except Exception:
        return None
    a, b = max(0, int(t0 * sr)), min(len(audio), int(t1 * sr))
    if b - a < int(0.2 * sr):
        return None
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    # soundfile 不支持 .opus 写;统一用 .wav 落盘(后续 build_dataset 的 resolve_audio 会搜 .wav)
    wav_path = str(Path(out_path).with_suffix('.wav'))
    sf.write(wav_path, audio[a:b], sr)
    return wav_path


def run(manifest, sources_cfg, presets_cfg, out_labels, out_corpus, out_audio_dir,
        allow_humanize_fallback=False, seed=20260706, limit=None):
    import partitura
    pieces = list(read_jsonl(manifest))
    if limit:
        pieces = pieces[:limit]
    out_audio_dir = Path(out_audio_dir); out_audio_dir.mkdir(parents=True, exist_ok=True)
    label_fh = open(out_labels, "a", encoding="utf-8") if out_labels else None
    corpus_fh = open(out_corpus, "a", encoding="utf-8") if out_corpus else None
    rep = {"pieces": len(pieces), "vn_ok": 0, "vn_fail": 0, "humanized": 0,
           "utts": 0, "tast": 0, "failures": []}
    t0 = time.time()
    for i, piece in enumerate(pieces):
        pid = piece.get("piece_id", f"p{i}")
        composer = piece.get("vn", {}).get("composer_used") or piece.get("composer") or "Beethoven"
        xml_rel = piece.get("xml_norm") or piece.get("xml_raw")
        if not xml_rel:
            continue
        xml_path = xml_rel if Path(xml_rel).is_absolute() else str(ROOT / "work" / "xml_norm" / xml_rel)
        try:
            s = partitura.load_musicxml(xml_path)
            part = s.parts[0] if hasattr(s, "parts") and s.parts else s
            ir = part_to_ir(part)
        except Exception as e:
            rep["failures"].append({"piece_id": pid, "reason": f"load:{type(e).__name__}"})
            continue

        # 整曲 VN 推理(R-S5.1:CLI 每曲一次;要复用模型实例可改 InferenceModel,见 GUIDE §5)
        perf_mid = str(out_audio_dir / f"{pid}_perf.mid")
        csv_path = vn_infer(xml_path, composer, perf_mid)
        tmap = None
        if csv_path:
            tmap, diag = csv_to_tmap(csv_path, part)
        if tmap is None:
            rep["vn_fail"] += 1
            if not allow_humanize_fallback:
                rep["failures"].append({"piece_id": pid, "reason": "vn_no_tmap"})
                continue
            from rubato.render.humanize import humanize_timemap
            tmap = humanize_timemap(ir, seed=seed, piece_id=pid)   # R-S5.9 兜底
            rep["humanized"] += 1
            perf_mid = None                                        # 无 VN MIDI,退化(需 humanize 渲染,略)
        else:
            rep["vn_ok"] += 1

        # 整曲渲染(VN 演奏 MIDI → 音频),再按段切
        whole_audio = str(out_audio_dir / f"{pid}_whole.opus")
        if perf_mid:
            try:
                render_midi(perf_mid, pid, sources_cfg, presets_cfg, whole_audio)
            except Exception as e:
                rep["failures"].append({"piece_id": pid, "reason": f"render:{type(e).__name__}"})
                continue

        segs = segment_score(ir, min_measures=2, max_measures=16, max_sec=40.0, sec_per_whole=2.0)
        bounds = [m.start for m in ir.measures] + [ir.score_end]
        for si, (sub_ir, (a, b)) in enumerate(segs):
            utt_id = f"pdmxperf_{pid}_{si:03d}"
            score_off = bounds[a] if a < len(bounds) else bounds[-1]
            labels, _ = make_labels(sub_ir, "human", tmap=tmap, score_offset=score_off)
            if not labels.get("A2S"):
                continue
            seg_audio = None
            if perf_mid:
                t_lo = float(tmap(bounds[a])); t_hi = float(tmap(bounds[min(b, len(bounds)-1)]))
                seg_audio = _slice_audio(whole_audio, t_lo, t_hi,
                                         str(out_audio_dir / f"{utt_id}.opus"))
            row = {"utt_id": utt_id, "piece_id": pid, "kind": "human",
                   "audio_path": seg_audio,
                   **{k: labels.get(k) for k in ("A2S", "A2S_lite", "TAST")}, "AMT": None}
            rep["utts"] += 1
            if labels.get("TAST"):
                rep["tast"] += 1
            if label_fh:
                label_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            if corpus_fh:
                for d in ("A2S", "A2S_lite"):
                    if row.get(d):
                        corpus_fh.write(row[d].strip() + "\n")
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(pieces)}] vn_ok={rep['vn_ok']} vn_fail={rep['vn_fail']} "
                  f"utts={rep['utts']} tast={rep['tast']} ({(i+1)/(time.time()-t0):.2f} pc/s)")
    if label_fh:
        label_fh.close()
    if corpus_fh:
        corpus_fh.close()
    rep["elapsed_s"] = round(time.time() - t0, 1)
    print(f"\nDONE: vn_ok={rep['vn_ok']} vn_fail={rep['vn_fail']} humanized={rep['humanized']} "
          f"utts={rep['utts']} TAST={rep['tast']}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--sources", default="configs/sources.yaml")
    ap.add_argument("--presets", default="configs/recording_presets.yaml")
    ap.add_argument("--out-labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--out-corpus", default=str(ROOT / "work" / "a2s_corpus.txt"))
    ap.add_argument("--out-audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--allow-humanize-fallback", action="store_true",
                    help="仅在 VN 失败/超时的曲上兜底(SPEC R-S5.9);默认关,VN 失败即计入 failures")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    sources_cfg = yaml.safe_load(open(args.sources, encoding="utf-8"))
    presets_cfg = yaml.safe_load(open(args.presets, encoding="utf-8"))
    run(args.manifest, sources_cfg, presets_cfg, args.out_labels, args.out_corpus,
        args.out_audio_dir, allow_humanize_fallback=args.allow_humanize_fallback,
        limit=args.limit or None)


if __name__ == "__main__":
    main()
