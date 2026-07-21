"""
audit_split_leakage 判决性测试:合成 1 条干净引用 + 1 条泄漏引用 + 1 条 val 引用,
脚本必须只把 train→maestro-val/test 的那条判为泄漏。
"""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np


def _flac(path: Path, dur=1.0):
    import soundfile as sf
    sf.write(str(path), np.zeros(int(dur * 16000), dtype=np.float32), 16000)


def test_leak_detected_precisely():
    tmp = Path(tempfile.mkdtemp(prefix="leak_"))
    for name in ("A.flac", "B.flac", "C.flac"):
        _flac(tmp / name)
    csv = tmp / "maestro.csv"
    csv.write_text(
        "canonical_composer,midi_filename,audio_filename,split\n"
        "X,a.midi,2004/A.wav,train\n"
        "X,b.midi,2004/B.wav,validation\n"
        "X,c.midi,2004/C.wav,test\n", encoding="utf-8")
    rows = [
        {"utt_id": "n1", "split": "train", "audio_path": str(tmp / "A.flac")},   # 干净
        {"utt_id": "n2", "split": "train", "audio_path": str(tmp / "B.flac")},   # 泄漏(train→val)
        {"utt_id": "n3", "split": "val",   "audio_path": str(tmp / "C.flac")},   # 自身非 train,无罪
        {"utt_id": "n4", "split": "train", "audio_path": str(tmp / "missing.flac")},  # 解析失败
    ]
    lab = tmp / "nasap.jsonl"
    lab.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    out = subprocess.run(
        [sys.executable, "scripts/audit_split_leakage.py",
         "--nasap-labels", str(lab), "--maestro-csv", str(csv)],
        capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    t = out.stdout
    assert "场次=3 其中 val/test=2" in t, t
    assert "场次=1 涉及行=1" in t, t
    assert "B.flac(validation): 1 行" in t, t
    assert "存在泄漏" in t
    assert "无法解析音频=1" in t


def test_fix_quarantines_precisely_and_reversibly():
    """修复脚本:只隔离 train×val/test 行,评测行不动,原值可逆,复审计归零。"""
    from scripts.fix_split_leakage import QUARANTINE, build_vt_set, classify_rows
    tmp = Path(tempfile.mkdtemp(prefix="fix_"))
    for name in ("A.flac", "B.flac"):
        _flac(tmp / name)
    csv = tmp / "m.csv"
    csv.write_text("audio_filename,split\n2004/A.wav,train\n2004/B.wav,test\n",
                   encoding="utf-8")
    vt = build_vt_set(str(csv))
    assert vt == {"B.flac"}

    def resolver(_u, _k, r):
        p = r.get("audio_path")
        return (p, 1.0) if p and Path(p).exists() else None

    rows = [
        {"utt_id": "n1", "split": "train", "audio_path": str(tmp / "A.flac")},
        {"utt_id": "n2", "split": "train", "audio_path": str(tmp / "B.flac")},   # 隔离
        {"utt_id": "n3", "split": "test",  "audio_path": str(tmp / "B.flac")},   # 评测行不动
    ]
    out, st = classify_rows(rows, vt, resolver)
    assert st["quarantined"] == 1 and st["train_kept"] == 1 and st["untouched_test"] == 1
    assert out[1]["split"] == QUARANTINE and out[1]["split_orig"] == "train"
    assert out[0]["split"] == "train" and out[2]["split"] == "test"
    # 复审计归零:隔离后的行不再是 train,不会二次命中
    out2, st2 = classify_rows(out, vt, resolver)
    assert st2.get("quarantined", 0) == 0
    # partition 语义:隔离值落 other 桶,训练/评测两不进
    from rubato.data.assemble import partition_by_split
    part = partition_by_split(out)
    assert [u["utt_id"] for u in part["train"]] == ["n1"]
    assert [u["utt_id"] for u in part["test"]] == ["n3"]
    assert [u["utt_id"] for u in part["other"]] == ["n2"]


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            t0 = time.time()
            try:
                fn()
                print(f"  ok {name} ({time.time() - t0:.1f}s)")
            except Exception as e:
                fails += 1
                print(f"  FAIL {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if fails else 0)
