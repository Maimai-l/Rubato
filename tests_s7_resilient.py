"""s7 韧性驱动器回归:块失败二分单曲、超时杀、断点续跑、孤儿产物留档。
运行: python tests_s7_resilient.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import scripts.s7_resilient as rz

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


tmp = Path(tempfile.mkdtemp())

print("[0] spans_of:非连续待跑索引切成连续块")
check("spans_basic", rz.spans_of([0, 1, 2, 3], 8) == [(0, 4)])
check("spans_chunked", rz.spans_of(list(range(10)), 4) == [(0, 4), (4, 4), (8, 2)])
check("spans_gap", rz.spans_of([0, 1, 5, 6, 7], 8) == [(0, 2), (5, 3)])
check("spans_empty", rz.spans_of([], 8) == [])

# 假 s7:曲 3 失败(rc=1,且死前写了 0..2 —— 驱动器必须丢弃整块半截产物再二分),
# 曲 7 挂死(sleep,触发超时杀)。其余每曲写一行。
stub = tmp / "stub_s7.py"
stub.write_text(
    "import argparse, sys, time, json\n"
    "ap = argparse.ArgumentParser()\n"
    "ap.add_argument('--offset', type=int, default=0)\n"
    "ap.add_argument('--limit', type=int, default=0)\n"
    "ap.add_argument('--out-labels', default='')\n"
    "a = ap.parse_args()\n"
    "f = open(a.out_labels, 'a', encoding='utf-8')\n"
    "for i in range(a.offset, a.offset + a.limit):\n"
    "    if i == 3: sys.exit(1)\n"
    "    if i == 7: time.sleep(120)\n"
    "    f.write(json.dumps({'utt_id': f'nasap_p{i:03d}_x_000', 'piece': i}) + '\\n')\n"
    "    f.flush()\n",
    encoding="utf-8")

out = tmp / "nasap_labels.jsonl"
state = tmp / "state.json"
rep = tmp / "rep.json"
base = ["--script", str(stub), "--n-pieces", "12", "--out-labels", str(out),
        "--state", str(state), "--report", str(rep),
        "--chunk", "8", "--per-piece-timeout", "2", "--spawn-overhead", "1"]

print("[1] 全量跑:坏曲 3(rc=1)/挂死曲 7(超时)记名跳过,其余 10 曲全保")
rc = rz.main(base)
check("rc0", rc == 0, rc)
rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
check("rows_10", sorted(r["piece"] for r in rows) == [0, 1, 2, 4, 5, 6, 8, 9, 10, 11],
      sorted(r["piece"] for r in rows))
st = json.loads(state.read_text(encoding="utf-8"))
check("failed_named", set(st["failed"]) == {"3", "7"}, st["failed"])
check("timeout_reason", st["failed"]["7"].startswith("timeout"), st["failed"]["7"])
check("done_10", len(st["done"]) == 10)
check("no_dup_rows", len(rows) == len({r["piece"] for r in rows}))
check("report_written", json.loads(rep.read_text(encoding="utf-8"))["labels_total"] == 10)

print("[2] 续跑:无待跑 → 不新增行、状态不变")
rc2 = rz.main(base)
rows2 = [l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
check("resume_rc0", rc2 == 0)
check("resume_no_dup", len(rows2) == 10, len(rows2))

print("[3] --retry-failed:清记名重试(3/7 仍失败,不新增行)")
rc3 = rz.main([*base, "--retry-failed"])
st3 = json.loads(state.read_text(encoding="utf-8"))
check("retry_refail", set(st3["failed"]) == {"3", "7"})
check("retry_no_dup", len([l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]) == 10)

print("[4] 孤儿产物:有产物无状态 → 改名 .orphan 留档,从头重跑(不删、不停)")
state.unlink()
rc4 = rz.main(base)
check("orphan_kept", out.with_suffix(out.suffix + ".orphan").exists())
rows4 = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
check("orphan_rerun", sorted(r["piece"] for r in rows4) == [0, 1, 2, 4, 5, 6, 8, 9, 10, 11])
check("orphan_rc0", rc4 == 0)

print("[5] --restart:清干净重来")
rc5 = rz.main([*base, "--restart"])
check("restart_rc0", rc5 == 0)
check("restart_rows", len([l for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]) == 10)
check("lock_released", not state.with_suffix(".lock").exists())

print("[6] 单实例锁:活锁 → --no-wait 退出码 3 且不动产物;陈旧锁 → 接管照跑")
import time as _t
lock = state.with_suffix(".lock")
lock.write_text("99999", encoding="utf-8")            # 新鲜锁 = 有实例在跑
rows_before = out.read_text(encoding="utf-8")
rc6 = rz.main([*base, "--no-wait"])
check("locked_rc3", rc6 == 3, rc6)
check("locked_untouched", out.read_text(encoding="utf-8") == rows_before)
check("lock_not_stolen", lock.exists())
import os as _os
_os.utime(lock, (_t.time() - 99999, _t.time() - 99999))   # 陈旧锁 = 持有者已死
rc7 = rz.main([*base, "--no-wait"])
check("stale_takeover_rc0", rc7 == 0, rc7)
check("stale_lock_released", not lock.exists())

print("[7] 孤儿 .part 清扫 + _try_unlink 容错")
orphan_part = out.parent / (out.stem + ".part999_1234")
orphan_part.write_text("junk", encoding="utf-8")
rz.main(base)                                          # 续跑(无待办)顺带清扫
check("orphan_part_swept", not orphan_part.exists())
check("unlink_missing_ok", rz._try_unlink(tmp / "no_such_file", tries=1, delay=0.0))

print(f"\n全部通过: {PASS} 项")
