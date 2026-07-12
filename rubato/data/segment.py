"""
S8 分段与标签生成(R-S8.1~8.6)。四路数据 → 统一 (音频段, 多 dialect 标签)。

关键不变量:
  - 乐谱类切段小节对齐(R-S8.1):贪心聚合连续小节,4≤小节数≤32 且渲染时长≤40s,
    段起点必在小节线,末尾不足并入或弃。禁止任意时间点切乐谱类样本。
  - dialects 可用性(R-S8.3):flat/human→{A2S,A2S_lite,TAST};vn→依 CSV;
    maestro→{AMT};nasap→{A2S,A2S_lite,TAST}。合成域不做 AMT。
  - validate() 门(R-S8.4):任何违规该样本整条废弃。

修复问题#12:AMT 窗内时间戳用【窗内相对时间】(t - t0),不是整曲绝对时间。
  整曲绝对时间在 4000-bin/10ms(=40s)编码下会把 40s 后的音符全部钳到末 bin,
  标签损坏。窗切分后每窗都从 0 起,落进 0-40s 有效区间。
"""
from __future__ import annotations
from fractions import Fraction

from rubato.intermo.core import (
    Note, Measure, ScoreIR, TimeMap, project, perf_to_amt,
    text_to_units, validate_units,
)


# ---------------------------------------------------------------- 乐谱类切段(R-S8.1)

def _seg_seconds(sub_ir: ScoreIR, offset: Fraction, tmap: TimeMap | None,
                 sec_per_whole: float | None) -> float:
    """段渲染时长(秒)。有 tmap 用其算(结束-开始);否则用恒速 sec_per_whole。"""
    length = sub_ir.score_end                       # sub_ir 已归零,长度=score_end
    if tmap is not None:
        return float(tmap(offset + length) - tmap(offset))
    if sec_per_whole is not None:
        return float(length) * sec_per_whole
    return 0.0


def _slice_ir(ir: ScoreIR, a: int, b: int) -> tuple[ScoreIR, Fraction]:
    """
    取小节 [a,b) 组成子 IR,归零到 start=0。跨段边界的音符截断到段内(R-S2.4)。
    返回 (sub_ir, 原始起点 offset)。
    """
    bounds = [m.start for m in ir.measures] + [ir.score_end]
    lo, hi = bounds[a], bounds[b]
    measures = [Measure(ir.measures[i].start - lo, ir.measures[i].num,
                        ir.measures[i].den, ir.measures[i].fifths) for i in range(a, b)]
    notes = []
    for n in ir.notes:
        on, off = n.onset, n.offset
        if off <= lo or on >= hi:
            continue                                # 完全在段外
        c_on = max(on, lo)
        c_off = min(off, hi)                        # 跨边界截断(offset 补在边界)
        if c_off > c_on:
            notes.append(Note(n.staff, n.pitch, c_on - lo, c_off - c_on))
    return ScoreIR(notes, measures, hi - lo), lo


def segment_score(ir: ScoreIR, min_measures: int = 4, max_measures: int | None = 32,
                  max_sec: float = 40.0, sec_per_whole: float | None = None,
                  tmap: TimeMap | None = None) -> list[tuple[ScoreIR, tuple[int, int]]]:
    """
    R-S8.1:小节对齐贪心聚合。返回 [(sub_ir, (a,b)), ...],a/b 为原始小节索引。
    约束:min_measures≤(b-a)≤max_measures 且段渲染时长≤max_sec;段起点在小节线。
    末不足 min_measures 的尾巴向前并入(仍≤max_measures 且≤max_sec)否则弃。
    max_measures=None【用户决定 2026-07-11】:小节数不设上限,时间(max_sec)是唯一上限 ——
    段尽量长,在 ≤max_sec 内装下尽可能多的完整小节(PDMX 训练数据用;nASAP 仍按论文 4–32 重叠窗)。
    """
    n = len(ir.measures)
    mm = max_measures if max_measures else n        # None = 无小节数上限,只受 max_sec 约束
    segs = []
    a = 0
    while a < n:
        b = a + min_measures
        if b > n:                                   # 末尾不足 min:尝试并入上一段
            if segs and (n - segs[-1][1][0]) <= mm:
                pa, _ = segs[-1][1]
                sub, off = _slice_ir(ir, pa, n)
                if _seg_seconds(sub, off, tmap, sec_per_whole) <= max_sec:
                    segs[-1] = (sub, (pa, n))
                    break
            break                                   # 并不进去 → 丢弃尾巴
        # 贪心向后扩,直到超时或小节上限或到末尾 —— 段【尽量长】
        best_b = b
        for bb in range(b, min(a + mm, n) + 1):
            sub, off = _slice_ir(ir, a, bb)
            if _seg_seconds(sub, off, tmap, sec_per_whole) <= max_sec:
                best_b = bb
            else:
                break
        sub, off = _slice_ir(ir, a, best_b)
        segs.append((sub, (a, best_b)))
        a = best_b
    return segs


