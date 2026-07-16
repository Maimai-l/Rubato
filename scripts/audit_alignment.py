"""音频↔标签对齐审计 —— 病 C 根因排查第一步(不需要模型/GPU,分钟级)。

背景(D27,2026-07-16):探针三对照判定 decoder 完全忽略音频(错配音频命中率不变、
encoder 输出正常)。热启动的 cross-attention 本来会用,22k 步把它训废的头号嫌疑是
【训练对里音频和标签系统性对不上】(窗口偏移记错/配错文件/渲染错位)——那样"忽略音频"
就是降 loss 最快的路:模型学得对,数据是错的。这类 bug 冒烟测不出(文本记忆即可达标)、
loss 曲线看不出,只能直接审计数据。

本工具做的事:对每个抽样训练对,用【与训练完全相同的加载路径】(load_audio + win)读音频,
算能量起音包络;从标签解析音符起音时刻(AMT/TAST 自带 10ms 时间戳);两者做互相关扫滞后。
  对齐        → 相关峰在 lag≈0
  系统性平移  → 峰值明显但偏移(窗口账错,修账即可)
  配错/坏渲染 → 扫遍 ±2s 都不相关

用法(执行端,不训练):
  python scripts/audit_alignment.py                  # 每源 8 条
  python scripts/audit_alignment.py --per-source 16
报告自动追加 reports/alignment_audit.md(代码写,commit+push 即上报,勿编辑)。

判读(预登记):
  单对:peak ≥ 0.25 且 |best_lag| ≤ 50ms → OK;peak ≥ 0.25 但 lag 偏 → SHIFTED;
        peak < 0.25 → UNCORRELATED。(±50ms 带宽吸收分帧测量学偏差;记账 bug 是百 ms~秒级。
        注意:音乐准周期,配错对也可能在大滞后蒙出峰 → |lag|>500ms 的 SHIFTED 按配错同等对待)
  单源:≥1/3 非 OK → 该源判"对齐故障"。三源全 OK → 数据洗清嫌疑,转查训练侧
  (SpecAugment/cross-attention,规划端出下一张卡)。
"""
from __future__ import annotations
import argparse
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout

harden_stdout()

HOP_MS = 10
SR = 16000


# ---------------------------------------------------------------- 纯逻辑(沙盒可测)

def onset_envelope(audio, sr: int = SR, hop_ms: int = HOP_MS, frame_ms: int = 32):
    """能量起音包络:分帧 RMS → 半波整流一阶差分。10ms 网格,与标签时间戳同格。"""
    import numpy as np
    a = np.asarray(audio, dtype=np.float32).reshape(-1)
    hop = int(sr * hop_ms / 1000)
    frame = int(sr * frame_ms / 1000)
    if len(a) < frame:
        return np.zeros(0, dtype=np.float32)
    n = 1 + (len(a) - frame) // hop
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    rms = np.sqrt((a[idx] ** 2).mean(axis=1))
    d = np.diff(rms, prepend=rms[:1])
    return np.maximum(d, 0.0)


def label_onset_train(onsets_sec, n_frames: int, hop_ms: int = HOP_MS, spread: int = 2):
    """音符起音时刻 → 10ms 网格上的脉冲串(三角核铺开 ±spread 帧,容忍量化)。"""
    import numpy as np
    imp = np.zeros(max(n_frames, 1), dtype=np.float32)
    for t in onsets_sec:
        c = int(round(t * 1000 / hop_ms))
        for k in range(-spread, spread + 1):
            j = c + k
            if 0 <= j < len(imp):
                imp[j] += (spread + 1 - abs(k)) / (spread + 1)
    return imp


def _ncc(a, b) -> float:
    import numpy as np
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a * a).sum()) * np.sqrt((b * b).sum()))
    return float((a * b).sum() / d) if d > 1e-12 else 0.0


def best_lag(env, imp, max_lag_frames: int = 200) -> dict:
    """扫 ±max_lag(默认 ±2s):返回 corr@0 / 峰值 / 峰值滞后(ms,正 = 音频事件比标签晚)。"""
    import numpy as np
    n = min(len(env), len(imp))
    if n < 80:                                    # <0.8s 没法判
        return {"corr0": 0.0, "peak": 0.0, "lag_ms": 0, "n_frames": n}
    e, m = np.asarray(env[:n]), np.asarray(imp[:n])
    corr0 = _ncc(e, m)
    peak, peak_lag = corr0, 0
    for lag in range(-max_lag_frames, max_lag_frames + 1):
        if lag == 0:
            continue
        if lag > 0:
            a, b = e[lag:], m[: n - lag]
        else:
            a, b = e[: n + lag], m[-lag:]
        if len(a) < 80:
            continue
        c = _ncc(a, b)
        if c > peak:
            peak, peak_lag = c, lag
    return {"corr0": round(corr0, 3), "peak": round(peak, 3),
            "lag_ms": peak_lag * HOP_MS, "n_frames": n}


