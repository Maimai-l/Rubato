"""
nASAP 韧性驱动器 —— 逐曲隔离 + 硬超时 + 断点续跑,一首挂死不再全盘卡死。

背景(执行端实测):s7_full_nasap 全量跑到 Beethoven 奏鸣曲段(~140/519)时 partitura
反复展开(malformed repeat → 小节数爆炸)卡死,3 次重试同位置死亡,每次残留僵尸进程。
病根与 P4 巨曲相同:挂死发生在 partitura 库内部,进程内没法打断 —— 唯一可靠的隔离是
【子进程 + 超时杀】。手工分块跑的问题:一块里一首坏曲会丢掉整块、没有哪首失败的记账、
--fresh 误用还会删掉前面的产出。

本驱动器(替代 SOP P5c 的直跑):
  1. 状态存盘 work/nasap_s7_state.json:done 索引 + failed{索引: 原因},随时中断随时续;
  2. 【单实例锁】work/nasap_s7_state.lock:执行端实测"手动实例 + sop --go 实例"双开,
     后者删前者正在写的 .part 文件当场炸(WinError 32)。锁被占默认礼貌等待(--go 全自动),
     持锁方每块 touch 刷新,超时未刷新判死接管;
  3. 待跑索引切成连续块(缺省 8 首/块),每块起一个 s7 子进程(--offset/--limit)写【本实例
     独名临时文件 .part{i0}_{pid}】,成功才并入主标签文件 —— append 语义由持锁驱动器独占;
  4. 块超时/失败 → 自动二分为单曲重试:好曲全保,只有真坏曲记名跳过(不再整块陪葬);
  5. 超时子进程由 subprocess.run 杀死,不留僵尸;Windows 上被杀子进程的文件句柄释放有延迟,
     所有删除走 _try_unlink 容错重试,删不掉的孤儿 .part 下次启动清扫 —— 删除永不炸主流程;
  6. 主标签文件已存在但无状态文件(来历不明,如手工分块的半截产物)→ 改名 .orphan 留档,
     从头重跑 —— 不删任何东西,也不停下来等人;
  7. 收尾打印 nasap_segments=/nasap_failed=(SOP 解析)+ 失败清单落 reports/s7_resilient.json。

用法(执行端;sop_next --go 的 P5c 就是它,一般不用手动跑):
  python scripts/s7_resilient.py                  # 跑/续跑(锁被占则等待)
  python scripts/s7_resilient.py --retry-failed   # 修完代码后重试之前记名失败的曲
  python scripts/s7_resilient.py --restart        # 清状态+产物,整轮重来
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rubato.platform import harden_stdout

ROOT = Path(r"D:\vscode_projects\ee_download")
WORK = ROOT / "work"


def count_pieces(csv_path: str) -> int:
    import pandas as pd
    df = pd.read_csv(str(csv_path))
    has = df["maestro_audio_performance"].notna() & (df["maestro_audio_performance"] != "")
    return int(has.sum())


def _try_unlink(p: Path, tries: int = 5, delay: float = 2.0) -> bool:
    """Windows 容错删除:被杀子进程的句柄释放有延迟(实测 WinError 32 炸过整个驱动器)。
    重试几轮;仍占用 → 放着不管(孤儿 .part 下次启动清扫),绝不让删除失败中断主流程。"""
    for _ in range(tries):
        try:
            p.unlink(missing_ok=True)
            return True
        except OSError:
            time.sleep(delay)
    return False


def acquire_lock(lock: Path, stale_sec: float, wait: bool) -> bool:
    """单实例锁(O_EXCL 原子创建,内容 pid)。持锁方每完成一块 touch 刷新 mtime;
    锁 mtime 超过 stale_sec 未刷新 = 持锁方已死 → 接管。wait=True 时礼貌等待
    (--go 全自动:等手动实例跑完自己接着干,不停下来要人拍板)。"""
    t0 = time.time()
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
                holder = lock.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue                    # 锁刚被释放,立刻重试
            if age > stale_sec:
                print(f"⚠ 锁陈旧({age:.0f}s 未刷新,持有者 pid={holder} 判定已死)→ 接管")
                _try_unlink(lock, tries=2, delay=1.0)
                continue
            if not wait:
                print(f"✗ 另一实例在跑(pid={holder},锁 {lock});等它跑完或删锁后重试")
                return False
            if int(time.time() - t0) % 300 < 30:
                print(f"… 等待另一实例(pid={holder})释放锁({(time.time() - t0) / 60:.0f} 分钟)",
                      flush=True)
            time.sleep(30)


def spans_of(pending: list[int], chunk: int) -> list[tuple[int, int]]:
    """待跑索引 → 连续 (offset, k) 块,k≤chunk。"""
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(pending):
        j = i
        while (j + 1 < len(pending) and pending[j + 1] == pending[j] + 1
               and (j - i + 1) < chunk):
            j += 1
        out.append((pending[i], j - i + 1))
        i = j + 1
    return out


def _drive(args, out: Path, state_p: Path, lock: Path) -> int:
    if args.restart:
        _try_unlink(out)
        _try_unlink(state_p)
        print("--restart:已清产物+状态。")
    if out.exists() and not state_p.exists():
        orphan = out.with_suffix(out.suffix + ".orphan")
        out.replace(orphan)                 # 不删,留档;来历不明的产物不能混进正品
        print(f"⚠ 发现无状态记账的旧产物(手工分块跑的残缺件?)→ 已改名留档 {orphan.name},从头重跑")

    n = args.n_pieces or count_pieces(args.metadata)
    st = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() \
        else {"done": [], "failed": {}}
    done: set[int] = set(st.get("done", []))
    failed: dict[str, str] = dict(st.get("failed", {}))
    if args.retry_failed and failed:
        print(f"--retry-failed:重试 {len(failed)} 首记名失败曲")
        failed = {}

    def save():
        st2 = {"done": sorted(done), "failed": failed}
        state_p.parent.mkdir(parents=True, exist_ok=True)
        state_p.write_text(json.dumps(st2, ensure_ascii=False), encoding="utf-8")
        try:
            lock.touch()                    # 心跳:证明持锁方活着(接管判据)
        except OSError:
            pass

    pending = [i for i in range(n) if i not in done and str(i) not in failed]
    print(f"pieces={n} done={len(done)} failed={len(failed)} pending={len(pending)}")

    def run_span(i0: int, k: int) -> tuple[bool, str | None, int]:
        """跑 [i0, i0+k):成功 → (True, None, 并入行数);失败/超时 → (False, 原因, 0)。"""
        tmp = out.with_suffix(f".part{i0}_{os.getpid()}")   # 独名:不与旧/并发实例残件相撞
        _try_unlink(tmp, tries=2, delay=1.0)
        cmd = [args.python, args.script, "--offset", str(i0), "--limit", str(k),
               "--out-labels", str(tmp)]
        timeout = args.per_piece_timeout * k + args.spawn_overhead
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        try:
            p = subprocess.run(cmd, cwd=str(REPO), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=timeout, env=env)
            ok, reason = p.returncode == 0, None if p.returncode == 0 else f"rc={p.returncode}"
        except subprocess.TimeoutExpired:
            ok, reason = False, f"timeout>{timeout:.0f}s"   # run() 已杀子进程,不留僵尸
        lines = 0
        if ok and tmp.exists():
            with open(tmp, encoding="utf-8") as fi, open(out, "a", encoding="utf-8") as fo:
                for line in fi:
                    if line.strip():
                        fo.write(line if line.endswith("\n") else line + "\n")
                        lines += 1
        _try_unlink(tmp)                    # 删不掉就留作孤儿,下次启动清扫
        return ok, reason, lines

    t0 = time.time()
    n_rows = 0
    for i0, k in spans_of(pending, args.chunk):
        ok, reason, lines = run_span(i0, k)
        if ok:
            done.update(range(i0, i0 + k))
            n_rows += lines
            print(f"[{i0}..{i0 + k}) OK +{lines} 行(累计新增 {n_rows},{time.time() - t0:.0f}s)",
                  flush=True)
        elif k == 1:
            failed[str(i0)] = reason or "?"
            print(f"[{i0}] 失败记名跳过: {reason}", flush=True)
        else:
            print(f"[{i0}..{i0 + k}) 块失败({reason})→ 二分单曲重试", flush=True)
            for i in range(i0, i0 + k):
                ok1, r1, l1 = run_span(i, 1)
                if ok1:
                    done.add(i)
                    n_rows += l1
                else:
                    failed[str(i)] = r1 or "?"
                    print(f"  [{i}] 失败记名跳过: {r1}", flush=True)
        save()

    total = 0
    if out.exists():
        with open(out, encoding="utf-8") as f:
            total = sum(1 for line in f if line.strip())
    rep = {"pieces": n, "done": len(done), "failed": failed,
           "labels_total": total, "elapsed_s": round(time.time() - t0, 1)}
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n===== 收尾(失败清单已落 {args.report})=====")
    print(f"  完成 {len(done)}/{n} 曲;失败记名 {len(failed)} 曲(逐曲原因见报告)")
    print(f"  nasap_segments={total}")
    print(f"  nasap_failed={len(failed)}")
    if failed:
        worst = list(failed.items())[:8]
        print("  失败样本: " + "; ".join(f"#{i}:{r}" for i, r in worst))
        print("  【贴回给用户】失败占比大(>5%)才值得修 repeat 展开;零星挂死曲跳过即可。")
    return 0 if total > 0 and len(done) + len(failed) == n else 1


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="nASAP s7 逐曲隔离驱动(超时杀/断点续跑/失败记名)")
    ap.add_argument("--metadata", default=str(ROOT / "asap-dataset" / "asap-dataset" / "metadata.csv"))
    ap.add_argument("--out-labels", default=str(WORK / "nasap_labels.jsonl"))
    ap.add_argument("--state", default=str(WORK / "nasap_s7_state.json"))
    ap.add_argument("--script", default=str(REPO / "scripts" / "s7_full_nasap.py"))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--report", default=str(ROOT / "reports" / "s7_resilient.json"))
    ap.add_argument("--n-pieces", type=int, default=0, help="0=从 metadata 数(测试用覆盖)")
    ap.add_argument("--chunk", type=int, default=8)
    ap.add_argument("--per-piece-timeout", type=float, default=180.0)
    ap.add_argument("--spawn-overhead", type=float, default=60.0,
                    help="子进程解释器+import 的额外时限(测试可调小)")
    ap.add_argument("--restart", action="store_true", help="清状态+产物,整轮重来")
    ap.add_argument("--retry-failed", action="store_true", help="清失败记名,重试那些曲")
    ap.add_argument("--no-wait", action="store_true", help="锁被占时立即退出(缺省礼貌等待)")
    args = ap.parse_args(argv)

    out = Path(args.out_labels)
    state_p = Path(args.state)
    lock = state_p.with_suffix(".lock")
    stale = args.per_piece_timeout * args.chunk + args.spawn_overhead * 2 + 120
    if not acquire_lock(lock, stale_sec=stale, wait=not args.no_wait):
        return 3
    try:
        # 孤儿 .part 清扫(上一实例被杀/崩溃的残件;仍被占用的跳过,下次再清)
        for f in out.parent.glob(out.stem + ".part*"):
            _try_unlink(f, tries=1, delay=0.0)
        return _drive(args, out, state_p, lock)
    finally:
        _try_unlink(lock, tries=3, delay=0.5)


if __name__ == "__main__":
    raise SystemExit(main())
