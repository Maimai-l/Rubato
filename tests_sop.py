"""sop_next 状态机回归测试:自动推进、GATE 硬停、失败不记账、断点续走、判据数字解析。
运行: python tests_sop.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ["SOP_ROOT"] = str(tmp)
os.environ["SOP_STATE"] = str(tmp / "state.json")
os.environ["SOP_LOGS"] = str(tmp / "logs")
sys.path.insert(0, ".")

import scripts.sop_next as sop

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


PY = sys.executable
FLAG = tmp / "fail_flag"


def fake_steps():
    return [
        dict(id="A", title="步骤A(解析数字)",
             cmds=[[PY, "-c", "print('DONE: ok=7 fail=0')"]],
             parse={"ok": r"ok=(\d+)", "fail": r"fail=(\d+)"}),
        dict(id="B", title="步骤B(判据不过就停)",
             cmds=[[PY, "-c", "print('vn_ok=3')"]],
             parse={"vn_ok": r"vn_ok=(\d+)"},
             require=lambda n: None if int(n["vn_ok"]) >= 3 else "太小"),
        dict(id="C", title="步骤C(GATE 拦截)", gate="G1",
             cmds=[[PY, "-c", "print('gated work done')"]]),
        dict(id="D", title="步骤D(可失败:flag 文件存在就 exit 1)",
             cmds=[[PY, "-c",
                    f"import sys,os; sys.exit(1 if os.path.exists(r'{FLAG}') else 0)"]]),
    ]


sop._steps = fake_steps

print("[1] --go 自动推进 A、B,到 C 的 GATE 硬停(rc=3)")
rc = sop.main(["--go"])
check("gate_rc3", rc == 3, rc)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("ab_done", st["done"] == ["A", "B"], st["done"])
check("numbers_parsed", st["numbers"]["A"] == {"ok": "7", "fail": "0"}, st["numbers"])

print("[2] 再跑 --go 仍被 GATE 拦(不静默越闸)")
check("still_gated", sop.main(["--go"]) == 3)

print("[3] --approve G1 后 --go 过闸;D 因 flag 失败(rc=1)且不记账")
FLAG.touch()
check("approve_rc0", sop.main(["--approve", "G1"]) == 0)
rc = sop.main(["--go"])
check("fail_rc1", rc == 1, rc)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("c_done_d_not", st["done"] == ["A", "B", "C"], st["done"])

print("[4] 排障后重跑 --go:从 D 继续(断点续走,不重复 A/B/C),全部完成 rc=0")
FLAG.unlink()
rc = sop.main(["--go"])
check("resume_finish_rc0", rc == 0, rc)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("all_done", st["done"] == ["A", "B", "C", "D"], st["done"])

print("[5] --status 正常渲染;--reset-step 标回未完成")
check("status_rc0", sop.main(["--status"]) == 0)
check("reset_rc0", sop.main(["--reset-step", "D"]) == 0)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("d_reset", "D" not in st["done"], st["done"])

print("[6] require 判据失败:数字不达标 → rc=1 不记账")
sop._steps = lambda: [dict(id="R", title="判据步",
                           cmds=[[PY, "-c", "print('vn_ok=1')"]],
                           parse={"vn_ok": r"vn_ok=(\d+)"},
                           require=lambda n: None if int(n["vn_ok"]) >= 15 else "vn_ok<15")]
Path(os.environ["SOP_STATE"]).unlink()
rc = sop.main(["--go"])
check("require_fail_rc1", rc == 1, rc)
sp = Path(os.environ["SOP_STATE"])   # 失败不落盘:state 要么不存在,要么 done 为空
st = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {"done": []}
check("require_not_done", st["done"] == [], st["done"])

print(f"\n全部通过: {PASS} 项")
