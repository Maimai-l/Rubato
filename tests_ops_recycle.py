"""worker 回收(max_tasks_per_child)回归测试 —— 修 S4/S5 的"RSS 棘轮式泄漏"。
spawn/forkserver 启动法会重新 import 主模块,所以本测试必须带 __main__ 守卫,独立成文件。
运行: python tests_ops_recycle.py
"""
import os
import sys

sys.path.insert(0, ".")

from rubato.ops import pipeline_map, mem_budget_map

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


def cpu_pid(x):
    return (x, os.getpid())


def main():
    print("[1] pipeline_map + max_tasks_per_child:结果不变、worker 确实被回收(pid 更替)")
    results = []
    st = pipeline_map(range(24), lambda x: x * 10, cpu_pid, n_cpu=2,
                      on_result=lambda i, r: results.append(r),
                      max_tasks_per_child=3, log=lambda *a: None)
    check("all_ok", st["ok"] == 24, st)
    check("values_correct", sorted(v for v, _ in results) == [x * 10 for x in range(24)])
    n_pids = len({p for _, p in results})
    # 24 任务 / 每进程 3 个 = 至少 8 代 worker;不回收的话只会有 2 个 pid
    check("workers_recycled", n_pids >= 4, f"distinct pids={n_pids}(不回收时=2)")

    print("[2] mem_budget_map + max_tasks_per_child:预算准入不受回收影响")
    res2 = []
    st2 = mem_budget_map(list(range(12)), cpu_pid, weight_fn=lambda t: 1.0, budget_gb=3.0,
                         max_workers=3, on_result=lambda t, r: res2.append(r),
                         max_tasks_per_child=2, log=lambda *a: None)
    check("budget_all_ok", st2["ok"] == 12, st2)
    check("budget_recycled", len({p for _, p in res2}) >= 4,
          f"distinct pids={len({p for _, p in res2})}")

    print("[3] 不传 max_tasks_per_child:旧行为不变(worker 常驻)")
    res3 = []
    st3 = pipeline_map(range(8), lambda x: x, cpu_pid, n_cpu=2,
                       on_result=lambda i, r: res3.append(r), log=lambda *a: None)
    check("legacy_ok", st3["ok"] == 8, st3)

    print(f"\n全部通过: {PASS} 项")


if __name__ == "__main__":
    main()
