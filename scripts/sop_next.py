"""
SOP 状态机驱动器 —— 执行端【只需要反复跑一条命令】,流程自动推进,不依赖任何人的记忆。

为什么存在:长流程会忘、"说要做 X"然后不动。本脚本把 SOP_RERUN.md 变成状态机:
进度存 work/sop_state.json(磁盘,不靠上下文记忆);每次 --go 找到下一步、直接执行、
解析判据数字、存档、打印【贴回给用户】块;GATE 步骤硬停,必须用户明确批准后
用 --approve 才能过 —— "要不要做"永远是用户说了算,"做"就是跑 --go。

执行端用法(全部三条,没有别的):
  python scripts/sop_next.py --status          # 看进度表(随时)
  python scripts/sop_next.py --go              # 执行下一步(连续推进,遇 GATE/失败/长任务边界停)
  python scripts/sop_next.py --approve P1      # 仅当用户明确说"批准 P1"时运行

底层脚本全部可续跑/幂等:任何一步中断后重跑 --go 会安全继续,不重复已完成的工作。
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from rubato.platform import harden_stdout

ROOT = Path(os.environ.get("SOP_ROOT", r"D:\vscode_projects\ee_download"))
WORK = ROOT / "work"
STATE = Path(os.environ.get("SOP_STATE", str(WORK / "sop_state.json")))
LOGD = Path(os.environ.get("SOP_LOGS", str(ROOT / "reports")))
PY = sys.executable


# ---------------------------------------------------------------- P0 的本地动作(改名留档)

def _p0_action(log):
    for name in ("a2s_corpus.txt", "pdmx_a2s_labels.jsonl"):
        src, dst = WORK / name, WORK / (name + ".old")
        if src.exists() and not dst.exists():
            src.rename(dst)
            log(f"  留档: {name} -> {name}.old")
        else:
            log(f"  跳过: {name}(不存在或已留档)")
    try:
        rev = subprocess.run(["git", "log", "--oneline", "-1"], cwd=str(REPO),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30).stdout.strip()
    except Exception:
        rev = "unknown"
    log(f"  commit: {rev}")
    return {"commit": rev.split(" ")[0] if rev else "unknown"}


# ---------------------------------------------------------------- 步骤表(照 SOP_RERUN.md)

def _steps():
    S = lambda *a: [PY, *a]
    return [
        dict(id="P0", title="准备:旧语料/旧文本标签改名留档 + 记录 commit",
             action=_p0_action),
        dict(id="P1a", title="S4 速度钳制·干跑(报告离谱速度曲数)",
             cmds=[S("scripts/s4_fix_tempo.py")],
             parse={"outlier_pieces": r"的曲 = (\d+)"}),
        dict(id="P1b", title="S4 速度钳制·实施(钳 80bpm + 删旧整曲音频)", gate="P1",
             cmds=[S("scripts/s4_fix_tempo.py", "--apply")],
             parse={"clamped": r"改写 set_tempo (\d+)", "audio_deleted": r"删整曲音频 (\d+)"}),
        dict(id="P2a", title="S5 全量清场(repair --all --apply,labels 留 .bak)",
             cmds=[S("scripts/s5_repair_segments.py", "--all", "--apply")],
             parse={"rows_dropped": r"剔除 (\d+) 行", "audio_deleted": r"删段音频 (\d+)"}),
        dict(id="P2b", title="S5 VN 冒烟(20 曲,判据 vn_ok≥15)",
             cmds=[S("scripts/s5_vn_render.py", "--limit", "20",
                     "--out-corpus", str(WORK / "a2s_corpus_vn.txt"))],
             parse={"vn_ok": r"vn_ok=(\d+)", "utts": r"utts=(\d+)", "tast": r"TAST=(\d+)"},
             require=lambda n: None if int(n.get("vn_ok", 0)) >= 15
                     else f"vn_ok={n.get('vn_ok')} < 15,冒烟不过,停"),
        dict(id="P2c", title="S5 VN 全量重渲(天级,可中断后重跑 --go 续)", gate="P2FULL",
             cmds=[S("scripts/s5_vn_render.py",
                     "--out-corpus", str(WORK / "a2s_corpus_vn.txt"))],
             parse={"vn_ok": r"vn_ok=(\d+)", "utts": r"utts=(\d+)", "tast": r"TAST=(\d+)",
                    "vn_recycles": r"vn_子进程回收=(\d+)"}),
        dict(id="P3", title="S4 补渲被删的离谱速度曲(其余自动跳过)",
             cmds=[S("scripts/s4_parallel.py")],
             parse={"ok": r"ok=(\d+)", "fail": r"fail=(\d+)"}),
        dict(id="P4", title="文本标签全量重生成(真 tmap 分段,CPU)",
             cmds=[S("scripts/s5_parallel.py")]),
        dict(id="P5a", title="MAESTRO AMT 切窗·冒烟(5 场)",
             cmds=[S("scripts/s6_amt_windows.py", "--limit", "5")],
             parse={"windows": r"windows=(\d+)", "labels": r"labels=(\d+)"},
             require=lambda n: None if int(n.get("labels", 0)) > 0 else "labels=0,停"),
        dict(id="P5b", title="MAESTRO AMT 切窗·全量",
             cmds=[S("scripts/s6_amt_windows.py")],
             parse={"windows": r"windows=(\d+)", "labels": r"labels=(\d+)",
                    "win_fail": r"win_fail=(\d+)"}),
        dict(id="P6a", title="S4 段切割·冒烟(20 曲)",
             cmds=[S("scripts/s4_slice_segments.py", "--limit", "20")],
             parse={"sliced": r"sliced = (\d+)", "structure_mismatch": r"structure_mismatch = (\d+)"}),
        dict(id="P6b", title="S4 段切割·全量(重点看 structure_mismatch 占比)",
             cmds=[S("scripts/s4_slice_segments.py")],
             parse={"sliced": r"sliced = (\d+)", "structure_mismatch": r"structure_mismatch = (\d+)",
                    "seg_too_long": r"seg_too_long = (\d+)"},
             require=lambda n: None if int(n.get("sliced", 0)) > 0 else "sliced=0,配对全失败,停"),
        dict(id="P7", title="tokenizer 重训(两份语料)+ 字形覆盖检查", gate="P7",
             cmds=[[PY, "-c",
                    "from rubato.data.tokenizer import train_unigram; "
                    f"print(train_unigram([r'{WORK / 'a2s_corpus.txt'}', r'{WORK / 'a2s_corpus_vn.txt'}'],"
                    f"r'{WORK / 'rubato_spm'}',vocab_size=8000,spec_path='configs/vocab_spec.json'))"],
                   [PY, "-c",
                    "from rubato.data.tokenizer import check_glyph_coverage as c; "
                    f"print(c(r'{WORK / 'rubato_spm.model'}'))"]],
             parse={"vocab": r"vocab_size\D+(\d+)", "split_rate": r"split_rate\D+([\d.]+)"},
             require=lambda n: None if n.get("vocab") == "8000"
                     and float(n.get("split_rate", 1)) < 0.30
                     else f"vocab={n.get('vocab')} split_rate={n.get('split_rate')} 未达标,停"),
    ]


# ---------------------------------------------------------------- 状态机

def _load():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": [], "approvals": {}, "numbers": {}}


def _save(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def _run_step(step, st) -> bool:
    """执行一步。成功→记账返回 True;失败→打印贴回块返回 False。"""
    sid = step["id"]
    LOGD.mkdir(parents=True, exist_ok=True)
    log_path = LOGD / f"sop_{sid}.log"
    lines: list[str] = []

    def log(s):
        print(s, flush=True)
        lines.append(s)

    print(f"\n━━━ [{sid}] {step['title']} ━━━", flush=True)
    t0 = time.time()
    rc = 0
    if step.get("action"):
        try:
            nums = step["action"](log) or {}
        except Exception as e:
            log(f"  失败: {type(e).__name__}: {e}")
            rc = 1
            nums = {}
    else:
        nums = {}
        for cmd in step["cmds"]:
            log("  $ " + " ".join(str(c) for c in cmd))
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            p = subprocess.Popen(cmd, cwd=str(REPO), stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, env=env)
            for raw in p.stdout:
                s = raw.decode("utf-8", errors="replace").rstrip()
                print("  " + s, flush=True)
                lines.append(s)
            rc = p.wait()
            if rc != 0:
                break
        text = "\n".join(lines)
        for key, pat in (step.get("parse") or {}).items():
            m = re.search(pat, text)
            if m:
                nums[key] = m.group(1)
    log_path.write_text("\n".join(lines), encoding="utf-8")

    ok = rc == 0
    err = None
    if ok and step.get("require"):
        err = step["require"](nums)
        ok = err is None
    dt = time.time() - t0

    print(f"\n===== 贴回给用户([{sid}] {'完成' if ok else '失败'},{dt / 60:.1f} 分钟)=====")
    print(f"  {step['title']}")
    for k, v in nums.items():
        print(f"  {k} = {v}")
    if not ok:
        print(f"  ✗ {'退出码 ' + str(rc) if rc else ''}{err or ''}")
        print(f"  日志尾部({log_path}):")
        for s in lines[-12:]:
            print("    " + s)
        print("  【停】把这一块整段贴给用户,等指示。不要自己修、不要重试别的命令。")
        return False
    st["done"].append(sid)
    st["numbers"][sid] = nums
    _save(st)
    return True


def cmd_status(steps, st):
    print("SOP 进度(状态存盘 work/sop_state.json,不怕忘):")
    for s in steps:
        mark = "✅" if s["id"] in st["done"] else \
               ("🚫GATE未批" if s.get("gate") and not st["approvals"].get(s["gate"]) else "⬜")
        nums = st["numbers"].get(s["id"], {})
        extra = ("  " + " ".join(f"{k}={v}" for k, v in nums.items())) if nums else ""
        print(f"  {mark} [{s['id']}] {s['title']}{extra}")
    nxt = next((s for s in steps if s["id"] not in st["done"]), None)
    if nxt is None:
        print("\n全部完成。把 --status 输出整个贴给用户。")
    elif nxt.get("gate") and not st["approvals"].get(nxt["gate"]):
        print(f"\n下一步 [{nxt['id']}] 是 GATE({nxt['gate']}):把当前进度贴给用户,"
              f"等用户明确批准后运行: python scripts/sop_next.py --approve {nxt['gate']}")
    else:
        print(f"\n下一步: [{nxt['id']}] —— 运行 python scripts/sop_next.py --go")


def cmd_go(steps, st):
    ran = 0
    while True:
        nxt = next((s for s in steps if s["id"] not in st["done"]), None)
        if nxt is None:
            print("\n全部完成 ✅。运行 --status 并把进度表贴给用户。")
            return 0
        if nxt.get("gate") and not st["approvals"].get(nxt["gate"]):
            print(f"\n🚫 GATE [{nxt['gate']}] 拦在 [{nxt['id']}] {nxt['title']} 之前。")
            print("   把上面的贴回块/进度发给用户;【只有用户明确说批准】才运行:")
            print(f"   python scripts/sop_next.py --approve {nxt['gate']}")
            print("   然后再 --go。在那之前不要做任何别的事。")
            return 3
        if not _run_step(nxt, st):
            return 1
        ran += 1


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="SOP 状态机:--go 执行下一步;--status 看进度;--approve 过闸")
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--approve", default="", metavar="GATE",
                    help="仅当用户明确批准(如 P1/P2FULL/P7)")
    ap.add_argument("--reset-step", default="", help="把某步标回未完成(仅用户指示时用)")
    args = ap.parse_args(argv)
    steps = _steps()
    st = _load()
    if args.approve:
        st["approvals"][args.approve] = True
        _save(st)
        print(f"GATE {args.approve} 已记录为【用户已批准】。现在运行 --go 继续。")
        return 0
    if args.reset_step:
        st["done"] = [d for d in st["done"] if d != args.reset_step]
        _save(st)
        print(f"[{args.reset_step}] 已标回未完成。")
        return 0
    if args.go:
        return cmd_go(steps, st)
    cmd_status(steps, st)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
