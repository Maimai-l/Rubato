"""
InterMo 表示核心 —— 论文 §2 的参考实现。

设计原则:
1. 一切乐谱时间用 fractions.Fraction(单位:全音符),禁止浮点 —— 小节求和校验要求精确。
2. IR(ScoreIR)与文本(serialize/parse)严格双向:parse(serialize(ir)) == ir。
3. Canonical 序列化是唯一的:同一 IR 只有一种合法文本(幂等性可测)。
4. 所有边界决策集中在本文件头部的 DECISIONS 表,与规格文档一一对应。

DECISIONS(冻结的自由选择,变更须同步规格文档):
  D-01 单元间分隔 = 恰一个空格;单元内部致密无空格(tokenizer 预切分边界即空格)
  D-02 拼写音高字形 = [A-Ga-g](--|-|#|##)?[0-8],大写=onset 小写=offset(论文字形)
  D-03 MIDI 音高字形 = N{0..127} onset / n{0..127} offset(lite 与 AMT 共用)
  D-04 小节线字形 = |{m}/{n}k{sig},sig ∈ {0, #1..#7, -1..-7}(五度圈数)
  D-05 终止小节线:文档最后一个单元必须是小节线(携带末尾 offset),复用最后小节的签名
  D-06 落在小节线时刻的事件归属小节线单元;若其前有时间推进,先发一个空 moment 的补齐 interval
  D-07 时间戳 = <|t{0..3999}|>(10ms bin),TAST 中每个单元后恰一枚;单调钳制(bin>=前一枚)
  D-08 力度 = <|v{1..127}|> 紧跟对应 onset;踏板 = <|ped1|>/<|ped0|> 置于单元 moment 最前
  D-09 AMT 最短音长 = 1 bin(off_bin >= on_bin+1),量化下限计数上报
  D-10 首小节(弱起)与末小节允许短于声明拍号;内部小节必须精确等于
"""
from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass, field
from fractions import Fraction

# ---------------------------------------------------------------- 音高

STEP_SEMITONE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
STEP_ORDER = {s: i for i, s in enumerate("CDEFGAB")}
ALTER_GLYPH = {-2: "--", -1: "-", 0: "", 1: "#", 2: "##"}
GLYPH_ALTER = {v: k for k, v in ALTER_GLYPH.items()}


@dataclass(frozen=True)
class SPitch:
    """拼写音高。sort_key 先按 MIDI 再按 (step, alter) 保证 canonical 排序确定。"""
    step: str
    alter: int
    octave: int

    @property
    def midi(self) -> int:
        return (self.octave + 1) * 12 + STEP_SEMITONE[self.step] + self.alter

    def glyph(self, onset: bool) -> str:
        s = self.step if onset else self.step.lower()
        return f"{s}{ALTER_GLYPH[self.alter]}{self.octave}"

    @property
    def sort_key(self):
        return (self.midi, STEP_ORDER[self.step], self.alter)


# ---------------------------------------------------------------- IR

@dataclass(frozen=True)
class Note:
    staff: str          # 'PL' | 'PR'
    pitch: SPitch
    onset: Fraction     # 全音符单位
    dur: Fraction

    @property
    def offset(self) -> Fraction:
        return self.onset + self.dur


@dataclass(frozen=True)
class Measure:
    start: Fraction
    num: int            # 拍号分子
    den: int            # 拍号分母
    fifths: int         # 调号五度圈数,负=降号


@dataclass
class ScoreIR:
    notes: list[Note]
    measures: list[Measure]     # 按 start 排序,首个 start==0
    score_end: Fraction

    def normalized(self) -> "ScoreIR":
        notes = sorted(self.notes, key=lambda n: (n.onset, n.staff, n.pitch.sort_key, n.dur))
        measures = sorted(self.measures, key=lambda m: m.start)
        return ScoreIR(notes, measures, self.score_end)

    def __eq__(self, other):
        a, b = self.normalized(), other.normalized()
        return a.notes == b.notes and a.measures == b.measures and a.score_end == b.score_end


# ---------------------------------------------------------------- 单元流

