"""
S5/S8 PDMX MusicXML → InterMo A2S 标签批量生成(修复问题#11)。

此前状态:PDMX 有 ~130k MusicXML,应经 part_to_ir → segment_score → project(A2S/A2S_lite)
产出 A2S 文本标签,但【从未批量跑】。后果连锁:
  - 问题#3/#13:tokenizer 语料只有 nASAP 39.9M chars,PDMX 的 1,002k utterance A2S 标签缺失
    → UnigramLM 语料不足 → 词表缩到 4760、字形 100% 分裂。
  - 问题#4:训练 dataloader 无配对 tokenized 标签。

本脚本产出:
  - labels.jsonl:{utt_id, piece_id, measure_range, A2S, A2S_lite, TAST=null, AMT=null}
  - a2s_corpus.txt:A2S + A2S_lite 文本(每行一条),直接喂 tokenizer 训练(R-S9 语料)
并落实:
  - 问题#14:黑名单过滤(nASAP test / ASAP-Beyer work_key 不进 train 标签)
  - §2.4:失败样本永不静默丢弃,全部进 failures 计数。
"""
from __future__ import annotations
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.platform import read_jsonl, write_jsonl, write_text, read_text
from rubato.intermo.partitura_adapter import part_to_ir
from rubato.data.segment import segment_score, make_labels
from rubato.data.nasap import segment_score_overlap
from rubato.data.pdmx import build_blacklist, work_key


def load_musicxml_part(xml_path: str):
    import partitura
    s = partitura.load_musicxml(xml_path)
    return s.parts[0] if hasattr(s, "parts") and s.parts else s


