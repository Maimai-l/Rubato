"""
nASAP 保守 split 后置分配(R-S7.4)—— 把一直没人调用的 conservative_split 真正接上。

为什么必须有:ASAP metadata.csv 没有 split 列,s7 的 split 透传拿不到任何值 →
assemble 把 nASAP 全体默认 train → nasap_val/test = 0:训练的 eval hook 没有 nASAP
可评(可解析率/OMR-NED 全空),论文的 nASAP test 协议也无从谈起。
conservative_split(rubato/data/nasap.py)当初就是为此实现的,却从未被任何脚本调用
(模块 docstring 自己写着"s7 必须调它")—— 本脚本补上这最后一环。

做法(后置、幂等、与分块跑 s7 兼容):
  读全量 nasap_labels.jsonl(s7 行带 work_key)→ 按 (演奏,谱) 聚合段数 →
  conservative_split(val 目标 512 段,work_key 级隔离,同作品绝不跨 split)→
  行内写 split 后原地重写(留 .bak)→ manifest 落盘 work/nasap_split.json →
  验证表:三 split 段数 + work_key 零交集断言。

用法(执行端,s7 全量重跑完后):
  python scripts/s7_assign_split.py            # 干跑:只打表
  python scripts/s7_assign_split.py --apply    # 实施(留 .bak)+ 验证表
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout
from rubato.data.nasap import conservative_split

ROOT = Path(r"D:\vscode_projects\ee_download")


def piece_of(utt_id: str) -> str:
    """utt_id = nasap_{perf}_{xml}_{si:03d} → 去掉段号 = (演奏,谱) 单元。"""
    return utt_id.rsplit("_", 1)[0]


def load_rows(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_assignment(rows: list[dict], val_target: int) -> tuple[dict, dict]:
    per_piece: dict[str, dict] = {}
    for r in rows:
        pid = piece_of(str(r.get("utt_id", "")))
        d = per_piece.setdefault(pid, {"piece_id": pid,
                                       "work_key": r.get("work_key") or f"__nokey__|{pid}",
                                       "n_segments": 0})
        d["n_segments"] += 1
    res = conservative_split(list(per_piece.values()), val_segment_target=val_target)
    return res["assignment"], res["manifest"]


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="nASAP 标签行分配 train/val/test(R-S7.4,默认干跑)")
    ap.add_argument("--labels", default=str(ROOT / "work" / "nasap_labels.jsonl"))
    ap.add_argument("--val-target", type=int, default=512, help="val 段数目标(R-S7.4)")
    ap.add_argument("--manifest-out", default=str(ROOT / "work" / "nasap_split.json"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.labels)
    if not path.exists():
        print(f"✗ 标签文件不存在: {path}")
        return 1
    rows = load_rows(path)
    no_wk = sum(1 for r in rows if not r.get("work_key"))
    if no_wk:
        print(f"  ⚠ {no_wk}/{len(rows)} 行缺 work_key(旧版 s7 产物?)—— 这些行按 piece 独立键处理,"
              "但正确做法是先用新 s7 --fresh 重跑标签")
    assignment, manifest = build_assignment(rows, args.val_target)

    counts = {"train": 0, "val": 0, "test": 0}
    for r in rows:
        counts[assignment[piece_of(str(r["utt_id"]))]] += 1
    print(f"分配(work_key 级隔离,seed={manifest['seed']}):")
    print(f"  段数 train={counts['train']} val={counts['val']}(目标 {args.val_target}) test={counts['test']}")
    print(f"  作品 train={manifest['n_train_works']} val={manifest['n_val_works']} test={manifest['n_test_works']}")
    if not args.apply:
        print("\n干跑结束(未改文件)。加 --apply 实施(留 .bak)+ 写 manifest。")
        return 0

    # 隔离断言:同 work_key 不得跨 split(conservative_split 构造上保证,这里再验一遍不靠信任)
    wk_split: dict[str, set] = {}
    for r in rows:
        pid = piece_of(str(r["utt_id"]))
        wk_split.setdefault(r.get("work_key") or f"__nokey__|{pid}", set()).add(assignment[pid])
    leaks = {wk: sorted(s) for wk, s in wk_split.items() if len(s) > 1}
    if leaks:
        print(f"✗ work_key 跨 split(不应发生): {list(leaks.items())[:5]}")
        return 1

    bak = path.with_suffix(".bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fo:
        for r in rows:
            r["split"] = assignment[piece_of(str(r["utt_id"]))]
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)
    Path(args.manifest_out).write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                       encoding="utf-8")

    # 复扫验证(D10:改完必须复扫贴表,不靠"我改了"三个字)
    re_rows = load_rows(path)
    re_counts: dict = {}
    for r in re_rows:
        re_counts[r.get("split", "MISSING")] = re_counts.get(r.get("split", "MISSING"), 0) + 1
    missing = re_counts.get("MISSING", 0)
    ok = missing == 0 and re_counts.get("val", 0) > 0 and re_counts.get("test", 0) > 0
    print("\n===== 分配验证(复扫)=====")
    print(f"  {'✓' if missing == 0 else '✗'} 无 split 的行 = {missing}")
    print(f"  {'✓' if re_counts.get('val', 0) > 0 else '✗'} val 段 = {re_counts.get('val', 0)}")
    print(f"  {'✓' if re_counts.get('test', 0) > 0 else '✗'} test 段 = {re_counts.get('test', 0)}")
    print(f"  ✓ work_key 零跨 split(已断言)")
    print(f"  manifest → {args.manifest_out}")
    print("  结论: " + ("【干净】" if ok else "【异常,贴回给规划端】"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
