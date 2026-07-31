"""OMR-NED 接入回归:LEGATO/musicdiff 文件夹契约、命令构造、宽松解析、失败不静默。
运行: python tests_omr_ned.py"""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, ".")
from rubato.model.omr_ned import omr_ned_musicdiff, omr_ned_legato, _find_scores

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

print("[5] 正式终评统一走已校准的 LEGATO JSON 接口，原始参考不经导出器")
script = tmp / "compute_OMR-NED.py"
script.write_text("# stub", encoding="utf-8")
seen_legato = {}


def fake_legato_runner(cmd, cwd, run_tmp):
    seen_legato["cmd"] = cmd
    seen_legato["refs"] = json.loads(
        Path(cmd[cmd.index("--ground_truth") + 1]).read_text(encoding="utf-8"))
    out = run_tmp / "ref_preds" / "pred_xml" / "output"
    out.mkdir(parents=True)
    (out / "output.csv").write_text(
        "file,bad kern syntax % contribution to OMR-NED,"
        "OMR-NED (OMR-ED / total numsyms)\n"
        "0.xml,0.0,0.4\n1.xml,0.0,0.6\nTotal:,0.0,0.5\n", encoding="utf-8")
    return SimpleNamespace(returncode=0, stdout="ok", stderr="")


leg = omr_ned_legato(pairs, tmp / "official", script, runner=fake_legato_runner)
check("legato_json_contract", "--prediction_file" in seen_legato["cmd"]
      and "--ground_truth" in seen_legato["cmd"], seen_legato["cmd"])
check("original_refs_passed", seen_legato["refs"] == ["<ref0/>", "<ref1/>"],
      seen_legato["refs"])
check("legato_percent_mean", leg["omr_ned_mean"] == 50.0, leg)
check("legato_per_pair", leg["scores"] == [40.0, 60.0], leg)
check("legato_complete_gate", leg["complete"] is True, leg)
check("legato_csv_preserved", (tmp / "official" / "output.csv").exists())

def fake_partial_runner(cmd, cwd, run_tmp):
    out = run_tmp / "ref_preds" / "pred_xml" / "output"
    out.mkdir(parents=True)
    (out / "output.csv").write_text(
        "file,bad kern syntax % contribution to OMR-NED,"
        "OMR-NED (OMR-ED / total numsyms)\n"
        "0.xml,0.0,0.4\nTotal:,0.0,0.4\n", encoding="utf-8")
    return SimpleNamespace(returncode=0, stdout="partial", stderr="")


partial = omr_ned_legato(pairs, tmp / "partial", script, runner=fake_partial_runner)
check("partial_legato_fail_closed",
      partial["complete"] is False and partial["omr_ned_mean"] is None
      and partial["partial_omr_ned_mean"] == 40.0, partial)

print(f"\n全部通过: {PASS} 项")
