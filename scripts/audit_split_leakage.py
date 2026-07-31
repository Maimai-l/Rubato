"""
跨方言音频泄漏对账(用户问 maestro 切分引出,monitor 挂账项):
nasap(TAST/A2S)与 maestro(AMT)共用整曲录音库 —— 若某场演奏在 MAESTRO 官方口径里
属 validation/test,而它的 nasap 行落在 nasap-train,模型就在训练中"听过"评测音频
(跨方言泄漏,污染 amt_f1 与终评干净性;论文的保守 ASAP 切分正为防此)。

判定口径(零猜测):每行 nasap 用哪个 flac,由装配器自己的 resolve_audio 说了算
(同一代码路径);MAESTRO 场次的官方切分由 maestro CSV 说了算;两边按 flac 文件名对账。

输出 reports/split_leakage.md(代码写,只追加):
  - nasap-train 引用且属 maestro val/test 的录音清单(场次 + 涉及行数)= 泄漏集
  - 应为 0;非 0 → 涉事 nasap 行的处置(移出训练)由规划端出补丁,先贴回本报告

用法(执行端,CPU 分钟级,不停训):
  python scripts/audit_split_leakage.py
"""
from __future__ import annotations

import argparse
import time
from collections import Counter, defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rubato.platform import harden_stdout, read_jsonl          # noqa: E402
from scripts.gen_amt_labels import load_csv_rows               # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
import os                                                       # noqa: E402
BASE = Path(os.environ.get("RUBATO_BASE")
            or (ROOT.parent if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download"))
WORK = BASE / "work"


def main() -> int:
    harden_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--nasap-labels", default=str(WORK / "nasap_labels.jsonl"))
    ap.add_argument("--maestro-csv", default=str(BASE / "maestro-v3.0.0.csv"))
    ap.add_argument("--report", default=str(ROOT / "reports" / "split_leakage.md"),
                    help="报告追加目标(测试必须指到临时路径,严禁污染真报告)")
    args = ap.parse_args()

    lines = [f"\n## nasap-train × maestro val/test 音频对账 @ {time.strftime('%Y-%m-%d %H:%M:%S')}"]

    # MAESTRO 官方切分:flac 名 → split
    split_of: dict[str, str] = {}
    for r in load_csv_rows(args.maestro_csv):
        a = r.get("audio_filename") or ""
        if a:
            split_of[Path(a).with_suffix(".flac").name] = (r.get("split") or "").strip()
    n_vt = sum(1 for s in split_of.values() if s in ("validation", "test"))
    lines.append(f"  maestro CSV: 场次={len(split_of)} 其中 val/test={n_vt}")

    # nasap 行 → 实际 flac(装配器同一代码路径)
    from scripts.build_dataset import resolve_audio
    tally: Counter = Counter()
    leak_rows: Counter = Counter()          # flac 名 → 涉事 nasap-train 行数
    leak_splits: dict[str, str] = {}
    by_split: Counter = Counter()
    for row in read_jsonl(args.nasap_labels):
        sp = (row.get("split") or "train").strip() or "train"
        by_split[sp] += 1
        res = resolve_audio(row.get("utt_id", "?"), "nasap", row)
        if res is None:
            tally["无法解析音频"] += 1
            continue
        flac = Path(res[0]).name
        msp = split_of.get(flac)
        if msp is None:
            tally["不在 maestro CSV(非 maestro 录音)"] += 1
            continue
        tally[f"maestro-{msp}"] += 1
        if sp == "train" and msp in ("validation", "test"):
            leak_rows[flac] += 1
            leak_splits[flac] = msp

    lines.append("  nasap 行按自身 split: " + " ".join(f"{k}={v}" for k, v in sorted(by_split.items())))
    lines.append("  nasap 行按所引录音的 maestro 切分: "
                 + " ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    lines.append(f"  【泄漏集】nasap-train 引用 maestro val/test 录音: 场次={len(leak_rows)} "
                 f"涉及行={sum(leak_rows.values())}")
    for flac, n in leak_rows.most_common(20):
        lines.append(f"    - {flac}({leak_splits[flac]}): {n} 行")
    if len(leak_rows) > 20:
        lines.append(f"    …共 {len(leak_rows)} 场,余略(全清单以本脚本重跑 + grep 提取)")
    lines.append("  判定: " + ("干净 —— 无跨方言泄漏,挂账关案"
                                if not leak_rows else
                                "存在泄漏 —— 涉事行须移出训练,规划端出补丁前先贴回本报告"))

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n已追加 {out} —— git add + commit + push 即完成上报。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