# ---------------------------------------------------------------- AMT 智能切窗(R-S6.3)

def segment_amt(notes: list[dict], pedal: list[tuple[float, bool]],
                target_lo: float = 12.0, target_hi: float = 25.0,
                search: float = 1.0, window_max: float = 40.0):
    """
    R-S6.3:AMT 目标窗长 U[lo,hi];切点在候选 ±search 内找"无发声音符且踏板抬起"时刻。
    找不到则硬切并丢跨界音符。返回 [(win_notes, win_pedal, (t0,t1)), ...]。

    修复问题#12:win_notes / win_pedal 的时间【平移为窗内相对时间】(减 t0),
    使 perf_to_amt 的 10ms bin 落在 0-window_max 有效区间,不被钳到末 bin。
    """
    if not notes:
        return []
    end = max(n["off"] for n in notes)
    wins = []
    t0 = 0.0
    target = (target_lo + target_hi) / 2.0
    while t0 < end - 1e-6:
        cand = t0 + target
        cut = _find_cut(notes, pedal, cand, search, t0 + target_lo, t0 + target_hi)
        if cut is None or cut <= t0:
            cut = min(t0 + window_max, end)          # 硬切
        cut = min(cut, end)
        win_notes = [n for n in notes if n["on"] >= t0 - 1e-9 and n["on"] < cut - 1e-9]
        # 相对时间平移(问题#12):窗内所有事件减 t0
        rel_notes = [{"pitch": n["pitch"], "on": n["on"] - t0,
                      "off": min(n["off"], cut) - t0, "vel": n["vel"]}
                     for n in win_notes]
        rel_pedal = [(s - t0, d) for s, d in pedal if t0 - 1e-9 <= s < cut - 1e-9]
        if rel_notes:
            wins.append((rel_notes, rel_pedal, (t0, cut)))
        if cut <= t0:
            break
        t0 = cut
    return wins


def _find_cut(notes, pedal, cand, search, lo, hi):
    """在 [cand-search, cand+search] 内找无发声且踏板抬起的时刻;限制在 [lo,hi]。"""
    lo_b = max(lo, cand - search)
    hi_b = min(hi, cand + search)
    # 候选点:所有音符 offset(此刻可能静音),落在窗内的
    cands = sorted({n["off"] for n in notes if lo_b <= n["off"] <= hi_b})
    for c in cands:
        # 半开区间 [on, off):恰在 off 时刻该音已结束,不算发声
        sounding = any(n["on"] <= c < n["off"] for n in notes)
        pedal_down = _pedal_at(pedal, c)
        if not sounding and not pedal_down:
            return c
    return None


def _pedal_at(pedal, t: float) -> bool:
    """t 时刻踏板是否踩下(取 t 之前最后一次踏板事件)。"""
    state = False
    for s, down in pedal:
        if s <= t:
            state = down
        else:
            break
    return state


# ---------------------------------------------------------------- 标签生成(R-S8.3/8.4)

_DIALECTS_BY_KIND = {
    "flat":    ["A2S", "A2S_lite", "TAST"],
    "human":   ["A2S", "A2S_lite", "TAST"],
    "nasap":   ["A2S", "A2S_lite", "TAST"],
    "vn":      ["A2S", "A2S_lite"],                 # TAST 依 CSV(vn_tast_ok)
    "maestro": ["AMT"],
}


