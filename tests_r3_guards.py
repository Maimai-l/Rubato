"""
r3(restore)波次的两道机械守卫(D67)判决性测试:
① s3_filter restore 流禁写主 manifest;② s5 消费模式默认切 r3 staging + 强制显式清单。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from scripts import s5_vn_render as s5


def test_s3_restore_refuses_main_manifest():
    from scripts import s3_filter_pdmx as s3
    rc = s3.main(["--restore-candidates", "whatever.jsonl",
                  "--out-manifest", str(s3.OUT_MANIFEST)])
    assert rc == 2, f"restore 写主 manifest 必须被拒,得 rc={rc}"
    # dry-run 不落盘,允许走(后续在缺 CSV 的沙盒自然失败,但不许死在守卫上)
    try:
        s3.main(["--restore-candidates", "no_such.jsonl", "--dry-run"])
    except FileNotFoundError as e:
        assert "restore-candidates" in str(e), e     # 死因是候选文件缺失,不是守卫


def test_s5_native_defaults_and_guards():
    captured = {}
    orig_run = s5.run
    try:
        s5.run = lambda *a, **k: captured.update(k, _pos=a) or {"utts": 0}
        # 缺显式 manifest → 拒
        rc = s5.main(["--native-vn-root", "D:/x/vn_out"])
        assert rc == 2 and not captured, "消费模式没给 r3 清单必须被拒"
        # 显式清单 → 默认全部切 r3 staging
        rc2 = s5.main(["--native-vn-root", "D:/x/vn_out",
                       "--manifest", "D:/x/manifest_pieces_r3.jsonl"])
        assert rc2 == 0
        assert str(captured["_pos"][3]).endswith("pdmx_perf_labels_r3.staging.jsonl")
        assert captured["_pos"][4] == ""                                   # 语料不写
        assert str(captured["_pos"][5]).endswith("pdmx_audio_r3")
        assert str(captured["out_failures"]).endswith("s5_r3_failures.jsonl")
        assert captured["native_vn_root"] == "D:/x/vn_out"
        # 显式非 staging 标签名 → 拒
        captured.clear()
        rc3 = s5.main(["--native-vn-root", "D:/x/vn_out",
                       "--manifest", "D:/x/m_r3.jsonl",
                       "--out-labels", "D:/x/pdmx_perf_labels.jsonl"])
        assert rc3 == 2 and not captured, "消费模式直写正式名必须被拒(绕挂载闸)"
        # 二音色模式回归:r3 守卫不得误伤
        captured.clear()
        rc4 = s5.main(["--second-timbre"])
        assert rc4 == 0 and str(captured["_pos"][3]).endswith("_s2.staging.jsonl")
    finally:
        s5.run = orig_run


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
    print(("PASS" if not bad else "FAIL") + f" {len(fns)-bad}/{len(fns)}")
    sys.exit(1 if bad else 0)
