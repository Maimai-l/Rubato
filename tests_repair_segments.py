"""s5_repair_segments 回归测试 —— 外科手术式修复:只清含越界段的曲,好曲和非 VN 行原样保留。
用真实 wav(soundfile 写)验证时长扫描。运行: python tests_repair_segments.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import numpy as np
import soundfile as sf

import scripts.s5_repair_segments as rep

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


tmp = Path(tempfile.mkdtemp())
audio = tmp / "audio"; audio.mkdir()
SR = 8000


def _wav(name, dur_s):
    p = audio / name
    sf.write(str(p), np.zeros(int(dur_s * SR), dtype="float32"), SR)
    return str(p)


# 曲 A:两段都正常(12s/30s)→ 保留。曲 B:含 0.4s 碎片 → 重做。曲 C:含 45s 超长段 → 重做。
# 曲 D:标签声称有音频但文件缺失 → 重做。另有一条非 VN 行(文本标签)必须原样保留。
rows = [
    {"utt_id": "pdmxperf_A_000", "piece_id": "A", "audio_path": _wav("pdmxperf_A_000.wav", 12), "TAST": "x"},
    {"utt_id": "pdmxperf_A_001", "piece_id": "A", "audio_path": _wav("pdmxperf_A_001.wav", 30), "TAST": "x"},
    {"utt_id": "pdmxperf_B_000", "piece_id": "B", "audio_path": _wav("pdmxperf_B_000.wav", 0.4), "TAST": "x"},
    {"utt_id": "pdmxperf_B_001", "piece_id": "B", "audio_path": _wav("pdmxperf_B_001.wav", 10), "TAST": "x"},
    {"utt_id": "pdmxperf_C_000", "piece_id": "C", "audio_path": _wav("pdmxperf_C_000.wav", 45), "TAST": "x"},
    {"utt_id": "pdmxperf_D_000", "piece_id": "D", "audio_path": str(audio / "missing.wav"), "TAST": "x"},
    {"utt_id": "pdmx_T_000", "piece_id": "T", "measure_range": [0, 8], "A2S": "y"},   # 非 VN 行
]
labels = tmp / "labels.jsonl"
with open(labels, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
for pid in ("A", "B", "C", "D"):
    (audio / f"{pid}.done").touch()

print("[1] 扫描:B(过短)/C(过长)/D(音频缺失)判坏,A/T 不动")
bad, st = rep.scan(labels, 1.0, 41.0)
check("bad_set", bad == {"B", "C", "D"}, bad)
check("counts", st["too_short"] == 1 and st["too_long"] == 1 and st["missing_audio"] == 1, st)
check("vn_rows", st["vn_rows"] == 6, st)

print("[2] 干跑不改任何文件")
rc = rep.main(["--labels", str(labels), "--audio-dir", str(audio),
               "--min-sec", "1.0", "--max-sec", "40.0"])
check("dry_run_rc0", rc == 0)
check("dry_run_labels_intact", len(open(labels).readlines()) == 7)
check("dry_run_audio_intact", (audio / "pdmxperf_B_000.wav").exists())

print("[3] --apply:B/C/D 的行剔除、音频删除、.done 删除;A 与非 VN 行保留;.bak 备份")
rc = rep.main(["--labels", str(labels), "--audio-dir", str(audio),
               "--min-sec", "1.0", "--max-sec", "40.0", "--apply"])
check("apply_rc0", rc == 0)
kept = [json.loads(l) for l in open(labels) if l.strip()]
check("kept_rows", {r["utt_id"] for r in kept} ==
      {"pdmxperf_A_000", "pdmxperf_A_001", "pdmx_T_000"}, [r["utt_id"] for r in kept])
check("bak_exists", labels.with_suffix(".bak").exists())
check("bad_audio_deleted", not (audio / "pdmxperf_B_000.wav").exists()
      and not (audio / "pdmxperf_C_000.wav").exists())
check("good_audio_kept", (audio / "pdmxperf_A_000.wav").exists())
check("bad_done_deleted", not (audio / "B.done").exists() and not (audio / "D.done").exists())
check("good_done_kept", (audio / "A.done").exists())

print("[4] slack 容差:40.5s 段在 slack=1 下不算坏(小节界取整会略超)")
_wav("pdmxperf_E_000.wav", 40.5)
with open(labels, "a", encoding="utf-8") as f:
    f.write(json.dumps({"utt_id": "pdmxperf_E_000", "piece_id": "E",
                        "audio_path": str(audio / "pdmxperf_E_000.wav"), "TAST": "x"}) + "\n")
bad2, _ = rep.scan(labels, 1.0, 41.0)
check("slack_tolerates", "E" not in bad2, bad2)

print("[5] --all 全量重跑:所有 VN 曲(含好曲 A/E)都清,非 VN 行仍保留")
rc = rep.main(["--labels", str(labels), "--audio-dir", str(audio), "--all", "--apply"])
check("all_rc0", rc == 0)
kept = [json.loads(l) for l in open(labels) if l.strip()]
check("all_only_nonvn_left", {r["utt_id"] for r in kept} == {"pdmx_T_000"},
      [r["utt_id"] for r in kept])
check("all_audio_gone", not (audio / "pdmxperf_A_000.wav").exists()
      and not (audio / "pdmxperf_E_000.wav").exists())
check("all_done_gone", not (audio / "A.done").exists())

print(f"\n全部通过: {PASS} 项")
