"""
S5 表现性渲染驱动(此前只在 SPEC 设计、从未实现)。补上 PDMX 的【表现性音频 + TAST】。

【为什么必须有它】S4 只产恒速直排音频 → PDMX 只能供 A2S/A2S_lite,TAST 恒 null,
模型学不到"从有表现力的演奏里恢复乐谱"。本脚本按 SPEC R-S5:
  - 每段取一份【演奏】(引擎 humanize 兜底 / VN 主路径)→ 得 events + tmap;
  - events→MIDI→渲染音频(复用 S4 的 render_midi_to_wav44 + finalize);
  - make_labels(段, tmap) → A2S/A2S_lite/【TAST】,时间戳与音频同一 tmap ⇒ 天然对齐。
关键不变量:**TAST 的时间戳与音频必须同源**(同一 tmap)。所以 TAST 只能在这里(渲染处)产,
不能在纯文本的 s5_pdmx_a2s_labels(那产的是恒速估算,与真实音频不匹配 → 训练噪声)。

引擎:
  --engine humanize (默认,纯 CPU,SPEC R-S5.7 兜底):OU 速度 + onset/力度抖动,tmap 是真值。
  --engine vn       (SPEC R-S5.1-5.6 主路径,需 py312 的 VirtuosoNet):见 vn_perform() 的 [EXECUTOR] 钩子。
                     VN 失败/超时按 R-S5.9 自动回落 humanize(不重试超过 1 次)。

用法(执行端):
  python scripts/s5_vn_render.py --engine humanize \
    --out-labels work/pdmx_perf_labels.jsonl --out-corpus work/a2s_corpus.txt \
    --out-audio-dir work/pdmx_audio
产物:每段一个音频 work/pdmx_audio/<utt_id>.flac + 标签行(含 audio_path)+ A2S/A2S_lite 语料追加。
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import traceback
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from rubato.platform import read_jsonl
from rubato.intermo.partitura_adapter import part_to_ir
from rubato.data.segment import segment_score, make_labels
from rubato.render.humanize import humanize_events
from rubato.render.core import (
    events_to_midi, render_midi_to_wav44, finalize, assign_source_and_preset,
)

ROOT = Path(r"D:\vscode_projects\ee_download")


def vn_perform(sub_ir, utt_id: str):
    """
    【EXECUTOR】VirtuosoNet 主路径(SPEC R-S5.1-5.6)。构造一次 InferenceModel、循环 infer_xml
    (R-S5.1:绝不每曲重载 172MB),midi_decode_options={bool_pedal,no_plot,save_csv}(R-S5.2)。
    save_csv 每行↔乐谱音符含演奏 onset → 构成 time_map(R-S5.6 主路径)。
    返回 (events, pedal, tmap) 或 None(失败/无映射 → 调用方回落 humanize,R-S5.9)。
    未接 VN 时返回 None,全程走 humanize。
    """
    return None


def perform(sub_ir, utt_id: str, engine: str, seed: int):
    """取一段的演奏 (events, pedal, tmap, used)。engine=vn 优先,失败回落 humanize(R-S5.9)。"""
    if engine == "vn":
        try:
            got = vn_perform(sub_ir, utt_id)
        except Exception:
            got = None
        if got is not None:
            ev, ped, tm = got
            return ev, ped, tm, "vn"
    ev, ped, tm = humanize_events(sub_ir, base_sec_per_whole=2.0, seed=seed, piece_id=utt_id)
    return ev, ped, tm, "humanize"


def render_events(events, pedal, utt_id, sources_cfg, presets_cfg, out_audio_dir: Path):
    """events → MIDI → 44.1k wav → 预设链 → 16k opus/flac。返回落盘路径或 None(渲染失败)。"""
    import tempfile
    out_audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_audio_dir / f"{utt_id}.opus"
    with tempfile.TemporaryDirectory() as td:
        mid = str(Path(td) / f"{utt_id}.mid")
        wav = str(Path(td) / f"{utt_id}.wav")
        events_to_midi(events, pedal, mid)
        src_id, preset_id = assign_source_and_preset(utt_id, sources_cfg, presets_cfg)
        source = sources_cfg["sources"][src_id]
        preset = presets_cfg["presets"][preset_id] if "presets" in presets_cfg \
            else {"id": preset_id}
        render_midi_to_wav44(mid, source, sources_cfg, wav, utt_id=utt_id)
        finalize(wav, preset, sources_cfg, presets_cfg, utt_id, str(out_path))
    return str(out_path)


def run(manifest, sources_cfg, presets_cfg, out_labels, out_corpus, out_audio_dir,
        engine="humanize", seed=20260706, limit=None):
    pieces = list(read_jsonl(manifest))
    if limit:
        pieces = pieces[:limit]
    out_audio_dir = Path(out_audio_dir)
    label_fh = open(out_labels, "a", encoding="utf-8") if out_labels else None
    corpus_fh = open(out_corpus, "a", encoding="utf-8") if out_corpus else None
    rep = {"pieces": len(pieces), "utts": 0, "tast": 0, "render_fail": 0,
           "engine": engine, "vn_used": 0, "humanize_used": 0, "failures": []}
    t0 = time.time()
    for i, piece in enumerate(pieces):
        pid = piece.get("piece_id", f"p{i}")
        xml_rel = piece.get("xml_norm") or piece.get("xml_raw")
        if not xml_rel:
            continue
        xml_path = xml_rel if Path(xml_rel).is_absolute() else str(ROOT / "work" / "xml_norm" / xml_rel)
        try:
            import partitura
            s = partitura.load_musicxml(xml_path)
            part = s.parts[0] if hasattr(s, "parts") and s.parts else s
            ir = part_to_ir(part)
            segs = segment_score(ir, min_measures=2, max_measures=16, max_sec=40.0, sec_per_whole=2.0)
        except Exception as e:
            rep["failures"].append({"piece_id": pid, "reason": f"{type(e).__name__}:{str(e)[:80]}"})
            continue
        for si, (sub_ir, (a, b)) in enumerate(segs):
            utt_id = f"pdmxperf_{pid}_{si:03d}"
            try:
                events, pedal, tmap, used = perform(sub_ir, utt_id, engine, seed)
                rep["vn_used" if used == "vn" else "humanize_used"] += 1
                audio_path = render_events(events, pedal, utt_id, sources_cfg, presets_cfg, out_audio_dir)
            except Exception as e:
                rep["render_fail"] += 1
                rep["failures"].append({"utt_id": utt_id, "reason": f"render:{type(e).__name__}:{str(e)[:60]}"})
                continue
            labels, fails = make_labels(sub_ir, "human", tmap=tmap, score_offset=Fraction(0))
            if not labels.get("A2S"):
                continue
            row = {"utt_id": utt_id, "piece_id": pid, "kind": "human",
                   "audio_path": audio_path,
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
        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(pieces)}] utts={rep['utts']} tast={rep['tast']} "
                  f"({(i+1)/(time.time()-t0):.1f} pieces/s)")
    if label_fh:
        label_fh.close()
    if corpus_fh:
        corpus_fh.close()
    rep["elapsed_s"] = round(time.time() - t0, 1)
    print(f"\nDONE engine={engine}: utts={rep['utts']} TAST={rep['tast']} "
          f"render_fail={rep['render_fail']}")
    print(f"  audio → {out_audio_dir}\n  labels → {out_labels}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["humanize", "vn"], default="humanize")
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--sources", default="configs/sources.yaml")
    ap.add_argument("--presets", default="configs/recording_presets.yaml")
    ap.add_argument("--out-labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--out-corpus", default=str(ROOT / "work" / "a2s_corpus.txt"))
    ap.add_argument("--out-audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    sources_cfg = yaml.safe_load(open(args.sources, encoding="utf-8"))
    presets_cfg = yaml.safe_load(open(args.presets, encoding="utf-8"))
    run(args.manifest, sources_cfg, presets_cfg, args.out_labels, args.out_corpus,
        args.out_audio_dir, engine=args.engine, limit=args.limit or None)


if __name__ == "__main__":
    main()
