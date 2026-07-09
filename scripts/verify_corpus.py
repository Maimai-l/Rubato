"""
校验合并后的 tokenizer 语料是否合规(CORPUS_REGEN.md §2 的不变量)。
用法:  python scripts/verify_corpus.py  D:\path\to\tok_corpus.txt
只读、不改文件。每条不变量给 PASS/FAIL + 数字,末尾总判。

校验项:
  1. 文件非空、UTF-8、无空行、无行内连续空格(SentencePiece 按空格切,脏空格会污染切分)。
  2. 【只 A2S + A2S_lite】:不得含时间戳/力度/踏板/beat 字形(那些是 TAST/AMT/DBD,
     混进来 = 装配放错了方言,偏离论文 §3.2)。判据:含 '<|' 或独立 '*' 的行数 == 0。
  3. 可解析:抽样 N 行跑 InterMo validate,违规率应≈0(字形/切分坏了这里会炸)。
  4. 两种音高都在:A2S(拼写,如 PR:C4)与 A2S_lite(MIDI,如 N60/n60)都要有。
  5. 规模/去重报告:总行数、distinct 行数、distinct 比。distinct 比过低(<0.5)提示可能重复过多;
     ==1.0 未必是问题(overlap 切段天然少重),只报数不当 FAIL。
"""
from __future__ import annotations
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.intermo.core import text_to_units, validate_units

SAMPLE = 3000          # 抽样解析行数(大文件不必全解析)


def main(path: str) -> int:
    p = Path(path)
    if not p.exists():
        print(f"FAIL  文件不存在: {path}")
        return 1

    total = blank = dirty_ws = ts_like = 0
    has_spell = has_midi = False
    distinct = set()
    sample_lines = []

    with p.open(encoding="utf-8") as f:
        for i, raw in enumerate(f):
            line = raw.rstrip("\n")
            total += 1
            if not line.strip():
                blank += 1
                continue
            if "  " in line or line != line.strip():
                dirty_ws += 1
            # 2. 非 A2S 字形:时间戳/力度/踏板 '<|...|>' 或独立 beat '*'
            if "<|" in line or re.search(r"(?:^|\s)\*", line):
                ts_like += 1
            # 4. 音高种类
            if re.search(r"[A-Ga-g](?:--|##|-|#)?\d", line):
                has_spell = True
            if re.search(r"[Nn]\d", line):
                has_midi = True
            distinct.add(line)
            if len(sample_lines) < SAMPLE:
                sample_lines.append(line)

    # 3. 抽样解析
    parse_fail = 0
    fail_examples = []
    for line in sample_lines:
        try:
            v = validate_units(text_to_units(line))
            if v:
                parse_fail += 1
                if len(fail_examples) < 3:
                    fail_examples.append((line[:60], v[:2]))
        except Exception as e:
            parse_fail += 1
            if len(fail_examples) < 3:
                fail_examples.append((line[:60], [type(e).__name__]))

    nonblank = total - blank
    distinct_ratio = round(len(distinct) / max(nonblank, 1), 3)
    parse_rate = round(1 - parse_fail / max(len(sample_lines), 1), 4)

    def verdict(ok): return "PASS" if ok else "FAIL"

    c1 = total > 0 and blank == 0 and dirty_ws == 0
    c2 = ts_like == 0
    c3 = parse_rate >= 0.99
    c4 = has_spell and has_midi

    print(f"文件: {path}")
    print(f"  [1] 非空/无空行/无脏空格   {verdict(c1)}  行数={total} 空行={blank} 脏空格行={dirty_ws}")
    print(f"  [2] 只 A2S+A2S_lite         {verdict(c2)}  含<|或*的行={ts_like}"
          + ("" if c2 else "  ← TAST/AMT/DBD 混进来了,装配放错方言"))
    print(f"  [3] 可解析(抽样{len(sample_lines)})  {verdict(c3)}  解析通过率={parse_rate}")
    if fail_examples:
        for ex, v in fail_examples:
            print(f"        例: {ex!r} -> {v}")
    print(f"  [4] 拼写+MIDI 两种音高都在  {verdict(c4)}  spell={has_spell} midi={has_midi}")
    print(f"  [5] 规模/去重(仅报告)     distinct={len(distinct)} / {nonblank} = {distinct_ratio}")

    ok = c1 and c2 and c3 and c4
    print("\n" + ("全部通过 ✓  语料可用于 train_unigram。" if ok else
                  "有 FAIL ✗  先按上面修,别拿去训 tokenizer。"))
    # 提醒(无法从内容判定,只能过程保证):
    print("提醒:确认此语料是【拉了 adapter<、D-06、字形三处修正之后】重生成的;"
          "旧地基上的 A2S 文本与现在不同,grep 看不出来,只能靠流程保证。")
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python scripts/verify_corpus.py <tok_corpus.txt>")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
