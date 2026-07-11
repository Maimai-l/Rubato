"""
S5 VN 段长修复 —— 外科手术式重做,不全量重跑。

背景(reports/s5_vn_segmentation_bug.md):旧版 segment_score 没传 tmap,用恒速 120bpm 假设决定
段边界,快曲切出 0.2s 碎片、慢曲切出 93s 超长段(max_sec=40 形同虚设)。段内音频↔TAST 是同一
真 tmap 产的、内部自洽 —— 所以【长度正常的段是合法数据,不必重跑】;只有含越界段的曲需要重做。

本脚本:扫描 labels 里每个 VN 段的真实音频时长(读 wav 头,快)→ 找出含越界段(<min-sec 或
>max-sec)的曲 → --apply 时:①从 labels 移除这些曲的行(原文件备份 .bak);②删这些曲的段音频;
③删 .done。之后重跑 s5_vn_render.py,按标签判完成的续跑机制会【只重做这些曲】(分段 bug 已修)。

用法(执行端):
  python scripts/s5_repair_segments.py                 # 干跑:只报告,什么都不改
  python scripts/s5_repair_segments.py --apply         # 实施:改 labels(留 .bak)+ 删坏曲音频/.done
  python scripts/s5_vn_render.py                       # 之后:只重渲被清掉的曲(新分段)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout

ROOT = Path(r"D:\vscode_projects\ee_download")
VN_PREFIX = "pdmxperf_"          # 只动 VN 行;其他写者(文本标签等)的行原样保留


def _duration_s(audio_path: str) -> float | None:
    """读音频头拿时长(秒),不载数据。失败(文件缺/坏)返回 None。"""
    try:
        import soundfile as sf
        info = sf.info(audio_path)
        return float(info.frames) / float(info.samplerate)
    except Exception:
        return None


def scan(labels_path: Path, min_sec: float, max_sec: float):
    """流式过 labels,按曲聚合 VN 段时长。返回 (bad:set[pid], stats:dict)。
    坏曲判据:任一段 <min_sec / >max_sec / 音频缺失(行声称有 audio_path 但读不到)。"""
    bad, stats = set(), {"rows": 0, "vn_rows": 0, "pieces": set(), "too_short": 0,
                         "too_long": 0, "missing_audio": 0, "no_audio_field": 0,
                         "min_seen": float("inf"), "max_seen": 0.0}
    with open(labels_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            stats["rows"] += 1
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not str(row.get("utt_id", "")).startswith(VN_PREFIX):
                continue
            stats["vn_rows"] += 1
            pid = row.get("piece_id")
            stats["pieces"].add(pid)
            ap = row.get("audio_path")
            if not ap:
                stats["no_audio_field"] += 1      # humanize 无音频行:不据此判坏
                continue
            dur = _duration_s(ap)
            if dur is None:
                stats["missing_audio"] += 1
                bad.add(pid)
                continue
            stats["min_seen"] = min(stats["min_seen"], dur)
            stats["max_seen"] = max(stats["max_seen"], dur)
            if dur < min_sec:
                stats["too_short"] += 1; bad.add(pid)
            elif dur > max_sec:
                stats["too_long"] += 1; bad.add(pid)
    return bad, stats


def apply_repair(labels_path: Path, audio_dir: Path, bad: set) -> dict:
    """实施:labels 剔除坏曲 VN 行(原文件 → .bak);删坏曲段音频与 .done。返回统计。"""
    out = {"rows_kept": 0, "rows_dropped": 0, "audio_deleted": 0, "done_deleted": 0}
    tmp = labels_path.with_suffix(".tmp")
    with open(labels_path, "r", encoding="utf-8") as fi, \
         open(tmp, "w", encoding="utf-8") as fo:
        for line in fi:
            s = line.strip()
            if not s:
                continue
            drop = False
            try:
                row = json.loads(s)
                drop = (str(row.get("utt_id", "")).startswith(VN_PREFIX)
                        and row.get("piece_id") in bad)
            except Exception:
                pass
            if drop:
                out["rows_dropped"] += 1
            else:
                out["rows_kept"] += 1
                fo.write(s + "\n")
    bak = labels_path.with_suffix(".bak")
    if bak.exists():
        bak.unlink()
    labels_path.rename(bak)
    tmp.rename(labels_path)
    for pid in bad:
        for f in audio_dir.glob(f"{VN_PREFIX}{pid}_*"):     # 段音频(.wav/.opus)
            try:
                f.unlink(); out["audio_deleted"] += 1
            except OSError:
                pass
        dm = audio_dir / f"{pid}.done"
        if dm.exists():
            try:
                dm.unlink(); out["done_deleted"] += 1
            except OSError:
                pass
    return out


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="按真实音频时长找出坏分段的曲,清掉待重渲(默认干跑)")
    ap.add_argument("--labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--min-sec", type=float, default=1.0)
    ap.add_argument("--max-sec", type=float, default=40.0, help="与 segment_score 的 max_sec 一致")
    ap.add_argument("--slack", type=float, default=1.0,
                    help="max-sec 容差(秒):切片按小节界取整会略超 max_sec,不算坏")
    ap.add_argument("--all", action="store_true",
                    help="全量重跑模式:所有 VN 曲都标记重做(不看时长)。用于分段算法级修复后的整体重渲")
    ap.add_argument("--apply", action="store_true", help="实施修复(默认只报告)")
    args = ap.parse_args(argv)

    labels_path, audio_dir = Path(args.labels), Path(args.audio_dir)
    if not labels_path.exists():
        print(f"labels 不存在: {labels_path}"); return 2
    bad, st = scan(labels_path, args.min_sec, args.max_sec + args.slack)
    if args.all:
        bad = set(st["pieces"])          # 全部 VN 曲重做(标签行/段音频/.done 全清,labels 留 .bak)
        print("【--all 全量重跑模式】不按时长筛,所有 VN 曲的行/音频/.done 都将清除待重渲。")
    n_pieces = len(st["pieces"])
    print(f"扫描 {labels_path}")
    print(f"  行数 {st['rows']}(VN 行 {st['vn_rows']},涉及 {n_pieces} 曲)")
    print(f"  段时长范围 [{st['min_seen']:.1f}s, {st['max_seen']:.1f}s] | "
          f"过短(<{args.min_sec}s): {st['too_short']} | 过长(>{args.max_sec}+{args.slack}s): {st['too_long']} | "
          f"音频缺失: {st['missing_audio']} | 无音频字段(humanize): {st['no_audio_field']}")
    print(f"  → 含越界段需重做的曲: {len(bad)} / {n_pieces}"
          f"({0 if not n_pieces else round(100 * len(bad) / n_pieces, 1)}%)")
    if not args.apply:
        print("\n干跑结束(未改任何文件)。确认后加 --apply 实施;实施后重跑 s5_vn_render.py 只补这些曲。")
        return 0
    out = apply_repair(labels_path, audio_dir, bad)
    print(f"\n已实施:labels 保留 {out['rows_kept']} 行、剔除 {out['rows_dropped']} 行"
          f"(原文件备份 {labels_path.with_suffix('.bak').name});"
          f"删段音频 {out['audio_deleted']} 个、.done {out['done_deleted']} 个。")
    print("下一步:python scripts/s5_vn_render.py  (按标签续跑,只重渲被清掉的曲,分段已按真 tmap)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
