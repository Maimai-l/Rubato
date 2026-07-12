"""
SOP 状态机驱动器 —— 一条命令从 P0 自动干到 P7,【不需要任何人催、任何人批】。

为什么存在:长流程会忘、"说要做 X"然后不动、等人说"执行"才执行 —— 全部病根一次拔掉。
进度存 work/sop_state.json(磁盘,不靠记忆);--go 自动连续推进:找下一步→执行→解析判据
数字→存档→打印【贴回给用户】块→继续下一步,直到 P7 全部完成。中途【只有真失败】才停
(判据不达标/退出码非零),失败块自带日志尾部,贴回后修复,再跑 --go 从断点继续。

执行端用法(两条,没有别的;启动后不要等任何人发话):
  python scripts/sop_next.py --go              # 一路干到底;失败才停;中断后重跑即续
  python scripts/sop_next.py --status          # 看进度表(随时)

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
PY_VN = r"D:\ProgramData\envs\py312\python.exe"     # VN/VirtuosoNet 必须 py312(与 NeMo 环境隔离)
PY_NEMO = r"D:\ProgramData\envs\nemo_test\python.exe"  # 其余脚本用 NeMo 环境


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
    S = lambda *a, py=PY: [py, *a]
    SV = lambda *a: [PY_VN, *a]   # VN/VirtuosoNet 用 py312
    return [
        dict(id="P0", title="准备:旧语料/旧文本标签改名留档 + 记录 commit",
             action=_p0_action),
        dict(id="P1a", title="S4 速度钳制·干跑(报告离谱速度曲数)",
             cmds=[S("scripts/s4_fix_tempo.py")],
             parse={"outlier_pieces": r"的曲 = (\d+)"}),
        dict(id="P1b", title="S4 速度钳制·实施(钳 80bpm + 删旧整曲音频)",
             cmds=[S("scripts/s4_fix_tempo.py", "--apply")],
             parse={"clamped": r"改写 set_tempo (\d+)", "audio_deleted": r"删整曲音频 (\d+)"}),
        dict(id="P1c", title="乐器审计:剔除非钢琴曲(鼓/吉他/人声…)+ 彻底清产物 + 验证表",
             cmds=[S("scripts/s3_instrument_audit.py", "--apply")],
             parse={"nonpiano": r"非钢琴 (\d+) 曲"},
             require=lambda n: None),   # 审计脚本清不干净会自己 exit 1(验证表非全 0)
        dict(id="P2a", title="S5 全量清场(repair --all --apply,labels 留 .bak)",
             cmds=[SV("scripts/s5_repair_segments.py", "--all", "--apply")],
             parse={"rows_dropped": r"剔除 (\d+) 行", "audio_deleted": r"删段音频 (\d+)"}),
        dict(id="P2b", title="S5 VN 冒烟(20 曲,判据 vn_ok≥15)",
             cmds=[SV("scripts/s5_vn_render.py", "--limit", "20",
                     "--out-corpus", str(WORK / "a2s_corpus_vn.txt"))],
             parse={"vn_ok": r"vn_ok=(\d+)", "utts": r"utts=(\d+)", "tast": r"TAST=(\d+)"},
             require=lambda n: None if int(n.get("vn_ok", 0)) >= 15
                     else f"vn_ok={n.get('vn_ok')} < 15,冒烟不过,停"),
        dict(id="P2c", title="S5 VN 全量重渲(天级,可中断后重跑 --go 续)",
             cmds=[SV("scripts/s5_vn_render.py",
                     "--out-corpus", str(WORK / "a2s_corpus_vn.txt"))],
             parse={"vn_ok": r"vn_ok=(\d+)", "utts": r"utts=(\d+)", "tast": r"TAST=(\d+)",
                    "vn_recycles": r"vn_子进程回收=(\d+)"}),
        dict(id="P2d", title="VN 段抽听采样(5 段音频+标签 → 贴文件夹路径给用户听)",
             cmds=[S("scripts/spot_check.py", "--labels", str(WORK / "pdmx_perf_labels.jsonl"),
                     "--n", "5", "--tag", "vn")]),
        # id=P2c1(弃 P2c0):旧版证据链读 .bak 翻车(多写者首份保留 → 扫出 affected=0 空转,
        # 还无条件重置了下游把执行端吓停)。新证据 = 活文件 TAST=null 行 + 待渲侧车;
        # 换 id 使执行端已记完成的 P2c0 不挡道,--go 自动重跑本步。
        dict(id="P2c1", title="钳制 TAST 整曲清场(D18 重渲;证据=活文件 TAST=null 行;无则秒过)",
             cmds=[S("scripts/rerender_tast_clamped.py", "--apply")],
             parse={"affected_pieces": r"受影响: (\d+) 曲", "live_null_rows": r"TAST=null 行 (\d+)",
                    "rows_dropped": r"标签行剔除 (\d+)"},
             # 真清了东西才重置下游(P2c 续跑补渲 → P2e 复扫验证 → 语料/tokenizer/装配重来);
             # 无受影响曲的空转【不】重置 —— 上次无条件重置把执行端吓出一份事故报告。
             resets=["P2c", "P2e", "P6c", "P7", "P8"],
             resets_if=lambda n: int(n.get("affected_pieces", "0") or 0) > 0),
        dict(id="P2e", title="TAST 戳修复(绝对演奏秒→段内相对秒;钳制行置 null;幂等)",
             cmds=[S("scripts/repair_tast_labels.py", "--apply")],
             parse={"tast_shifted": r"已修 (\d+) 行", "tast_nulled": r"置 null (\d+) 行"}),
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
        dict(id="P5c", title="nASAP 标签重生成(韧性驱动:逐曲隔离+超时杀+断点续跑,挂死曲记名跳过)",
             cmds=[S("scripts/s7_resilient.py")],
             parse={"nasap_segments": r"nasap_segments=(\d+)",
                    "nasap_failed": r"nasap_failed=(\d+)"},
             require=lambda n: None if int(n.get("nasap_segments", 0)) > 1000
                     else f"nasap_segments={n.get('nasap_segments')} 过少,对齐/标签管线有问题,停"),
        dict(id="P5d", title="nASAP 保守 split 分配(R-S7.4:val≈512 段,work_key 隔离)",
             cmds=[S("scripts/s7_assign_split.py", "--apply")],
             parse={"nasap_val": r"val 段 = (\d+)", "nasap_test": r"test 段 = (\d+)"}),
        dict(id="P6a", title="S4 段切割·冒烟(20 曲)",
             cmds=[S("scripts/s4_slice_segments.py", "--limit", "20")],
             parse={"sliced": r"sliced = (\d+)", "structure_mismatch": r"structure_mismatch = (\d+)"}),
        dict(id="P6b", title="S4 段切割·全量(重点看 structure_mismatch 占比)",
             cmds=[S("scripts/s4_slice_segments.py")],
             parse={"sliced": r"sliced = (\d+)", "structure_mismatch": r"structure_mismatch = (\d+)",
                    "seg_too_long": r"seg_too_long = (\d+)"},
             require=lambda n: None if int(n.get("sliced", 0)) > 0 else "sliced=0,配对全失败,停"),
        dict(id="P6b2", title="S4 段抽听采样(5 段音频+标签 → 贴文件夹路径给用户听)",
             cmds=[S("scripts/spot_check.py", "--labels", str(WORK / "pdmx_a2s_labels.jsonl"),
                     "--n", "5", "--tag", "s4")]),
        dict(id="P6c", title="语料重建(从标签文件确定性重建,不再依赖追加顺序)",
             cmds=[S("scripts/rebuild_corpus.py")],
             parse={"corpus_lines": r"corpus_lines=(\d+)"},
             require=lambda n: None if int(n.get("corpus_lines", 0)) > 100000
                     else f"corpus_lines={n.get('corpus_lines')} 过少,标签文件有问题,停"),
        dict(id="P7", title="tokenizer 重训(重建后语料)+ 字形覆盖检查",
             cmds=[[PY, "-c",
                    "from rubato.data.tokenizer import train_unigram; "
                    f"print(train_unigram([r'{WORK / 'a2s_corpus.txt'}'],"
                    f"r'{WORK / 'rubato_spm'}',vocab_size=8000,spec_path='configs/vocab_spec.json'))"],
                   [PY, "-c",
                    "from rubato.data.tokenizer import check_glyph_coverage as c; "
                    f"print(c(r'{WORK / 'rubato_spm.model'}'))"]],
             parse={"vocab": r"vocab_size\D+(\d+)", "split_rate": r"split_rate\D+([\d.]+)"},
             require=lambda n: None if n.get("vocab") == "8000"
                     and float(n.get("split_rate", 1)) < 0.30
                     else f"vocab={n.get('vocab')} split_rate={n.get('split_rate')} 未达标,停"),
        dict(id="P8", title="装配终检:build_dataset --dry-run(每源 kept>0,no_audio 不占大头)",
             cmds=[S("scripts/build_dataset.py", "--dry-run")],
             parse={"nasap_kept": r"nasap\s+rows=\s*\d+ kept=\s*(\d+)",
                    "maestro_kept": r"maestro\s+rows=\s*\d+ kept=\s*(\d+)",
                    "nasap_val": r"nasap_val=(\d+)", "maestro_val": r"maestro_val=(\d+)",
                    "train": r"train=(\d+)"},
             # 上轮 P8 的三大坑必须挡死:nasap kept=0(配不上音频)、maestro=整曲 1276 条、
             # val 全空(split 没进来)—— 任一复发,直接停,别带病开训。
             require=lambda n: None if (int(n.get("nasap_kept", 0)) > 0
                                        and int(n.get("maestro_kept", 0)) >= 5000
                                        and int(n.get("nasap_val", 0)) > 0
                                        and int(n.get("maestro_val", 0)) > 0)
                     else (f"装配红线未过:nasap_kept={n.get('nasap_kept')} "
                           f"maestro_kept={n.get('maestro_kept')}(整曲版才会只有 ~1276)"
                           f" nasap_val={n.get('nasap_val')} maestro_val={n.get('maestro_val')},停")),
    ]


# ---------------------------------------------------------------- 自动上报(git,best-effort)

def _git_report(sid: str, ok: bool, title: str, nums: dict, tail: list[str]):
    """步骤结果自动写进 repo 并推送 —— 规划端从 git 直接看到每步成败,不再依赖人肉转述
    (实测教训:SOP 日志落在数据盘 reports/,不在 repo 里,失败信息到不了规划端)。
    全程 best-effort:git 任何一步失败只打印一行,绝不影响 SOP 主流程。
    SOP_AUTO_REPORT=0 完全关闭(测试必须关 —— 假步骤真推送把垃圾提交推上过共享分支)。"""
    if os.environ.get("SOP_AUTO_REPORT", "1") == "0":
        return
    d = REPO / "reports" / "sop_blocks"
    d.mkdir(parents=True, exist_ok=True)
    body = [f"# [{sid}] {'完成' if ok else '失败'} — {title}",
            f"- time: {time.strftime('%Y-%m-%d %H:%M:%S')}"]
    body += [f"- {k} = {v}" for k, v in nums.items()]
    if not ok and tail:
        body += ["", "## 日志尾部", "```", *tail[-30:], "```"]
    text = "\n".join(body) + "\n"
    (d / f"{sid}.md").write_text(text, encoding="utf-8")
    paths = [f"reports/sop_blocks/{sid}.md"]
    if not ok:
        (REPO / "reports" / "sop_last_failure.md").write_text(text, encoding="utf-8")
        paths.append("reports/sop_last_failure.md")

    def _git(*a):
        return subprocess.run(["git", *a], cwd=str(REPO), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=180)
    try:
        _git("add", *paths)
        if _git("commit", "-m", f"sop-auto: [{sid}] {'ok' if ok else 'FAIL'}").returncode != 0:
            return                                    # 无变化可提交
        if _git("push").returncode != 0:
            _git("pull", "--rebase", "--autostash")   # 分支被规划端推进过 → 变基后再推
            if _git("push").returncode != 0:
                print("  (状态块已提交,推送失败 —— 之后手动 git push 即可)")
                return
        print(f"  (状态块已自动推送 → reports/sop_blocks/{sid}.md)")
    except Exception as e:
        print(f"  (自动上报失败: {type(e).__name__} —— 不影响主流程)")


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
    _git_report(sid, ok, step["title"], nums, lines)
    if not ok:
        print(f"  ✗ {'退出码 ' + str(rc) if rc else ''}{err or ''}")
        print(f"  日志尾部({log_path}):")
        for s in lines[-12:]:
            print("    " + s)
        print("  【停】失败块已自动推送给规划端;把这一块贴给用户即可。不要自己修、不要重试别的命令。")
        return False
    fire = step.get("resets_if")
    if step.get("resets") and (fire is None or fire(nums)):
        for r in step["resets"]:
            if r in st["done"]:
                st["done"].remove(r)
                print(f"  ↺ [{r}] 已自动标回未完成(本步产出使其必须重跑,--go 会按序补上)")
    st["done"].append(sid)
    st["numbers"][sid] = nums
    _save(st)
    return True


def cmd_status(steps, st):
    print("SOP 进度(状态存盘 work/sop_state.json,不怕忘):")
    for s in steps:
        mark = "✅" if s["id"] in st["done"] else "⬜"
        nums = st["numbers"].get(s["id"], {})
        extra = ("  " + " ".join(f"{k}={v}" for k, v in nums.items())) if nums else ""
        print(f"  {mark} [{s['id']}] {s['title']}{extra}")
    nxt = next((s for s in steps if s["id"] not in st["done"]), None)
    if nxt is None:
        print("\n全部完成。把 --status 输出整个贴给用户。")
    else:
        print(f"\n下一步: [{nxt['id']}] —— 运行 python scripts/sop_next.py --go(会自动一路干到底)")


def cmd_go(steps, st):
    ran = 0
    while True:
        nxt = next((s for s in steps if s["id"] not in st["done"]), None)
        if nxt is None:
            print("\n全部完成 ✅。运行 --status 并把进度表贴给用户。")
            return 0
        if not _run_step(nxt, st):
            return 1
        ran += 1


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="SOP 状态机:--go 自动干到底(失败才停);--status 看进度")
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset-step", default="", help="把某步标回未完成(逗号可多步,仅用户指示时用)")
    args = ap.parse_args(argv)
    steps = _steps()
    st = _load()
    if args.reset_step:
        targets = {t.strip() for t in args.reset_step.split(",") if t.strip()}
        st["done"] = [d for d in st["done"] if d not in targets]
        _save(st)
        print(f"{sorted(targets)} 已标回未完成。")
        return 0
    if args.go:
        return cmd_go(steps, st)
    cmd_status(steps, st)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
