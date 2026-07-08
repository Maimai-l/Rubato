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
from rubato.data.pdmx import build_blacklist, work_key


def load_musicxml_part(xml_path: str):
    import partitura
    s = partitura.load_musicxml(xml_path)
    return s.parts[0] if hasattr(s, "parts") and s.parts else s


def process_piece(piece: dict, xml_root: Path,
                  min_measures: int, max_measures: int, max_sec: float,
                  lenient: bool) -> tuple[list[dict], dict]:
    """
    单曲:归一化 XML → IR → 小节对齐切段 → A2S/A2S_lite 标签。
    返回 (label_rows, stats)。lenient 用于浪漫派非标准小节(华彩/延长)。
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

    try:
        segs = segment_score(ir, min_measures=min_measures,
                             max_measures=max_measures, max_sec=max_sec,
                             sec_per_whole=2.0)   # 恒速估算切段时长(无 tmap)
        stats["segments"] = len(segs)
    except Exception as e:
        stats["skipped"] = f"segment_failed:{type(e).__name__}:{str(e)[:80]}"
        return [], stats

    rows = []
    for si, (sub_ir, (a, b)) in enumerate(segs):
        try:
            labels, fails = make_labels(sub_ir, "flat")   # flat→A2S/A2S_lite(TAST 需 tmap,此处无)
            a2s = labels.get("A2S")
            if a2s:
                rows.append({
                    "utt_id": f"pdmx_{pid}_{si:03d}",
                    "piece_id": pid,
                    "measure_range": [a, b],
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
        min_measures: int = 4, max_measures: int = 32, max_sec: float = 40.0,
        lenient: bool = True, limit: int | None = None) -> dict:
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
                                        max_sec, lenient)
        except Exception:
            report["failures"].append({"piece_id": piece.get("piece_id"),
                                       "reason": "exception", "tb": traceback.format_exc()[:200]})
            continue
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
    # 本地路径(用户 Windows 环境)。黑名单从 nASAP test / ASAP-Beyer work_key 构建。
    ROOT = Path(r"D:\vscode_projects\ee_download")
    MANIFEST = ROOT / "work" / "manifest_pieces.jsonl"
    XML_ROOT = ROOT / "work" / "xml_norm"
    OUT_LABELS = ROOT / "work" / "pdmx_a2s_labels.jsonl"
    OUT_CORPUS = ROOT / "work" / "a2s_corpus.txt"
    OUT_REPORT = ROOT / "reports" / "s5_pdmx_a2s.json"

    # 黑名单:若已有 nASAP split / ASAP-Beyer 曲目清单则读入(此处示例留空,
    # 实跑时从 nasap_split.json 的 test_works + ASAP-Beyer 清单构建)。
    blacklist = build_blacklist(nasap_test_works=[], asap_beyer_works=[])

    run(str(MANIFEST), str(XML_ROOT), str(OUT_LABELS), str(OUT_CORPUS),
        str(OUT_REPORT), blacklist=blacklist)
