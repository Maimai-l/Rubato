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


# ---------------------------------------------------------------- 进程池构造(可选 worker 回收)

def _make_pool(max_workers, initializer=None, initargs=(), max_tasks_per_child=None):
    """
    构造 ProcessPoolExecutor;max_tasks_per_child>0 时【每 N 个任务回收重开 worker 进程】。
    为什么关键:长命 worker 每跑一曲,partitura/lxml/numpy 的峰值分配会把进程 RSS 顶到
    "历史最大那曲"的水位且【不还给 OS】(glibc/Windows heap 都这样)—— n 个 worker 各自
    棘轮式涨,宏观上就是"内存像泄漏、越跑越高、最后炸"。定期回收进程 = 把水位清零,RSS 有界。
    内存预算只管【同时】占用,管不住这种【累积】增长 —— 两者必须都做。
    注意:CPython 里 max_tasks_per_child 与 fork 启动法不兼容(Windows spawn 天然没问题);
    Linux 默认 fork 时自动换 forkserver。py<3.11 或不支持时静默退回旧行为(不回收)。
    """
    from concurrent.futures import ProcessPoolExecutor
    kw = dict(max_workers=max_workers, initializer=initializer, initargs=initargs)
    if max_tasks_per_child:
        import multiprocessing as mp
        kw["max_tasks_per_child"] = int(max_tasks_per_child)
        try:
            if os.name != "nt" and mp.get_start_method(allow_none=True) in (None, "fork"):
                kw["mp_context"] = mp.get_context("forkserver")
        except Exception:
            pass
        try:
            return ProcessPoolExecutor(**kw)
        except (TypeError, ValueError):
            kw.pop("max_tasks_per_child", None)
            kw.pop("mp_context", None)
    return ProcessPoolExecutor(**kw)


# ---------------------------------------------------------------- 内存预算调度(永不 OOM)

