"""
按曲清理 + 验证 —— 解决"executor 清不干净、说清了也没法确认"的问题。

原则:
  1. 【穷举】一首曲的所有产物类别写死在 ARTIFACTS 里(上次事故:清了 .done 和段音频,
     但 _vn/ 里 VN 的 .mid/.csv、_perf.mid/_whole.opus 中间文件、两份标签文件里的行全漏了)。
     以后新增产物类型必须加进这张表,清理才算完整。
  2. 【验证可贴】purge 后自动跑 verify,输出每类残留计数表 —— 全 0 才算清干净。
     执行端把这张表贴回来,用户看数字确认,不听"我清了"。
"""
from __future__ import annotations
import json
import os
from pathlib import Path


def _labels_rows_for(labels_path: Path, pids: set, prefixes: tuple) -> int:
    """数 labels 文件里属于 pids 的行(utt_id 前缀匹配 + piece_id 匹配)。文件缺失 → 0。"""
    if not labels_path or not Path(labels_path).exists():
        return 0
    n = 0
    with open(labels_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            uid = str(row.get("utt_id", ""))
            if row.get("piece_id") in pids and uid.startswith(prefixes):
                n += 1
    return n


def piece_files(audio_dir: Path, pid: str) -> dict[str, list[Path]]:
    """一首曲在音频目录下的【全部】文件产物,按类别。新增产物类型必须在这里登记。"""
    audio_dir = Path(audio_dir)
    vn_dir = audio_dir / "_vn"
    cats = {
        "whole_audio":   [audio_dir / f"pdmx_{pid}{e}" for e in (".opus", ".flac", ".wav")],
        "s4_segments":   list(audio_dir.glob(f"pdmx_{pid}_*")),
        "vn_segments":   list(audio_dir.glob(f"pdmxperf_{pid}_*")),
        "intermediates": [audio_dir / f"{pid}_whole.opus", audio_dir / f"{pid}_perf.mid"],
        "done_marker":   [audio_dir / f"{pid}.done"],
        # 上次被漏掉的:VN 输出目录里这曲的演奏 MIDI 和 CSV(命名含 xml stem = pid)
        "vn_mid_csv":    list(vn_dir.glob(f"*{pid}*")) if vn_dir.exists() else [],
    }
    return {k: [p for p in v if p.exists()] for k, v in cats.items()}


def purge_label_rows(labels_path: Path, pids: set, prefixes: tuple) -> tuple[int, int]:
    """从 labels 剔除属于 pids 的行(原文件 → .bak,重复清理时不覆盖旧备份)。返回 (保留, 剔除)。"""
    labels_path = Path(labels_path)
    if not labels_path.exists():
        return 0, 0
    kept = dropped = 0
    tmp = labels_path.with_suffix(".tmp")
    with open(labels_path, "r", encoding="utf-8") as fi, open(tmp, "w", encoding="utf-8") as fo:
        for line in fi:
            s = line.strip()
            if not s:
                continue
            drop = False
            try:
                row = json.loads(s)
                uid = str(row.get("utt_id", ""))
                drop = row.get("piece_id") in pids and uid.startswith(prefixes)
            except Exception:
                pass
            if drop:
                dropped += 1
            else:
                kept += 1
                fo.write(s + "\n")
    bak = labels_path.with_suffix(".bak")
    if not bak.exists():
        labels_path.rename(bak)
    else:
        labels_path.unlink()
    tmp.rename(labels_path)
    return kept, dropped


def purge_pieces(pids: set, audio_dir, label_files: list) -> dict:
    """删除 pids 的全部文件产物 + 标签行。label_files: [(path, (utt前缀,...)), ...]。返回统计。"""
    st: dict = {"pieces": len(pids)}
    for pid in pids:
        for cat, files in piece_files(Path(audio_dir), pid).items():
            for f in files:
                try:
                    f.unlink()
                    st[cat] = st.get(cat, 0) + 1
                except OSError:
                    st[cat + "_fail"] = st.get(cat + "_fail", 0) + 1
    for path, prefixes in label_files:
        kept, dropped = purge_label_rows(Path(path), pids, prefixes)
        st[f"label_rows_dropped:{Path(path).name}"] = dropped
    return st


def verify_pieces(pids: set, audio_dir, label_files: list) -> tuple[bool, dict]:
    """验证 pids 的产物已清干净:每类残留计数,全 0 = 干净。这张表就是给用户看的凭证。"""
    counts: dict = {}
    for pid in pids:
        for cat, files in piece_files(Path(audio_dir), pid).items():
            counts[cat] = counts.get(cat, 0) + len(files)
    for path, prefixes in label_files:
        counts[f"label_rows:{Path(path).name}"] = _labels_rows_for(Path(path), pids, prefixes)
    clean = all(v == 0 for v in counts.values())
    return clean, counts


def format_verify(clean: bool, counts: dict) -> str:
    lines = ["===== 清理验证(每类残留计数,全 0 才算清干净)====="]
    for k, v in sorted(counts.items()):
        lines.append(f"  {'✓' if v == 0 else '✗'} {k} = {v}")
    lines.append("  结论: " + ("【干净】" if clean else "【没清干净,把此表贴回给用户】"))
    return "\n".join(lines)
