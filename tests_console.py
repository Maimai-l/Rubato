"""GBK 控制台硬化回归测试 —— 复现并锁死执行端 S5 五次崩溃的真凶(打印 '−' 崩)。
运行: python tests_console.py

背景:执行端 Windows 控制台是 GBK(cp936),print 一个非 GBK 字符('−' U+2212、作曲家名
'Fauré'、音乐符号 '♭')会 UnicodeEncodeError 整个进程崩 —— S5 五次全崩在预算打印的 '−',
VN 一次没跑成。harden_stdout() 放宽 stdout 的编码错误策略(坏字符转义,不抛异常),中文照常。
"""
import io
import sys

sys.path.insert(0, ".")
from rubato.platform import harden_stdout, quiet_wandb

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


_real = sys.stdout


def _gbk():
    buf = io.BytesIO()
    return buf, io.TextIOWrapper(buf, encoding="gbk", line_buffering=True)


print("[1] 硬化前:GBK stdout 打印 '−' 必崩(复现执行端 BLOCKER)")
buf, w = _gbk(); sys.stdout = w
crashed = False
try:
    print("可用 15.8 − 留 4.0")
except UnicodeEncodeError:
    crashed = True
w.flush(); sys.stdout = _real
try: w.detach()
except Exception: pass
check("pre_harden_crashes_on_minus", crashed, "GBK 下 '−' 应崩,复现执行端")

print("[2] 硬化后:'−'/Fauré/♭/↔/⇒/中文 全部打印不崩")
buf, w = _gbk(); sys.stdout = w
harden_stdout()
ok = True; err = None
try:
    print("可用 15.8 − 留 4.0 | Fauré/Dvořák | A♭3 | ↔ ⇒ | ✓✗²")
    print("中文照常:内存预算调度 回收 关")
except Exception as e:
    ok = False; err = repr(e)
sys.stdout.flush(); data = buf.getvalue(); sys.stdout = _real
try: w.detach()
except Exception: pass
check("post_harden_no_crash", ok, err or "")
check("chinese_still_gbk", "内存预算调度".encode("gbk") in data, "中文应仍按 GBK 正常编码")
check("bad_chars_escaped_not_dropped", b"\\u2212" in data, "坏字符应转义保留,不静默丢")

print("[3] quiet_wandb 关掉 wandb 的 stdout 拦截(virtuoso import 带出 wandb 的根因)")
import os
for k in ("WANDB_CONSOLE", "WANDB_MODE", "WANDB_SILENT"):
    os.environ.pop(k, None)
quiet_wandb()
check("wandb_console_off", os.environ.get("WANDB_CONSOLE") == "off")
check("wandb_mode_disabled", os.environ.get("WANDB_MODE") == "disabled")

print("[4] harden_stdout 幂等 + 真实 stdout 上调用不炸")
harden_stdout(); harden_stdout()
check("idempotent_on_real_stdout", True)

print(f"\n全部通过: {PASS} 项")
