"""
S12 窗合并参考实现(R-S12.1.3)。供执行者对照/替换其字符串匹配版。

SPEC:每窗保留完整落在前20s的小节;窗间【在小节线合并】;跨小节延音靠 Dyck open 状态跨窗延续。

审查发现的关键点(为什么字符串 suffix/prefix 匹配不可靠):
  A2S 中音符的 offset 标记出现在【下一个小节线】处(如 C4 起于小节0,其 offset "c4" 挂在小节1的
  小节线上)。所以"在小节线合并"不是切字符串——重叠小节在窗1末尾(offset 形态)与窗2开头
  (onset 形态)的文本【本就不同】,token 流匹配会失败。正确做法必须在【解析后的语义层】操作:
  按小节重建音符,识别重叠小节,在小节边界重新拼接并让 Dyck 状态自然跨缝。

本实现走 IR 层:各窗 A2S → 局部 ScoreIR → 按小节索引对齐重叠 → 拼接成全局 ScoreIR → 投影回 A2S。
这样重叠去重和 Dyck 闭合都由 ScoreIR 的结构保证,不依赖脆弱的字符串匹配。
"""
from __future__ import annotations

from fractions import Fraction
from rubato.intermo.core import (
    Note, Measure, ScoreIR, text_to_units, units_to_ir, validate_units, project,
)


def a2s_to_ir(a2s_text: str):
    """A2S 文本 → ScoreIR(经解析,失败抛异常)。"""
    return units_to_ir(text_to_units(a2s_text))


def merge_windows_ref(window_a2s: list[str], overlap_measures_hint: int = None) -> str:
    """
    R-S12.1.3 参考合并。window_a2s: 各窗【已剥时间戳】的 A2S 文本。
    返回合并后完整 A2S。

    做法(语义层):
      1. 每窗解析成局部 ScoreIR(小节列表 + 音符)。
      2. 相邻窗按小节内容识别重叠(比较小节内音符集合,非字符串)。
      3. 窗2 去掉与窗1 重叠的整小节,音符时间平移后接到全局。
      4. 全局 ScoreIR 投影回 A2S —— Dyck 闭合、小节求和由结构天然保证。
    """
    if not window_a2s:
        return "|4/4k0"

    irs = []
    for w in window_a2s:
        try:
            irs.append(a2s_to_ir(w))
        except Exception:
            continue          # 不可解析的窗跳过(执行者侧应已按 R-S12.2 处理)
    if not irs:
        return "|4/4k0"

    # 从第一窗起,逐窗按小节拼接
    acc = irs[0]
    for nxt in irs[1:]:
        acc = _concat_ir(acc, nxt, overlap_measures_hint)
    return project(acc, "A2S")


def _measure_note_signature(ir: ScoreIR, mi: int):
    """某小节内音符的 (staff, pitch, 相对起点, 时长) 集合,用于结构比对重叠。"""
    bounds = [m.start for m in ir.measures] + [ir.score_end]
    lo, hi = bounds[mi], bounds[mi + 1]
    sig = set()
    for n in ir.notes:
        if lo <= n.onset < hi:
            sig.add((n.staff, str(n.pitch), n.onset - lo, n.dur))
    return frozenset(sig)


def _sig_jaccard(sa: frozenset, sb: frozenset) -> float:
    if not sa and not sb:
        return 1.0
    union = len(sa | sb)
    return len(sa & sb) / union if union else 1.0


def _concat_ir(a: ScoreIR, b: ScoreIR, overlap_hint: int = None) -> ScoreIR:
    """
    把 b 接到 a 之后,自动识别并去除重叠小节。
    重叠判定三级:
      1. 精确:a 结尾 k 小节的音符签名序列 == b 开头 k 小节;
      2. 模糊:解码噪声下逐小节 Jaccard 均值 ≥0.6 也算重叠(两窗对同一小节的
         转写可有少量差异,精确匹配会漏);
      3. 都不中 → overlap=0【不丢内容】。旧实现强制 overlap=1,窗间内容真不重叠时
         会静默扔掉一个真实小节 —— 宁可重复,不可丢失(重复可被后续人工/评测发现,
         丢失不可恢复)。
    """
    na, nb = len(a.measures), len(b.measures)
    max_k = min(na, nb, 8) if overlap_hint is None else min(overlap_hint, na, nb)
    overlap = 0
    for k in range(max_k, 0, -1):                     # 1. 精确
        a_sigs = [_measure_note_signature(a, na - k + i) for i in range(k)]
        b_sigs = [_measure_note_signature(b, i) for i in range(k)]
        if a_sigs == b_sigs:
            overlap = k
            break
    if overlap == 0 and overlap_hint is None:          # 2. 模糊
        best_k, best_score = 0, 0.0
        for k in range(max_k, 0, -1):
            sims = [_sig_jaccard(_measure_note_signature(a, na - k + i),
                                 _measure_note_signature(b, i)) for i in range(k)]
            score = sum(sims) / k
            if score >= 0.6 and score > best_score:
                best_k, best_score = k, score
        overlap = best_k                               # 3. 仍为 0 → 不去重,保内容

    # 拼接:a 全部 + b 从第 overlap 个小节起,时间平移到 a 末尾
    shift = a.score_end                       # b 的起点接到 a 末尾
    b_bounds = [m.start for m in b.measures] + [b.score_end]
    b_skip_start = b_bounds[overlap] if overlap < len(b_bounds) else b.score_end

    new_measures = list(a.measures)
    for i in range(overlap, nb):
        m = b.measures[i]
        new_measures.append(Measure(m.start - b_skip_start + shift, m.num, m.den, m.fifths))

    a_notes = list(a.notes)
    b_notes = [Note(n.staff, n.pitch, n.onset - b_skip_start + shift, n.dur)
               for n in b.notes if n.onset >= b_skip_start]

    # 接缝延音融合(Dyck open 状态跨窗的 IR 层实现):
    # 窗文本各自自包含,跨缝长音在 a 侧以"offset 恰在缝上"结束、b 侧以"onset 恰在缝上"
    # 重新开始 —— 同 (staff,pitch) 配对时合并为一个音,恢复延音。两遍处理,不边遍历边删。
    seam_ons = {(n.staff, str(n.pitch)): n for n in b_notes if n.onset == shift}
    fused_a, consumed = [], set()
    for n in a_notes:
        key = (n.staff, str(n.pitch))
        if n.offset == shift and n.onset < shift and key in seam_ons and key not in consumed:
            tail = seam_ons[key]
            fused_a.append(Note(n.staff, n.pitch, n.onset, tail.offset - n.onset))
            consumed.add(key)
        else:
            fused_a.append(n)
    fused_b = [n for n in b_notes
               if not (n.onset == shift and (n.staff, str(n.pitch)) in consumed)]
    new_notes = fused_a + fused_b

    new_end = shift + (b.score_end - b_skip_start)
    return ScoreIR(new_notes, new_measures, new_end)


def merge_and_validate(window_a2s: list[str]) -> tuple[str, list[str]]:
    """合并 + 校验。返回 (merged_text, violations)。"""
    merged = merge_windows_ref(window_a2s)
    return merged, validate_units(text_to_units(merged))