def process_piece(piece: dict, xml_root: Path,
                  min_measures: int, max_measures: int | None, max_sec: float,
                  lenient: bool, overlap: bool = False) -> tuple[list[dict], dict]:
    """
    单曲:归一化 XML → IR → 小节对齐切段 → A2S/A2S_lite 标签。
    返回 (label_rows, stats)。lenient 用于浪漫派非标准小节(华彩/延长)。
    overlap=True 使用重叠切窗(每段步长=段长一半),提升 tokenizer 语料覆盖。
    """
    pid = piece["piece_id"]
    stats = {"piece_id": pid, "segments": 0, "labels": 0}
    xml_rel = piece.get("xml_norm") or piece.get("xml_raw")
    if not xml_rel:
        stats["skipped"] = "no_xml_path"
        return [], stats
    xml_path = str(xml_root / xml_rel) if not Path(xml_rel).is_absolute() else xml_rel

    try:
        part = load_musicxml_part(xml_path)
    except Exception as e:
        stats["skipped"] = f"load_failed:{type(e).__name__}:{str(e)[:80]}"
        return [], stats
    try:
        ir = part_to_ir(part)
    except Exception as e:
        stats["skipped"] = f"part_to_ir_failed:{type(e).__name__}:{str(e)[:80]}"
        return [], stats

    # 【分段用真实速度图,不再恒速 120bpm】(与 S5 VN 同一类 bug 的 S4 侧修复):
    # 该曲的渲染 MIDI 自带 set_tempo 真速度 → midi_time 提取 tmap;max_sec=40 约束按真实秒生效,
    # 快曲不再被切碎、慢曲不再超训练窗。结构守卫:MIDI 小节网格须与 IR 对齐(展开反复等结构
    # 不一致 → 回退恒速并计数,此时该曲的段在 s4_slice_segments 处也会被 structure_mismatch 跳过)。
    tmap = None
    midi_path = piece.get("midi_path")
    if midi_path and Path(midi_path).exists():
        # 【巨曲守卫】(执行端痛点的正确解法,替代其 --no-midi-tempo 全局开关):个别"黑乐谱"式
        # 巨 MIDI 解析要几分钟,卡住整个 P4;只对【超阈值的那几首】回退恒速并计数,其余曲保持真速度。
        # 全局关掉真速度 = 为几首巨曲把全体分段正确性交出去,不干;且旧开关在 run() 里引用 __main__
        # 的 args,经 s5_parallel 导入调用时必 NameError —— 已一并撤除。
        import os as _os
        max_mb = float(_os.environ.get("S5_TEMPO_MIDI_MAX_MB", "20"))
        if Path(midi_path).stat().st_size > max_mb * 1e6:
            stats["tempo_fallback"] = "midi_too_big"
        else:
            try:
                from rubato.data.midi_time import midi_time
                mtmap, mmeasures, mtotal = midi_time(midi_path)
                if (len(mmeasures) == len(ir.measures)
                        and abs(float(mtotal - ir.score_end)) <= 1.0 / 16):
                    tmap = mtmap
                else:
                    stats["tempo_fallback"] = "structure_mismatch"
            except Exception as e:
                stats["tempo_fallback"] = f"midi_fail:{type(e).__name__}"
    else:
        stats["tempo_fallback"] = "no_midi"
    try:
        if overlap:
            segs = segment_score_overlap(ir, tmap, min_measures=min_measures,
                                         max_measures=max_measures, max_sec=max_sec)
        else:
            segs = segment_score(ir, min_measures=min_measures,
                                 max_measures=max_measures, max_sec=max_sec,
                                 tmap=tmap, sec_per_whole=None if tmap else 2.0)
        stats["segments"] = len(segs)
    except Exception as e:
        stats["skipped"] = f"segment_failed:{type(e).__name__}:{str(e)[:80]}"
        return [], stats

    rows = []
    bounds = [m.start for m in ir.measures] + [ir.score_end]
    for si, (sub_ir, (a, b)) in enumerate(segs):
        try:
            # flat→A2S/A2S_lite。此路【故意不产 TAST】:TAST 时间戳必须与音频同一 tmap,
            # 本脚本不渲染音频(恒速估算与真实音频不匹配)。PDMX 的表现性音频+匹配 TAST
            # 由 scripts/s5_vn_render.py 产(仅 VirtuosoNet)。本脚本只供 tokenizer 语料 + A2S 训练标签。
            labels, fails = make_labels(sub_ir, "flat")
            a2s = labels.get("A2S")
            if a2s:
                rows.append({
                    "utt_id": f"pdmx_{pid}_{si:03d}",
                    "piece_id": pid,
                    "measure_range": [a, b],
                    # 【弱起免疫】IR 的真实乐谱位置(全音符)。切割器直接拿位置过 MIDI 速度图,
                    # 不再从拍号算术重建小节网格 —— 弱起小节会让重建网格整体错位且守卫恰好双过。
                    "score_range": [float(bounds[a]), float(bounds[b])],
                    "A2S": a2s,
                    "A2S_lite": labels.get("A2S_lite"),
                    "TAST": None, "AMT": None,
                })
            else:
                stats.setdefault("seg_fails", []).append({"seg": si, "fails": fails[:2]})
        except Exception as e:
            stats.setdefault("seg_fails", []).append({"seg": si, "err": f"{type(e).__name__}"})
    stats["labels"] = len(rows)
    return rows, stats


