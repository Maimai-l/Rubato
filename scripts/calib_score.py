"""
校准全量第 4 步:LEGATO 官方 compute_OMR-NED 逐对打分 + 代码写报告(D54/REF_SYSTEM_CALIB)。

流程:
  0) 自检:取第一对的【参考谱 vs 参考谱】跑官方脚本,应得 ≈0(U10 同款验证)。
     自检不过 = 调用形式不对 → 当场中止,把官方脚本的用法/报错整段贴回,不许自行改造。
  1) 逐对:est(我们管线的 Tkun→M2ST 产出 xml) vs ref(ASAP xml_score),取输出末尾数值。
  2) 报告由本脚本写入 reports/CALIB_FULL.txt(代码写数;重跑覆盖,机器产物不算旧报告)。

判据(预登记于 REF_SYSTEM_CALIB.md,先于数据,不许挪):
  通过   = 均值落 [60,80] 且 |均值-69.1| ≤ 5
  灰区   = 5 < |均值-69.1| ≤ 10 → 抽 5 曲人工比对 XML 后定
  失败   = |均值-69.1| > 10 或管线跑不通 → 修好前二轮不得开训
  (若官方脚本输出 0-1 口径,×100 换算后对带 —— 此换算在此预登记。)

用法(执行端,LEGATO 所在环境 = U10 验证过的那个):
  python scripts/calib_score.py
  python scripts/calib_score.py --legato-script D:\\...\\compute_OMR-NED.py   # 自动找不到时
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("RUBATO_WORK")
            or (ROOT.parent / "work" if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download\work"))

PUB = 69.1          # Tkun→M2ST 公开 ASAP OMR-NED(REF_SYSTEM_CALIB.md,论文 Table 2)


def find_legato_script() -> Path | None:
    env = os.environ.get("RUBATO_LEGATO_SCRIPT")
    if env and Path(env).exists():
        return Path(env)
    # U10 的实际 checkout 名为 legato-main；保留旧 legato 路径兼容性。
    for base in (WORK.parent / "legato", WORK.parent / "legato-main"):
        if base.exists():
            hits = sorted(base.rglob("compute_OMR-NED.py"))
            if hits:
                return hits[0]
    return None


def run_one(py: str, script: Path, est: str, ref: str, timeout: int):
    """经 LEGATO 官方 JSON 接口计算一对 XML 的 OMR-NED。

    compute_OMR-NED.py 不是 ``script est.xml ref.xml`` 的 CLI；它接收两个
    JSON 列表，内部用 musicdiff 的 ML-folder 模式写 ``output.csv``。每对采用
    独立临时目录，避免官方脚本的 ``assert not exists(pred_folder)`` 重跑冲突。
    """
    try:
        est_text = Path(est).read_text(encoding="utf-8")
        ref_text = Path(ref).read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"读取 XML 失败: {type(exc).__name__}: {exc}"
    with tempfile.TemporaryDirectory(prefix="rubato_calib_legato_") as td:
        tmp = Path(td)
        pred_json, ref_json = tmp / "pred_xml.json", tmp / "ref.json"
        pred_json.write_text(json.dumps([est_text], ensure_ascii=False), encoding="utf-8")
        ref_json.write_text(json.dumps([ref_text], ensure_ascii=False), encoding="utf-8")
        try:
            r = subprocess.run([py, str(script), "--prediction_file", str(pred_json),
                                "--ground_truth", str(ref_json), "--prediction_type", "xml"],
                               capture_output=True, text=True, errors="backslashreplace",
                               timeout=timeout, cwd=str(script.parent))
        except subprocess.TimeoutExpired:
            return None, f"TIMEOUT>{timeout}s"
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        tail = " | ".join(ln.strip() for ln in out.strip().splitlines()[-3:])
        if r.returncode != 0:
            return None, f"rc={r.returncode} {tail}"
        csv_path = tmp / "ref_preds" / "pred_xml" / "output" / "output.csv"
        if not csv_path.exists():
            return None, f"官方脚本未写 output.csv: {tail}"
        try:
            with csv_path.open(encoding="utf-8", newline="") as fh:
                table = list(csv.reader(fh))
            header = [x.strip() for x in table[0]]
            col = header.index("OMR-NED (OMR-ED / total numsyms)")
            total = next(row for row in table[1:] if row and row[0].strip() == "Total:")
            return float(total[col]), tail
        except (IndexError, StopIteration, ValueError) as exc:
            return None, f"无法解析官方 output.csv: {type(exc).__name__}: {exc}; {tail}"


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="LEGATO OMR-NED 逐对打分 + 校准判决(代码写报告)")
    ap.add_argument("--pairs", default=str(WORK / "calib_pairs.jsonl"))
    ap.add_argument("--est-dir", default=str(WORK / "calib_full_xml"))
    ap.add_argument("--legato-script", default=None, help="compute_OMR-NED.py 路径(默认自动找)")
    ap.add_argument("--python", default=sys.executable, help="跑官方脚本用的 python")
    ap.add_argument("--timeout", type=int, default=1800, help="单对秒数上限")
    ap.add_argument("--report", default=str(ROOT / "reports" / "CALIB_FULL.txt"))
    args = ap.parse_args(argv)

    script = Path(args.legato_script) if args.legato_script else find_legato_script()
    if not script or not script.exists():
        print("✗ 找不到 compute_OMR-NED.py —— 用 --legato-script 指到 U10 验证过的那份,"
              "或设环境变量 RUBATO_LEGATO_SCRIPT")
        return 1
    pp = Path(args.pairs)
    if not pp.exists():
        print(f"✗ 配对清单不存在: {pp}(先跑 scripts/calib_pairs.py)")
        return 1
    pairs = list(read_jsonl(pp))
    if not pairs:
        print(f"✗ 配对清单为空: {pp}")
        return 1
    est_dir = Path(args.est_dir)

    # ---- 自检:ref vs ref ≈ 0(调用形式与 U10 相同则必过)----
    ref0 = pairs[0]["ref_xml"]
    s0, tail0 = run_one(args.python, script, ref0, ref0, args.timeout)
    if s0 is None:
        print(f"✗ 自检失败(ref vs ref 跑不通): {tail0}")
        print("  → 不要继续。把下面两条的完整输出整段贴回:")
        print(f"    {args.python} {script} --help")
        print(f"    {args.python} {script} {ref0} {ref0}")
        return 1
    s0n = s0 * 100.0 if s0 <= 1.5 else s0
    if abs(s0n) > 2.0:
        print(f"✗ 自检异常:相同文件得分 {s0}(应≈0)—— 调用形式或口径不对,整段贴回,勿继续")
        return 1
    print(f"自检通过: ref vs ref = {s0}")

    # ---- 逐对打分 ----
    rows, missing = [], []
    for i, p in enumerate(pairs):
        est = est_dir / f"{p['perf_id']}.xml"
        if not est.exists() or est.stat().st_size == 0:
            missing.append(p["perf_id"])
            continue
        sc, tail = run_one(args.python, script, str(est), p["ref_xml"], args.timeout)
        rows.append({"perf_id": p["perf_id"], "score": sc, "note": "" if sc is not None else tail})
        print(f"  [{i+1}/{len(pairs)}] {p['perf_id']}: "
              f"{sc if sc is not None else '✗ ' + tail}")

    ok = [r for r in rows if r["score"] is not None]
    raw = [r["score"] for r in ok]
    scaled_note = ""
    vals = raw
    if raw and max(raw) <= 1.5:                    # 0-1 口径 → ×100(预登记换算)
        vals = [v * 100.0 for v in raw]
        scaled_note = "(官方脚本输出为 0-1 口径,已 ×100 对带 —— 预登记换算)"

    lines = []
    lines.append("# CALIB_FULL —— Tkun→M2ST 全量校准比分(本文件由 scripts/calib_score.py 代码生成,重跑覆盖)")
    lines.append(f"生成时间: {_dt.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"官方脚本: {script}")
    lines.append(f"自检 ref-vs-ref: {s0}(通过)")
    lines.append(f"配对总数 {len(pairs)} | est-xml 缺失 {len(missing)} | 打分成功 {len(ok)} | 打分失败 {len(rows)-len(ok)}")
    if missing:
        lines.append("缺失(M2ST 未产出): " + ", ".join(missing))
    lines.append("")
    lines.append("perf_id\tOMR-NED\t备注")
    for r in rows:
        lines.append(f"{r['perf_id']}\t{r['score'] if r['score'] is not None else 'FAIL'}\t{r['note']}")
    lines.append("")
    if vals:
        mean = statistics.fmean(vals)
        med = statistics.median(vals)
        std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        lines.append(f"均值 {mean:.2f} | 中位 {med:.2f} | 总体std {std:.2f} | n={len(vals)} {scaled_note}")
        diff = abs(mean - PUB)
        if 60.0 <= mean <= 80.0 and diff <= 5.0:
            verdict = f"通过(均值 {mean:.2f} ∈ [60,80] 且 |Δ{PUB}|={diff:.2f} ≤ 5)"
        elif diff <= 10.0:
            verdict = f"灰区(|Δ{PUB}|={diff:.2f} ∈ (5,10])→ 按预登记抽 5 曲人工比对 XML 后定"
        else:
            verdict = f"失败(|Δ{PUB}|={diff:.2f} > 10)→ 评测链有 bug,修好前二轮不得开训"
        lines.append(f"判决(判据预登记于 REF_SYSTEM_CALIB.md,先于数据): {verdict}")
    else:
        lines.append("判决: 失败(零成功打分 = 管线跑不通)→ 修好前二轮不得开训")

    rp = Path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"报告已写: {rp}")
    for ln in lines[-4:]:
        print(ln)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
