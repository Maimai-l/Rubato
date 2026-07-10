"""
进程监控/清理工具 —— 解决"不知道怎么 loop 审进程、关进程、重开"。跨平台(Windows/Linux),psutil 可选。

用法:
  python scripts/procmon.py list                 # 列出渲染/训练相关进程 + 内存
  python scripts/procmon.py list --pattern sfizz  # 只看匹配的
  python scripts/procmon.py watch --interval 5    # 每 5s 刷新一次(loop 审进程,Ctrl-C 退出)
  python scripts/procmon.py mem                   # 系统内存一览
  python scripts/procmon.py kill --pid 12345      # 按 PID 杀
  python scripts/procmon.py kill --pattern sfizz  # 按名字/命令行匹配杀(会先让你确认数量)
  python scripts/procmon.py kill --pattern sfizz --yes   # 不确认直接杀

典型救火 loop(渲染/VN 把内存吃爆时):
  1. watch 看哪个 pattern 的 worker 太多/占内存太高;
  2. kill --pattern <引擎>(sfizz_render / virtuoso / python) 清掉;
  3. 用更小的 max_workers 重开对应脚本(s4/s5 都可续跑,不会重复已完成的)。
"""
from __future__ import annotations
import argparse
import os
import sys
import time

DEFAULT_PATTERNS = ("sfizz", "fluidsynth", "virtuoso", "python", "ffmpeg")


def _procs_psutil():
    import psutil
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "memory_info", "cpu_percent", "create_time"]):
        try:
            info = p.info
            rss = (info["memory_info"].rss / 1e6) if info["memory_info"] else 0.0
            cmd = " ".join(info["cmdline"] or [])[:120]
            out.append({"pid": info["pid"], "name": info["name"] or "",
                        "rss_mb": rss, "cmd": cmd,
                        "age_s": time.time() - (info["create_time"] or time.time())})
        except Exception:
            continue
    return out


def _procs_linux():
    out = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode(errors="replace").strip()
            rss_kb = 0
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss_kb = int(line.split()[1]); break
            name = cmd.split()[0].split("/")[-1] if cmd else pid
            out.append({"pid": int(pid), "name": name, "rss_mb": rss_kb / 1000.0,
                        "cmd": cmd[:120], "age_s": 0.0})
        except Exception:
            continue
    return out


def _procs_windows():
    import subprocess, csv, io
    out = []
    try:
        raw = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True, text=True, timeout=15).stdout
        for row in csv.DictReader(io.StringIO(raw)):
            mem = row.get("Mem Usage", "0").replace(",", "").replace(" K", "").strip() or "0"
            try:
                rss = int(mem) / 1000.0
            except ValueError:
                rss = 0.0
            out.append({"pid": int(row.get("PID", 0)), "name": row.get("Image Name", ""),
                        "rss_mb": rss, "cmd": row.get("Image Name", ""), "age_s": 0.0})
    except Exception:
        pass
    return out


def list_procs():
    try:
        import psutil  # noqa
        return _procs_psutil()
    except Exception:
        pass
    if sys.platform.startswith("win"):
        return _procs_windows()
    return _procs_linux()


def sys_mem_gb():
    from rubato.ops import available_gb
    return available_gb()


def _match(p, patterns):
    hay = (p["name"] + " " + p["cmd"]).lower()
    return any(pat.lower() in hay for pat in patterns)


def cmd_list(patterns, top=40):
    procs = [p for p in list_procs() if _match(p, patterns)]
    procs.sort(key=lambda p: p["rss_mb"], reverse=True)
    total = sum(p["rss_mb"] for p in procs)
    print(f"{'PID':>7}  {'RSS(MB)':>9}  {'NAME':<18} CMD")
    for p in procs[:top]:
        print(f"{p['pid']:>7}  {p['rss_mb']:>9.0f}  {p['name'][:18]:<18} {p['cmd']}")
    print(f"--- {len(procs)} 个匹配进程,合计 RSS {total/1000:.1f}GB;系统可用 {sys_mem_gb():.1f}GB ---")
    return procs


def cmd_kill(patterns, pid, yes):
    victims = []
    if pid is not None:
        victims = [p for p in list_procs() if p["pid"] == pid]
    else:
        victims = [p for p in list_procs() if _match(p, patterns) and p["pid"] != os.getpid()]
    if not victims:
        print("没有匹配的进程。")
        return
    print(f"将终止 {len(victims)} 个进程:")
    for p in victims[:20]:
        print(f"  {p['pid']:>7}  {p['rss_mb']:>7.0f}MB  {p['name']}")
    if not yes:
        ans = input("确认?(y/N) ").strip().lower()
        if ans != "y":
            print("已取消。")
            return
    killed = 0
    for p in victims:
        try:
            if sys.platform.startswith("win"):
                import subprocess
                subprocess.run(["taskkill", "/F", "/PID", str(p["pid"])],
                               capture_output=True, timeout=10)
            else:
                os.kill(p["pid"], 9)
            killed += 1
        except Exception as e:
            print(f"  杀 {p['pid']} 失败: {e}")
    print(f"已终止 {killed}/{len(victims)}。")


def main():
    ap = argparse.ArgumentParser(description="进程监控/清理")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "watch"):
        s = sub.add_parser(name)
        s.add_argument("--pattern", nargs="*", default=list(DEFAULT_PATTERNS))
        if name == "watch":
            s.add_argument("--interval", type=float, default=5.0)
    sub.add_parser("mem")
    k = sub.add_parser("kill")
    k.add_argument("--pid", type=int, default=None)
    k.add_argument("--pattern", nargs="*", default=[])
    k.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if args.cmd == "list":
        cmd_list(args.pattern)
    elif args.cmd == "watch":
        try:
            while True:
                os.system("cls" if sys.platform.startswith("win") else "clear")
                print(time.strftime("%H:%M:%S"))
                cmd_list(args.pattern)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n退出监控。")
    elif args.cmd == "mem":
        print(f"系统可用内存: {sys_mem_gb():.1f}GB")
    elif args.cmd == "kill":
        if args.pid is None and not args.pattern:
            print("需要 --pid 或 --pattern")
            return
        cmd_kill(args.pattern, args.pid, args.yes)


if __name__ == "__main__":
    main()
