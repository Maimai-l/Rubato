"""
泄漏修复(D51):把"nasap-train 引用 maestro val/test 录音"的 1,239 行移出训练。

方法:split 改写为 "quarantine_leak" —— partition_by_split 把未知 split 归入 other 桶,
训练/评测两边都不进(评测池零变动,eval 历史连续性保住);行本体保留 + 原 split 存
split_orig,完全可逆。改写前整文件备份 .bak。

判定口径与 audit_split_leakage 完全同源(resolve_audio + maestro CSV),不另立标准。
生效时机:下一次训练重启的装配(本脚本只改标签文件,不动正在跑的训练)。

用法(执行端):
  python scripts/fix_split_leakage.py            # 干跑:报数,不写
  python scripts/fix_split_leakage.py --apply    # 备份 + 改写 + 复审计自证
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rubato.platform import harden_stdout, read_jsonl          # noqa: E402
from scripts.gen_amt_labels import load_csv_rows               # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get("RUBATO_BASE")
            or (ROOT.parent if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download"))
WORK = BASE / "work"

QUARANTINE = "quarantine_leak"


def build_vt_set(maestro_csv: str) -> set:
    """maestro val/test 场次的 flac 名集合。"""
    vt = set()
    for r in load_csv_rows(maestro_csv):
        a = r.get("audio_filename") or ""
        if a and (r.get("split") or "").strip() in ("validation", "test"):
            vt.add(Path(a).with_suffix(".flac").name)
    return vt


def classify_rows(rows: list[dict], vt: set, resolver) -> tuple[list[dict], Counter]:
    """返回 (改写后的行列表, 计数)。只动 split==train 且引用 val/test 录音的行。"""
    st: Counter = Counter()
    out = []
    for row in rows:
        r = dict(row)
        sp = (r.get("split") or "train").strip() or "train"
        if sp == "train":
            res = resolver(r.get("utt_id", "?"), "nasap", r)
            if res is not None and Path(res[0]).name in vt:
                r["split_orig"] = r.get("split", "train")
                r["split"] = QUARANTINE
                st["quarantined"] += 1
            else:
                st["train_kept"] += 1
        else:
            st[f"untouched_{sp}"] += 1
        out.append(r)
    return out, st


def main() -> int:
    harden_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--nasap-labels", default=str(WORK / "nasap_labels.jsonl"))
    ap.add_argument("--maestro-csv", default=str(BASE / "maestro-v3.0.0.csv"))
    ap.add_argument("--apply", action="store_true", help="缺省干跑;--apply 才备份+改写")
    args = ap.parse_args()

    from scripts.build_dataset import resolve_audio
    vt = build_vt_set(args.maestro_csv)
    rows = list(read_jsonl(args.nasap_labels))
    new_rows, st = classify_rows(rows, vt, resolve_audio)

    lines = [f"\n## 泄漏修复{'(已执行)' if args.apply else '(干跑)'} "
             f"@ {time.strftime('%Y-%m-%d %H:%M:%S')}",
             "  " + " ".join(f"{k}={v}" for k, v in sorted(st.items())),
             f"  隔离口径: split→{QUARANTINE}(partition 落 other 桶,训练/评测两不进;"
             f"原值存 split_orig,可逆)"]
    if args.apply:
        bak = args.nasap_labels + ".bak"
        if not Path(bak).exists():
            shutil.copy2(args.nasap_labels, bak)
            lines.append(f"  备份: {bak}")
        with open(args.nasap_labels, "w", encoding="utf-8") as fo:
            for r in new_rows:
                fo.write(json.dumps(r, ensure_ascii=False) + "\n")
        # 自证:改写后复跑判定,泄漏应为 0
        vt2 = build_vt_set(args.maestro_csv)
        _, st2 = classify_rows(list(read_jsonl(args.nasap_labels)), vt2, resolve_audio)
        lines.append(f"  复审计: 残余可隔离行={st2.get('quarantined', 0)}(应为 0)")
        lines.append("  生效: 下一次训练重启的装配(时机由 EXECUTOR.md 指令决定,勿自行重启)")
    out = ROOT / "reports" / "split_leakage.md"
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n已追加 {out} —— git add + commit + push 即完成上报。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
