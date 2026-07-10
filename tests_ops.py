"""运行期工具测试:内存感知并发 + 流式可续跑池 + 流式合并。运行: python tests_ops.py"""
import sys, os, tempfile
sys.path.insert(0, ".")
from rubato.ops import pick_workers, stream_map, concat_files, available_gb

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)


# 顶层可 pickle 的 worker 函数(multiprocessing 要求,必须在使用前定义)
def _square(x): return x * x
def _reciprocal(x): return 1.0 / x


print("[1] pick_workers:按内存/CPU 定并发,不写死")
# 32GB 可用、每 worker 1.5GB、留 4GB → (32-4)/1.5≈18,但 CPU=8 封顶 → 8
check("mem_and_cpu_cap", pick_workers(1.5, avail_gb=32, cpu=8) == 8, pick_workers(1.5, avail_gb=32, cpu=8))
# 内存紧:8GB 可用、每 worker 1.5GB、留 4GB → (8-4)/1.5=2
check("mem_bound", pick_workers(1.5, avail_gb=8, cpu=16) == 2, pick_workers(1.5, avail_gb=8, cpu=16))
# 音源巨大:每 worker 6GB、可用 10GB、留 4 → (10-4)/6=1
check("huge_worker_floor1", pick_workers(6.0, avail_gb=10, cpu=16) == 1, pick_workers(6.0, avail_gb=10, cpu=16))
# hard_cap 再封顶
check("hard_cap", pick_workers(0.5, avail_gb=64, cpu=32, hard_cap=6) == 6)
# 永不为 0
check("never_zero", pick_workers(100.0, avail_gb=2, cpu=8) == 1)

print("[2] available_gb 返回正数(跨平台探测能跑)")
check("avail_positive", available_gb() > 0, available_gb())

print("[3] stream_map:即时落盘不累积 + 可续跑跳过已完成")
tmp = tempfile.mkdtemp()
out = os.path.join(tmp, "results.txt")
def _done(t): return os.path.exists(os.path.join(tmp, f"d_{t}"))
written = []
def _on(t, res):
    open(os.path.join(tmp, f"d_{t}"), "w").close()   # 标记完成(续跑用)
    with open(out, "a") as w: w.write(f"{t}:{res}\n")
tasks = list(range(20))
st = stream_map(tasks, _square, max_workers=4, done_fn=_done, on_result=_on, log=lambda *a: None)
check("first_run_all", st["ok"] == 20 and st["done_skipped"] == 0, st)
# 第二次:全部已完成 → 全跳过,不重复跑
st2 = stream_map(tasks, _square, max_workers=4, done_fn=_done, on_result=_on, log=lambda *a: None)
check("resume_skips_all", st2["done_skipped"] == 20 and st2["submitted"] == 0, st2)
# 结果只写了一遍(没因续跑重复)
lines = open(out).read().strip().splitlines()
check("no_dup_on_resume", len(lines) == 20, len(lines))
check("results_correct", "3:9" in lines and "5:25" in lines)

print("[4] concat_files:逐块追加不吃内存 + 跳过缺块")
a = os.path.join(tmp, "a.txt"); b = os.path.join(tmp, "b.txt")
open(a, "w").write("l1\nl2\n"); open(b, "w").write("l3\n")
merged = os.path.join(tmp, "m.txt")
n = concat_files([a, os.path.join(tmp, "missing.txt"), b], merged)
check("concat_lines", n == 3, n)
check("concat_content", open(merged).read() == "l1\nl2\nl3\n", repr(open(merged).read()))

print("[5] stream_map 记录失败不崩(一个任务抛错)")
st3 = stream_map([1, 0, 2], _reciprocal, max_workers=2, on_result=lambda t, r: None, log=lambda *a: None)
check("failure_counted", st3["failed"] == 1 and st3["ok"] == 2, st3)

print(f"\n全部通过: {PASS} 项")
