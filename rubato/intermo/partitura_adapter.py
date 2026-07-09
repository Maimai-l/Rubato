"""
partitura 适配器:MusicXML ↔ ScoreIR。

职责边界:本文件只做"partitura 对象 → IR"与"IR → partitura 对象"的忠实搬运 +
R-S2.4 剔除策略;一切 InterMo 语义在 core.py。

已知不确定点(在真实 PDMX 上由执行者复核):
  A-1 partitura 对不同 MusicXML 方言的 staff 编号(此处假定 1=上=PR, 2=下=PL)
  A-2 变 divisions 乐谱(divs/quarter 中途变化)—— v0 直接剔除
"""
from __future__ import annotations
from fractions import Fraction
from .core import SPitch, Note, Measure, ScoreIR, SerializeError


class AdapterError(Exception):
    pass


def part_to_ir(part, stats: dict | None = None) -> ScoreIR:
    """partitura Part → ScoreIR。tied notes 合并;同 (staff,pitch) 重叠合一。"""
    import numpy as np
    stats = stats if stats is not None else {}

    # 每四分音符的 division 数;变 divisions 剔除(A-2)
    # np.atleast_2d:部分 partitura 版本单条记录时返回一维数组,直接 qmap[0][1] 会索引失败
    qmap = np.atleast_2d(part.quarter_durations())
    if qmap.size == 0:
        raise AdapterError("无 divisions 信息")
    dpq_values = {int(q) for _, q in qmap}
    if len(dpq_values) != 1:
        raise AdapterError(f"变 divisions: {dpq_values}")
    dpq = dpq_values.pop()
    whole = dpq * 4  # 全音符的 div 数

    def to_frac(div: int) -> Fraction:
        return Fraction(int(div), whole)

    # 音符:用 tied 合并视图
    notes = []
    merged = 0
    seen: dict[tuple, list[list]] = {}
    for n in part.notes_tied:
        staff_no = getattr(n, "staff", None) or 1
        staff = "PR" if staff_no == 1 else "PL"
        alter = n.alter if n.alter is not None else 0
        p = SPitch(n.step, int(alter), int(n.octave))
        on = to_frac(n.start.t)
        off = to_frac(n.end_tied.t)
        if off <= on:
            stats["zero_dur_dropped"] = stats.get("zero_dur_dropped", 0) + 1
            continue
        seen.setdefault((staff, p), []).append([on, off])
    # 同 (staff,pitch) 【严格重叠】才合一(声部交叠 unison);【相接】(前 offset==后 onset)
    # 保留为两个音符 —— 那是"释放再重按同音"(re-articulation),InterMo 的一等公民
    # (banner 例:a-3c4f4A-3C4F4 释放并重按同一和弦)。用 <= 会把相连同音八分并成一个
    # 四分,把重奏织体(重复和弦伴奏型,钢琴里极常见)静默抹掉——故用严格 <。
    for (staff, p), ivals in seen.items():
        ivals.sort()
        cur = ivals[0]
        for iv in ivals[1:]:
            if iv[0] < cur[1]:                       # 严格重叠 → 合一;相接(==)保留为两个音
                cur[1] = max(cur[1], iv[1])
                merged += 1
            else:
                notes.append(Note(staff, p, cur[0], cur[1] - cur[0]))
                cur = iv
        notes.append(Note(staff, p, cur[0], cur[1] - cur[0]))
    stats["unison_merged"] = merged

    # 小节:起点 + 当时生效的拍号/调号
    from partitura.score import TimeSignature, KeySignature
    tss = sorted(part.iter_all(TimeSignature), key=lambda x: x.start.t)
    kss = sorted(part.iter_all(KeySignature), key=lambda x: x.start.t)
    if not tss:
        raise AdapterError("无拍号")

    def active(objs, t, default=None):
        cur = default
        for o in objs:
            if o.start.t <= t:
                cur = o
            else:
                break
        return cur

    measures = []
    pms = sorted(part.iter_all(getattr(__import__("partitura.score", fromlist=["Measure"]), "Measure")),
                 key=lambda m: m.start.t)
    if not pms:
        raise AdapterError("无小节")
    for m in pms:
        ts = active(tss, m.start.t)
        ks = active(kss, m.start.t)
        if ts is None:
            raise AdapterError("小节前无拍号")
        fifths = int(ks.fifths) if ks is not None else 0
        measures.append(Measure(to_frac(m.start.t), int(ts.beats), int(ts.beat_type), fifths))

    score_end = to_frac(pms[-1].end.t)
    # 平移:首小节起点归零(部分文件首小节 t != 0)
    shift = measures[0].start
    if shift != 0:
        notes = [Note(n.staff, n.pitch, n.onset - shift, n.dur) for n in notes]
        measures = [Measure(m.start - shift, m.num, m.den, m.fifths) for m in measures]
        score_end -= shift
    return ScoreIR(notes, measures, score_end)


def ir_to_part(ir: ScoreIR, dpq: int = 480):
    """ScoreIR → partitura Part(用于渲染回 MusicXML / 评测)。"""
    import partitura.score as spt
    part = spt.Part("P0", "Piano", quarter_duration=dpq)
    whole = dpq * 4
    to_div = lambda f: int(f * whole)

    prev_sig = None
    prev_key = None
    for i, m in enumerate(ir.measures):
        end = ir.measures[i + 1].start if i + 1 < len(ir.measures) else ir.score_end
        part.add(spt.Measure(number=i + 1), start=to_div(m.start), end=to_div(end))
        if (m.num, m.den) != prev_sig:
            part.add(spt.TimeSignature(m.num, m.den), start=to_div(m.start))
            prev_sig = (m.num, m.den)
        if m.fifths != prev_key:
            part.add(spt.KeySignature(m.fifths, mode="major"), start=to_div(m.start))
            prev_key = m.fifths
    for idx, n in enumerate(ir.notes):
        part.add(
            spt.Note(id=f"n{idx}", step=n.pitch.step, octave=n.pitch.octave,
                     alter=(n.pitch.alter or None), staff=(1 if n.staff == "PR" else 2)),
            start=to_div(n.onset), end=to_div(n.offset),
        )
    spt.add_measures  # noqa —— 小节已手动添加
    return part
