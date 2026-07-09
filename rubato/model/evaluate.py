"""
S13 评测。规格见 SPEC.md R-S13.1~13.4。

指标(R-S13.1):
  - AMT note F1(mir_eval,onset 50ms 容差)@ MAESTRO test
  - A2S/TAST 的 OMR-NED @ nASAP test(LEGATO 官方脚本,bootstrap 95% CI)
  - TAST note F1 @ nASAP test

归因分类(R-S13.3):每个失败 {解析失败 | 分段/合并伪影 | 音乐内容错误} 三选一——
  前两类是工程 bug,只有第三类是模型能力问题。这个区分决定"继续训练能不能缩差距"。

分层:
  纯逻辑(沙盒可测):note F1 计算、bootstrap CI、归因分类判定、报告对照。
  外部依赖(本地):LEGATO OMR-NED 脚本(U10 已验证)、Verovio/MuseScore 渲染人检。
"""
from __future__ import annotations
import re

from rubato.intermo.core import text_to_units, validate_units


# ---------------------------------------------------------------- note F1(R-S13.1)

def notes_to_intervals(notes: list[dict]):
    """
    AMT 事件 → mir_eval 格式 (intervals, pitches_hz)。notes: [{pitch(MIDI), on, off}]。
    关键:mir_eval.transcription 期望 pitch 单位是 Hz(内部转 cents 比对),
    传 MIDI 整数会被当 Hz 导致半音差被误判为匹配。必须 MIDI→Hz。
    """
    import numpy as np
    if not notes:
        return np.zeros((0, 2)), np.array([])
    intervals = np.array([[n["on"], n["off"]] for n in notes])
    midi = np.array([n["pitch"] for n in notes], dtype=float)
    pitches_hz = 440.0 * 2 ** ((midi - 69) / 12)     # MIDI → Hz
    return intervals, pitches_hz


def note_f1(ref_notes: list[dict], est_notes: list[dict],
            onset_tolerance: float = 0.05, offset_ratio: float = 0.2,
            offset_min_tolerance: float = 0.05) -> dict:
    """
    R-S13.1:note F1,onset 50ms 容差。用 mir_eval.transcription。
    返回 {precision, recall, f1, n_ref, n_est, precision_off, recall_off, f1_off}。

    论文 Table 3 的 note F1 是两套并列的:onset-only(只对 onset+pitch)与
    onset+offset(还要求 offset 在 max(offset_min_tolerance, offset_ratio×时长) 内)。
    只报 onset-only 会系统性地【偏乐观】——offset 完全错也算命中。这里两套都算,
    f1 仍为 onset-only(向后兼容既有调用),f1_off 为带 offset 的严格版,供论文对照。
    """
    import mir_eval
    ref_int, ref_p = notes_to_intervals(ref_notes)
    est_int, est_p = notes_to_intervals(est_notes)
    if len(ref_int) == 0 and len(est_int) == 0:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "n_ref": 0, "n_est": 0,
                "precision_off": 1.0, "recall_off": 1.0, "f1_off": 1.0}
    if len(ref_int) == 0 or len(est_int) == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0,
                "n_ref": len(ref_int), "n_est": len(est_int),
                "precision_off": 0.0, "recall_off": 0.0, "f1_off": 0.0}
    # onset-only 匹配(不看 offset,pitch 需一致)
    p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_int, ref_p, est_int, est_p,
        onset_tolerance=onset_tolerance, offset_ratio=None)
    # onset+offset 匹配(offset 也要在容差内)
    po, ro, fo, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_int, ref_p, est_int, est_p,
        onset_tolerance=onset_tolerance, offset_ratio=offset_ratio,
        offset_min_tolerance=offset_min_tolerance)
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "n_ref": len(ref_int), "n_est": len(est_int),
            "precision_off": round(po, 4), "recall_off": round(ro, 4),
            "f1_off": round(fo, 4)}


# ---------------------------------------------------------------- bootstrap CI(R-S13.1)

