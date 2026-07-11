"""
乐器审计 —— 补 S3 过滤器的洞(执行端实听抓到鼓谱):内容级判定每首曲是不是钢琴,
非钢琴的从 manifest 剔除并【彻底清理】其全部产物(音频/中间文件/VN mid+csv/标签行),
清完自动输出验证表(每类残留计数,全 0 才算干净)。

为什么会漏:旧过滤器唯一的"钢琴"代理是 n_tracks∈{1,2} —— 独奏鼓/吉他/人声全是 1-2 轨照样过。
本审计查内容:谱面 <unpitched>/打击乐谱号/TAB/10通道/GM 音色号 + MIDI 通道与音色,任一强信号=非钢琴。

用法(执行端;SOP 驱动器会自动跑,无需手动):
  python scripts/s3_instrument_audit.py               # 干跑:报告各原因计数 + 例子
  python scripts/s3_instrument_audit.py --apply       # 剔除 manifest(留 .bak)+ 清产物 + 验证表
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl
from rubato.data.pdmx import classify_score_file, classify_midi_file
from rubato.data.cleanup import purge_pieces, verify_pieces, format_verify
from rubato.ops import auto_map

ROOT = Path(r"D:\vscode_projects\ee_download")


def _classify_task(t):
    """并行 worker(模块顶层,可 pickle):谱面优先、MIDI 兜底,任一非钢琴即非钢琴。
    每曲几十毫秒的纯 CPU 活 × 5 万曲 —— 单线程数小时,进程池分钟级。"""
    pid, xml_path, midi_path = t
    if xml_path and Path(xml_path).exists():
        ok, why = classify_score_file(xml_path)
        if not ok:
            return pid, False, why
    if midi_path and Path(midi_path).exists():
        ok, why = classify_midi_file(midi_path)
        if not ok:
            return pid, False, why
    return pid, True, "ok"


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="内容级乐器审计:剔除非钢琴曲并彻底清理其产物(默认干跑)")
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--xml-root", default=str(ROOT / "work" / "xml_norm"))
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--text-labels", default=str(ROOT / "work" / "pdmx_a2s_labels.jsonl"))
    ap.add_argument("--vn-labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--out-ids", default=str(ROOT / "reports" / "nonpiano_ids.txt"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=0, help="0=自动(核数,≤16)")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    pieces = list(read_jsonl(args.manifest))
    if args.limit:
        pieces = pieces[:args.limit]
    xml_root = Path(args.xml_root)
    tasks = []
    for p in pieces:
        pid = p.get("piece_id")
        if not pid:
            continue
        xml_rel = p.get("xml_norm") or p.get("xml_raw")
        xp = str(Path(xml_rel) if (xml_rel and Path(xml_rel).is_absolute())
                 else (xml_root / xml_rel)) if xml_rel else ""
        tasks.append((pid, xp, p.get("midi_path") or ""))
    bad: dict[str, str] = {}
    reasons: dict[str, int] = {}

    def _collect(_t, res):
        pid, ok, why = res
        if not ok:
            bad[pid] = why
            key = why.split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1

    auto_map(tasks, _classify_task, workers=args.workers, on_result=_collect)

    print(f"乐器审计: {len(pieces)} 曲中发现非钢琴 {len(bad)} 曲"
          f"({0 if not pieces else round(100 * len(bad) / len(pieces), 1)}%)")
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {k} = {v}")
    for pid, why in list(bad.items())[:10]:
        print(f"  例: {pid}  ← {why}")
    Path(args.out_ids).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_ids).write_text("\n".join(f"{pid}\t{why}" for pid, why in sorted(bad.items())),
                                  encoding="utf-8")
    print(f"  名单 → {args.out_ids}")
    if not args.apply:
        print("\n干跑结束(未改任何文件)。--apply = 剔除 manifest + 清产物 + 验证。")
        return 0

    pids = set(bad)
    # ① manifest 剔除(原文件 → .bak,不覆盖旧备份)
    mpath = Path(args.manifest)
    tmp = mpath.with_suffix(".tmp")
    kept = 0
    with open(mpath, "r", encoding="utf-8") as fi, open(tmp, "w", encoding="utf-8") as fo:
        for line in fi:
            s = line.strip()
            if not s:
                continue
            try:
                if json.loads(s).get("piece_id") in pids:
                    continue
            except Exception:
                pass
            fo.write(s + "\n")
            kept += 1
    bak = mpath.with_suffix(".bak")
    if not bak.exists():
        mpath.rename(bak)
    else:
        mpath.unlink()
    tmp.rename(mpath)
    print(f"manifest: 保留 {kept} 曲,剔除 {len(pids)} 曲(备份 {bak.name})")

    # ② 产物清理 + ③ 验证(全 0 才算干净,这张表贴回给用户)
    label_files = [(args.text_labels, ("pdmx_",)), (args.vn_labels, ("pdmxperf_",))]
    st = purge_pieces(pids, args.audio_dir, label_files)
    print("清理统计: " + " ".join(f"{k}={v}" for k, v in sorted(st.items())))
    clean, counts = verify_pieces(pids, args.audio_dir, label_files)
    print(format_verify(clean, counts))
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
