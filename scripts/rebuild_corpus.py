"""
语料重建 —— tokenizer 语料从此是【标签文件的确定性函数】,不再是各管线追加出来的历史状态。

为什么:旧模式下 a2s_corpus.txt 由文本管线/VN 管线/nASAP 各自追加,顺序耦合、无法审计、
清理污染曲(如鼓谱)后语料里的坏行没法定位剔除。现在:每次要训 tokenizer 前跑本脚本,
从【当前的】标签文件流式重建语料(A2S + A2S_lite,每行一条)—— 标签清干净了,语料自然干净。

用法: python scripts/rebuild_corpus.py    # 覆盖写 work/a2s_corpus.txt,打印各源行数
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout

ROOT = Path(r"D:\vscode_projects\ee_download")
DIALECTS = ("A2S", "A2S_lite")      # 论文 §3.2:tokenizer 只喂 A2S + A2S_lite


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="从标签文件重建 tokenizer 语料(确定性,覆盖写)")
    ap.add_argument("--labels", nargs="*", default=[
        str(ROOT / "work" / "pdmx_a2s_labels.jsonl"),
        str(ROOT / "work" / "pdmx_perf_labels.jsonl"),
        str(ROOT / "work" / "nasap_labels.jsonl"),
    ])
    ap.add_argument("--out", default=str(ROOT / "work" / "a2s_corpus.txt"))
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    per_src: dict[str, int] = {}
    total = 0
    with open(out, "w", encoding="utf-8", newline="\n") as fo:
        for lp in args.labels:
            n = 0
            p = Path(lp)
            if not p.exists():
                print(f"  [跳过] 标签文件不存在: {lp}")
                per_src[p.name] = -1
                continue
            with open(p, "r", encoding="utf-8") as fi:
                for line in fi:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    for d in DIALECTS:
                        t = row.get(d)
                        if isinstance(t, str) and t.strip():
                            fo.write(t.strip() + "\n")
                            n += 1
            per_src[p.name] = n
            total += n
    print("语料重建完成(覆盖写,与标签严格一致):")
    for k, v in per_src.items():
        print(f"  {k}: {'缺失' if v < 0 else str(v) + ' 行'}")
    print(f"  合计 corpus_lines={total} → {out}")
    return 0 if total > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
