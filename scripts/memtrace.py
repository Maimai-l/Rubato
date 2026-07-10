"""
S5 内存去向追踪器 —— 回答一个问题:内存到底涨在【主进程 VN】还是【worker 渲染池】还是【worker 数量】?

规划端(我)看不到你 Windows 本机的实时内存,所以别猜:你【和 S5 同时】跑这个脚本,
它每隔几秒采一次样,把"主进程 RSS / worker 数 / worker RSS 之和 / 系统占用"打成一张表,
你把输出(或它写的 memtrace.csv)贴回来,我一眼就知道该拧哪个旋钮 / 改哪段代码。

用法(另开一个终端,和 s5_vn_render.py 同时跑):
  python scripts/memtrace.py                      # 每 5s 采样,直到 Ctrl-C;同时写 reports/memtrace.csv
  python scripts/memtrace.py --interval 3         # 采样更密
  python scripts/memtrace.py --seconds 600        # 只跑 10 分钟自动停
  python scripts/memtrace.py --match s5_vn_render # 主进程识别关键字(默认就是它)

判读(贴回来我会看,但你也能自己看):
  * 主进程 RSS 一路涨、workers 之和平稳 → 泄漏在【主进程 VN】(本次已加的引擎定期重建应压住;
    若仍涨,把 S5_VN_RECYCLE 调小,如 set S5_VN_RECYCLE=50)。
  * 主进程 RSS 平、workers 之和/数量涨 → 泄漏在【worker】(把 S5_TASKS_PER_CHILD 调小,如 8;
    或 S5_RESERVE_GB 调大)。
  * worker 数量远超预期 → 预算/并发没收住,贴回来我改。
"""
from __future__ import annotations
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from rubato.platform import harden_stdout   # GBK 控制台打印进程名/路径不崩
except Exception:
    def harden_stdout(errors="backslashreplace"):
        for s in (sys.stdout, sys.stderr):
            try:
                s.reconfigure(errors=errors)
            except Exception:
                pass


def _sys_mem():
    try:
        import psutil
        vm = psutil.virtual_memory()
        return vm.total / 1e9, vm.available / 1e9, vm.percent
    except Exception:
        return 0.0, 0.0, 0.0


def _snapshot(match: str):
    """返回 (main_rss_gb, n_workers, worker_rss_sum_gb, worker_rss_max_gb, aux)。
    main = 命令行含 `match` 的 python 进程;workers = 它的子进程;aux = virtuoso/sfizz/ffmpeg 占用。"""
    import psutil
    main_procs, mains = [], []
    aux = {"virtuoso": 0.0, "sfizz": 0.0, "ffmpeg": 0.0}
    for p in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
        try:
            cmd = " ".join(p.info["cmdline"] or "")
            nm = (p.info["name"] or "").lower()
            rss = (p.info["memory_info"].rss / 1e9) if p.info["memory_info"] else 0.0
            if match in cmd and "python" in nm:
                main_procs.append(p); mains.append(rss)
            for key in aux:
                if key in nm or key in cmd.lower():
                    aux[key] += rss
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            continue
    if not main_procs:
        return None
    # 取 RSS 最大的那个含关键字的 python 作为主进程(其余多半是它的池子父/子)
    main = max(main_procs, key=lambda p: (p.info["memory_info"].rss if p.info["memory_info"] else 0))
    main_rss = (main.info["memory_info"].rss / 1e9) if main.info["memory_info"] else 0.0
    wrss = []
    try:
        for c in main.children(recursive=True):
            try:
                wrss.append(c.memory_info().rss / 1e9)
            except Exception:
                pass
    except Exception:
        pass
    return main_rss, len(wrss), sum(wrss), (max(wrss) if wrss else 0.0), aux


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=5.0, help="采样间隔秒")
    ap.add_argument("--seconds", type=float, default=0, help=">0 则跑这么久自动停;默认到 Ctrl-C")
    ap.add_argument("--match", default="s5_vn_render", help="主进程命令行识别关键字")
    ap.add_argument("--out", default=str(Path("reports") / "memtrace.csv"))
    args = ap.parse_args()
    harden_stdout()

    try:
        import psutil  # noqa
    except Exception:
        print("需要 psutil:pip install psutil", file=sys.stderr)
        raise SystemExit(2)

    outp = Path(args.out); outp.parent.mkdir(parents=True, exist_ok=True)
    total_gb, _, _ = _sys_mem()
    hdr = ("elapsed_s", "sys_used_%", "sys_avail_GB", "main_VN_RSS_GB",
           "n_workers", "workers_RSS_sum_GB", "worker_RSS_max_GB",
           "virtuoso_GB", "sfizz_GB", "ffmpeg_GB")
    print(f"# 总内存 {total_gb:.1f}GB | 匹配主进程关键字 = '{args.match}' | 每 {args.interval}s 采样 | 写 {outp}")
    print("  " + "  ".join(f"{h:>16}" for h in hdr))
    fh = open(outp, "w", encoding="utf-8")
    fh.write(",".join(hdr) + "\n"); fh.flush()

    t0 = time.time()
    n_missing = 0
    while True:
        snap = _snapshot(args.match)
        el = time.time() - t0
        _, avail, pct = _sys_mem()
        if snap is None:
            n_missing += 1
            print(f"  [{el:8.0f}s] 未发现含 '{args.match}' 的 python 主进程(S5 还没起?)  系统占用 {pct:.0f}% 可用 {avail:.1f}GB")
            if n_missing >= 6 and args.seconds == 0:
                print("  连续多次没找到主进程 —— 确认 S5 在另一个终端跑着,或用 --match 传对关键字。")
        else:
            main_rss, nw, wsum, wmax, aux = snap
            row = (f"{el:.0f}", f"{pct:.0f}", f"{avail:.1f}", f"{main_rss:.2f}",
                   f"{nw}", f"{wsum:.2f}", f"{wmax:.2f}",
                   f"{aux['virtuoso']:.2f}", f"{aux['sfizz']:.2f}", f"{aux['ffmpeg']:.2f}")
            print("  " + "  ".join(f"{v:>16}" for v in row), flush=True)
            fh.write(",".join(row) + "\n"); fh.flush()
        if args.seconds and el >= args.seconds:
            break
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            break
    fh.close()
    print(f"\n采样结束。把上面这张表(或 {outp})整段贴回来,我据此定位并给下一步。")


if __name__ == "__main__":
    main()