def mem_budget_map(tasks, fn, weight_fn, *, budget_gb: float, max_workers: int | None = None,
                   on_result=None, done_fn=None, key_fn=None, initializer=None, initargs=(),
                   max_tasks_per_child=None, log=print, log_every: int = 50):
    """
    并发跑 fn(task),硬保证【同时运行的 task 权重之和 ≤ budget_gb】—— 按内存准入,永不超预算。
    weight_fn(task) -> gb:该 task 的内存占用(如它要加载的音源大小)。异构音源(146MB~6.5GB)
    正是靠这个:大音源少并发、小音源多并发,自动填满预算但不爆。
    单个 task 权重 > budget 时仍会【单独】跑(否则永远进不来),但同时只此一个。
    done_fn(task)=True 的跳过(可续跑)。返回 {total, done_skipped, ok, failed, peak_gb_est}。
    """
    from concurrent.futures import FIRST_COMPLETED, wait
    tasks = [t for t in tasks if not (done_fn and done_fn(t))]
    max_workers = max_workers or (os.cpu_count() or 4)
    stats = {"total": len(tasks), "done_skipped": 0, "ok": 0, "failed": 0, "peak_gb_est": 0.0}
    used = 0.0
    running = {}                     # future -> (task, weight)
    it = iter(tasks)
    pending = next(it, None)
    done = 0
    with _make_pool(max_workers, initializer=initializer, initargs=initargs,
                    max_tasks_per_child=max_tasks_per_child) as ex:
        while pending is not None or running:
            # 尽量准入:空闲时允许单个超预算,否则要求 used+w ≤ budget 且未满 worker
            while pending is not None:
                w = max(0.01, float(weight_fn(pending)))
                fits = (used + w <= budget_gb) or (not running)
                if fits and len(running) < max_workers:
                    fut = ex.submit(fn, pending)
                    running[fut] = (pending, w)
                    used += w
                    stats["peak_gb_est"] = max(stats["peak_gb_est"], used)
                    pending = next(it, None)
                else:
                    break
            if not running:
                break
            for fut in wait(list(running), return_when=FIRST_COMPLETED)[0]:
                task, w = running.pop(fut)
                used -= w
                try:
                    res = fut.result()
                    if on_result is not None:
                        on_result(task, res)
                    stats["ok"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    log(f"[mem_budget] 失败 {key_fn(task) if key_fn else task}: "
                        f"{type(e).__name__}: {str(e)[:100]}")
                done += 1
                if done % log_every == 0:
                    log(f"[mem_budget] {done}/{len(tasks)} 运行中={len(running)} "
                        f"占用≈{used:.1f}/{budget_gb:.1f}GB 峰值≈{stats['peak_gb_est']:.1f}GB "
                        f"可用={available_gb():.1f}GB")
    return stats


# ---------------------------------------------------------------- GPU/CPU 流水线(重叠两阶段)

def pipeline_map(items, gpu_stage, cpu_stage, *, n_cpu: int, on_result=None,
                 done_fn=None, key_fn=None, max_inflight: int | None = None,
                 weight_fn=None, budget_gb: float | None = None,
                 initializer=None, initargs=(), max_tasks_per_child=None,
                 log=print, log_every: int = 50):
    """
    两阶段流水线,让【快的 GPU 阶段】和【慢的 CPU 阶段】重叠,GPU 不再干等 CPU。
      gpu_stage(item) -> mid | None : 主进程【顺序】跑(GPU 单卡,~0.5s)。返回 None = 丢弃该 item。
      cpu_stage(mid)  -> result     : 进程池【并行】跑(CPU,~5s,吃满多核)。必须是模块顶层函数。
      on_result(item, result)       : 主进程即时消费(落盘),不在内存累积。
    在途 CPU 任务的准入:
      - 默认按【个数】封顶 max_inflight(默认 2*n_cpu);
      - 若给 weight_fn(mid)->gb + budget_gb,则按【内存和 ≤ budget】准入(异构音源不 OOM),
        大音源少并发/小音源多并发,同时运行的音源内存和永远 ≤ budget。GPU 会在 CPU 内存吃满时
        自然暂停(反正 CPU 是瓶颈),空出来再继续 —— 重叠不丢、内存不爆。
    done_fn(item)=True 的直接跳过(可续跑)。返回 {total, done_skipped, dropped, ok, failed, peak_gb_est}。
    """
    from concurrent.futures import FIRST_COMPLETED, wait
    items = list(items)
    max_inflight = max_inflight or (2 * n_cpu)
    stats = {"total": len(items), "done_skipped": 0, "dropped": 0, "ok": 0, "failed": 0,
             "peak_gb_est": 0.0}
    done = 0
    used = 0.0
    fut_item = {}
    fut_w = {}

    def _reap(futs, block):
        nonlocal done, used
        if not futs:
            return futs
        if block:
            got, futs2 = wait(futs, return_when=FIRST_COMPLETED)
        else:
            got = [f for f in futs if f.done()]
            futs2 = set(futs) - set(got)
        for f in got:
            it = fut_item[f]
            used -= fut_w.pop(f, 0.0)
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
                    f"inflight={len(futs2)} used≈{used:.1f}GB mem={available_gb():.1f}GB")
            del fut_item[f]
        return set(futs2)

    inflight = set()
    with _make_pool(n_cpu, initializer=initializer, initargs=initargs,
                    max_tasks_per_child=max_tasks_per_child) as ex:
        for it in items:
            if done_fn is not None and done_fn(it):
                stats["done_skipped"] += 1
                continue
            mid = gpu_stage(it)                 # GPU,主进程,快
            if mid is None:
                stats["dropped"] += 1
                continue
            w = max(0.01, float(weight_fn(mid))) if weight_fn else 0.0
            # 准入:内存预算优先(给了 budget 时),否则按个数。放不下就阻塞回收在途,腾出再提交。
            if weight_fn and budget_gb is not None:
                while inflight and used + w > budget_gb:
                    inflight = _reap(inflight, block=True)
            while len(inflight) >= max_inflight:
                inflight = _reap(inflight, block=True)
            fut = ex.submit(cpu_stage, mid)     # CPU,后台并行,慢
            fut_item[fut] = it
            fut_w[fut] = w
            used += w
            stats["peak_gb_est"] = max(stats["peak_gb_est"], used)
            inflight.add(fut)
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
