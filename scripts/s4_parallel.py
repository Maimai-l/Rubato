"""
S4 parallel batch render: MIDI → 16k Opus via sfizz.
Multi-worker pipeline test. Runs first N pieces then reports throughput.
"""
from __future__ import annotations
import json, sys, time, tempfile, os, multiprocessing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.render.core import (
    render_midi_to_wav44, finalize, assign_source_and_preset, render_qc,
)
from rubato.ops import mem_budget_map, available_gb
from rubato.platform import harden_stdout   # Windows GBK 控制台:打印 '−' 会崩,先硬化
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
    """统一走 render.core.soundfont_weights:按【解码后】大小估(FLAC×2),不再按文件大小低估。
    (执行端实测 ExperienceNY 文件 6.9GB → sfizz RSS ~12GB,按文件大小准入会放行过多并发 OOM。)"""
    from rubato.render.core import soundfont_weights
    return soundfont_weights(sources_cfg, CONFIG_DIR.parent, mem_factor=MEM_FACTOR)

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
    last_error = None
    last_qc = None
    for attempt in range(1, 3):  # R-S4.4: QC failure gets exactly one re-render
        try:
            render_midi_to_wav44(
                midi_path, source, sources, wav_path, utt_id=utt_id,
                timeout_s=float(sources["render"].get("timeout_s", 600)))
            finalize(wav_path, preset, sources, presets, utt_id, opus_path)
            last_qc = render_qc(
                midi_path, opus_path,
                tol_s=float(sources["render"].get("duration_tol_s", 1.5)),
                gate_db=float(sources["render"].get("silence_gate_db", -60)))
            if last_qc["ok"]:
                return {
                    "utt_id": utt_id,
                    "elapsed_s": round(time.time() - t0, 1),
                    "source": src_id,
                    "preset": preset_id,
                    "attempts": attempt,
                    "qc": last_qc,
                    "ok": True,
                }
            last_error = (
                "render_qc:"
                f"audible={last_qc.get('audible')} "
                f"diff_s={last_qc.get('diff_s')} "
                f"error={last_qc.get('error')}")
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:120]}"
        finally:
            if os.path.exists(wav_path):
                os.unlink(wav_path)
        # Never let a failed but non-empty file satisfy the resume predicate.
        if os.path.exists(opus_path):
            os.unlink(opus_path)
    return {
        "utt_id": utt_id,
        "error": last_error or "render_failed",
        "elapsed_s": round(time.time() - t0, 1),
        "source": src_id,
        "preset": preset_id,
        "attempts": 2,
        "qc": last_qc,
        "ok": False,
    }


def _done(task) -> bool:
    op = Path(task[2]) / f"{task[1]}.opus"
    return op.exists() and op.stat().st_size > 0     # 已渲染 → 跳过(可续跑,不重复)


def main():
    harden_stdout()   # 先硬化控制台编码,任何非 GBK 字符打印不再崩(执行端 GBK Windows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sources_cfg, presets_cfg = load_configs()
    src_gb = _source_weights(sources_cfg)

    pieces = []
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        for line in f:
            p = json.loads(line.strip())
            # 【D35 修复】原条件 split=="train" 把 split 缺失的曲(装配端默认按 train 用)
            # 和 val/test 曲静默漏渲 —— 3,150 曲 12,014 行因此成了永久 no_audio,而且
            # pdmx val/test 无音频导致其评测池形同虚设。渲染资格 = 有 MIDI,与 split 无关
            # (val/test 也需要音频才能被评测;泄漏防护在装配端黑名单,不靠不渲染)。
            if p.get("midi_path"):
                pieces.append(p)
    tasks = [(p["midi_path"], f"pdmx_{p['piece_id']}", str(OUT_DIR)) for p in pieces[:N_PIECES]]

    # 【音源亲和】按分配到的音源排序:同音源的曲【连续】渲染 —— ①OS 页缓存保持热(6.9GB 的
    # FLAC 不必每曲从盘重读,sfizz 加载快一个量级);②同一时段在跑的任务权重同质,准入并发稳定
    # (全程 3×小音源 或 1×大音源,不再大/小混排把预算切碎)。分配是 hash 确定的,排序不改分配;
    # 跳过逻辑按 .opus 存在判断,排序不影响续跑。
    def _task_source(task):
        sid, _ = assign_source_and_preset(task[1], sources_cfg, presets_cfg)
        return sid
    tasks.sort(key=lambda t: (_task_source(t), t[1]))

    def weight_fn(task):
        sid, _ = assign_source_and_preset(task[1], sources_cfg, presets_cfg)
        return BASE_GB + src_gb.get(sid, 2.0)        # 音源【解码后】大小 + worker 自身常驻(GB)

    budget = max(2.0, available_gb() - RESERVE_GB)
    print(f"S4 render: {len(tasks)} 曲 | 内存预算 {budget:.1f}GB(可用 {available_gb():.1f} - 留 {RESERVE_GB}) "
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
