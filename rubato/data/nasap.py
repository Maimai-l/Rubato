"""
S7 nASAP(R-S7.3/7.4)。重叠切窗 + 保守 split。

修复问题#15:conservative_split 此前已实现却从未被调用。s7_full_nasap.py / S8 汇聚
必须调它产出 val=512 段、train/val/test 按 work_key 隔离的划分,并落盘 nasap_split.json。
"""
from __future__ import annotations
import hashlib
from fractions import Fraction

from rubato.intermo.core import TimeMap
from rubato.data.segment import segment_score

SEED = 20260706


# ---------------------------------------------------------------- 重叠切窗(R-S7.3)

def segment_score_overlap(ir, tmap: TimeMap | None = None,
                          min_measures: int = 4, max_measures: int | None = 32,
                          max_sec: float = 40.0, sec_per_whole: float | None = None):
    """
    R-S7.3【论文明确 nASAP 用重叠窗】:小节对齐 4–32 小节 ≤40s,重叠步长=段长一半。
    返回 [(sub_ir, (a,b)), ...],起点比非重叠版更密。

    实现:先跑非重叠贪心切段拿到各段的小节跨度,再以每段跨度的一半为步长起新段。
    """
    # 【坑】tmap 与 sec_per_whole 都缺时,_seg_seconds 返回 0 → max_sec 约束【静默失效】,
    # 段只受 max_measures 限制(慢曲照样超训练窗)。调用方必须给一个时间源;两者都没给时
    # 此处兜底恒速 2.0(可见于签名,不再静默)。
    if tmap is None and sec_per_whole is None:
        sec_per_whole = 2.0
    base = segment_score(ir, min_measures, max_measures, max_sec, tmap=tmap,
                         sec_per_whole=sec_per_whole)
    if not base:
        return []
    n = len(ir.measures)
    starts = set()
    for sub, (a, b) in base:
        starts.add(a)
        step = max(1, (b - a) // 2)                 # 半段步长
        starts.add(min(a + step, n - 1))
    segs = []
    seen = set()
    for a in sorted(starts):
        # 从 a 起按同约束贪心扩一段
        one = segment_score(_slice_from(ir, a), min_measures, max_measures,
                            max_sec, tmap=_shift_tmap_from(ir, tmap, a),
                            sec_per_whole=sec_per_whole)
        if not one:
            continue
        sub, (la, lb) = one[0]
        key = (a, a + (lb - la))
        if key in seen:
            continue
        seen.add(key)
        segs.append((sub, (a, a + (lb - la))))
    return segs


def _slice_from(ir, a: int):
    """取从小节 a 到曲末的子 IR(归零),供重叠切窗从任意小节起段。"""
    from rubato.data.segment import _slice_ir
    sub, _ = _slice_ir(ir, a, len(ir.measures))
    return sub


def _shift_tmap_from(ir, tmap, a: int):
    if tmap is None:
        return None
    bounds = [m.start for m in ir.measures] + [ir.score_end]
    offset = bounds[a]
    anchors = []
    seen = set()
    for p in [m.start - offset for m in ir.measures[a:]] + [ir.score_end - offset]:
        if p >= 0 and p not in seen:
            seen.add(p)
            anchors.append((p, float(tmap(p + offset))))
    return TimeMap(anchors) if len(anchors) >= 2 else None


# ---------------------------------------------------------------- 保守 split(R-S7.4)

def _u(*parts) -> float:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:15], 16) / float(16 ** 15)


def conservative_split(pieces: list[dict], val_segment_target: int = 512,
                       seed: int = SEED) -> dict:
    """
    R-S7.4【不变量】:按 work_key 划分;val=达到 val_segment_target 段所属曲目集合,
    test=其余保留曲的一部分,train=剩下。同 work_key 的 piece 必同 split(零交集)。

    pieces: [{piece_id, work_key, n_segments}]。
    返回 {assignment:{piece_id:split}, manifest:{val_works, test_works, train_works, seed}}。
    可复现:曲目顺序由 hash(seed, work_key) 定。
    """
    # 按 work_key 聚合
    by_wk: dict = {}
    for p in pieces:
        by_wk.setdefault(p["work_key"], {"pieces": [], "segs": 0})
        by_wk[p["work_key"]]["pieces"].append(p["piece_id"])
        by_wk[p["work_key"]]["segs"] += p.get("n_segments", 0)

    # 确定性打乱 work_key 顺序
    works = sorted(by_wk, key=lambda wk: _u(seed, wk))

    assignment = {}
    val_works, test_works, train_works = [], [], []
    val_segs = 0
    # 先填 val 到达标
    i = 0
    while i < len(works) and val_segs < val_segment_target:
        wk = works[i]
        val_works.append(wk)
        val_segs += by_wk[wk]["segs"]
        for pid in by_wk[wk]["pieces"]:
            assignment[pid] = "val"
        i += 1
    # 再填等量规模的 test(取与 val 相近的段数,或至少 1 个曲目)
    test_segs = 0
    while i < len(works) and (test_segs < val_segs or not test_works):
        wk = works[i]
        test_works.append(wk)
        test_segs += by_wk[wk]["segs"]
        for pid in by_wk[wk]["pieces"]:
            assignment[pid] = "test"
        i += 1
    # 其余全 train
    while i < len(works):
        wk = works[i]
        train_works.append(wk)
        for pid in by_wk[wk]["pieces"]:
            assignment[pid] = "train"
        i += 1

    manifest = {"seed": seed, "val_target": val_segment_target,
                "val_segments": val_segs, "test_segments": test_segs,
                "val_works": sorted(val_works), "test_works": sorted(test_works),
                "train_works": sorted(train_works),
                "n_val_works": len(val_works), "n_test_works": len(test_works),
                "n_train_works": len(train_works)}
    return {"assignment": assignment, "manifest": manifest}