@dataclass
class Unit:
    """一个语义单元:interval + moment。bar=None 表示 metric interval。"""
    frac: Fraction | None            # metric interval;bar 单元为 None
    bar: tuple[int, int, int] | None  # (num, den, fifths);metric 单元为 None
    time: Fraction                   # 该 moment 的乐谱时刻(全音符单位)
    offs: list = field(default_factory=list)   # [(staff, SPitch|int)]
    ons: list = field(default_factory=list)    # [(staff, SPitch|int, vel|None)]
    pedal: int | None = None         # AMT 专用: 1/0
    ts_bin: int | None = None        # TAST/AMT 专用


def _sig_glyph(fifths: int) -> str:
    if fifths == 0:
        return "0"
    return f"#{fifths}" if fifths > 0 else f"-{-fifths}"


def _pitch_key(p) -> tuple:
    return p.sort_key if isinstance(p, SPitch) else (p,)


# ---------------------------------------------------------------- IR → 单元流

class SerializeError(Exception):
    pass


def ir_to_units(ir: ScoreIR, lenient_measures: bool = False) -> list[Unit]:
    """
    lenient_measures=False(默认):严格 D-10,内部小节须等于声明拍号(合成数据、规范乐谱)。
    lenient_measures=True:允许华彩/延长号等非标准小节长度(真实浪漫派数据)。
      此时内部小节长度可 ≠ 声明拍号;小节自包含性仍保持(每小节 interval 和 = 其实际长度)。
      代价:小节和校验改为"和 = 实际长度"而非"和 = 声明拍号"——模型仍能学,但失去
      "拍号即长度"的强约束。用于避免丢弃 5/19+ 的浪漫派曲目(本地反馈问题4)。
    """
    ir = ir.normalized()
    if not ir.measures or ir.measures[0].start != 0:
        raise SerializeError("首小节必须始于 0")
    for n in ir.notes:
        if n.onset < 0 or n.offset > ir.score_end or n.dur <= 0:
            raise SerializeError(f"音符越界: {n}")
    # D-10:内部小节长度检查
    for i, m in enumerate(ir.measures):
        length = (ir.measures[i + 1].start if i + 1 < len(ir.measures) else ir.score_end) - m.start
        declared = Fraction(m.num, m.den)
        if length <= 0:
            raise SerializeError(f"小节 {i} 长度 {length} 非正")
        if not lenient_measures:
            if length > declared:
                raise SerializeError(f"小节 {i} 长度 {length} 超过声明 {declared}(华彩/延长?试 lenient_measures=True)")
            if 0 < i < len(ir.measures) - 1 and length != declared:
                raise SerializeError(f"内部小节 {i} 长度 {length} != 声明 {declared}(华彩/延长?试 lenient_measures=True)")
        # lenient 模式:任何正长度都接受,小节自包含由 interval 求和自然保证

    ons_at, offs_at = defaultdict(list), defaultdict(list)
    for n in ir.notes:
        ons_at[n.onset].append((n.staff, n.pitch))
        offs_at[n.offset].append((n.staff, n.pitch))
    bar_at = {m.start: m for m in ir.measures}

    points = sorted(set(ons_at) | set(offs_at) | set(bar_at) | {ir.score_end})
    units: list[Unit] = []
    prev = Fraction(0)
    for p in points:
        is_bar = (p in bar_at) or (p == ir.score_end)
        if is_bar:
            if p > prev:                                   # D-06:补齐 interval,空 moment
                units.append(Unit(frac=p - prev, bar=None, time=p))
            m = bar_at.get(p, ir.measures[-1])             # D-05:终止小节线复用签名
            u = Unit(frac=None, bar=(m.num, m.den, m.fifths), time=p)
        else:
            u = Unit(frac=p - prev, bar=None, time=p)
        u.offs = sorted(offs_at.get(p, []), key=lambda e: (e[0], _pitch_key(e[1])))
        u.ons = sorted([(s, pt, None) for s, pt in ons_at.get(p, [])],
                       key=lambda e: (e[0], _pitch_key(e[1])))
        units.append(u)
        prev = p
    return units


# ---------------------------------------------------------------- 单元流 → 文本