def run(manifest_path: str, xml_root: str, out_labels: str, out_corpus: str,
        out_report: str, blacklist: set | None = None,
        min_measures: int = 1, max_measures: int | None = None, max_sec: float = 40.0,
        lenient: bool = True, overlap: bool = False, limit: int | None = None) -> dict:
    """批量驱动。blacklist=work_key 集合(命中的曲整曲跳过,不产 train 标签)。"""
    blacklist = blacklist or set()
    xml_root = Path(xml_root)
    pieces = list(read_jsonl(manifest_path))
    if limit:
        pieces = pieces[:limit]

    report = {"total": len(pieces), "processed": 0, "skipped": 0,
              "blacklisted": 0, "total_segments": 0, "total_labels": 0,
              "total_a2s_chars": 0, "failures": []}
    all_rows = []
    corpus_lines = []
    t0 = time.time()

    for i, piece in enumerate(pieces):
        if not piece.get("parse_ok", True):
            report["skipped"] += 1
            report["failures"].append({"piece_id": piece.get("piece_id"), "reason": "parse_ok_false"})
            continue
        wk = piece.get("work_key") or work_key(piece.get("composer_meta", ""),
                                               piece.get("title", ""))
        if wk in blacklist:                       # 问题#14:黑名单曲不进 train 标签
            report["blacklisted"] += 1
            continue
        try:
            rows, stats = process_piece(piece, xml_root, min_measures, max_measures,
                                        max_sec, lenient, overlap)
        except Exception:
            report["failures"].append({"piece_id": piece.get("piece_id"),
                                       "reason": "exception", "tb": traceback.format_exc()[:200]})
            continue
        if stats.get("tempo_fallback"):
            tf = report.setdefault("tempo_fallback", {})
            key = str(stats["tempo_fallback"]).split(":")[0]
            tf[key] = tf.get(key, 0) + 1
        if rows:
            report["processed"] += 1
            report["total_segments"] += stats["segments"]
            report["total_labels"] += stats["labels"]
            all_rows.extend(rows)
            for r in rows:
                report["total_a2s_chars"] += len(r["A2S"])
                corpus_lines.append(r["A2S"])
                if r.get("A2S_lite"):
                    corpus_lines.append(r["A2S_lite"])
        else:
            report["skipped"] += 1
            report["failures"].append({"piece_id": piece.get("piece_id"),
                                       "reason": stats.get("skipped", "no_labels")})
        if (i + 1) % 200 == 0:
            rate = (i + 1) / (time.time() - t0)
            print(f"  [{i+1}/{len(pieces)}] processed={report['processed']} "
                  f"labels={report['total_labels']} ({rate:.1f} pieces/s)")

    write_jsonl(out_labels, all_rows)
    write_text(out_corpus, "\n".join(corpus_lines) + "\n")
    report["elapsed_s"] = round(time.time() - t0, 1)
    report["failures"] = report["failures"][:100]
    Path(out_report).parent.mkdir(parents=True, exist_ok=True)
    write_text(out_report, json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nDONE: {report['processed']} pieces → {report['total_labels']} labels, "
          f"{report['total_a2s_chars']:,} A2S chars (corpus for tokenizer).")
    print(f"  labels: {out_labels}\n  corpus: {out_corpus}\n  report: {out_report}")
    return report


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=str, default="")
    ap.add_argument("--out-labels", type=str, default="")
    ap.add_argument("--out-corpus", type=str, default="")
    ap.add_argument("--out-report", type=str, default="")
    ap.add_argument("--min-measures", type=int, default=1)
    ap.add_argument("--max-measures", type=int, default=0,
                    help="0=不设小节数上限(用户决定:时间 max-sec 是唯一上限,段尽量长)")
    ap.add_argument("--overlap", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    ROOT = Path(r"D:\vscode_projects\ee_download")
    MANIFEST = Path(args.manifest) if args.manifest else ROOT / "work" / "manifest_pieces.jsonl"
    XML_ROOT = ROOT / "work" / "xml_norm"
    OUT_LABELS = Path(args.out_labels) if args.out_labels else ROOT / "work" / "pdmx_a2s_labels.jsonl"
    OUT_CORPUS = Path(args.out_corpus) if args.out_corpus else ROOT / "work" / "a2s_corpus.txt"
    OUT_REPORT = Path(args.out_report) if args.out_report else ROOT / "reports" / "s5_pdmx_a2s.json"

    blacklist = build_blacklist(nasap_test_works=[], asap_beyer_works=[])

    run(str(MANIFEST), str(XML_ROOT), str(OUT_LABELS), str(OUT_CORPUS),
        str(OUT_REPORT), blacklist=blacklist,
        min_measures=args.min_measures, max_measures=args.max_measures or None,
        overlap=bool(args.overlap), limit=args.limit if args.limit else None)