def make_labels(ir: ScoreIR, kind: str, tmap: TimeMap | None = None,
                vn_tast_ok: bool = False, score_offset: Fraction = Fraction(0)):
    """
    R-S8.3/8.4:对一个乐谱段生成其 kind 允许的所有 dialect 文本;违规即整条废弃。
    返回 (labels_dict, fails)。maestro 走 make_amt_label,不经此路。

    score_offset:段在原曲的起点(Fraction)。sub_ir 已归零,但 tmap 建在原曲坐标系,
    故 TAST 打戳时用 score_offset 平移的局部 tmap(段>0 时不平移会全部映射到曲首,错)。
    """
    dialects = list(_DIALECTS_BY_KIND.get(kind, []))
    if kind == "vn" and vn_tast_ok:
        dialects.append("TAST")

    labels, fails = {}, []
    local_tmap = _shift_tmap(ir, tmap, score_offset) if tmap is not None else None
    for d in dialects:
        try:
            if d == "TAST":
                if local_tmap is None:
                    continue                        # 无 tmap 不出 TAST
                text = project(ir, "TAST", local_tmap)
            else:
                text = project(ir, d)
            viol = validate_units(text_to_units(text))
            if viol:
                fails.append({"dialect": d, "reason": f"validate:{viol[:2]}"})
                continue
            labels[d] = text
        except Exception as e:
            fails.append({"dialect": d, "reason": f"{type(e).__name__}:{str(e)[:60]}"})
    return labels, fails


def _shift_tmap(sub_ir: ScoreIR, tmap: TimeMap, offset: Fraction) -> TimeMap:
    """
    构造段内局部 tmap:local(x) = tmap(x + offset) − tmap(offset)。用段内小节起点做锚点。

    秒轴必须一并归零(减 tmap(offset)):段音频是从 tmap(offset) 秒切/读出来的,
    时间戳要的是【段内相对秒】。旧版只平移乐谱轴、秒轴保持绝对演奏时间 ——
    S5 多段曲与 nASAP 所有段的 TAST 戳随段起点整体偏移,超 40s 的段被
    stamp_units 全钳到末 bin(4000-bin 编码上限),且与切片/窗读音频错位。
    offset==0 且 tmap(0)==0 时返回原 tmap(常见于每段独立渲染的路径,无需重建)。
    """
    base = float(tmap(offset))
    if offset == 0 and abs(base) < 1e-9:
        return tmap
    pts = sorted({m.start for m in sub_ir.measures} | {Fraction(0), sub_ir.score_end})
    anchors = [(p, float(tmap(p + offset)) - base) for p in pts]
    # 去重同秒锚点保持 TimeMap 可构建
    seen, uniq = set(), []
    for p, s in anchors:
        if p not in seen:
            seen.add(p)
            uniq.append((p, s))
    if len(uniq) < 2:
        uniq = [(Fraction(0), 0.0),
                (sub_ir.score_end, float(tmap(offset + sub_ir.score_end)) - base)]
    return TimeMap(uniq)


def validate_amt(text: str) -> list[str]:
    """
    AMT 专用校验:只查 Dyck 平衡 + 时间戳单调。
    AMT dialect 无乐谱结构(无小节线/interval),故不适用 validate_units 的
    终止小节线与小节求和检查——那两项对 AMT 恒失败(TERMINAL_BAR_MISSING)。
    """
    units = text_to_units(text)
    full = validate_units(units)
    # 保留 Dyck / 时间戳类违规,丢弃小节结构类(AMT 无小节)
    return [v for v in full if v.startswith(("DYCK_", "TS_"))]


def make_amt_label(win_notes: list[dict], win_pedal: list[tuple[float, bool]]):
    """
    R-S8.3:AMT 段标签。win_notes/win_pedal 已是窗内相对时间(segment_amt 平移过)。
    返回 (labels_dict, fails)。违规废弃。
    """
    try:
        text, stats = perf_to_amt(win_notes, win_pedal)
        viol = validate_amt(text)
        if viol:
            return {}, [{"dialect": "AMT", "reason": f"validate:{viol[:2]}"}]
        return {"AMT": text}, []
    except Exception as e:
        return {}, [{"dialect": "AMT", "reason": f"{type(e).__name__}:{str(e)[:60]}"}]


# ---------------------------------------------------------------- 泄漏终检(A-S8.3)

def leakage_check(utts: list[dict]) -> dict:
    """
    A-S8.3:train 与 val/test 在 {work_key, dup_cluster, maestro 曲目} 三维交集为空。
    utts: [{utt_id, split, work_key, maestro_id, dup_cluster}]。
    返回 {ok, violations:{work_key:[...], dup_cluster:[...], maestro_id:[...]}}。
    """
    dims = {"work_key": {}, "dup_cluster": {}, "maestro_id": {}}
    for u in utts:
        for dim in dims:
            v = u.get(dim)
            if v is None:
                continue
            dims[dim].setdefault(v, set()).add(u["split"])
    violations = {}
    for dim, table in dims.items():
        bad = [k for k, splits in table.items()
               if "train" in splits and (splits & {"val", "test"})]
        if bad:
            violations[dim] = bad
    return {"ok": not violations, "violations": violations}
