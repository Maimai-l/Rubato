"""
nASAP utt_id 唯一化 v2 —— 修 P5d split 泄漏的根因;v1 两个错已修(执行端实测抓出):

v1 错①【乐章互撞,dup_after=584】:一个 MAESTRO 录音是完整演出,对应 ASAP 里同一奏鸣曲
的多个乐章条目(共用音频,靠 win 各取一段),演奏者 stem 也相同 → hash(音频) 区分不了。
v2:tag = h8(perf_audio | work_key) —— ASAP 标题带乐章号("piano sonatas 17 3"),
(录音, 乐章, 段号) 唯一。

v1 错②【work_key 反查污染 1,075 行】:metadata 反查表按音频建键,同音频多乐章"最后行赢",
把第 1 乐章的 work_key 覆盖成第 3 乐章的。行内 work_key 本就是 s7 按各自 metadata 行写的
【权威值】,根本不需要反查。v2:彻底删掉反查;并且【以 .bak2(v1 动手前的原件)为源】
重新生成 —— 同时自动撤销 v1 已写入的污染,重跑几遍都是同一结果(纯函数)。

用法(执行端;SOP P5c2 就是它):
  python scripts/s7_fix_uttids.py            # 干跑:撞名统计
  python scripts/s7_fix_uttids.py --apply    # 以原件重新生成(首跑先留 .bak2)+ 验证表
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
_TAG_RE = re.compile(r"^nasap_(.+)_[0-9a-f]{8}_(\d+)$")


def h8(s: str) -> str:
    return hashlib.sha256(str(s).encode()).hexdigest()[:8]


def canon(row: dict) -> str | None:
    """规范 utt_id = nasap_{演奏者stem}_{h8(音频|work_key)}_{段号}。缺 perf_audio 返回 None。
    stem 提取顺序:旧原始形(…_xml_score_N)→ 带旧 tag 形(v1 产物)→ 兜底剥尾段号。"""
    old = str(row.get("utt_id") or "")
    perf = str(row.get("perf_audio") or "")
    if not old.startswith("nasap_") or not perf:
        return None
    tag = h8(f"{perf}|{row.get('work_key') or ''}")
    m = _OLD_RE.match(old)
    if m:
        return f"nasap_{m.group(1)}_{tag}_{m.group(2)}"
    m = _TAG_RE.match(old)
    if m:
        return f"nasap_{m.group(1)}_{tag}_{m.group(2)}"
    body = old[len("nasap_"):]
    stem, si = body.rsplit("_", 1) if "_" in body else (body, "000")
    return f"nasap_{stem}_{tag}_{si}"


def _dups(rows) -> int:
    seen, d = set(), 0
    for r in rows:
        u = str(r.get("utt_id"))
        d += 1 if u in seen else 0
        seen.add(u)
    return d


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="nASAP utt_id 唯一化 v2(以原件重新生成,默认干跑)")
    ap.add_argument("--labels", default=str(ROOT / "work" / "nasap_labels.jsonl"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.labels)
    if not path.exists():
        print(f"标签文件不存在({path})→ 无事可做。")
        return 0
    bak = path.with_suffix(".bak2")
    src = bak if bak.exists() else path             # 有原件用原件:v1 的污染一并撤销
    rows = list(read_jsonl(str(src)))
    n_rewrite = n_nocanon = 0
    out_rows = []
    seen_canon: set = set()
    dup_samples: list = []
    for r in rows:
        c = canon(r)
        if c is None:
            n_nocanon += 1
        else:
            if c in seen_canon:
                # 规范化后仍同 id = 同(录音, 乐章, 段号)的重复对齐变体(ASAP 偶见同演奏
                # 多版对齐)。近重复训练样本,保首份丢后份 —— 大声记账,绝不静默。
                dup_samples.append(c)
                continue
            seen_canon.add(c)
            if c != r.get("utt_id"):
                n_rewrite += 1
                r = dict(r, utt_id=c)
        out_rows.append(r)
    print(f"源 = {src.name}(以原件重新生成,v1 的 work_key 污染一并撤销)")
    print(f"共 {len(rows)} 行:重写前重复 utt_id = {_dups(rows)},需重写 {n_rewrite} 行,"
          f"重复对齐变体丢弃 {len(dup_samples)} 行,无法规范 {n_nocanon} 行")
    if dup_samples:
        print("  变体样本(前 5): " + "; ".join(dup_samples[:5]))
        if len(dup_samples) > 0.05 * max(len(rows), 1):
            print("  ⚠ 变体占比 >5%,超出'偶见'范围 —— 贴回给规划端核对,别急着装配")
    if not args.apply:
        print("\n干跑结束(未改文件)。加 --apply 实施(首跑留 .bak2)。")
        return 0

    if not bak.exists():
        shutil.copy2(path, bak)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fo:
        for r in out_rows:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)

    # 复扫验证(D10):唯一性 + 每 piece 的 work_key 单值
    re_rows = list(read_jsonl(str(path)))
    dup_after = _dups(re_rows)
    piece_wk: dict = {}
    for r in re_rows:
        piece_wk.setdefault(str(r.get("utt_id")).rsplit("_", 1)[0], set()).add(r.get("work_key"))
    multi_wk = sum(1 for s in piece_wk.values() if len(s) > 1)
    print(f"已重写 {n_rewrite} 行(备份 {bak.name})")
    print("===== 唯一化验证(复扫)=====")
    print(f"  {'✓' if dup_after == 0 else '✗'} 重写后重复 utt_id = {dup_after}")
    print(f"  {'✓' if multi_wk == 0 else '✗'} 一 piece 多 work_key = {multi_wk}")
    print("  结论: " + ("【干净】" if dup_after == 0 and multi_wk == 0 else "【异常,贴回给规划端】"))
    return 0 if dup_after == 0 and multi_wk == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
