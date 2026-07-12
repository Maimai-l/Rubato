"""
nASAP utt_id 唯一化 —— 修 P5d split 泄漏的【根因】(不是 split 逻辑的锅)。

病根(执行端 P5d 质量闸拦下的 5 个跨 split 作品,回查到底):ASAP 数据集每首曲的乐谱
文件一律叫 xml_score.musicxml,而 s7 旧版 utt_id 用了文件名 stem →
  nasap_{演奏者}_xml_score_{段号}
同一演奏者录过的【不同曲子】生成完全相同的 utt_id。两个后果:
  ① split 分配把不同作品并成一个 piece(取首行的 work_key)→ 另一作品的段"跨" split;
  ② 装配(assemble)对重名 utt_id 静默去重 → 后写的曲整段丢失。

修法(后置重写,不重跑 s7):新 utt = nasap_{演奏者}_{h8}_{段号},h8 = 演奏音频引用
(perf_audio)的 sha256 前 8 位 —— 一场录音只对应一首曲,(perf_audio, 段号) 天然唯一。
work_key 顺带从 metadata 反查校正(按 perf_audio 映射,权威源)。幂等:已是规范形的行跳过。

用法(执行端;SOP P5c2 就是它):
  python scripts/s7_fix_uttids.py            # 干跑:撞名统计
  python scripts/s7_fix_uttids.py --apply    # 重写(留 .bak)+ 唯一性验证表
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl

ROOT = Path(r"D:\vscode_projects\ee_download")
_OLD_RE = re.compile(r"^nasap_(.+?)_xml_score_(\d+)$")


def h8(s: str) -> str:
    return hashlib.sha256(str(s).encode()).hexdigest()[:8]


def canon(row: dict) -> str | None:
    """行的规范 utt_id;无法规范(缺 perf_audio)返回 None。已规范的行原样返回。"""
    old = str(row.get("utt_id") or "")
    perf = str(row.get("perf_audio") or "")
    if not old.startswith("nasap_") or not perf:
        return None
    tag = h8(perf)
    parts = old.split("_")
    if len(parts) >= 3 and parts[-2] == tag:
        return old                                   # 已是规范形(幂等)
    m = _OLD_RE.match(old)
    if m:
        stem, si = m.group(1), m.group(2)
    else:                                            # 兜底:剥掉尾段号
        stem, si = old[len("nasap_"):].rsplit("_", 1) if "_" in old[len("nasap_"):] \
            else (old[len("nasap_"):], "000")
    return f"nasap_{stem}_{tag}_{si}"


def meta_workkey_map(csv_path: Path) -> dict:
    """maestro_audio_performance → work_key(composer|title),metadata 为权威源。"""
    m: dict = {}
    if not csv_path.exists():
        return m
    import pandas as pd
    from rubato.data.pdmx import work_key
    df = pd.read_csv(str(csv_path))
    for _, r in df.iterrows():
        ma = str(r.get("maestro_audio_performance") or "")
        if ma:
            m[ma] = work_key(str(r.get("composer") or ""), str(r.get("title") or ""))
    return m


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="nASAP utt_id 唯一化(默认干跑)")
    ap.add_argument("--labels", default=str(ROOT / "work" / "nasap_labels.jsonl"))
    ap.add_argument("--metadata", default=str(ROOT / "asap-dataset" / "asap-dataset" / "metadata.csv"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.labels)
    if not path.exists():
        print(f"标签文件不存在({path})→ 无事可做。")
        return 0
    rows = list(read_jsonl(str(path)))
    seen: dict = {}
    n_dup_before = n_rewrite = n_nocanon = n_wk_fix = 0
    wk_map = meta_workkey_map(Path(args.metadata))
    for r in rows:
        old = str(r.get("utt_id") or "")
        n_dup_before += 1 if old in seen else 0
        seen[old] = True
        c = canon(r)
        if c is None:
            n_nocanon += 1
            continue
        if c != old:
            n_rewrite += 1
            if args.apply:
                r["utt_id"] = c
        wk_auth = wk_map.get(str(r.get("perf_audio") or ""))
        if wk_auth and r.get("work_key") != wk_auth:
            n_wk_fix += 1
            if args.apply:
                r["work_key"] = wk_auth
    print(f"共 {len(rows)} 行:重写前重复 utt_id = {n_dup_before},需重写 {n_rewrite} 行,"
          f"work_key 校正 {n_wk_fix} 行,无法规范 {n_nocanon} 行")
    if not args.apply:
        print("\n干跑结束(未改文件)。加 --apply 实施(留 .bak)。")
        return 0

    bak = path.with_suffix(".bak2")                 # .bak 已被多写者占用,这里独立命名
    if not bak.exists():
        shutil.copy2(path, bak)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)

    # 复扫验证(D10):唯一性 + 每 piece 的 work_key 单值
    re_rows = list(read_jsonl(str(path)))
    ids: dict = {}
    dup_after = 0
    piece_wk: dict = {}
    for r in re_rows:
        u = str(r.get("utt_id"))
        dup_after += 1 if u in ids else 0
        ids[u] = True
        piece_wk.setdefault(u.rsplit("_", 1)[0], set()).add(r.get("work_key"))
    multi_wk = sum(1 for s in piece_wk.values() if len(s) > 1)
    print(f"已重写 {n_rewrite} 行(重写 {n_rewrite} 行,备份 {bak.name})")
    print("===== 唯一化验证(复扫)=====")
    print(f"  {'✓' if dup_after == 0 else '✗'} 重写后重复 utt_id = {dup_after}")
    print(f"  {'✓' if multi_wk == 0 else '✗'} 一 piece 多 work_key = {multi_wk}")
    print("  结论: " + ("【干净】" if dup_after == 0 and multi_wk == 0 else "【异常,贴回给规划端】"))
    return 0 if dup_after == 0 and multi_wk == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