def bootstrap_ci(scores: list[float], n_resample: int = 10000,
                 ci: float = 0.95, seed: int = 20260706) -> dict:
    """
    R-S13.1:bootstrap 95% CI,10k 重采样。返回 {mean, lo, hi}。
    """
    import numpy as np
    if not scores:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    rng = np.random.default_rng(seed)
    arr = np.array(scores)
    means = np.array([rng.choice(arr, size=len(arr), replace=True).mean()
                      for _ in range(n_resample)])
    alpha = (1 - ci) / 2
    return {"mean": round(float(arr.mean()), 4),
            "lo": round(float(np.quantile(means, alpha)), 4),
            "hi": round(float(np.quantile(means, 1 - alpha)), 4),
            "n": len(scores)}


# ---------------------------------------------------------------- 归因分类(R-S13.3)

def classify_failure(est_a2s: str, ref_a2s: str | None = None,
                     omr_ned: float | None = None,
                     ned_threshold: float = 0.3) -> str:
    """
    R-S13.3:失败三分类。
      - parse_fail:est 无法解析(validate 违规)→ 工程 bug(解析/生成)
      - merge_artifact:可解析但有分段/合并伪影特征(小节数与 ref 差异大、重复小节)→ 工程 bug
      - content_error:可解析、结构正常,但音乐内容错(OMR-NED 高)→ 模型能力问题
    只有 content_error 是"继续训练能缩"的;前两类是 bug,训练缩不了。
    """
    viol = validate_a2s_safe(est_a2s)
    if viol:
        return "parse_fail"
    # 合并伪影检测:小节数与 ref 显著不符,或有连续重复小节
    if ref_a2s is not None:
        est_bars = est_a2s.count("|")
        ref_bars = ref_a2s.count("|")
        if ref_bars > 0 and abs(est_bars - ref_bars) / ref_bars > 0.2:
            return "merge_artifact"
    if _has_duplicate_measures(est_a2s):
        return "merge_artifact"
    # 结构正常但内容错(OMR-NED 高)
    if omr_ned is not None and omr_ned > ned_threshold:
        return "content_error"
    return "content_error"      # 默认:结构对但有差异 → 归模型


def validate_a2s_safe(a2s: str) -> list[str]:
    try:
        return validate_units(text_to_units(a2s))
    except Exception as e:
        return [f"parse:{type(e).__name__}"]


def _has_duplicate_measures(a2s: str) -> bool:
    """检测连续重复小节(合并伪影特征)。含音符内容的小节:有 PR:/PL: 或音高字符。"""
    def has_notes(m):
        return ("PR:" in m or "PL:" in m or
                re.search(r"[A-Ga-g][#\-b]?\d", m) is not None)
    measures = [m.strip() for m in a2s.split("|") if m.strip() and has_notes(m)]
    for i in range(len(measures) - 1):
        if measures[i] == measures[i + 1] and len(measures[i]) > 8:
            return True
    return False


# ---------------------------------------------------------------- OMR-NED(R-S13.1,本地)

def omr_ned_via_legato(est_xml: str, ref_xml: str, legato_fn) -> float:
    """
    R-S13.1:OMR-NED 用 LEGATO 官方脚本(U10 已验证 compute_OMR-NED.py)。
    legato_fn: 执行者注入的 LEGATO 调用(输入两个 MusicXML 路径,返回 NED 浮点)。
    本函数只是契约封装,实际计算在 LEGATO。
    """
    return legato_fn(est_xml, ref_xml)


# ---------------------------------------------------------------- AMT 文本 → 音符事件

