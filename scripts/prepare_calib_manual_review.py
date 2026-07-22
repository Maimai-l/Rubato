"""Prepare five stratified XML pairs for the preregistered grey-zone review."""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import read_jsonl


def read_scores(report: Path) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    for line in report.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) < 2 or not fields[0].startswith("nasap_"):
            continue
        try:
            rows.append((fields[0], float(fields[1])))
        except ValueError:
            continue
    return sorted(rows, key=lambda item: item[1])


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    work = root.parent / "work"
    ap = argparse.ArgumentParser(description="Prepare five score-quantile XML review pairs")
    ap.add_argument("--report", default=str(root / "reports" / "CALIB_FULL.txt"))
    ap.add_argument("--pairs", default=str(work / "calib_pairs.jsonl"))
    ap.add_argument("--est-dir", default=str(work / "calib_full_xml"))
    ap.add_argument("--out-dir", default=str(work / "calib_manual_review_5"))
    args = ap.parse_args()

    report, pairs_path, est_dir, out_dir = map(Path, (args.report, args.pairs, args.est_dir, args.out_dir))
    scores = read_scores(report)
    if len(scores) < 5:
        print(f"✗ 报告中可解析分数不足 5: {len(scores)}")
        return 2
    if out_dir.exists():
        print(f"✗ 审核目录已存在，拒绝覆盖: {out_dir}")
        return 2
    refs = {row["perf_id"]: row["ref_xml"] for row in read_jsonl(pairs_path)}
    indices = [0, (len(scores) - 1) // 4, (len(scores) - 1) // 2,
               3 * (len(scores) - 1) // 4, len(scores) - 1]
    selected = [scores[i] for i in indices]

    out_dir.mkdir(parents=True)
    manifest: list[tuple[str, str, str, str]] = []
    for rank, (perf_id, score) in enumerate(selected, 1):
        est = est_dir / f"{perf_id}.xml"
        ref = Path(refs.get(perf_id, ""))
        if not est.is_file() or not ref.is_file():
            print(f"✗ 源文件缺失: {perf_id}")
            return 2
        dest = out_dir / f"{rank:02d}_{perf_id}"
        dest.mkdir()
        shutil.copy2(est, dest / "estimate_m2st.xml")
        shutil.copy2(ref, dest / "reference_asap.xml")
        manifest.append((str(rank), perf_id, f"{score:.12g}", dest.name))
        print(f"  [{rank}/5] {perf_id}\tscore={score:.12g}")

    with (out_dir / "MANIFEST.tsv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(["rank_by_score", "perf_id", "raw_omr_ned", "folder"])
        writer.writerows(manifest)
    print(f"审核包已写: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
