"""VNSubprocess 回收机制回归测试(无需 GPU/virtuoso)。
用【假子进程 echo】+【注入的 RSS 函数】验证:RSS 超 cap 就 kill+重开、结果始终正确、监控线程也回收。
spawn/fork 会重 import 主模块,故必须 __main__ 守卫,独立成文件。运行: python tests_vn_subprocess.py
"""
import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, ".")

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


def echo_child(req_q, resp_q, checkpoint, out_dir):
    """假 VN 子进程:构造瞬间 ready;每条请求回 (ok, xml+'.mid', xml+'.csv')。不需要 torch/virtuoso。"""
    resp_q.put(("ready", None, None))
    while True:
        item = req_q.get()
        if item is None:
            return
        xml, composer = item
        resp_q.put(("ok", f"{xml}.mid", f"{xml}.csv"))


def hung_child(req_q, resp_q, checkpoint, out_dir):
    """假 VN 子进程:ready 后收到请求就【卡死不回】—— 复现执行端"某曲推理卡住+泄漏涨到 25GB"。"""
    resp_q.put(("ready", None, None))
    while True:
        item = req_q.get()
        if item is None:
            return
        time.sleep(3600)     # 卡死:永不回复


def main():
    import scripts.s5_vn_render as s5
    ctx = mp.get_context("fork" if os.name != "nt" else "spawn")

    print("[1] 正常推理:结果正确、不回收(RSS 恒低于 cap)")
    vn = s5.VNSubprocess("ckpt", out_dir="/tmp", rss_cap_gb=4.0, monitor_sec=999,
                         ctx=ctx, child_target=echo_child, rss_fn=lambda p: 0.5)
    r = [vn.infer(f"piece{i}", "Beethoven") for i in range(5)]
    check("results_correct", r == [(f"piece{i}.mid", f"piece{i}.csv") for i in range(5)], r)
    check("no_recycle_under_cap", vn.recycles == 0, vn.recycles)
    check("n_infer_counted", vn.n_infer == 5, vn.n_infer)
    vn.close()

    print("[2] RSS 超 cap:每次推理后回收(kill+重开),结果仍正确")
    calls = {"n": 0}
    def growing_rss(p):
        calls["n"] += 1
        return 5.0        # 恒超 cap=4 → 每次 infer 后都应回收
    vn = s5.VNSubprocess("ckpt", out_dir="/tmp", rss_cap_gb=4.0, monitor_sec=999,
                         ctx=ctx, child_target=echo_child, rss_fn=growing_rss)
    r = [vn.infer(f"p{i}", "Bach") for i in range(3)]
    check("results_correct_after_recycle", r == [(f"p{i}.mid", f"p{i}.csv") for i in range(3)], r)
    check("recycled_each_time", vn.recycles >= 3, vn.recycles)   # 3 次推理各触发一次回收
    vn.close()

    print("[3] 监控线程:空闲期(不推理)RSS 超 cap 也回收")
    vn = s5.VNSubprocess("ckpt", out_dir="/tmp", rss_cap_gb=4.0, monitor_sec=0.2,
                         ctx=ctx, child_target=echo_child, rss_fn=lambda p: 9.0)
    time.sleep(1.0)      # 不做任何 infer,只等监控线程发现 RSS 超标并回收
    check("monitor_recycled_idle", vn.recycles >= 1, f"recycles={vn.recycles}(监控应已回收)")
    vn.close()

    print("[4] close 后子进程确实终止")
    vn = s5.VNSubprocess("ckpt", out_dir="/tmp", rss_cap_gb=4.0, monitor_sec=999,
                         ctx=ctx, child_target=echo_child, rss_fn=lambda p: 0.1)
    vn.infer("x", "Y")
    vn.close()
    check("proc_dead_after_close", vn.proc is None or not vn.proc.is_alive(), "close 后应无存活子进程")

    print("[5] 【执行端 OOM 复现】推理卡死 + RSS 超标:监控【推理进行中】也能砍,infer 快速失败")
    # 旧版 infer() 全程握锁等结果 → 监控被锁死整个 infer_timeout(180s),泄漏子进程不受 cap 约束
    # 涨到 25GB(执行端 memtrace 实锤)。新版等待期不握锁:监控发现超标即砍,在飞 infer 秒级失败。
    vn = s5.VNSubprocess("ckpt", out_dir="/tmp", rss_cap_gb=4.0, monitor_sec=0.3,
                         infer_timeout=60.0,      # 故意设很长:证明不是靠超时、是靠监控砍
                         ctx=ctx, child_target=hung_child, rss_fn=lambda p: 9.0)
    t0 = time.time()
    r = vn.infer("stuck_piece", "Chopin")
    dt = time.time() - t0
    check("hung_infer_fails_fast", r == (None, None), r)
    check("killed_by_monitor_not_timeout", dt < 15.0, f"{dt:.1f}s(旧版要等满 60s)")
    check("monitor_recycled_during_infer", vn.recycles >= 1, vn.recycles)
    vn.close()

    print(f"\n全部通过: {PASS} 项")


if __name__ == "__main__":
    main()
