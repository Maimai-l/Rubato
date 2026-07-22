"""回填 nASAP 标签漏写的 xml_score 字段。

S7 原生成器已从 ASAP metadata.csv 读取 xml_score，但历史版本没有将它写入
nasap_labels.jsonl。这里以稳定键 (perf_audio, work_key) 从原始 metadata 恢复该字段。

默认 dry-run；--apply 会先建立 .pre_xml_backfill.bak，再原子替换标签文件。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.data.pdmx import work_key  # noqa: E402
from rubato.platform import harden_stdout, read_jsonl  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("RUBATO_WORK")
            or (ROOT.parent / "work" if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download\work"))
ASAP = Path(os.environ.get("RUBATO_ASAP")
            or (WORK.parent / "asap-dataset" / "asap-dataset"))


def _metadata_index(path: Path) -> dict[tuple[str, str], set[str]]:
    index: dict[tuple[str, str], set[str]] = defaultdict(set)
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            audio = str(row.get("maestro_audio_performance") or "").strip()
            xml = str(row.get("xml_score") or "").strip()
            if audio and xml:
                index[(audio, work_key(row.get("composer") or "", row.get("title") or ""))].add(xml)
    return index


def main(argv=None) -> int:
    harden_stdout()
    ap = argparse.ArgumentParser(description="回填 nASAP labels 的 xml_score（默认 dry-run）")
    ap.add_argument("--labels", default=str(WORK / "nasap_labels.jsonl"))
    ap.add_argument("--metadata", default=str(ASAP / "metadata.csv"))
    ap.add_argument("--apply", action="store_true", help="验证全部通过后备份并写入回填字段")
    args = ap.parse_args(argv)

    labels_p, meta_p = Path(args.labels), Path(args.metadata)
    if not labels_p.exists() or not meta_p.exists():
        print(f"✗ 输入不存在: labels={labels_p.exists()} metadata={meta_p.exists()}")
        return 2
    index = _metadata_index(meta_p)
    rows = list(read_jsonl(labels_p))
    state = Counter()
    examples: list[str] = []
    resolved: list[str | None] = []
    for row in rows:
        existing = str(row.get("xml_score") or "").strip()
        if existing:
            state["already_present"] += 1
            resolved.append(existing)
            continue
        key = (str(row.get("perf_audio") or "").strip(), str(row.get("work_key") or "").strip())
        candidates = index.get(key, set())
        if len(candidates) == 1:
            xml = next(iter(candidates))
            if not (ASAP / xml).is_file():
                state["xml_file_missing"] += 1
                resolved.append(None)
                if len(examples) < 5:
                    examples.append(f"xml_file_missing {row.get('utt_id')} -> {xml}")
            else:
                state["recoverable"] += 1
                resolved.append(xml)
        elif not candidates:
            state["mapping_missing"] += 1
            resolved.append(None)
            if len(examples) < 5:
                examples.append(f"mapping_missing {row.get('utt_id')}")
        else:
            state["mapping_ambiguous"] += 1
            resolved.append(None)
            if len(examples) < 5:
                examples.append(f"mapping_ambiguous {row.get('utt_id')} -> {sorted(candidates)}")

    bad = state["mapping_missing"] + state["mapping_ambiguous"] + state["xml_file_missing"]
    print("nASAP xml_score 回填核验")
    print(f"  rows={len(rows)} already_present={state['already_present']} recoverable={state['recoverable']} "
          f"mapping_missing={state['mapping_missing']} mapping_ambiguous={state['mapping_ambiguous']} "
          f"xml_file_missing={state['xml_file_missing']}")
    for ex in examples:
        print(f"  样本: {ex}")
    if bad:
        print("✗ 核验未闭合：不写入。")
        return 1
    if not args.apply:
        print("--dry-run OK：确认后使用 --apply 回填。")
        return 0

    backup = labels_p.with_name(labels_p.name + ".pre_xml_backfill.bak")
    if backup.exists():
        print(f"✗ 备份已存在，拒绝覆盖: {backup}")
        return 2
    tmp = labels_p.with_name(labels_p.name + ".xml_backfill.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row, xml in zip(rows, resolved):
            if not row.get("xml_score"):
                row["xml_score"] = xml
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    labels_p.replace(backup)
    tmp.replace(labels_p)
    print(f"✓ 已回填 {state['recoverable']} 行；备份: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
