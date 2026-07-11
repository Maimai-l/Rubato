"""
S4 段音频切割 —— 用【渲染所用 MIDI 自己的速度图】把整曲音频切成与文本标签对齐的段音频。

背景:S4 渲的是整曲(pdmx_{pid}.opus),而训练配对(build_dataset.resolve_audio)期望
每段一个音频 pdmx_{pid}_{si}.flac —— 这一环此前【没有实现】;且若按恒速 2s/全音符换算段边界,
除恰好 120bpm 的曲外每段都切错位置(标签污染)。本脚本用 rubato.data.midi_time 从 MIDI 提取
真实 set_tempo 速度图 + time_signature 小节网格,按标签行的 measure_range 精确切割。

对齐保障(不静默):标签的小节索引超出 MIDI 小节网格(如 MIDI 展开了反复)→ 该曲跳过并计
structure_mismatch;段真实时长越界(<min-sec / >max-sec+slack,慢曲超训练窗)→ 该段跳过并计数。
跳过的段不会有音频文件,assemble 时计入 no_audio,可见、可追。

用法(执行端,S4 渲染完成后):
  python scripts/s4_slice_segments.py --limit 20     # 冒烟:先 20 曲,看 sliced/skip 计数
  python scripts/s4_slice_segments.py                # 全量;已存在的段 flac 自动跳过(可续跑)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl
from rubato.data.midi_time import midi_time

ROOT = Path(r"D:\vscode_projects\ee_download")


def _read_audio(path):
    import soundfile as sf
    return sf.read(str(path), dtype="float32")


def _write_flac(path, audio, sr):
    import soundfile as sf
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr, format="FLAC")


def _find_whole(audio_dir: Path, pid: str):
    for ext in (".opus", ".flac", ".wav"):
        p = audio_dir / f"pdmx_{pid}{ext}"
        if p.exists():
            return p
    return None


def slice_piece(pid: str, rows: list[dict], midi_path: str, audio_dir: Path, out_dir: Path,
                min_sec: float, max_sec: float, st: dict):
    whole = _find_whole(audio_dir, pid)
    if whole is None:
        st["no_whole_audio"] += 1
        return
    try:
        tmap, measures, total = midi_time(midi_path)
    except Exception:
        st["midi_fail"] += 1
        return
    todo = [r for r in rows
            if not (out_dir / f"{r['utt_id']}.flac").exists()]     # 已切过的段跳过(续跑)
    st["seg_resumed"] += len(rows) - len(todo)
    if not todo:
        return
    # 对齐校验:标签小节索引必须落在 MIDI 小节网格内(b 允许 == len,表示切到曲尾)
    n = len(measures)
    if any(r["measure_range"][1] > n or r["measure_range"][0] >= n for r in todo):
        st["structure_mismatch"] += 1       # MIDI 展开反复/结构不一致 → 整曲跳过,绝不切错位
        return
    try:
        audio, sr = _read_audio(whole)      # 整曲只读一次
    except Exception:
        st["audio_read_fail"] += 1
        return
    for r in todo:
        a, b = r["measure_range"]
        t0 = float(tmap(measures[a]))
        t1 = float(tmap(measures[b])) if b < n else float(tmap(total))
        dur = t1 - t0
        if dur < min_sec:
            st["seg_too_short"] += 1
            continue
        if dur > max_sec:
            st["seg_too_long"] += 1         # 慢曲超训练窗:不产出(文本标签行保留,配对时计 no_audio)
            continue
        i0, i1 = max(0, int(t0 * sr)), min(len(audio), int(t1 * sr))
        if i1 - i0 < int(min_sec * sr):
            st["seg_too_short"] += 1
            continue
        _write_flac(out_dir / f"{r['utt_id']}.flac", audio[i0:i1], sr)
        st["sliced"] += 1
    st["pieces_done"] += 1


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="S4 整曲音频 → 按 MIDI 真实速度图切段(与文本标签对齐)")
    ap.add_argument("--labels", default=str(ROOT / "work" / "pdmx_a2s_labels.jsonl"))
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--out-dir", default="", help="段音频输出目录;默认与 --audio-dir 相同")
    ap.add_argument("--min-sec", type=float, default=1.0)
    ap.add_argument("--max-sec", type=float, default=40.0)
    ap.add_argument("--slack", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 曲(冒烟)")
    args = ap.parse_args(argv)

    audio_dir = Path(args.audio_dir)
    out_dir = Path(args.out_dir) if args.out_dir else audio_dir
    midi_by_pid = {}
    for p in read_jsonl(args.manifest):
        if p.get("piece_id") and p.get("midi_path"):
            midi_by_pid[p["piece_id"]] = p["midi_path"]

    st = {"pieces": 0, "pieces_done": 0, "sliced": 0, "seg_resumed": 0,
          "seg_too_short": 0, "seg_too_long": 0, "structure_mismatch": 0,
          "no_whole_audio": 0, "no_midi": 0, "midi_fail": 0, "audio_read_fail": 0}

    def _vn_text_rows():
        for row in read_jsonl(args.labels):
            uid = str(row.get("utt_id", ""))
            # 只处理 S4/文本标签行:pdmx_ 前缀、带 measure_range、无自带音频(pdmxperf_ 是 VN 行)
            if uid.startswith("pdmx_") and not uid.startswith("pdmxperf_") \
                    and row.get("measure_range") and not row.get("audio_path"):
                yield row

    for pid, rows in groupby(_vn_text_rows(), key=lambda r: r.get("piece_id")):
        st["pieces"] += 1
        if args.limit and st["pieces"] > args.limit:
            st["pieces"] -= 1
            break
        rows = list(rows)
        midi_path = midi_by_pid.get(pid)
        if not midi_path:
            st["no_midi"] += 1
            continue
        slice_piece(pid, rows, midi_path, audio_dir, out_dir,
                    args.min_sec, args.max_sec + args.slack, st)

    print("S4 段切割(按 MIDI 真实速度图):")
    for k, v in st.items():
        print(f"  {k} = {v}")
    print(f"  段音频 → {out_dir}/<utt_id>.flac;跳过的段无文件,assemble 时计 no_audio(可见可追)。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
