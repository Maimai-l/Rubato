"""
LEGATO / musicdiff OMR-NED 接入(论文正式指标,R-S13.1)。

正式入口 ``omr_ned_legato`` 直接调用已校准的 LEGATO ``compute_OMR-NED.py``
JSON 接口：只导出预测 A2S，参考始终读取原始人工 MusicXML，避免“两边经同一
导出器而抵消口音”的评测漏洞。旧的文件夹契约函数仅保留兼容/诊断用途。

沙盒可测:文件夹布局/命令构造/输出解析(runner 可注入)。
LOCAL:partitura 导出、真 musicdiff 运行(执行端 U10 验证过 musicdiff 可用)。
输出解析是 best-effort(musicdiff 的输出文件格式以执行端首次真实运行为准 ——
拿到样本后钉死解析,解析不出时 raw stdout/文件清单原样带回,绝不静默)。
"""
from __future__ import annotations
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


def omr_ned_legato(pairs: list[tuple[str, str]], workdir, legato_script,
                   python_exe: str | None = None, musicdiff_source=None,
                   runner=None) -> dict:
    """经 LEGATO 官方 ``compute_OMR-NED.py`` JSON 接口批量打分。

    这是 ``scripts/calib_score.py`` 已用 Tkun→M2ST 外部锚验证过的调用方式。
    ``pairs`` 为 ``[(pred_xml_string, original_reference_xml_string), ...]``；
    预测允许由 InterMo 导出，但参考必须是原始人工 MusicXML，不能再经同一导出器
    “两边抵消口音”。返回的 ``omr_ned_mean``/``scores`` 统一为论文的 0–100 口径。
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    script = Path(legato_script)
    if not script.exists():
        return {"returncode": -1, "omr_ned_mean": None, "scores": [],
                "n_pairs": len(pairs), "n_scores_parsed": 0,
                "complete": False,
                "stdout_tail": f"LEGATO script not found: {script}",
                "output_files": []}
    if not pairs:
        return {"returncode": 0, "omr_ned_mean": None, "scores": [],
                "n_pairs": 0, "n_scores_parsed": 0,
                "complete": False,
                "stdout_tail": "no evaluable pairs", "output_files": []}
    child_env = None
    if musicdiff_source:
        source = Path(musicdiff_source)
        if not (source / "musicdiff").is_dir():
            return {"returncode": -1, "omr_ned_mean": None, "scores": [],
                    "n_pairs": len(pairs), "n_scores_parsed": 0,
                    "complete": False,
                    "stdout_tail": f"MusicDiff source has no musicdiff/: {source}",
                    "output_files": []}
        child_env = os.environ.copy()
        old_pp = child_env.get("PYTHONPATH", "")
        child_env["PYTHONPATH"] = (
            str(source) + (os.pathsep + old_pp if old_pp else ""))

    with tempfile.TemporaryDirectory(prefix="rubato_legato_") as td:
        tmp = Path(td)
        pred_json = tmp / "pred_xml.json"
        ref_json = tmp / "ref.json"
        pred_json.write_text(json.dumps([p for p, _r in pairs], ensure_ascii=False),
                             encoding="utf-8")
        ref_json.write_text(json.dumps([r for _p, r in pairs], ensure_ascii=False),
                            encoding="utf-8")
        cmd = [python_exe or sys.executable, str(script),
               "--prediction_file", str(pred_json),
               "--ground_truth", str(ref_json), "--prediction_type", "xml"]
        try:
            if runner is None:
                r = subprocess.run(cmd, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   timeout=7200, cwd=str(script.parent),
                                   env=child_env)
            else:
                r = runner(cmd, str(script.parent), tmp)
        except Exception as e:
            return {"returncode": -1, "omr_ned_mean": None, "scores": [],
                    "n_pairs": len(pairs), "n_scores_parsed": 0,
                    "complete": False,
                    "stdout_tail": f"{type(e).__name__}: {e}",
                    "output_files": []}

        stdout = ((getattr(r, "stdout", "") or "") + "\n"
                  + (getattr(r, "stderr", "") or ""))
        csv_path = tmp / "ref_preds" / "pred_xml" / "output" / "output.csv"
        result = {"returncode": int(getattr(r, "returncode", -1)),
                  "n_pairs": len(pairs), "stdout_tail": stdout[-3000:],
                  "scores": [], "n_scores_parsed": 0,
                  "omr_ned_mean": None, "complete": False,
                  "output_files": []}
        if csv_path.exists():
            shutil.copy2(csv_path, workdir / "output.csv")
            result["output_files"].append("output.csv")
            try:
                with csv_path.open(encoding="utf-8", newline="") as fh:
                    rows = list(csv.reader(fh))
                header = [x.strip() for x in rows[0]]
                # output.csv 里几十个“... % contribution to OMR-NED”列都含
                # OMR-NED；模糊取第一个会稳定读到 bad-kern contribution(常为0)，
                # 把整套正式分数伪装成完美 0。只准匹配最终归一化总分列。
                target = "OMR-NED (OMR-ED / total numsyms)"
                col = header.index(target)
                raw_scores = []
                total_raw = None
                for row in rows[1:]:
                    if not row or len(row) <= col:
                        continue
                    try:
                        value = float(row[col])
                    except ValueError:
                        continue
                    if row[0].strip().lower().startswith("total"):
                        total_raw = value
                    else:
                        raw_scores.append(value)
                scale = 100.0 if ([total_raw] + raw_scores
                                  and max([v for v in [total_raw] + raw_scores
                                           if v is not None], default=0.0) <= 1.5) else 1.0
                result["scores"] = [v * scale for v in raw_scores]
                result["n_scores_parsed"] = len(raw_scores)
                if total_raw is not None:
                    result["omr_ned_mean"] = total_raw * scale
                elif raw_scores:
                    result["omr_ned_mean"] = sum(raw_scores) / len(raw_scores) * scale
            except Exception as e:
                result["stdout_tail"] += f"\nCSV parse failed: {type(e).__name__}: {e}"
        result["complete"] = (
            result["returncode"] == 0
            and result["n_scores_parsed"] == result["n_pairs"]
            and result["omr_ned_mean"] is not None)
        if not result["complete"] and result["omr_ned_mean"] is not None:
            # 条件均值不能冒充全量正式指标。保留解析值供排错，正式字段 fail closed。
            result["partial_omr_ned_mean"] = result["omr_ned_mean"]
            result["omr_ned_mean"] = None
            result["stdout_tail"] += (
                f"\nIncomplete LEGATO result: rc={result['returncode']} "
                f"parsed={result['n_scores_parsed']}/{result['n_pairs']}")
        return result
