"""
r3 收尾两工具的判决性测试:失败释放(标签/产物两路 + 终败保留 + 幂等备份)、
WAV→FLAC 三相(转换删源、标签原子改写、核验账目、断点幂等)。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _run(script: str, extra, work: Path):
    env = dict(os.environ)
    env["RUBATO_WORK"] = str(work)
    return subprocess.run([PY, str(ROOT / "scripts" / script), *extra],
                          capture_output=True, text=True, env=env, cwd=str(ROOT))


def test_failures_release():
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        # 曲 A:已有标签(释放);曲 B:有 MIDI+CSV 产物(释放);曲 C:啥都没有(保留)
        with open(work / "pdmx_perf_labels_r3_native.staging.jsonl", "w", encoding="utf-8") as f:
            f.write(json.dumps({"piece_id": "QmA", "utt_id": "pdmxperf_QmA_000"}) + "\n")
        leaf = work / "vn_native_r3_train" / "10" / "9"
        leaf.mkdir(parents=True)
        (leaf / "9_QmB_by_isgn_Bach.mid").write_bytes(b"MThd")
        (leaf / "9_QmB_by_isgn_Bach.mid_midi_notes.csv").write_text("x", encoding="utf-8")
        fl = work / "pdmx_vn_failures_r3_native.jsonl"
        with open(fl, "w", encoding="utf-8") as f:
            for pid in ("QmA", "QmB", "QmC"):
                f.write(json.dumps({"piece_id": pid, "reason": "old"}) + "\n")
        (work / "manifest_pieces_r3_train.jsonl").write_text("", encoding="utf-8")
        r = _run("r3_failures_release.py", [], work)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "保留终败 1" in r.stdout and "已有标签 1" in r.stdout and "待消费 1" in r.stdout, r.stdout
        kept = [json.loads(l) for l in open(fl, encoding="utf-8")]
        assert [k["piece_id"] for k in kept] == ["QmC"]
        assert fl.with_suffix(fl.suffix + ".pre_release.bak").exists()
        assert "s5_vn_render.py --native-vn-root" in r.stdout, "必须打印下一步消费命令"
        r2 = _run("r3_failures_release.py", [], work)      # 幂等:再跑不变、备份不覆盖
        assert "保留终败 1" in r2.stdout, r2.stdout


def test_wav2flac_three_phases():
    import soundfile as sf
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        adir = work / "pdmx_audio_r3_native"
        adir.mkdir(parents=True)
        sf.write(str(adir / "u1.wav"), [0.1] * 1600, 16000)          # 待转
        sf.write(str(adir / "u2.flac"), [0.1] * 1600, 16000)         # 已是 flac
        lp = work / "pdmx_perf_labels_r3_native.staging.jsonl"
        rows = [
            {"utt_id": "u1", "audio_path": str(adir / "u1.wav")},
            {"utt_id": "u2", "audio_path": str(adir / "u2.flac")},
            {"utt_id": "u3", "audio_path": str(adir / "u3.wav")},    # 真缺失
        ]
        lp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        r = _run("wav2flac_labels.py", [], work)
        assert "新转 1 | 失败 0" in r.stdout, r.stdout
        assert "改写: 1 行" in r.stdout, r.stdout
        assert "flac 2 | 仍 wav 0 | 缺失 1 | 不可读 0" in r.stdout, r.stdout
        assert not (adir / "u1.wav").exists() and (adir / "u1.flac").exists()
        got = [json.loads(l) for l in open(lp, encoding="utf-8")]
        assert got[0]["audio_path"].endswith("u1.flac")
        assert got[2]["audio_path"].endswith("u3.wav")               # 缺失行不乱改
        assert lp.with_suffix(lp.suffix + ".pre_flac.bak").exists()
        r2 = _run("wav2flac_labels.py", [], work)                     # 幂等
        assert "新转 0 | 失败 0" in r2.stdout and "改写: 0 行" in r2.stdout, r2.stdout


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
