"""
S5 parallel launcher: split manifest → N workers → merge results.
Fixes single-threaded bottleneck: 53k pieces × 0.3 pieces/s = 38h → ~10h with 4 workers.
"""
from __future__ import annotations
import json
import sys
import time
import multiprocessing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts dir

import importlib.util
_s5_spec = importlib.util.spec_from_file_location(
    "s5_pdmx_a2s_labels", Path(__file__).resolve().parent / "s5_pdmx_a2s_labels.py")
_s5 = importlib.util.module_from_spec(_s5_spec)
_s5_spec.loader.exec_module(_s5)
run_s5 = _s5.run
read_jsonl = _s5.read_jsonl
write_jsonl = _s5.write_jsonl
write_text = _s5.write_text
read_text = _s5.read_text

from rubato.ops import pick_workers, concat_files

ROOT = Path(r"D:\vscode_projects\ee_download")
MANIFEST = ROOT / "work" / "manifest_pieces.jsonl"
# 不再写死 24:s5 是纯文本(partitura 解析),每 worker ~0.6GB;按内存/CPU 自动定,再封顶 16。
N_WORKERS = pick_workers(per_worker_gb=0.6, hard_cap=16)


def split_manifest(pieces: list, n: int) -> list[list]:
    """Split pieces into n roughly equal chunks."""
    chunk_size = max(1, len(pieces) // n)
    chunks = []
    for i in range(n):
        start = i * chunk_size
        end = start + chunk_size if i < n - 1 else len(pieces)
        chunks.append(pieces[start:end])
    return chunks


def worker(chunk: list, work_dir: Path, worker_id: int) -> dict:
    """Process one chunk. Writes chunk-specific output files."""
    chunk_manifest = work_dir / f"manifest_chunk_{worker_id}.jsonl"
    chunk_labels = work_dir / f"pdmx_a2s_labels_{worker_id}.jsonl"
    chunk_corpus = work_dir / f"a2s_corpus_{worker_id}.txt"
    chunk_report = ROOT / "reports" / f"s5_pdmx_a2s_{worker_id}.json"

    # Write chunk manifest
    write_jsonl(str(chunk_manifest), chunk)

    # Run S5
    report = run_s5(
        str(chunk_manifest), str(ROOT / "work" / "xml_norm"),
        str(chunk_labels), str(chunk_corpus), str(chunk_report),
        blacklist=set(),
        min_measures=2, max_measures=16, overlap=True,
    )
    report["worker_id"] = worker_id
    report["chunk_size"] = len(chunk)
    return report


def merge_outputs(work_dir: Path, n: int):
    """把分块产物【流式】合并到最终文件——逐块追加,不把全部标签/语料读进内存(旧实现会 OOM)。"""
    total_processed = total_segments = total_labels = total_chars = total_skipped = 0
    for i in range(n):
        chunk_report = ROOT / "reports" / f"s5_pdmx_a2s_{i}.json"
        if chunk_report.exists():
            with open(chunk_report, 'r') as f:
                r = json.load(f)
            total_processed += r.get("processed", 0)
            total_segments += r.get("total_segments", 0)
            total_labels += r.get("total_labels", 0)
            total_chars += r.get("total_a2s_chars", 0)
            total_skipped += r.get("skipped", 0)

    # 流式合并(concat_files 一次只驻留一块的缓冲)
    label_entries = concat_files(
        [str(work_dir / f"pdmx_a2s_labels_{i}.jsonl") for i in range(n)],
        str(work_dir / "pdmx_a2s_labels.jsonl"))
    corpus_lines = concat_files(
        [str(work_dir / f"a2s_corpus_{i}.txt") for i in range(n)],
        str(work_dir / "a2s_corpus.txt"))

    merged = {
        "stage": "S5-parallel", "workers": n,
        "processed": total_processed, "skipped": total_skipped,
        "total_segments": total_segments, "total_labels": total_labels,
        "total_a2s_chars": total_chars,
        "corpus_lines": corpus_lines, "label_entries": label_entries,
    }
    report_path = ROOT / "reports" / "s5_pdmx_a2s.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # Clean up chunk files
    for i in range(n):
        for pattern in [f"manifest_chunk_{i}.jsonl", f"pdmx_a2s_labels_{i}.jsonl",
                         f"a2s_corpus_{i}.txt"]:
            p = work_dir / pattern
            if p.exists():
                p.unlink()

    return merged


def main():
    print(f"S5 Parallel: {N_WORKERS} workers")
    work_dir = ROOT / "work"
    pieces = list(read_jsonl(str(MANIFEST)))
    print(f"  Total pieces: {len(pieces)}")
    chunks = split_manifest(pieces, N_WORKERS)
    for i, c in enumerate(chunks):
        print(f"  Worker {i}: {len(c)} pieces")

    t0 = time.time()
    with multiprocessing.Pool(N_WORKERS) as pool:
        results = pool.starmap(worker, [(c, work_dir, i) for i, c in enumerate(chunks)])

    elapsed = time.time() - t0
    print(f"\nAll workers done in {elapsed/60:.1f}m")

    for r in results:
        print(f"  Worker {r['worker_id']}: {r['processed']} processed, "
              f"{r['total_labels']} labels, {r.get('skipped', 0)} skipped")

    merged = merge_outputs(work_dir, N_WORKERS)
    print(f"\nMerged: {merged['processed']} pieces → {merged['total_labels']} labels, "
          f"{merged['total_a2s_chars']:,} A2S chars, {merged['corpus_lines']} corpus lines")
    print(f"  Corpus: {work_dir / 'a2s_corpus.txt'}")
    print(f"  Labels: {work_dir / 'pdmx_a2s_labels.jsonl'}")


if __name__ == "__main__":
    main()
