"""RECALL 对账:定性"标签有、整曲音频无"的曲(D34,回答"3,683 诡异")。

矛盾现场:s4_parallel(按 manifest 名单)说整曲全在;s4_slice(按标签名单)说 3,683 曲
缺整曲。两个工具走的名单不同 → 差集应当 = 已被过滤/清场的曲的【遗留标签行】
(非钢琴清场 D8、泄漏黑名单、人工清理)。本脚本不靠推理,逐曲给证据:

每个缺整曲的曲判三件事:
  in_manifest?   在过滤后 manifest 里吗(在 → s4_parallel 应该渲过,矛盾要上报)
  rows_have_flac 它的标签行里,段 flac 实存几行(段在 = 训练早在用,缺整曲无害)
  rows_missing   段 flac 缺几行(这些才是真 no_audio 行)
汇总四类:
  A 清场遗留(不在 manifest,段也缺)→ 按设计留在池外,勿复活
  B 无害(不在 manifest 但段全在 / 或整曲被清理但段全在)→ 训练照用,不用管
  C 【矛盾】在 manifest 且段缺 → s4_parallel 本该渲它,贴回样例待规划端查
  D 在 manifest 且段全在(仅整曲被清)→ 无害
输出计数 + 每类 ≤10 个样例,追加 reports/recall_explain.md(代码写,commit+push 即上报)。
"""
from __future__ import annotations
import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl

harden_stdout()


def _find_whole(audio_dir: Path, pid: str):
    for ext in (".opus", ".flac", ".wav"):
        p = audio_dir / f"pdmx_{pid}{ext}"
        if p.exists():
            return p
    return None


def explain(labels_path, manifest_path, audio_dir, out_dir) -> dict:
    audio_dir, out_dir = Path(audio_dir), Path(out_dir)
    manifest_ids = set()
    for r in read_jsonl(str(manifest_path)):
        if r.get("piece_id"):
            manifest_ids.add(r["piece_id"])

    by_piece: dict[str, list] = defaultdict(list)
    for r in read_jsonl(str(labels_path)):
        pid = r.get("piece_id")
        uid = r.get("utt_id")
        if pid and uid:
            by_piece[pid].append(uid)

    cats = {"A_purged_stale": [], "B_benign_no_manifest": [],
            "C_CONFLICT_in_manifest_missing": [], "D_benign_in_manifest": []}
    rows = {"A": 0, "B": 0, "C": 0, "D": 0}
    n_no_whole = 0
    for pid, uids in by_piece.items():
        if _find_whole(audio_dir, pid) is not None:
            continue
        n_no_whole += 1
        missing = [u for u in uids if not (out_dir / f"{u}.flac").exists()]
        inm = pid in manifest_ids
        if inm and missing:
            cats["C_CONFLICT_in_manifest_missing"].append((pid, len(uids), len(missing)))
            rows["C"] += len(missing)
        elif inm:
            cats["D_benign_in_manifest"].append((pid, len(uids), 0))
            rows["D"] += len(uids)
        elif missing:
            cats["A_purged_stale"].append((pid, len(uids), len(missing)))
            rows["A"] += len(missing)
        else:
            cats["B_benign_no_manifest"].append((pid, len(uids), 0))
            rows["B"] += len(uids)
    return {"n_no_whole": n_no_whole, "cats": cats, "rows": rows,
            "n_manifest": len(manifest_ids), "n_label_pieces": len(by_piece)}


def main():
    ROOT = Path(r"D:\vscode_projects\ee_download")
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", default=str(ROOT / "work" / "pdmx_a2s_labels.jsonl"))
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent
                                         / "reports" / "recall_explain.md"))
    args = ap.parse_args()

    r = explain(args.labels, args.manifest, args.audio_dir, args.audio_dir)
    lines = [f"\n## RECALL 对账 @ {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"  标签曲数={r['n_label_pieces']} manifest曲数={r['n_manifest']} "
             f"缺整曲音频曲数={r['n_no_whole']}(应≈切割报告的 no_whole_audio=3,683)"]
    names = {"A_purged_stale": "A 清场遗留(池外,勿复活)",
             "B_benign_no_manifest": "B 无害(不在 manifest,段全在)",
             "C_CONFLICT_in_manifest_missing": "C 【矛盾,贴回待查】在 manifest 且段缺",
             "D_benign_in_manifest": "D 无害(在 manifest,段全在)"}
    for k, label in names.items():
        lst = r["cats"][k]
        rk = k[0]
        lines.append(f"  {label}: 曲={len(lst)} 涉及行={r['rows'][rk]}")
        for pid, n_u, n_m in lst[:10]:
            lines.append(f"    - {pid}(行={n_u} 缺段={n_m})")
    verdict = ("对账闭合:缺整曲的曲全部落在 A/B/D(清场遗留或无害),无矛盾类"
               if not r["cats"]["C_CONFLICT_in_manifest_missing"] else
               "存在 C 类矛盾曲 —— s4_parallel 名单/路径逻辑与实际不符,规划端待查")
    lines.append(f"  判定: {verdict}")
    for s in lines:
        print(s, flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"报告已落盘 {out}(git add + commit + push 即上报,勿编辑)", flush=True)


if __name__ == "__main__":
    main()
