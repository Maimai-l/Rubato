"""
运行期工具:内存感知的并发规模 + 流式/可续跑的进程池。
解决执行端的两类痛:①并行 worker 数写死(16/24),每个 worker 抱一份 1.4GB 音源 → 内存炸;
②合并阶段把全部结果读进内存再 join → 大语料/大标签直接 OOM。
纯逻辑、可在沙盒测(见 tests_ops.py);渲染/训练由执行端跑。
"""
from __future__ import annotations
import os


# ---------------------------------------------------------------- 内存探测(跨平台,psutil 可选)

def available_gb() -> float:
    """可用物理内存(GB)。psutil 优先;否则 Linux /proc/meminfo;否则 Windows wmic;都不行返回一个保守值。"""
    try:
        import psutil
        return psutil.virtual_memory().available / 1e9
    except Exception:
        pass
    # Linux
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                k, _, v = line.partition(":")
                info[k] = int(v.strip().split()[0])  # kB
        for key in ("MemAvailable", "MemFree"):
            if key in info:
                return info[key] / 1e6
    except Exception:
        pass
    # Windows
    try:
        import subprocess
        out = subprocess.run(["wmic", "OS", "get", "FreePhysicalMemory", "/value"],
                             capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if "FreePhysicalMemory" in line:
                return int(line.split("=")[1].strip()) / 1e6  # kB → GB
    except Exception:
        pass
    return 8.0  # 保守兜底


def pick_workers(per_worker_gb: float, hard_cap: int | None = None,
                 reserve_gb: float = 4.0, avail_gb: float | None = None,
                 cpu: int | None = None) -> int:
    """
    按【每个 worker 的内存占用】和【当前可用内存】算安全并发数,不再写死 16/24。
    per_worker_gb:一个 worker 的常驻内存(如 Salamander 音源 ~1.5GB;VN 模型 ~0.5GB)。
    reserve_gb:留给系统/主进程的余量。hard_cap:再封顶(如 CPU 核数或你想要的上限)。
    """
    cpu = cpu or os.cpu_count() or 4
    avail = available_gb() if avail_gb is None else avail_gb
    by_mem = int((avail - reserve_gb) / max(per_worker_gb, 0.05))
    n = min(cpu, by_mem)
    if hard_cap is not None:
        n = min(n, hard_cap)
    return max(1, n)


# ---------------------------------------------------------------- 流式 + 可续跑的进程池

def stream_map(tasks, fn, *, max_workers: int, key_fn=None, done_fn=None,
               on_result=None, log=print, log_every: int = 50,
               mem_floor_gb: float = 2.0):
    """
    对 tasks 逐个跑 fn(task),结果【即时】交给 on_result(task, result) 落盘 —— 不在内存里累积,
    从根上避免"合并时 OOM"。已完成的(done_fn(task)==True)直接跳过 → 可续跑。
    每完成一个查一次可用内存,低于 mem_floor_gb 就【大声警告】(不是静默 OOM,方便你 kill 重开)。
    返回 {submitted, done_skipped, ok, failed, low_mem_events}。
    fn 必须是模块顶层函数(可 pickle)。
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed
    tasks = list(tasks)
    pending = []
    stats = {"total": len(tasks), "done_skipped": 0, "ok": 0, "failed": 0,
             "low_mem_events": 0}
    for t in tasks:
        if done_fn is not None and done_fn(t):
            stats["done_skipped"] += 1
        else:
            pending.append(t)
    stats["submitted"] = len(pending)
    if not pending:
        log(f"[stream_map] 全部已完成,跳过 {stats['done_skipped']}")
        return stats

    done = 0
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        fut_to_task = {ex.submit(fn, t): t for t in pending}
        for fut in as_completed(fut_to_task):
            t = fut_to_task[fut]
            try:
                res = fut.result()
                if on_result is not None:
                    on_result(t, res)
                stats["ok"] += 1
            except Exception as e:
                stats["failed"] += 1
                log(f"[stream_map] 任务失败 {key_fn(t) if key_fn else t}: {type(e).__name__}: {str(e)[:100]}")
            done += 1
            if done % log_every == 0:
                avail = available_gb()
                if avail < mem_floor_gb:
                    stats["low_mem_events"] += 1
                    log(f"⚠ [stream_map] 可用内存 {avail:.1f}GB < 下限 {mem_floor_gb}GB —— "
                        f"worker 可能过多,建议 kill 后减小 max_workers 重开(可续跑)。")
                log(f"[stream_map] {done}/{len(pending)} ok={stats['ok']} fail={stats['failed']} "
                    f"mem_avail={avail:.1f}GB")
    return stats


# ---------------------------------------------------------------- GPU/CPU 流水线(重叠两阶段)

def pipeline_map(items, gpu_stage, cpu_stage, *, n_cpu: int, on_result=None,
                 done_fn=None, key_fn=None, max_inflight: int | None = None,
                 initializer=None, initargs=(), log=print, log_every: int = 50):
    """
    两阶段流水线,让【快的 GPU 阶段】和【慢的 CPU 阶段】重叠,GPU 不再干等 CPU。
      gpu_stage(item) -> mid | None : 主进程【顺序】跑(GPU 单卡,~0.5s)。返回 None = 丢弃该 item。
      cpu_stage(mid)  -> result     : 进程池【并行】跑(CPU,~5s,吃满多核)。必须是模块顶层函数。
      on_result(item, result)       : 主进程即时消费(落盘),不在内存累积。
    机制:主进程跑 gpu_stage(item_N) 后【非阻塞】submit cpu_stage 到池,立刻去 gpu_stage(item_N+1);
    N 个 CPU worker 在后台渲染。在途 CPU 任务超过 max_inflight(默认 2*n_cpu)时才回收一批,
    防 GPU 跑太快把队列堆爆内存。done_fn(item)=True 的直接跳过(可续跑)。
    返回 {total, done_skipped, dropped, ok, failed}。
    """
    from concurrent.futures import ProcessPoolExecutor, FIRST_COMPLETED, wait
    items = list(items)
    max_inflight = max_inflight or (2 * n_cpu)
    stats = {"total": len(items), "done_skipped": 0, "dropped": 0, "ok": 0, "failed": 0}
    done = 0

    def _reap(futs, block):
        nonlocal done
        if not futs:
            return futs
        if block:
            got, futs2 = wait(futs, return_when=FIRST_COMPLETED)
        else:
            got = [f for f in futs if f.done()]
            futs2 = set(futs) - set(got)
        for f in got:
            it = fut_item[f]
            try:
                res = f.result()
                if on_result is not None:
                    on_result(it, res)
                stats["ok"] += 1
            except Exception as e:
                stats["failed"] += 1
                log(f"[pipeline] cpu 阶段失败 {key_fn(it) if key_fn else it}: "
                    f"{type(e).__name__}: {str(e)[:100]}")
            done += 1
            if done % log_every == 0:
                log(f"[pipeline] {done} 完成 ok={stats['ok']} fail={stats['failed']} "
                    f"inflight={len(futs2)} mem={available_gb():.1f}GB")
            del fut_item[f]
        return set(futs2)

    fut_item = {}
    inflight = set()
    with ProcessPoolExecutor(max_workers=n_cpu, initializer=initializer,
                             initargs=initargs) as ex:
        for it in items:
            if done_fn is not None and done_fn(it):
                stats["done_skipped"] += 1
                continue
            mid = gpu_stage(it)                 # GPU,主进程,快
            if mid is None:
                stats["dropped"] += 1
                continue
            fut = ex.submit(cpu_stage, mid)     # CPU,后台并行,慢
            fut_item[fut] = it
            inflight.add(fut)
            # GPU 跑太快时回收在途,封顶内存;否则非阻塞收一波
            while len(inflight) >= max_inflight:
                inflight = _reap(inflight, block=True)
            inflight = _reap(inflight, block=False)
        while inflight:                          # 收尾:等所有 CPU 任务完成
            inflight = _reap(inflight, block=True)
    return stats


# ---------------------------------------------------------------- 流式合并(不吃内存)

def concat_files(chunk_paths, out_path, *, skip_missing: bool = True) -> int:
    """把多个分块文件【逐块追加】到 out_path,一次只驻留一块的缓冲 —— 不像旧 merge 把全部读进内存。
    返回写出的总行数。"""
    from pathlib import Path
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out_path, "w", encoding="utf-8") as w:
        for cp in chunk_paths:
            if not os.path.exists(cp):
                if skip_missing:
                    continue
                raise FileNotFoundError(cp)
            with open(cp, "r", encoding="utf-8") as r:
                for line in r:
                    w.write(line)
                    if line.endswith("\n"):
                        n += 1
    return n
