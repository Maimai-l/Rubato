"""apply_preset 混音修复回归:能量归一 vs 旧峰值对齐、WET_SCALE/NOISE_DB_OFFSET 旋钮。
运行: python tests_preset_mix.py"""
import os
import sys

sys.path.insert(0, ".")
import numpy as np

from rubato.render.irgen import apply_preset

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))


SR = 16000
rng = np.random.default_rng(0)
# 干声:稀疏敲击(高峰值/低 RMS,钢琴式)—— 峰值对齐 bug 在这种信号上最夸张
x = np.zeros(SR * 2, dtype=np.float32)
x[::4000] = 0.9
# IR:指数衰减尾(0.5s),能量远大于峰值比
t = np.arange(int(0.5 * SR), dtype=np.float32)
ir = (rng.standard_normal(len(t)).astype(np.float32) * np.exp(-t / (0.15 * SR)))
P = {"wet": 0.5, "shelf4k": 0.0, "lp": 0, "hp": 0, "noise": -120, "gain_jitter": 0.0}

print("[1]【bug 复现→修复】同一 wet=0.5:旧峰值对齐的湿声响度显著高于能量归一(糊的来源)")
for k in ("RUBATO_WET_SCALE", "RUBATO_NOISE_DB_OFFSET"):
    os.environ.pop(k, None)
y_leg = apply_preset(x, P, sr=SR, seed=1, ir_override=ir, wet_mode="legacy")
y_fix = apply_preset(x, P, sr=SR, seed=1, ir_override=ir, wet_mode="energy")
check("legacy_louder_wet", rms(y_leg) > rms(y_fix) * 1.3,
      f"legacy={rms(y_leg):.4f} fixed={rms(y_fix):.4f}")   # 旧算法至少响 30%+(实测通常远超)

print("[2] 能量归一语义:wet=0 → 纯干声;WET_SCALE=0 同效")
P0 = dict(P, wet=0.0)
y_dry = apply_preset(x, P0, sr=SR, seed=1, ir_override=ir)
check("wet0_is_dry", np.allclose(y_dry, x, atol=1e-4), rms(np.abs(y_dry - x)))
os.environ["RUBATO_WET_SCALE"] = "0"
y_s0 = apply_preset(x, P, sr=SR, seed=1, ir_override=ir)
check("scale0_is_dry", np.allclose(y_s0, x, atol=1e-4))
os.environ["RUBATO_WET_SCALE"] = "0.5"
y_half = apply_preset(x, P, sr=SR, seed=1, ir_override=ir)
os.environ.pop("RUBATO_WET_SCALE")
y_full = apply_preset(x, P, sr=SR, seed=1, ir_override=ir)
# 湿声成分(y - (1-mix)x)随 scale 单调收缩
check("scale_monotone", rms(y_half - x) < rms(y_full - x), (rms(y_half - x), rms(y_full - x)))

print("[3] 噪底旋钮:静音输入下输出≈噪底,NOISE_DB_OFFSET=-12 → 噪底 RMS 降 ~4 倍")
sil = np.zeros(SR, dtype=np.float32)
Pn = dict(P, wet=0.0, noise=-40)
n0 = rms(apply_preset(sil, Pn, sr=SR, seed=2, ir_override=ir))
os.environ["RUBATO_NOISE_DB_OFFSET"] = "-12"
n1 = rms(apply_preset(sil, Pn, sr=SR, seed=2, ir_override=ir))
os.environ.pop("RUBATO_NOISE_DB_OFFSET")
check("noise_offset", 3.0 < n0 / max(n1, 1e-12) < 5.5, n0 / max(n1, 1e-12))  # -12dB ≈ ×0.251

print(f"\n全部通过: {PASS} 项")