def units_to_text(units: list[Unit], midi_pitch: bool = False,
                  with_ts: bool = False, with_vel: bool = False) -> str:
    """midi_pitch=True 即 lite/AMT 的音高字形;with_ts/with_vel 控制 TAST/AMT 附加物。"""
    atoms = []
    staff_state = None
    for u in units:
        if u.bar is not None:
            s = f"|{u.bar[0]}/{u.bar[1]}k{_sig_glyph(u.bar[2])}"
        elif u.frac is not None:
            s = f"{u.frac.numerator}/{u.frac.denominator}"
        else:
            s = ""                                          # AMT:无乐谱结构,无头单元
        if u.pedal is not None:                            # D-08
            s += f"<|ped{u.pedal}|>"
        # moment:staff 低→高;每 staff 内 off 先 on 后(已在 ir_to_units 排序)
        for staff in ("PL", "PR", None):                   # None = AMT 无谱表
            offs = [e for e in u.offs if e[0] == staff]
            ons = [e for e in u.ons if e[0] == staff]
            if not offs and not ons:
                continue
            if staff is not None and staff_state != staff:
                s += f"{staff}:"
                staff_state = staff
            for _, p in offs:
                s += f"n{p}" if midi_pitch and not isinstance(p, SPitch) else (
                     f"n{p.midi}" if midi_pitch else p.glyph(False))
            for _, p, vel in ons:
                s += f"N{p}" if midi_pitch and not isinstance(p, SPitch) else (
                     f"N{p.midi}" if midi_pitch else p.glyph(True))
                if with_vel and vel is not None:
                    s += f"<|v{vel}|>"
        atoms.append(s)
        if with_ts:
            if u.ts_bin is None:
                raise SerializeError("with_ts 但单元缺 ts_bin")
            atoms.append(f"<|t{u.ts_bin}|>")
    return " ".join(atoms)


# ---------------------------------------------------------------- 文本 → 单元流/IR

class ParseError(Exception):
    pass


_BAR_RE = re.compile(r"^\|(\d+)/(\d+)k(0|#[1-7]|-[1-7])")
_FRAC_RE = re.compile(r"^(\d+)/(\d+)")
_TS_RE = re.compile(r"^<\|t(\d{1,4})\|>$")
_MOMENT_RE = re.compile(
    r"(PL:|PR:)"
    r"|<\|v(\d{1,3})\|>"
    r"|<\|ped([01])\|>"
    r"|([A-G])(--|##|-|#)?([0-8])"
    r"|([a-g])(--|##|-|#)?([0-8])"
    r"|N(\d{1,3})"
    r"|n(\d{1,3})"
)


def _parse_sig(s: str) -> int:
    if s == "0":
        return 0
    return int(s[1:]) if s[0] == "#" else -int(s[1:])


def text_to_units(text: str) -> list[Unit]:
    units: list[Unit] = []
    staff_state = None
    t = Fraction(0)
    for atom in text.split(" "):
        if not atom:
            raise ParseError("连续空格")
        m = _TS_RE.match(atom)
        if m:
            if not units:
                raise ParseError("时间戳前无单元")
            units[-1].ts_bin = int(m.group(1))
            continue
        mb = _BAR_RE.match(atom)
        if mb:
            u = Unit(frac=None, bar=(int(mb.group(1)), int(mb.group(2)), _parse_sig(mb.group(3))), time=t)
            rest = atom[mb.end():]
        else:
            mf = _FRAC_RE.match(atom)
            if mf:
                frac = Fraction(int(mf.group(1)), int(mf.group(2)))
                t += frac
                u = Unit(frac=frac, bar=None, time=t)
                rest = atom[mf.end():]
            else:                                        # AMT 无头单元:整体是 moment
                u = Unit(frac=None, bar=None, time=t)
                rest = atom
        pos = 0
        pending_on = None
        for mm in _MOMENT_RE.finditer(rest):
            if mm.start() != pos:
                raise ParseError(f"moment 解析间隙: {rest[pos:mm.start()]!r} in {atom!r}")
            pos = mm.end()
            g = mm.groups()
            if g[0]:
                staff_state = g[0][:-1]
            elif g[1]:                                   # velocity → 附着最近 onset
                if pending_on is None:
                    raise ParseError("velocity 无所属 onset")
                u.ons[pending_on] = (u.ons[pending_on][0], u.ons[pending_on][1], int(g[1]))
            elif g[2]:
                u.pedal = int(g[2])
            elif g[3]:                                   # 拼写 onset
                u.ons.append((staff_state, SPitch(g[3], GLYPH_ALTER[g[4] or ""], int(g[5])), None))
                pending_on = len(u.ons) - 1
            elif g[6]:                                   # 拼写 offset
                u.offs.append((staff_state, SPitch(g[6].upper(), GLYPH_ALTER[g[7] or ""], int(g[8]))))
            elif g[9]:                                   # MIDI onset
                u.ons.append((staff_state, int(g[9]), None))
                pending_on = len(u.ons) - 1
            elif g[10]:                                  # MIDI offset
                u.offs.append((staff_state, int(g[10])))
        if pos != len(rest):
            raise ParseError(f"moment 尾部无法解析: {rest[pos:]!r} in {atom!r}")
        units.append(u)
    return units


