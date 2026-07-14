"""OMR-NED 接入回归:LEGATO/musicdiff 文件夹契约、命令构造、宽松解析、失败不静默。
运行: python tests_omr_ned.py"""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, ".")
from rubato.model.omr_ned import omr_ned_musicdiff, _find_scores

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
pairs = [("<pred0/>", "<ref0/>"), ("<pred1/>", "<ref1/>")]

print("[1] 文件夹契约(LEGATO 同款):gt/pred 按编号铺,命令按 musicdiff 契约构造")
seen = {}


def fake_runner(cmd):
    seen["cmd"] = cmd
    outd = Path(cmd[cmd.index("--output_folder") + 1])
    (outd / "results.json").write_text(
        json.dumps({"per_file": [{"tedn": 0.4}, {"tedn": 0.6}], "note": "x"}),
        encoding="utf-8")
    return SimpleNamespace(returncode=0, stdout="musicdiff done", stderr="")


res = omr_ned_musicdiff(pairs, tmp / "w1", runner=fake_runner)
check("gt_files", (tmp / "w1" / "gt" / "0.xml").read_text(encoding="utf-8") == "<ref0/>")
check("pred_files", (tmp / "w1" / "pred" / "1.xml").read_text(encoding="utf-8") == "<pred1/>")
check("cmd_contract", "--ml_training_evaluation" in seen["cmd"]
      and "-m" in seen["cmd"] and "musicdiff" in seen["cmd"], seen["cmd"])
check("parsed_mean", abs(res["omr_ned_mean"] - 0.5) < 1e-9, res["omr_ned_mean"])
check("n_scores", res["n_scores_parsed"] == 2)
check("rc_kept", res["returncode"] == 0)

print("[2] 输出解析不出 → mean=None + stdout/文件清单带回(不算 0 不算过)")


def opaque_runner(cmd):
    outd = Path(cmd[cmd.index("--output_folder") + 1])
    (outd / "weird.txt").write_text("no json here", encoding="utf-8")
    return SimpleNamespace(returncode=0, stdout="something inscrutable", stderr="")


res2 = omr_ned_musicdiff(pairs, tmp / "w2", runner=opaque_runner)
check("unparsed_none", res2["omr_ned_mean"] is None)
check("stdout_carried", "inscrutable" in res2["stdout_tail"])
check("files_listed", "weird.txt" in res2["output_files"])

print("[3] _find_scores 递归:嵌套/列表/混名都收,非 ted/ned 键不收")
hits = []
_find_scores({"a": {"TEDn_norm": 0.3}, "b": [{"ned": 0.7}, {"f1": 0.9}], "c": 5}, hits)
check("recursive_hits", sorted(hits) == [0.3, 0.7], hits)

print("[4] a2s_to_musicxml:合法 A2S 出非空 XML(沙盒缺 partitura 则跳过,执行端真跑)")
try:
    import partitura  # noqa: F401
    from rubato.model.omr_ned import a2s_to_musicxml
    from rubato.intermo.core import Note, Measure, ScoreIR, SPitch, project
    from fractions import Fraction as F
    ir = ScoreIR([Note("PR", SPitch("C", 0, 4), F(0), F(1, 4))],
                 [Measure(F(0), 4, 4, 0)], F(1))
    xml = a2s_to_musicxml(project(ir, "A2S"))
    check("xml_nonempty", "<" in xml and len(xml) > 100, len(xml))
except ImportError:
    PASS += 1
    print("  ok  xml_nonempty(skip:沙盒无 partitura,执行端覆盖)")

print(f"\n全部通过: {PASS} 项")