def amt_text_to_notes(amt_text: str, ts_ms: int = 10) -> list[dict]:
    """
    AMT 文本 → [{pitch, on, off, vel}](秒)。perf_to_amt 的逆变换,eval hook 用。
    未闭合音符按最后时间戳收尾;孤儿 offset 忽略(不抛,评测要鲁棒)。
    """
    if not amt_text or not amt_text.strip():
        return []
    units = text_to_units(amt_text.strip())
    notes: list[dict] = []
    open_notes: dict[int, tuple[float, int]] = {}    # pitch -> (on_sec, vel)
    last_t = 0.0
    for u in units:
        t = (u.ts_bin * ts_ms / 1000.0) if u.ts_bin is not None else last_t
        last_t = max(last_t, t)
        for _staff, p in u.offs:
            pitch = p if isinstance(p, int) else p.midi
            if pitch in open_notes:
                on, vel = open_notes.pop(pitch)
                notes.append({"pitch": pitch, "on": on, "off": max(t, on + ts_ms / 1000.0),
                              "vel": vel})
        for _staff, p, vel in u.ons:
            pitch = p if isinstance(p, int) else p.midi
            if pitch not in open_notes:              # 重复 onset 忽略后者
                open_notes[pitch] = (t, vel if vel is not None else 64)
    for pitch, (on, vel) in open_notes.items():      # 未闭合 → 末时间戳收尾
        notes.append({"pitch": pitch, "on": on, "off": max(last_t, on + ts_ms / 1000.0),
                      "vel": vel})
    notes.sort(key=lambda n: (n["on"], n["pitch"]))
    return notes


# ---------------------------------------------------------------- 报告对照(R-S13.4)

# 论文对照数字(修正:原版把 Table 3 的 note F1(87.1/91.0)误标成 OMR-NED,
# 会让 gap_annotation 对着错误目标下"可缩/结构性"结论)。
# OMR-NED 越低越好:论文 Table 2,Rubato TAST @ ASAP = 64.3。
# note F1 越高越好:论文 Table 3,TAST @ ASAP = 91.0,TAST @ MAESTRO = 87.1,AMT @ MAESTRO = 97.0。
PAPER_NUMBERS = {
    "maestro_amt_f1": 97.0,
    "nasap_omr_ned": 64.3,          # 论文 ASAP OMR-NED(TAST 输出)
    "nasap_tast_note_f1": 91.0,     # 论文 ASAP note F1(TAST)
    "maestro_tast_note_f1": 87.1,   # 论文 MAESTRO note F1(TAST)
}


def gap_annotation(metric: str, value: float, tol_trainable: float = 5.0) -> dict:
    """
    R-S13.4:每指标对照论文 + 差距标注「继续训练可缩」或「结构性」。
    差距 ≤ tol_trainable → 训练可缩;更大 → 结构性(需改架构/数据)。
    """
    paper = PAPER_NUMBERS.get(metric)
    if paper is None:
        return {"metric": metric, "value": value, "paper": None, "note": "无对照数字"}
    gap = paper - value
    return {
        "metric": metric, "value": value, "paper": paper, "gap": round(gap, 2),
        "verdict": "继续训练可缩" if abs(gap) <= tol_trainable else "结构性差距",
    }


def build_eval_report(metrics: dict, failures: list[dict]) -> str:
    """
    R-S13.4:生成 outputs/eval_report.md 文本。
    metrics: {metric_name: value};failures: [{utt_id, category}]。
    """
    from collections import Counter
    lines = ["# 评测报告\n"]
    lines.append("## 指标对照论文\n")
    for m, v in metrics.items():
        ann = gap_annotation(m, v)
        if ann.get("paper"):
            lines.append(f"- {m}: {v} (论文 {ann['paper']}, 差距 {ann['gap']}, "
                         f"**{ann['verdict']}**)")
        else:
            lines.append(f"- {m}: {v}")
    lines.append("\n## 失败归因(R-S13.3)\n")
    cats = Counter(f["category"] for f in failures)
    total = sum(cats.values())
    lines.append(f"总失败: {total}")
    for cat in ("parse_fail", "merge_artifact", "content_error"):
        n = cats.get(cat, 0)
        tag = "工程 bug" if cat != "content_error" else "模型能力"
        lines.append(f"- {cat}: {n} ({tag})")
    lines.append("\n> 只有 content_error 是继续训练能缩的;parse_fail/merge_artifact 是工程 bug。")
    return "\n".join(lines)
