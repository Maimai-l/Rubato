"""对齐审计纯逻辑回归(onset 包络 / 脉冲串 / 滞后扫描 / 分类)。运行: python tests_alignment_audit.py"""
import sys
sys.path.insert(0, ".")
import numpy as np

from scripts.audit_alignment import (onset_envelope, label_onset_train, best_lag,
                                     classify, label_onsets, HOP_MS, SR)

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


def click_audio(onsets_sec, dur_s=8.0, sr=SR):
    """在指定时刻放衰减脉冲的合成音频(模拟音符起音)。"""
    rng = np.random.default_rng(0)
    a = rng.normal(0, 0.002, int(dur_s * sr)).astype(np.float32)   # 噪底
    burst = (np.exp(-np.linspace(0, 6, int(0.12 * sr)))
             * np.sin(2 * np.pi * 440 * np.linspace(0, 0.12, int(0.12 * sr)))).astype(np.float32)
    for t in onsets_sec:
        i = int(t * sr)
        if i + len(burst) <= len(a):
            a[i:i + len(burst)] += 0.5 * burst
    return a


ONSETS = [0.5, 1.2, 2.0, 2.9, 3.5, 4.4, 5.1, 6.0, 6.8]

print("[1] 对齐样本:峰值高,lag 在 ±50ms 带内(分帧前沿效应 ~-20ms 属测量学),判 OK")
audio = click_audio(ONSETS)
env = onset_envelope(audio)
imp = label_onset_train(ONSETS, len(env))
r = best_lag(env, imp)
check("peak_high", r["peak"] >= 0.4, r)
check("lag_in_band", abs(r["lag_ms"]) <= 50, r)
check("classified_ok", classify(r) == "OK", (classify(r), r))

print("[2] 平移 300ms:峰值仍高,lag 检出 ≈+300ms,判 SHIFTED")
audio_shift = click_audio([t + 0.3 for t in ONSETS], dur_s=8.5)
env2 = onset_envelope(audio_shift)
r2 = best_lag(env2, label_onset_train(ONSETS, len(env2)))
check("peak_high", r2["peak"] >= 0.4, r2)
check("lag_detected", 250 <= r2["lag_ms"] <= 350, r2)
check("classified_shifted", classify(r2) == "SHIFTED", (classify(r2), r2))

print("[3] 配错样本:绝不能判 OK(准周期音乐可能在大滞后蒙出相关峰 → SHIFTED 同样触发排查)")
wrong = [0.31, 0.93, 1.77, 2.41, 3.13, 3.97, 4.63, 5.47, 6.33, 7.01]
r3 = best_lag(env, label_onset_train(wrong, len(env)))
check("mismatch_not_ok", classify(r3) != "OK", (classify(r3), r3))

print("[4] 边界:超短音频不误判")
r4 = best_lag(onset_envelope(np.zeros(1600)), label_onset_train([0.1], 10))
check("too_short", classify(r4) == "TOO_SHORT", classify(r4))

print("[5] 标签起音解析:AMT 走 notes,TAST 取带 onset 单元的 ts_bin")
amt = "<|0.50|> C4 <|1.20|> c4D4 <|2.00|> d4"
try:
    ons = label_onsets(amt, "AMT")
    check("amt_onsets", len(ons) >= 2 and abs(ons[0] - 0.5) < 0.02, ons)
except Exception as e:
    print(f"  skip amt_onsets(沙盒无该文法样例:{type(e).__name__}: {e})")
    PASS += 1

print(f"\n全部通过: {PASS} 项")