def units_to_ir(units: list[Unit]) -> ScoreIR:
    if not units or units[-1].bar is None:
        raise ParseError("缺少终止小节线(D-05)")
    notes, measures = [], []
    open_notes: dict[tuple, Fraction] = {}
    for u in units:
        for staff, p in u.offs:
            key = (staff, p)
            if key not in open_notes:
                raise ParseError(f"孤儿 offset: {key} @ {u.time}")
            onset = open_notes.pop(key)
            notes.append(Note(staff, p, onset, u.time - onset))
        for staff, p, _vel in u.ons:
            key = (staff, p)
            if key in open_notes:
                raise ParseError(f"重复 onset(Dyck 深度>1): {key} @ {u.time}")
            open_notes[key] = u.time
        if u.bar is not None and u is not units[-1]:
            measures.append(Measure(u.time, *u.bar))
    if open_notes:
        raise ParseError(f"未闭合音符: {sorted(open_notes)}")
    return ScoreIR(notes, measures, units[-1].time)


# ---------------------------------------------------------------- 校验器

def validate_units(units: list[Unit], allow_pickup: bool = True,
                   lenient_measures: bool = False) -> list[str]:
    """
    lenient_measures=True:华彩/延长小节模式。小节 interval 和只需自洽(>0),
    不要求 == 声明拍号。Dyck 与时间戳检查不变。与 ir_to_units(lenient_measures=True) 配对。
    """
    """返回违规清单(空=通过)。三类:Dyck、小节求和、时间戳单调。"""
    v = []
    open_keys = set()
    for u in units:
        for staff, p in u.offs:
            k = (staff, p)
            if k not in open_keys:
                v.append(f"DYCK_ORPHAN_OFFSET:{k}@{u.time}")
            else:
                open_keys.discard(k)
        for staff, p, _ in u.ons:
            k = (staff, p)
            if k in open_keys:
                v.append(f"DYCK_DOUBLE_ONSET:{k}@{u.time}")
            open_keys.add(k)
    if open_keys:
        v.append(f"DYCK_UNCLOSED:{sorted(open_keys, key=str)[:3]}")
    if not units or units[-1].bar is None:
        v.append("TERMINAL_BAR_MISSING")
        return v
    # 小节求和
    bar_idx = [i for i, u in enumerate(units) if u.bar is not None]
    for bi in range(len(bar_idx) - 1):
        a, b = bar_idx[bi], bar_idx[bi + 1]
        num, den, _ = units[a].bar
        s = sum((units[j].frac for j in range(a + 1, b + 1) if units[j].frac is not None), Fraction(0))
        declared = Fraction(num, den)
        first, last = bi == 0, bi == len(bar_idx) - 2
        if lenient_measures:
            # 华彩/延长:只要求和为正(小节非空且自洽),不比对声明拍号
            if s <= 0:
                v.append(f"MEASURE_SUM_NONPOS:{bi} got {s}")
        elif s > declared or ((not allow_pickup or not (first or last)) and s != declared):
            if not ((first or last) and s < declared and allow_pickup):
                v.append(f"MEASURE_SUM:{bi} got {s} want {declared}")
    # 时间戳单调
    prev_ts = -1
    for u in units:
        if u.ts_bin is not None:
            if u.ts_bin < prev_ts:
                v.append(f"TS_NONMONOTONE:{u.ts_bin}<{prev_ts}")
            prev_ts = u.ts_bin
    return v


