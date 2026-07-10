"""
S4 表现性无关的直排渲染(生产版):MIDI → 16k Opus,内存安全 + 可续跑 + 流式。

修掉旧版三宗罪:
  ① N_WORKERS=16 写死:每个 sfizz worker 抱一份 ~1.5GB 音源 → 16×=内存炸。改用内存感知的 pick_workers。
  ② load_configs 每个 task 重读 YAML:改成每进程只读一次(懒缓存)。
  ③ 只跑前 500、不可续跑:改成全量 + 跳过已存在的 .opus(可续跑),结果【流式】写盘不在内存累积。

用法:
  python scripts/s4_parallel.py                    # 全量,自动定 worker 数
  python scripts/s4_parallel.py --limit 500        # 先跑 500 试吞吐
  python scripts/s4_parallel.py --workers 6        # 手动封顶(内存吃紧时)
监控/救火:另开一个终端 `python scripts/procmon.py watch --pattern sfizz`,
  内存报警就 `python scripts/procmon.py kill --pattern sfizz` 再用更小 --workers 重开(会跳过已完成)。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from rubato.render.core import render_midi_to_wav44, finalize, assign_source_and_preset
from rubato.ops import pick_workers, stream_map

ROOT = Path(r"D:\vscode_projects\ee_download")
MANIFEST = ROOT / "work" / "manifest_pieces.jsonl"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"
OUT_DIR = ROOT / "work" / "s4_render"

# 每进程只读一次配置(懒缓存)——旧版每个 task 都 yaml.safe_load,纯浪费。
_CFG = None


def _cfg():
    global _CFG
    if _CFG is None:
        with open(CONFIG_DIR / "sources.yaml", encoding="utf-8") as f:
            sources = yaml.safe_load(f)
        with open(CONFIG_DIR / "recording_presets.yaml", encoding="utf-8") as f:
            presets = yaml.safe_load(f)
        _CFG = (sources, presets)
    return _CFG


def out_opus(utt_id: str) -> str:
    return str(OUT_DIR / f"{utt_id}.opus")


def render_one(task: tuple) -> dict:
    """task=(midi_path, utt_id)。渲染一条 → Opus。tmp wav 用完即删(finally)。"""
    midi_path, utt_id = task
    sources, presets = _cfg()
    wav_path = str(OUT_DIR / f"{utt_id}.wav")
    t0 = time.time()
    try:
        src_id, preset_id = assign_source_and_preset(utt_id, sources, presets)
        source = sources["sources"][src_id]
        preset = presets["presets"][preset_id]
        render_midi_to_wav44(midi_path, source, sources, wav_path, utt_id=utt_id,
                             timeout_s=float(sources["render"].get("timeout_s", 600)))
        finalize(wav_path, preset, sources, presets, utt_id, out_opus(utt_id))
        return {"utt_id": utt_id, "ok": True, "elapsed_s": round(time.time() - t0, 1)}
    except Exception as e:
        return {"utt_id": utt_id, "ok": False, "error": f"{type(e).__name__}: {str(e)[:80]}"}
    finally:
        if os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
            except OSError:
                pass


def _done(task) -> bool:
    return os.path.exists(out_opus(task[1]))      # 已渲染 → 跳过(可续跑)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=0, help="0=按内存自动定")
    ap.add_argument("--per-worker-gb", type=float, default=1.5,
                    help="单个渲染 worker 常驻内存估算(Salamander≈1.5)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = []
    with open(MANIFEST, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            p = json.loads(line)
            if p.get("split") == "train" and p.get("midi_path"):
                tasks.append((p["midi_path"], f"pdmx_{p['piece_id']}"))
    if args.limit:
        tasks = tasks[:args.limit]

    workers = args.workers or pick_workers(per_worker_gb=args.per_worker_gb, hard_cap=os.cpu_count())
    print(f"S4 render: {len(tasks)} pieces, workers={workers} "
          f"(每 worker≈{args.per_worker_gb}GB,内存感知), 输出 {OUT_DIR}")

    report_path = ROOT / "reports" / "s4_render.jsonl"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rf = open(report_path, "a", encoding="utf-8")

    def on_result(task, res):
        rf.write(json.dumps(res, ensure_ascii=False) + "\n")   # 流式写盘,不在内存累积

    t0 = time.time()
    stats = stream_map(tasks, render_one, max_workers=workers,
                       key_fn=lambda t: t[1], done_fn=_done, on_result=on_result,
                       log_every=50)
    rf.close()
    dt = time.time() - t0
    print(f"\nDONE: ok={stats['ok']} fail={stats['failed']} skipped(已存在)={stats['done_skipped']} "
          f"in {dt/60:.1f}m  low_mem_events={stats['low_mem_events']}")
    if stats["low_mem_events"]:
        print("⚠ 期间出现过低内存 —— 若还想更稳,--workers 调小重跑(会跳过已完成)。")
    print(f"  逐条状态: {report_path}")


if __name__ == "__main__":
    main()
