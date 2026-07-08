"""
S7 nASAP TimeMap(R-S7.2)。乐谱位置 ↔ 演奏秒的锚点构建。

修复问题#6(xml_id 匹配率 0.37%):nASAP 对齐 TSV 的 xml_id 与 partitura note id
命名不一致(TSV 里形如 'n1-1'/'P1-3-8' 等,partitura 的 note.id 形如 'n123'/带前缀),
精确字符串匹配几乎全丢。改为【多策略匹配 + 精确 xml_id 优先】:
  1. 直接 id 相等;
  2. 去前缀/去后缀的宽松相等;
  3. 都不中才算未匹配,计数入 stats(不静默丢)。
xml_id 精确对齐是核心:同音高在一曲中出现几十次,靠音高匹配必然错位(回归测试 [3])。
"""
from __future__ import annotations
from fractions import Fraction

from rubato.intermo.core import TimeMap


# ---------------------------------------------------------------- TSV 解析(R-S7.2)

def parse_alignment_tsv(rows: list[dict]) -> list[dict]:
    """
    nASAP 对齐 TSV 行 → 对齐记录。跳过未对齐行(xml_id 为 '*' 或空)。
    输出每条 {xml_id, perf_onset_sec, pitch}。
    列名容错:onset/xml_onset/perf_onset 皆可为演奏 onset;pitch 可缺。
    """
    out = []
    for r in rows:
        xid = (r.get("xml_id") or "").strip()
        if not xid or xid == "*":                    # nASAP 用 '*' 标未对齐
            continue
        onset = _first_float(r, ("onset", "perf_onset", "perf_onset_sec", "xml_onset"))
        if onset is None:
            continue
        pitch = _first_int(r, ("pitch", "midi_pitch", "midi"))
        out.append({"xml_id": xid, "perf_onset_sec": onset, "pitch": pitch})
    return out


def _first_float(d: dict, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _first_int(d: dict, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            try:
                return int(float(v))
            except (TypeError, ValueError):
                pass
    return None


# ---------------------------------------------------------------- xml_id 匹配(问题#6 核心)

def _normalize_xmlid(xid: str) -> str:
    """去掉常见前缀装饰,便于宽松匹配(如 'P1-1-8' 与 '1-8')。"""
    x = xid.strip()
    # 去掉声部/小节前缀里的字母前缀(保留数字与分隔)
    return x.lstrip("Pp").lstrip("-_")


def _build_match_index(xmlid_pos: dict) -> dict:
    """为宽松匹配建索引:归一化 id → 原 id(冲突时保留首个)。"""
    idx = {}
    for k in xmlid_pos:
        nk = _normalize_xmlid(k)
        idx.setdefault(nk, k)
        # 也索引末段(如 'a-b-c' → 'c'),覆盖 TSV 只给局部 id 的情况
        tail = k.split("-")[-1]
        idx.setdefault(f"__tail__{tail}", k)
    return idx


def match_xmlid(align_id: str, xmlid_pos: dict, match_idx: dict) -> str | None:
    """多策略把对齐记录的 xml_id 映射到乐谱位置表的键。返回命中的键或 None。"""
    if align_id in xmlid_pos:                         # 1. 精确
        return align_id
    nk = _normalize_xmlid(align_id)
    if nk in match_idx:                               # 2. 归一化后相等
        return match_idx[nk]
    tail = align_id.split("-")[-1]
    if f"__tail__{tail}" in match_idx:                # 3. 末段相等
        return match_idx[f"__tail__{tail}"]
    return None


# ---------------------------------------------------------------- TimeMap 构建(R-S7.2)

def build_timemap(alignment: list[dict], xmlid_pos: dict,
                  min_anchors: int = 2) -> tuple[TimeMap | None, dict]:
    """
    对齐记录 + {xml_id: 乐谱位置 Fraction} → (TimeMap, stats)。
    - 精确/宽松 xml_id 匹配得到 (score_pos, perf_sec) 锚点;
    - 按 score_pos 排序;演奏时间回跳(对齐错误)的锚点剔除并计数(不产负斜率图);
    - 锚点不足 min_anchors → 返回 (None, stats),不产坏图。
    stats: {total_aligned, matched_xmlid, dropped_no_scorepos, dropped_nonmonotone,
            anchors, slope_ok}。
    """
    stats = {"total_aligned": len(alignment), "matched_xmlid": 0,
             "dropped_no_scorepos": 0, "dropped_nonmonotone": 0,
             "anchors": 0, "slope_ok": False}
    match_idx = _build_match_index(xmlid_pos)

    raw = []
    for a in alignment:
        key = match_xmlid(a["xml_id"], xmlid_pos, match_idx)
        if key is None:
            stats["dropped_no_scorepos"] += 1
            continue
        stats["matched_xmlid"] += 1
        raw.append((xmlid_pos[key], a["perf_onset_sec"]))

    # 同一乐谱位置多音(和弦)取最早演奏 onset;按乐谱位置排序
    by_pos: dict = {}
    for pos, sec in raw:
        by_pos[pos] = min(sec, by_pos[pos]) if pos in by_pos else sec
    anchors = sorted(by_pos.items(), key=lambda kv: kv[0])

    # 演奏时间单调化:回跳点剔除(保留单调不降的最长前缀式过滤)
    mono = []
    last_sec = float("-inf")
    for pos, sec in anchors:
        if sec < last_sec:
            stats["dropped_nonmonotone"] += 1
            continue
        mono.append((pos, sec))
        last_sec = sec

    stats["anchors"] = len(mono)
    if len(mono) < min_anchors:
        return None, stats

    tmap = TimeMap([(p, s) for p, s in mono])
    # 斜率正性(总体演奏时间随乐谱位置增长)
    stats["slope_ok"] = mono[-1][1] > mono[0][1]
    return tmap, stats


# ---------------------------------------------------------------- partitura xml_id 位置表

def build_xmlid_map(part) -> dict:
    """
    partitura Part → {note.id: 乐谱位置 Fraction(全音符单位)}。
    对齐 TSV 的 xml_id 指向乐谱音符,需要它们的乐谱起始位置作锚点横坐标。
    """
    qmap = part.quarter_durations()
    import numpy as np
    if np.ndim(qmap) == 2:
        dpq = int(qmap[0][1])
    else:
        dpq = int(qmap[0][1]) if len(qmap) else 480
    whole = dpq * 4
    out = {}
    for n in part.notes_tied if hasattr(part, "notes_tied") else part.notes:
        nid = getattr(n, "id", None)
        if nid is None:
            continue
        out[str(nid)] = Fraction(int(n.start.t), whole)
    return out