# ---------------------------------------------------------------- 时间映射与 dialect 投影

class TimeMap:
    """乐谱时刻(全音符 Fraction)→ 演奏秒。分段线性,由 (score_pos, sec) 锚点构建。"""
    def __init__(self, anchors: list[tuple[Fraction, float]]):
        pts = sorted(set(anchors))
        if len(pts) < 2:
            raise ValueError("TimeMap 需要 ≥2 锚点")
        self.xs = [p[0] for p in pts]
        self.ys = [p[1] for p in pts]

    def __call__(self, x: Fraction) -> float:
        import bisect
        i = bisect.bisect_right(self.xs, x) - 1
        i = max(0, min(i, len(self.xs) - 2))
        x0, x1, y0, y1 = self.xs[i], self.xs[i + 1], self.ys[i], self.ys[i + 1]
        if x1 == x0:
            return y0
        return y0 + (y1 - y0) * float((x - x0) / (x1 - x0))


def stamp_units(units: list[Unit], tmap: TimeMap, ts_ms: int = 10, n_bins: int = 4000) -> int:
    """就地写 ts_bin(D-07 单调钳制)。返回被钳制的单元数。"""
    clamped, prev = 0, 0
    for u in units:
        b = int(round(tmap(u.time) / (ts_ms / 1000.0)))
        b = max(0, min(b, n_bins - 1))
        if b < prev:
            b, clamped = prev, clamped + 1
        u.ts_bin = b
        prev = b
    return clamped


def project(ir: ScoreIR, dialect: str, tmap: TimeMap | None = None) -> str:
    units = ir_to_units(ir)
    if dialect == "A2S":
        return units_to_text(units)
    if dialect == "A2S_lite":
        return units_to_text(units, midi_pitch=True)
    if dialect == "TAST":
        if tmap is None:
            raise SerializeError("TAST 需要 TimeMap")
        stamp_units(units, tmap)
        return units_to_text(units, with_ts=True)
    raise ValueError(f"未知 dialect {dialect}(AMT 走 perf_to_amt)")


def perf_to_amt(notes: list[dict], pedal: list[tuple[float, bool]] = (),
                ts_ms: int = 10, n_bins: int = 4000) -> tuple[str, dict]:
    """
    演奏事件 → AMT 文本。notes: [{pitch, on, off, vel}](秒);pedal: [(sec, down)]。
    返回 (text, stats)。D-09 最短音长 1 bin。
    """
    to_bin = lambda s: max(0, min(int(round(s / (ts_ms / 1000.0))), n_bins - 1))
    floor_count = 0
    per_bin: dict[int, Unit] = {}

    def unit(b: int) -> Unit:
        if b not in per_bin:
            per_bin[b] = Unit(frac=None, bar=None, time=Fraction(b))
        return per_bin[b]

    for nt in notes:
        ob = to_bin(nt["on"])
        fb = to_bin(nt["off"])
        if fb <= ob:
            fb, floor_count = ob + 1, floor_count + 1
        unit(ob).ons.append((None, int(nt["pitch"]), int(nt["vel"])))
        unit(fb).offs.append((None, int(nt["pitch"])))
    for sec, down in pedal:
        unit(to_bin(sec)).pedal = 1 if down else 0

    units = []
    for b in sorted(per_bin):
        u = per_bin[b]
        u.offs.sort(key=lambda e: e[1])
        u.ons.sort(key=lambda e: e[1])
        u.ts_bin = b
        units.append(u)
    text = " ".join(
        units_to_text([u], midi_pitch=True, with_ts=True, with_vel=True) for u in units
    )
    return text, {"min_dur_floored": floor_count, "n_units": len(units)}
