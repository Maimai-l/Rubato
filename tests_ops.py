"""运行期工具测试:内存感知并发 + 流式可续跑池 + 流式合并。

Windows process spawning re-imports this module, so all execution belongs under
the ``__main__`` guard and worker callables stay at module scope.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import sys
import tempfile

sys.path.insert(0, ".")

from rubato.ops import (
    available_gb, concat_files, mem_budget_map, pick_workers,
    pipeline_map, stream_map)

PASS = 0
_SHARED = {}


def check(name, cond, detail=""):
    global PASS
    if not cond:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)
    PASS += 1
    print(f"  ok  {name}")


def _square(x):
    return x * x


def _reciprocal(x):
    return 1.0 / x


def _cpu_stage(mid):
    return mid, os.getpid()


def _mb_init(cur, peak, lock):
    _SHARED["cur"], _SHARED["peak"], _SHARED["lock"] = cur, peak, lock


def _mb_task(item):
    import time
    idx, weight = item
    with _SHARED["lock"]:
        _SHARED["cur"].value += weight
        _SHARED["peak"].value = max(
            _SHARED["peak"].value, _SHARED["cur"].value)
    time.sleep(0.03)
    with _SHARED["lock"]:
        _SHARED["cur"].value -= weight
    return idx * 10


def main():
    print("[1] pick_workers:按内存/CPU 定并发,不写死")
    check("mem_and_cpu_cap", pick_workers(1.5, avail_gb=32, cpu=8) == 8)
    check("mem_bound", pick_workers(1.5, avail_gb=8, cpu=16) == 2)
    check("huge_worker_floor1", pick_workers(6, avail_gb=10, cpu=16) == 1)
    check("hard_cap", pick_workers(.5, avail_gb=64, cpu=32, hard_cap=6) == 6)
    check("never_zero", pick_workers(100, avail_gb=2, cpu=8) == 1)

    print("[2] available_gb 跨平台")
    check("avail_positive", available_gb() > 0, available_gb())

    print("[3] stream_map:即时落盘 + 可续跑")
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "results.txt")

        def done(task):
            return os.path.exists(os.path.join(td, f"d_{task}"))

        def on_result(task, result):
            open(os.path.join(td, f"d_{task}"), "w").close()
            with open(out, "a") as handle:
                handle.write(f"{task}:{result}\n")

        tasks = list(range(20))
        stats = stream_map(
            tasks, _square, max_workers=4, done_fn=done,
            on_result=on_result, log=lambda *a: None)
        check("first_run_all",
              stats["ok"] == 20 and stats["done_skipped"] == 0, stats)
        resumed = stream_map(
            tasks, _square, max_workers=4, done_fn=done,
            on_result=on_result, log=lambda *a: None)
        check("resume_skips_all",
              resumed["done_skipped"] == 20 and resumed["submitted"] == 0,
              resumed)
        lines = open(out).read().strip().splitlines()
        check("no_dup_on_resume", len(lines) == 20, len(lines))
        check("results_correct", "3:9" in lines and "5:25" in lines)

        print("[4] concat_files 流式合并")
        a, b = os.path.join(td, "a.txt"), os.path.join(td, "b.txt")
        open(a, "w").write("l1\nl2\n")
        open(b, "w").write("l3\n")
        merged = os.path.join(td, "m.txt")
        n = concat_files([a, os.path.join(td, "missing.txt"), b], merged)
        check("concat_lines", n == 3, n)
        check("concat_content", open(merged).read() == "l1\nl2\nl3\n")

    print("[5] stream_map 记录单任务失败")
    stats = stream_map(
        [1, 0, 2], _reciprocal, max_workers=2,
        on_result=lambda t, r: None, log=lambda *a: None)
    check("failure_counted",
          stats["failed"] == 1 and stats["ok"] == 2, stats)

    print("[6] pipeline_map:主进程阶段与子进程阶段")
    main_pid = os.getpid()
    gpu_pids, results = set(), []

    def gpu(item):
        gpu_pids.add(os.getpid())
        return None if item % 7 == 0 else item * 10

    stats = pipeline_map(
        range(30), gpu, _cpu_stage, n_cpu=4,
        on_result=lambda item, result: results.append((item, result)),
        max_inflight=6, log=lambda *a: None)
    check("gpu_in_main", gpu_pids == {main_pid}, gpu_pids)
    cpu_pids = {result[1] for _, result in results}
    check("cpu_in_children",
          main_pid not in cpu_pids and len(cpu_pids) >= 2, cpu_pids)
    expected_drop = len([x for x in range(30) if x % 7 == 0])
    check("dropped_multiples_of_7", stats["dropped"] == expected_drop, stats)
    check("ok_count", stats["ok"] == 30 - expected_drop, stats)
    check("pipeline_values",
          sorted(result[0] for _, result in results)
          == sorted(x * 10 for x in range(30) if x % 7 != 0))

    print("[7] pipeline_map 可续跑")
    resumed = pipeline_map(
        range(30), gpu, _cpu_stage, n_cpu=4,
        on_result=lambda i, r: None, done_fn=lambda x: True,
        log=lambda *a: None)
    check("pipeline_resume_skips_all",
          resumed["done_skipped"] == 30 and resumed["ok"] == 0, resumed)

    print("[8] mem_budget_map:并发权重不超预算")
    manager = mp.Manager()
    cur, peak, lock = (
        manager.Value("d", 0.0), manager.Value("d", 0.0), manager.Lock())
    weights = [6.5] * 4 + [1.5] * 10 + [0.15] * 20
    tasks = list(enumerate(weights))
    results = []
    stats = mem_budget_map(
        tasks, _mb_task, weight_fn=lambda task: task[1], budget_gb=8,
        max_workers=16, on_result=lambda task, result: results.append(result),
        initializer=_mb_init, initargs=(cur, peak, lock), log=lambda *a: None)
    check("all_ran", stats["ok"] == len(tasks), stats)
    check("peak_within_budget", peak.value <= 8 + 1e-6, peak.value)
    check("budget_results", sorted(results) == [i * 10 for i in range(len(tasks))])

    print("[9] 单个超预算 task 独占运行，不死锁")
    peak.value = cur.value = 0.0
    stats = mem_budget_map(
        [(0, 20.0), (1, 1.0)], _mb_task,
        weight_fn=lambda task: task[1], budget_gb=8, max_workers=4,
        on_result=lambda task, result: None,
        initializer=_mb_init, initargs=(cur, peak, lock), log=lambda *a: None)
    check("oversize_still_runs", stats["ok"] == 2, stats)
    manager.shutdown()
    print(f"\n全部通过: {PASS} 项")


if __name__ == "__main__":
    mp.freeze_support()
    main()
