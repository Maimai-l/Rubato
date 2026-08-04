"""
形式语言预训练语料生成器(D91;论文 §2 暗示 + Hu et al. 2025 配方)。

造什么:随机但【完全合法】的 InterMo 乐谱文本,专门操练两条形式性质 ——
  1. k-Shuffle-Dyck 音符开闭配对(和弦 + 跨时刻长音 = 真嵌套/交错);
  2. 小节算术(interval 逐小节精确加总 = 声明拍号;拍号/调号中途可变)。
这两条正是自由解码的头号/次号拒因(DYCK / MEASURE,D88)。

怎么保证合法:不手搓语法字符串 —— 随机采样 ScoreIR(音符/小节的结构化中间表示),
经【生产同一套】ir_to_units → units_to_text 序列化,再用【生产同一套】
text_to_units → validate_units 逐条回验;任何一条违规立即报错终止(fail-closed),
说明采样器有 bug,绝不产出脏语料。

产出:JSONL,每行 {"utt_id", "dialect"(A2S|TAST), "text", "n_atoms"}。
纯文本、零音频、零渲染、零 GPU;供 scripts/pretrain_decoder.py 消费。

用法(执行端,任意 python 环境,CPU 分钟级):
  python scripts/gen_formal_corpus.py --n 200000 --out D:\\vscode_projects\\ee_download\\work\\formal_corpus.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout  # noqa: E402
from rubato.intermo.core import (  # noqa: E402
    Measure, Note, ScoreIR, SPitch, TimeMap, project, text_to_units,
    validate_units)

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("RUBATO_WORK")
            or (ROOT.parent / "work" if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download\work"))

SIGS = [(4, 4), (3, 4), (2, 4), (6, 8), (3, 8), (2, 2)]
DURS = [(Fraction(1, 16), 3), (Fraction(1, 8), 5), (Fraction(1, 4), 4),
        (Fraction(3, 8), 1), (Fraction(1, 2), 2), (Fraction(3, 4), 1)]
STEPS = "CDEFGAB"
STAFF_OCT = {"PL": (2, 4), "PR": (4, 6)}


def _pick_dur(rng: random.Random) -> Fraction:
    total = sum(w for _, w in DURS)
    x = rng.uniform(0, total)
    for d, w in DURS:
        x -= w
        if x <= 0:
            return d
    return DURS[-1][0]


def _pick_pitch(rng: random.Random, staff: str, banned: set) -> SPitch | None:
    lo, hi = STAFF_OCT[staff]
    for _ in range(20):
        alter = rng.choice([-1, 0, 0, 0, 1] + ([-2, 2] if rng.random() < 0.05 else []))
        p = SPitch(rng.choice(STEPS), alter, rng.randint(lo, hi))
        if (staff, p) not in banned:
            return p
    return None


def sample_score(rng: random.Random) -> ScoreIR:
    """随机合法乐谱:双谱表独立事件流 + 和弦 + 跨时刻长音 + 变拍号/调号。"""
    n_meas = rng.randint(2, 10)
    num, den = rng.choice(SIGS)
    fifths = rng.randint(-6, 6)
    measures, start = [], Fraction(0)
    for _ in range(n_meas):
        if rng.random() < 0.15:
            num, den = rng.choice(SIGS)
        if rng.random() < 0.10:
            fifths = rng.randint(-6, 6)
        measures.append(Measure(start, num, den, fifths))
        start += Fraction(num, den)
    end = start

    notes: list[Note] = []
    for staff in ("PL", "PR"):
        open_notes: list[tuple[tuple, Fraction]] = []   # ((staff,pitch), offset)
        t = Fraction(0)
        while t < end:
            open_notes = [(k, off) for k, off in open_notes if off > t]
            d = min(_pick_dur(rng), end - t)
            if rng.random() < 0.20:                     # 休止
                t += d
                continue
            banned = {k for k, _ in open_notes}
            chord = []
            for _ in range(rng.randint(1, 3)):
                p = _pick_pitch(rng, staff, banned)
                if p is None:
                    break
                banned.add((staff, p))
                chord.append(p)
            for j, p in enumerate(chord):
                nd = d
                if j == 0 and rng.random() < 0.30:      # 长音:跨越后续时刻 = Dyck 嵌套
                    nd = min(d * rng.randint(2, 4), end - t)
                notes.append(Note(staff, p, t, nd))
                open_notes.append(((staff, p), t + nd))
            t += d
    # 空小节兜底:给无 onset 小节塞一个短音(密度,而非合法性必需)。
    # 必须排除跨小节【延音中】的音高 —— 否则同名音开着再开 = DYCK_DOUBLE_ONSET
    # (首版实测踩中,fail-closed 验证逮住)。
    for m in measures:
        m_len = Fraction(m.num, m.den)
        if not any(m.start <= n.onset < m.start + m_len for n in notes):
            open_at = {(n.staff, n.pitch) for n in notes
                       if n.onset <= m.start < n.offset}
            p = _pick_pitch(rng, "PR", open_at)
            if p is not None:
                notes.append(Note("PR", p, m.start, min(Fraction(1, 4), m_len)))
    return ScoreIR(notes, measures, end)


def gen_one(rng: random.Random, want_tast: bool) -> tuple[str, str]:
    """返回 (dialect, text),生成后立即用生产验证器回验,违规即抛错。"""
    ir = sample_score(rng)
    if want_tast:
        spw = rng.uniform(1.5, 3.0)                     # 常速:每全音符秒数
        tmap = TimeMap([(Fraction(0), 0.0), (ir.score_end, float(ir.score_end) * spw)])
        dialect, text = "TAST", project(ir, "TAST", tmap=tmap)
    else:
        dialect, text = "A2S", project(ir, "A2S")
    viol = validate_units(text_to_units(text))
    if viol:
        raise RuntimeError(f"采样器产出违规文本(bug,fail-closed): {viol[:4]}\n{text[:200]}")
    return dialect, text


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="形式语言(Dyck+小节算术)预训练语料生成")
    ap.add_argument("--n", type=int, default=200000, help="生成序列条数")
    ap.add_argument("--out", default=str(WORK / "formal_corpus.jsonl"))
    ap.add_argument("--seed", type=int, default=20260804)
    ap.add_argument("--tast-frac", type=float, default=0.5,
                    help="TAST(带时间戳)占比,其余为 A2S;两种都练,格式与正训一致")
    ap.add_argument("--max-atoms", type=int, default=700,
                    help="单条上限(空格分隔原子数);超限重采,保证进 1023 位置表")
    args = ap.parse_args(argv)
    if args.n <= 0 or not (0.0 <= args.tast_frac <= 1.0):
        raise ValueError(f"非法参数: n={args.n} tast_frac={args.tast_frac}")

    rng = random.Random(args.seed)
    t0 = time.time()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_tast = n_resample = 0
    atoms_sum = 0
    with open(out, "w", encoding="utf-8") as fh:
        for i in range(args.n):
            want_tast = rng.random() < args.tast_frac
            while True:
                dialect, text = gen_one(rng, want_tast)
                n_atoms = len(text.split())
                if n_atoms <= args.max_atoms:
                    break
                n_resample += 1
            n_tast += int(dialect == "TAST")
            atoms_sum += n_atoms
            fh.write(json.dumps(
                {"utt_id": f"formal_{args.seed}_{i:07d}", "dialect": dialect,
                 "text": text, "n_atoms": n_atoms}, ensure_ascii=False) + "\n")
            if (i + 1) % 20000 == 0:
                print(f"  {i + 1}/{args.n} ({time.time() - t0:.0f}s)", flush=True)
    print(f"完成: {args.n} 条 → {out}")
    print(f"  TAST {n_tast} / A2S {args.n - n_tast} | 平均原子 {atoms_sum / args.n:.1f}"
          f" | 超长重采 {n_resample} | 用时 {time.time() - t0:.0f}s")
    print("  合法性:每条已经 text_to_units+validate_units 回验(违规即崩,零容忍)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
