"""
S4 parallel batch render: MIDI → 16k Opus via sfizz.
Multi-worker pipeline test. Runs first N pieces then reports throughput.
"""
from __future__ import annotations
import json, sys, time, tempfile, os, multiprocessing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.render.core import render_midi_to_wav44, finalize, assign_source_and_preset
from rubato.ops import mem_budget_map, available_gb
import yaml

ROOT = Path(r"D:\vscode_projects\ee_download")
MANIFEST = ROOT / "work" / "manifest_pieces.jsonl"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"
OUT_DIR = ROOT / "work" / "pdmx_audio"
# 【内存预算调度,自动不 OOM】不再按固定 worker 数,而是按【每个音源的实际大小】准入:
#   大音源(ExperienceNY 6.5GB)少并发、小音源(Splendid 146MB)多并发,
#   同时运行的音源大小之和 ≤ 预算(可用内存 − 保留),硬保证不超内存(见 rubato.ops.mem_budget_map)。
# 权重 = 音源目录总大小(sfizz 常驻内存的安全上限;流式加载实际更少)。想更激进用 S4_MEM_FACTOR<1。
RESERVE_GB   = float(os.environ.get("S4_RESERVE_GB", "4"))     # 留给系统/主进程
MEM_FACTOR   = float(os.environ.get("S4_MEM_FACTOR", "1.0"))   # <1 = 承认 sfizz 流式、少留内存、更多并发
MAX_WORKERS  = int(os.environ.get("S4_WORKERS", "0") or 0) or min(os.cpu_count() or 4, 16)
# 【内存】worker 自身常驻(finalize 整曲音频数组 + heap 水位)计入预算;每 N 曲回收 worker 清 RSS 棘轮。
BASE_GB      = float(os.environ.get("S4_WORKER_BASE_GB", "0.5"))
RECYCLE      = int(os.environ.get("S4_TASKS_PER_CHILD", "16" if os.name == "nt" else "0"))
N_PIECES = 999999  # render all pieces


def _source_weights(sources_cfg) -> dict:
    """每个音源的常驻内存权重(GB)= 其 .sfz 所在目录的样本总大小(安全上限)。缺失→保守 2.0。"""
    repo = CONFIG_DIR.parent
    out = {}
    for sid, s in sources_cfg["sources"].items():
        d = (repo / s["path"]).parent
        gb = 2.0
        if d.exists():
            total = 0
            for f in d.rglob("*"):
                try:
                    if f.is_file():
                        total += f.stat().st_size
                except OSError:
                    pass
            gb = total / 1e9
        out[sid] = max(0.1, gb * MEM_FACTOR)
    return out

_CFG = None


def load_configs():
    global _CFG
    if _CFG is None:                    # 每进程只读一次(旧版每个 task 重读 YAML,纯浪费)
        with open(CONFIG_DIR / "sources.yaml", 'r', encoding='utf-8') as f:
            sources = yaml.safe_load(f)
        with open(CONFIG_DIR / "recording_presets.yaml", 'r', encoding='utf-8') as f:
            presets = yaml.safe_load(f)
        _CFG = (sources, presets)
    return _CFG


def render_one(args: tuple) -> dict:
    """Render one MIDI → Opus. Standalone for multiprocessing."""
    midi_path, utt_id, out_dir = args
    opus_path = str(Path(out_dir) / f"{utt_id}.opus")
    # Skip if already rendered (crash recovery)
    if os.path.isfile(opus_path) and os.path.getsize(opus_path) > 0:
        return {"utt_id": utt_id, "elapsed_s": 0, "source": "", "preset": "", "ok": True, "skipped": True}
    sources, presets = load_configs()
    t0 = time.time()

    src_id, preset_id = assign_source_and_preset(utt_id, sources, presets)
    source = sources["sources"][src_id]
    preset = presets["presets"][preset_id]

    wav_path = str(Path(out_dir) / f"{utt_id}.wav")
    try:
        render_midi_to_wav44(midi_path, source, sources, wav_path, utt_id=utt_id,
                             timeout_s=float(sources["render"].get("timeout_s", 600)))
        opus_path = str(Path(out_dir) / f"{utt_id}.opus")
        finalize(wav_path, preset, sources, presets, utt_id, opus_path)
        return {"utt_id": utt_id, "elapsed_s": round(time.time() - t0, 1),
                "source": src_id, "preset": preset_id, "ok": True}
    except Exception as e:
        return {"utt_id": utt_id, "error": f"{type(e).__name__}: {str(e)[:80]}",
                "elapsed_s": round(time.time() - t0, 1), "ok": False}
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)


def _done(task) -> bool:
    op = Path(task[2]) / f"{task[1]}.opus"
    return op.exists() and op.stat().st_size > 0     # 已渲染 → 跳过(可续跑,不重复)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources_cfg, presets_cfg = load_configs()
    src_gb = _source_weights(sources_cfg)

    pieces = []
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        for line in f:
            p = json.loads(line.strip())
            if p.get("split") == "train" and p.get("midi_path"):
                pieces.append(p)
    tasks = [(p["midi_path"], f"pdmx_{p['piece_id']}", str(OUT_DIR)) for p in pieces[:N_PIECES]]

    def weight_fn(task):
        sid, _ = assign_source_and_preset(task[1], sources_cfg, presets_cfg)
        return BASE_GB + src_gb.get(sid, 2.0)        # 音源大小 + worker 自身常驻(GB)

    budget = max(2.0, available_gb() - RESERVE_GB)
    print(f"S4 render: {len(tasks)} 曲 | 内存预算 {budget:.1f}GB(可用 {available_gb():.1f} − 留 {RESERVE_GB}) "
          f"| max_workers={MAX_WORKERS} | MEM_FACTOR={MEM_FACTOR}")
    print("  音源权重(GB): " + ", ".join(f"{k}={v:.1f}" for k, v in sorted(src_gb.items())))
    print("  → 大音源少并发、小音源多并发,同时运行的音源和 ≤ 预算,【硬保证不 OOM】。")

    report_path = ROOT / "reports" / "s4_render.jsonl"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    rf = open(report_path, "a", encoding="utf-8")
    counts = {"ok": 0, "fail": 0}

    def on_result(task, res):
        rf.write(json.dumps(res, ensure_ascii=False) + "\n")
        counts["ok" if res.get("ok") else "fail"] += 1

    t0 = time.time()
    stats = mem_budget_map(tasks, render_one, weight_fn=weight_fn, budget_gb=budget,
                           max_workers=MAX_WORKERS, done_fn=_done, on_result=on_result,
                           max_tasks_per_child=RECYCLE or None,
                           key_fn=lambda t: t[1], log_every=100)
    rf.close()
    dt = time.time() - t0
    print(f"\n{'='*50}")
    print(f"DONE: ok={counts['ok']} fail={counts['fail']} skipped(已存在)={stats['done_skipped']} "
          f"in {dt/60:.1f}m | 峰值内存占用≈{stats['peak_gb_est']:.1f}/{budget:.1f}GB")
    print(f"  逐条状态: {report_path}")
    print("  内存仍紧?set S4_RESERVE_GB=8 多留;想更快?set S4_MEM_FACTOR=0.5(承认 sfizz 流式)。")


if __name__ == "__main__":
    main()