def classify(r: dict, min_corr: float = 0.25, max_ok_lag_ms: int = 50) -> str:
    """以【峰值 + 峰值滞后】判,不看 corr@0:分帧 RMS 的帧窗前沿效应会让能量峰比名义
    起音早 ~20ms(合成测试实测),corr@0 因此系统性偏低;真正的记账 bug 是百 ms~秒级,
    ±50ms 带宽足以把测量学噪声和真问题分开。"""
    if r["n_frames"] < 80:
        return "TOO_SHORT"
    if r["peak"] >= min_corr and abs(r["lag_ms"]) <= max_ok_lag_ms:
        return "OK"
    if r["peak"] >= min_corr:
        return "SHIFTED"
    return "UNCORRELATED"


def label_onsets(label_text: str, dialect: str) -> list[float]:
    """标签 → 音符起音秒列表。AMT 走 amt_text_to_notes;TAST 取带 onset 单元的 ts_bin。"""
    if dialect == "AMT":
        from rubato.model.evaluate import amt_text_to_notes
        return sorted({n["on"] for n in amt_text_to_notes(label_text)})
    from rubato.intermo.core import text_to_units
    out = []
    for u in text_to_units(label_text):
        if getattr(u, "ons", None) and u.ts_bin is not None:
            out.append(u.ts_bin * HOP_MS / 1000.0)
    return sorted(set(out))


# ---------------------------------------------------------------- 主流程(执行端跑)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-source", type=int, default=8)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent
                                         / "reports" / "alignment_audit.md"))
    args = ap.parse_args()

    from scripts.build_dataset import SOURCES, resolve_audio, _pdmx_row_fn
    from rubato.data.assemble import assemble
    from rubato.data.dataset import load_audio

    pdmx_fn = _pdmx_row_fn()
    for src in SOURCES:
        if src["kind"] == "pdmx":
            src["row_fn"] = pdmx_fn
    utts, labels, _ = assemble(SOURCES, resolve_audio)

    # 每源抽 N 条【带时间戳标签】的训练对(确定性:按 utt_id 哈希排序)
    pick: dict[str, list] = {}
    for u in sorted(utts, key=lambda u: hashlib.sha256(u["utt_id"].encode()).hexdigest()):
        lab = labels.get(u["utt_id"], {}) or {}
        dia = "AMT" if lab.get("AMT") else ("TAST" if lab.get("TAST") else None)
        if not dia:
            continue
        pool = pick.setdefault(u["kind"], [])
        if len(pool) < args.per_source:
            pool.append((u, dia, lab[dia]))

    lines = [f"\n## 对齐审计 @ {time.strftime('%Y-%m-%d %H:%M:%S')}(per-source={args.per_source};"
             f"判读:OK=corr0≥0.25 且 |lag|≤50ms / SHIFTED=峰值≥0.25 但偏移 / UNCORRELATED=峰值<0.25)"]
    verdicts: dict[str, dict] = {}
    for kind, pool in sorted(pick.items()):
        counts: dict[str, int] = {}
        for u, dia, text in pool:
            try:
                audio = load_audio(u["audio_path"], win=u.get("win"))
                ons = label_onsets(text, dia)
                if not ons:
                    row = f"  {kind} {u['utt_id']}/{dia}: 标签无起音,跳过"
                    lines.append(row)
                    print(row, flush=True)
                    continue
                env = onset_envelope(audio)
                imp = label_onset_train(ons, len(env))
                r = best_lag(env, imp)
                v = classify(r)
                counts[v] = counts.get(v, 0) + 1
                row = (f"  {kind} {u['utt_id']}/{dia}: {v} corr0={r['corr0']} "
                       f"peak={r['peak']} lag={r['lag_ms']}ms onsets={len(ons)} "
                       f"帧={r['n_frames']}")
            except Exception as e:
                counts["ERROR"] = counts.get("ERROR", 0) + 1
                row = f"  {kind} {u['utt_id']}/{dia}: ERROR {type(e).__name__}: {e}"
            lines.append(row)
            print(row, flush=True)
        n_bad = sum(c for v, c in counts.items() if v not in ("OK",))
        n_all = sum(counts.values())
        verdict = "对齐故障" if (n_all and n_bad * 3 >= n_all) else "OK"
        verdicts[kind] = {"counts": counts, "verdict": verdict}
        row = f"  == {kind}: {counts} → {verdict}"
        lines.append(row)
        print(row, flush=True)

    summary = " / ".join(f"{k}:{v['verdict']}" for k, v in sorted(verdicts.items()))
    lines.append(f"  总判定: {summary}")
    print(f"  总判定: {summary}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"报告已落盘 {out}(git add + commit + push 即上报,勿编辑)", flush=True)


if __name__ == "__main__":
    main()
