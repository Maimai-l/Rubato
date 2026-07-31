"""
持久化时长缓存(D71,装配 O(N) 音频探测提速)判决性测试:
命中免探测 / (size,mtime) 失效重探 / 缺文件不缓存 / 坏行容忍 / 缓存故障不伤装配。
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path


def _fresh_bd(cache_path: str):
    """每个用例干净进程态:重载模块 + 指定缓存文件。"""
    os.environ["RUBATO_DUR_CACHE"] = cache_path
    import scripts.build_dataset as bd
    bd._dur_db_close()
    importlib.reload(bd)
    return bd


def test_probe_then_hit_without_reprobe():
    import soundfile as sf
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.flac"
        sf.write(str(wav), [0.1] * 32000, 16000)          # 2.0s
        cache = str(Path(td) / "dur.jsonl")
        bd = _fresh_bd(cache)
        assert abs(bd._flac_dur(str(wav)) - 2.0) < 1e-6
        if bd._DUR_DB_FH:
            bd._DUR_DB_FH.flush()
        assert Path(cache).exists() and json.loads(open(cache).readline())[3] == 2.0
        # 新"进程":内容换成噪声但恢复 size+mtime → 命中旧值 = 证明没有重新开文件探测
        st = os.stat(wav)
        raw = open(wav, "rb").read()
        open(wav, "wb").write(raw[:-4] + b"XXXX")          # 同尺寸破坏
        os.utime(wav, ns=(st.st_atime_ns, st.st_mtime_ns))
        bd2 = _fresh_bd(cache)
        assert bd2._flac_dur(str(wav)) == 2.0, "size+mtime 未变必须走缓存,不碰文件"


def test_invalidate_on_size_change_and_missing_not_cached():
    import soundfile as sf
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "b.flac"
        sf.write(str(wav), [0.1] * 16000, 16000)           # 1.0s
        cache = str(Path(td) / "dur.jsonl")
        bd = _fresh_bd(cache)
        assert abs(bd._flac_dur(str(wav)) - 1.0) < 1e-6
        if bd._DUR_DB_FH:
            bd._DUR_DB_FH.flush()
        sf.write(str(wav), [0.1] * 48000, 16000)           # 换内容:3.0s(size 变)
        bd2 = _fresh_bd(cache)
        assert abs(bd2._flac_dur(str(wav)) - 3.0) < 1e-6, "size 变必须重探"
        assert bd2._flac_dur(str(Path(td) / "nope.flac")) is None
        bd3 = _fresh_bd(cache)                              # 缺文件不得进缓存
        assert all("nope" not in k for k in bd3._DUR_DB), "缺失文件不许缓存"


def test_corrupt_lines_tolerated_and_cache_failure_harmless():
    import soundfile as sf
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "c.flac"
        sf.write(str(wav), [0.1] * 16000, 16000)
        cache = Path(td) / "dur.jsonl"
        cache.write_text('垃圾行\n["半截",1,\n', encoding="utf-8")   # 坏行 + 残行
        bd = _fresh_bd(str(cache))
        assert abs(bd._flac_dur(str(wav)) - 1.0) < 1e-6     # 坏行跳过,照常工作
        # 缓存目录不可写(指到不存在盘符风格路径)→ 装配仍必须工作
        bd2 = _fresh_bd(str(Path(td) / "no_dir_here" / ("x" * 260) / "dur.jsonl")
                        if os.name == "nt" else "/proc/definitely/not/writable/dur.jsonl")
        assert abs(bd2._flac_dur(str(wav)) - 1.0) < 1e-6
        bd2._dur_db_close()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        t0 = time.time()
        try:
            fn()
            print(f"  ok {fn.__name__} ({time.time()-t0:.1f}s)")
        except Exception as e:
            bad += 1
            import traceback
            print(f"  FAIL {fn.__name__}: {e}")
            traceback.print_exc(limit=4)
    os.environ.pop("RUBATO_DUR_CACHE", None)
    print(("PASS" if not bad else "FAIL") + f" {len(fns)-bad}/{len(fns)}")
    sys.exit(1 if bad else 0)
