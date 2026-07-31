"""sop_next 状态机回归测试:一条 --go 自动干到底、失败不记账、断点续走、判据数字解析。
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
os.environ["SOP_AUTO_REPORT"] = "0"   # 假步骤禁真 git:上报路径曾把测试垃圾推上共享分支
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
        dict(id="B", title="步骤B(判据达标)",
             cmds=[[PY, "-c", "print('vn_ok=17')"]],
             parse={"vn_ok": r"vn_ok=(\d+)"},
             require=lambda n: None if int(n["vn_ok"]) >= 15 else "vn_ok<15"),
        dict(id="C", title="步骤C(可失败:flag 存在就 exit 1)",
             cmds=[[PY, "-c",
                    f"import sys,os; sys.exit(1 if os.path.exists(r'{FLAG}') else 0)"]]),
        dict(id="D", title="步骤D(收尾)",
             cmds=[[PY, "-c", "print('tail done')"]]),
    ]


sop._steps = fake_steps

print("[1] 一条 --go 自动干到底:无闸、无需任何人批准,全部完成 rc=0")
rc = sop.main(["--go"])
check("auto_all_rc0", rc == 0, rc)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("all_done", st["done"] == ["A", "B", "C", "D"], st["done"])
check("numbers_parsed", st["numbers"]["A"] == {"ok": "7", "fail": "0"}, st["numbers"])

print("[2] 幂等:再跑 --go 不重复任何步骤,直接报全部完成")
check("rerun_rc0", sop.main(["--go"]) == 0)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("no_dup", st["done"] == ["A", "B", "C", "D"], st["done"])

print("[3] 中途失败:C 挂 → rc=1、C 不记账、A/B 保留;修复后重跑从 C 续走")
Path(os.environ["SOP_STATE"]).unlink()
FLAG.touch()
rc = sop.main(["--go"])
check("fail_rc1", rc == 1, rc)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("ab_done_c_not", st["done"] == ["A", "B"], st["done"])
FLAG.unlink()
rc = sop.main(["--go"])
check("resume_rc0", rc == 0, rc)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("resume_all", st["done"] == ["A", "B", "C", "D"], st["done"])

print("[4] --status 正常渲染;--reset-step 标回未完成")
check("status_rc0", sop.main(["--status"]) == 0)
check("reset_rc0", sop.main(["--reset-step", "D"]) == 0)
st = json.loads(Path(os.environ["SOP_STATE"]).read_text(encoding="utf-8"))
check("d_reset", "D" not in st["done"], st["done"])

print("[5] require 判据不达标 → rc=1 不记账(自动质量闸,非人肉闸)")
sop._steps = lambda: [dict(id="R", title="判据步",
                           cmds=[[PY, "-c", "print('vn_ok=1')"]],
                           parse={"vn_ok": r"vn_ok=(\d+)"},
                           require=lambda n: None if int(n["vn_ok"]) >= 15 else "vn_ok<15")]
Path(os.environ["SOP_STATE"]).unlink()
rc = sop.main(["--go"])
check("require_fail_rc1", rc == 1, rc)
sp = Path(os.environ["SOP_STATE"])
st = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {"done": []}
check("require_not_done", st["done"] == [], st["done"])

print("[5b] resets:某步完成 → 自动把下游步骤标回未完成(--go 按序补跑,不再要人记得 reset)")
sop._steps = lambda: [
    dict(id="X", title="产出步(触发下游重跑)",
         cmds=[[PY, "-c", "print('x')"]], resets=["Y", "Z"]),
    dict(id="Y", title="下游1", cmds=[[PY, "-c", "print('y')"]]),
    dict(id="Z", title="下游2", cmds=[[PY, "-c", "print('z')"]]),
]
sp.write_text(json.dumps({"done": ["Y", "Z"], "approvals": {}, "numbers": {}}), encoding="utf-8")
rc = sop.main(["--go"])                       # X 跑完重置 Y/Z → 循环按序把 Y/Z 补跑回来
check("resets_rc0", rc == 0, rc)
st = json.loads(sp.read_text(encoding="utf-8"))
check("resets_reran_downstream", st["done"] == ["X", "Y", "Z"], st["done"])

print("[5c] resets_if:条件不满足(空转步)→ 下游【不】被重置(上次无条件重置吓停过执行端)")
sop._steps = lambda: [
    dict(id="X2", title="空转步(affected=0)",
         cmds=[[PY, "-c", "print('受影响: 0 曲')"]],
         parse={"affected_pieces": r"受影响: (\d+) 曲"},
         resets=["Y2"], resets_if=lambda n: int(n.get("affected_pieces", "0") or 0) > 0),
    dict(id="Y2", title="下游", cmds=[[PY, "-c", "print('y2')"]]),
]
sp.write_text(json.dumps({"done": ["Y2"], "approvals": {}, "numbers": {}}), encoding="utf-8")
rc = sop.main(["--go"])
st = json.loads(sp.read_text(encoding="utf-8"))
check("resets_if_noop", rc == 0 and sorted(st["done"]) == ["X2", "Y2"], st["done"])
# 条件满足(affected>0)→ 重置生效
sop._steps = lambda: [
    dict(id="X3", title="真清场步(affected=3)",
         cmds=[[PY, "-c", "print('受影响: 3 曲')"]],
         parse={"affected_pieces": r"受影响: (\d+) 曲"},
         resets=["Y3"], resets_if=lambda n: int(n.get("affected_pieces", "0") or 0) > 0),
    dict(id="Y3", title="下游", cmds=[[PY, "-c", "print('y3')"]]),
]
sp.write_text(json.dumps({"done": ["Y3"], "approvals": {}, "numbers": {}}), encoding="utf-8")
rc = sop.main(["--go"])
st = json.loads(sp.read_text(encoding="utf-8"))
check("resets_if_fires", rc == 0 and st["done"] == ["X3", "Y3"], st["done"])

print("[6] 真实步骤表:无任何 gate 字段残留")
check("no_gates_left", all(not s.get("gate") for s in sop._steps())
      if sop._steps.__name__ != "<lambda>" else True)
import importlib
importlib.reload(sop)
check("real_steps_no_gate", all(not s.get("gate") for s in sop._steps()),
      [s["id"] for s in sop._steps() if s.get("gate")])

print(f"\n全部通过: {PASS} 项")
