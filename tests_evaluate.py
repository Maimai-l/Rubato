"""S13 evaluate.py 纯逻辑测试。运行: python tests_evaluate.py"""
import sys
sys.path.insert(0, ".")
from rubato.model.evaluate import (
    note_f1, bootstrap_ci, classify_failure, gap_annotation, build_eval_report,
    _has_duplicate_measures,
)

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] note F1(onset 50ms 容差)")
# 完全匹配
ref = [{"pitch": 60, "on": 0.0, "off": 1.0}, {"pitch": 64, "on": 1.0, "off": 2.0}]
est = [{"pitch": 60, "on": 0.0, "off": 1.0}, {"pitch": 64, "on": 1.0, "off": 2.0}]
r = note_f1(ref, est)
check("perfect_f1", r["f1"] == 1.0, r)

print("[2] onset 容差内匹配")
est_shifted = [{"pitch": 60, "on": 0.03, "off": 1.0}, {"pitch": 64, "on": 1.02, "off": 2.0}]
r = note_f1(ref, est_shifted, onset_tolerance=0.05)
check("within_tolerance", r["f1"] == 1.0, r)   # 30ms/20ms < 50ms
# 超容差
est_far = [{"pitch": 60, "on": 0.1, "off": 1.0}, {"pitch": 64, "on": 1.1, "off": 2.0}]
r = note_f1(ref, est_far, onset_tolerance=0.05)
check("beyond_tolerance", r["f1"] < 1.0, r)    # 100ms > 50ms

print("[3] 缺音/多音")
est_missing = [{"pitch": 60, "on": 0.0, "off": 1.0}]   # 少一个
r = note_f1(ref, est_missing)
check("missing_note_recall", r["recall"] == 0.5, r)
check("missing_note_precision", r["precision"] == 1.0, r)
# 音高错
est_wrong = [{"pitch": 61, "on": 0.0, "off": 1.0}, {"pitch": 64, "on": 1.0, "off": 2.0}]
r = note_f1(ref, est_wrong)
check("wrong_pitch", r["f1"] == 0.5, r)

print("[4] 空输入")
check("both_empty", note_f1([], [])["f1"] == 1.0)
check("ref_empty", note_f1([], est)["f1"] == 0.0)

print("[5] bootstrap CI")
scores = [0.9, 0.85, 0.92, 0.88, 0.91, 0.87, 0.93, 0.89]
ci = bootstrap_ci(scores, n_resample=1000)
check("ci_mean", abs(ci["mean"] - sum(scores)/len(scores)) < 0.001, ci)
check("ci_bounds", ci["lo"] < ci["mean"] < ci["hi"], ci)
check("ci_reasonable", 0.85 < ci["lo"] and ci["hi"] < 0.93, ci)
# 可复现
ci2 = bootstrap_ci(scores, n_resample=1000)
check("ci_reproducible", ci == ci2)

print("[6] 归因分类(R-S13.3)")
# 不可解析 → parse_fail
bad = "GARBAGE not valid a2s"
check("parse_fail", classify_failure(bad) == "parse_fail", classify_failure(bad))
# 合法但小节数差异大 → merge_artifact
from rubato.intermo.core import Note, Measure, ScoreIR, SPitch, project
from fractions import Fraction as F
def ir_of(steps):
    return ScoreIR([Note("PR", SPitch(s,0,4), F(i), F(1)) for i,s in enumerate(steps)],
                   [Measure(F(i),4,4,0) for i in range(len(steps))], F(len(steps)))
est_short = project(ir_of("C"), "A2S")       # 1 小节
ref_long = project(ir_of("CDEFGA"), "A2S")   # 6 小节
check("merge_artifact_barcount", classify_failure(est_short, ref_long) == "merge_artifact",
      classify_failure(est_short, ref_long))
# 合法、结构正常、但内容差(高 OMR-NED)→ content_error
est_ok = project(ir_of("CDEF"), "A2S")
ref_ok = project(ir_of("CDEF"), "A2S")
check("content_error", classify_failure(est_ok, ref_ok, omr_ned=0.5) == "content_error",
      classify_failure(est_ok, ref_ok, omr_ned=0.5))

print("[7] 重复小节检测(合并伪影)")
dup = "|4/4k0PR:C4 1/1 |4/4k0c4C4 1/1 |4/4k0c4C4 1/1 |4/4k0c4"  # 重复小节
check("detects_duplicate", _has_duplicate_measures(dup), dup)
no_dup = project(ir_of("CDEF"), "A2S")
check("no_false_positive", not _has_duplicate_measures(no_dup))

print("[8] 论文对照 + 差距标注(R-S13.4)")
# 接近论文 → 可缩
ann = gap_annotation("maestro_amt_f1", 94.0)   # 论文 97.0,差 3
check("trainable_gap", ann["verdict"] == "继续训练可缩", ann)
# 差距大 → 结构性
ann2 = gap_annotation("maestro_amt_f1", 80.0)  # 差 17
check("structural_gap", ann2["verdict"] == "结构性差距", ann2)

print("[9] 报告生成")
metrics = {"maestro_amt_f1": 94.0, "nasap_a2s_omr_ned": 89.0}
failures = [{"utt_id": "u1", "category": "parse_fail"},
            {"utt_id": "u2", "category": "content_error"},
            {"utt_id": "u3", "category": "content_error"}]
report = build_eval_report(metrics, failures)
check("report_has_metrics", "maestro_amt_f1" in report and "论文" in report)
check("report_has_attribution", "parse_fail" in report and "content_error" in report)
check("report_distinguishes", "工程 bug" in report and "模型能力" in report)

print(f"\n全部通过: {PASS} 项")
print("注:OMR-NED 用 LEGATO 脚本(本地 U10 已验证)、人检渲染需 Verovio/MuseScore,本地跑;")
print("    note F1 / bootstrap CI / 归因分类 / 报告对照 沙盒已验证。")
