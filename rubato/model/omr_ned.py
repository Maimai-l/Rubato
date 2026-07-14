"""
LEGATO / musicdiff OMR-NED 接入(论文正式指标,R-S13.1)。

执行端提供的参考脚本(reports/legato_omr_ned.py)本质:把预测/参照 MusicXML 字符串
写成编号文件夹,shell 出 `python -m musicdiff --ml_training_evaluation` 算 TEDn。
本模块复刻同一契约,外加我们缺的一环:A2S 文本 → MusicXML(a2s_to_ir → ir_to_part →
partitura.save_musicxml)。预测与参照走【同一个导出器】,导出器的口音两边抵消,
musicdiff 量到的就是内容差异。

沙盒可测:文件夹布局/命令构造/输出解析(runner 可注入)。
LOCAL:partitura 导出、真 musicdiff 运行(执行端 U10 验证过 musicdiff 可用)。
输出解析是 best-effort(musicdiff 的输出文件格式以执行端首次真实运行为准 ——
拿到样本后钉死解析,解析不出时 raw stdout/文件清单原样带回,绝不静默)。
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path


def a2s_to_musicxml(a2s_text: str) -> str:
    """A2S 文本 → MusicXML 字符串。LOCAL(需 partitura)。解析失败向上抛,调用方计数。"""
    import os
    import tempfile
    import partitura
    from rubato.model.merge_ref import a2s_to_ir
    from rubato.intermo.partitura_adapter import ir_to_part
    part = ir_to_part(a2s_to_ir(a2s_text))
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "x.musicxml")
        partitura.save_musicxml(part, p)
        with open(p, encoding="utf-8") as f:
            return f.read()


def _find_scores(obj, hits: list):
    """递归收集 key 含 ted/ned 的数值(musicdiff 输出格式钉死前的宽松解析)。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and any(t in str(k).lower() for t in ("ted", "ned")):
                hits.append(float(v))
            else:
                _find_scores(v, hits)
    elif isinstance(obj, list):
        for v in obj:
            _find_scores(v, hits)


def omr_ned_musicdiff(pairs: list[tuple[str, str]], workdir, runner=None,
                      python_exe: str | None = None) -> dict:
    """
    pairs: [(pred_xml_str, ref_xml_str)] → 按 LEGATO 契约铺文件夹 + 跑 musicdiff。
    返回 {returncode, stdout_tail, output_files, omr_ned_mean|None, n_pairs}。
    omr_ned_mean=None 表示解析不出 —— stdout/文件清单带回给规划端钉解析,不算 0 不算过。
    """
    workdir = Path(workdir)
    gt, pred, outd = workdir / "gt", workdir / "pred", workdir / "output"
    for d in (gt, pred, outd):
        d.mkdir(parents=True, exist_ok=True)
    for i, (est_xml, ref_xml) in enumerate(pairs):
        (gt / f"{i}.xml").write_text(ref_xml, encoding="utf-8")
        (pred / f"{i}.xml").write_text(est_xml, encoding="utf-8")
    cmd = [python_exe or sys.executable, "-m", "musicdiff", "--ml_training_evaluation",
           "--ground_truth_folder", str(gt), "--predicted_folder", str(pred),
           "--output_folder", str(outd)]
    if runner is None:
        def runner(c):
            return subprocess.run(c, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=7200)
    r = runner(cmd)
    res = {"n_pairs": len(pairs), "cmd": " ".join(cmd),
           "returncode": getattr(r, "returncode", -1),
           "stdout_tail": ((getattr(r, "stdout", "") or "") +
                           (getattr(r, "stderr", "") or ""))[-2000:],
           "output_files": sorted(p.name for p in outd.glob("*"))}
    hits: list = []
    for f in outd.glob("*.json"):
        try:
            _find_scores(json.loads(f.read_text(encoding="utf-8")), hits)
        except Exception:
            pass
    res["omr_ned_mean"] = (sum(hits) / len(hits)) if hits else None
    res["n_scores_parsed"] = len(hits)
    return res
