"""soundfont_weights 解码后大小估计回归测试 —— 修"按文件大小低估 FLAC 音源 2 倍 → 准入放行过多并发 OOM"。
(执行端实测:ExperienceNY 文件 6.9GB FLAC → sfizz 实际 RSS ~12GB。)
用 truncate 造稀疏文件模拟大样本,不占磁盘。运行: python tests_sf_weights.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from rubato.render.core import soundfont_weights

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


def _sparse(p: Path, size: int):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.truncate(size)          # 稀疏文件:st_size=size,不占实际磁盘


tmp = Path(tempfile.mkdtemp())
# 音源目录:0.3GB wav(未压缩)+ 0.3GB flac(压缩,解码 ×2)+ 大写扩展名 .FLAC 也要认
_sparse(tmp / "font" / "piano.sfz", 1000)
_sparse(tmp / "font" / "a.wav", 300_000_000)
_sparse(tmp / "font" / "b.flac", 300_000_000)
_sparse(tmp / "font" / "c.FLAC", 100_000_000)
cfg = {"sources": {"S": {"path": "font/piano.sfz"}}}

print("[1] 解码倍率:wav 按 1×、flac 按 2×(默认),大小写不敏感")
os.environ.pop("SF_DECODE_FACTOR", None)
w = soundfont_weights(cfg, tmp)["S"]
# 0.3(wav) + 0.6(flac×2) + 0.2(FLAC×2) + sfz≈0 = 1.1GB
check("default_2x", abs(w - 1.1) < 0.02, w)

print("[2] decode_factor 参数显式传入")
w1 = soundfont_weights(cfg, tmp, decode_factor=1.0)["S"]     # 旧行为:全按文件大小
check("factor_1_is_filesize", abs(w1 - 0.7) < 0.02, w1)
w3 = soundfont_weights(cfg, tmp, decode_factor=3.0)["S"]
check("factor_3", abs(w3 - (0.3 + 0.9 + 0.3)) < 0.02, w3)      # wav0.3 + flac0.3×3 + FLAC0.1×3

print("[3] env SF_DECODE_FACTOR 覆盖默认")
os.environ["SF_DECODE_FACTOR"] = "4.0"
w4 = soundfont_weights(cfg, tmp)["S"]
check("env_override", abs(w4 - (0.3 + 1.2 + 0.4)) < 0.02, w4)  # wav0.3 + flac0.3×4 + FLAC0.1×4
os.environ.pop("SF_DECODE_FACTOR", None)

print("[4] mem_factor 仍复合生效;目录缺失仍保守 2.0")
wh = soundfont_weights(cfg, tmp, mem_factor=0.5)["S"]
check("mem_factor_compose", abs(wh - 0.55) < 0.02, wh)
w_missing = soundfont_weights({"sources": {"X": {"path": "no/such.sfz"}}}, tmp)["X"]
check("missing_dir_conservative", w_missing == 2.0, w_missing)

print(f"\n全部通过: {PASS} 项")
