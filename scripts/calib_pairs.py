"""
校准全量第 1 步:枚举 nASAP test 配对(整曲录音 ↔ ASAP 参考谱)。

产出(代码写数,不许手抄):
  $WORK/calib_pairs.jsonl —— 每行 {perf_id, flac, ref_xml, n_segments}
  stdout 打印配对表 + 汇总(test 单元数 / 配上音频数 / 配上参考谱数 / 缺失明细)。

口径:
  - test 单元 = nasap_labels.jsonl 中 split=="test" 的行,按 utt_id 去掉末段号聚合
    (与 s7_assign_split.piece_of 同一约定;一个单元 = 一个(演奏,谱)对)。
  - 整曲音频 = 行内 audio_path/perf_audio 引用 → work/maestro_audio/<名>.flac
    (与 build_dataset.resolve_audio 的 nasap 分支同一映射,评测与训练同源)。
  - 参考谱 = ASAP 仓库内 xml_score 相对路径(逐个存在性校验)。
  - 同一参考谱可对应多个演奏(不同钢琴家)—— 每个演奏是独立配对,符合逐演奏评测协议。

用法(执行端,任意 python 环境):
  python scripts/calib_pairs.py
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl, write_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("RUBATO_WORK")
            or (ROOT.parent / "work" if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download\work"))
# ASAP 仓库根(参考谱所在):与 build_dataset 同一路径约定 $TP=数据盘根
ASAP = Path(os.environ.get("RUBATO_ASAP")
            or (WORK.parent / "asap-dataset" / "asap-dataset"))


def unit_of(utt_id: str) -> str:
    """utt_id = nasap_{perf}_{xml}_{si:03d} → 去段号 = (演奏,谱) 单元(s7 同约定)。"""
    return utt_id.rsplit("_", 1)[0]


def resolve_flac(ref: str) -> Path | None:
    cand = Path(str(ref))
    if cand.exists():
        return cand
    cand = WORK / "maestro_audio" / Path(str(ref)).with_suffix(".flac").name
    return cand if cand.exists() else None


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="枚举 nASAP test 校准配对(录音↔参考谱)")
    ap.add_argument("--labels", default=str(WORK / "nasap_labels.jsonl"))
    ap.add_argument("--out", default=str(WORK / "calib_pairs.jsonl"))
    args = ap.parse_args(argv)

    lp = Path(args.labels)
    if not lp.exists():
        print(f"✗ 标签文件不存在: {lp}")
        return 1
    if not ASAP.exists():
        print(f"✗ ASAP 仓库目录不存在: {ASAP}(可用环境变量 RUBATO_ASAP 覆写)")
        return 1

    units: dict[str, dict] = {}
    n_test_rows = 0
    for r in read_jsonl(lp):
        if r.get("split") != "test":
            continue
        n_test_rows += 1
        u = unit_of(str(r.get("utt_id", "")))
        d = units.setdefault(u, {"perf_id": u, "n_segments": 0,
                                 "audio_ref": r.get("audio_path") or r.get("perf_audio") or "",
                                 "xml_rel": str(r.get("xml_score", "") or "")})
        d["n_segments"] += 1

    pairs, miss_audio, miss_ref = [], [], []
    for u, d in sorted(units.items()):
        flac = resolve_flac(d["audio_ref"]) if d["audio_ref"] else None
        ref = ASAP / d["xml_rel"] if d["xml_rel"] else None
        if flac is None:
            miss_audio.append(u)
            continue
        if ref is None or not ref.exists():
            miss_ref.append(u)
            continue
        pairs.append({
            "perf_id": u, "flac": str(flac), "ref_xml": str(ref),
            "n_segments": d["n_segments"],
            # This is the repository's conservative local split, not the
            # paper's standard 102-recording ASAP benchmark.
            "benchmark": "rubato_local_conservative_holdout_v1",
            "benchmark_expected_count": len(units),
        })

    write_jsonl(args.out, pairs)
    print(f"nASAP test:行 {n_test_rows} / 单元 {len(units)}")
    print(f"配对成功 {len(pairs)} | 缺整曲音频 {len(miss_audio)} | 缺参考谱 {len(miss_ref)}")
    for u in miss_audio[:10]:
        print(f"  缺音频: {u} (ref={units[u]['audio_ref']!r})")
    for u in miss_ref[:10]:
        print(f"  缺参考谱: {u} (xml={units[u]['xml_rel']!r})")
    print(f"清单已写: {args.out}")
    for p in pairs:
        print(f"  {p['perf_id']}  segs={p['n_segments']}  flac={Path(p['flac']).name}")
    if not pairs:
        print("✗ 零配对 —— 不要继续后续步骤,整段贴回")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
