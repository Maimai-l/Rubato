"""目标序列超长过滤回归(执行端 CUDA device assert 实测:位置表 512 行 vs AMT 1000+ token)。
运行: python tests_len_filter.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import numpy as np
import soundfile as sf

from rubato.data.dataset import RubatoDataset

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


class Tok:
    """mock:逐字符切分(长度=字符数),id 恒 <8000。"""
    def encode(self, t, out_type=str, **k):
        return list(t)

    def piece_to_id(self, p):
        return abs(hash(p)) % 7999


tmp = Path(tempfile.mkdtemp())
wav = tmp / "a.flac"
sf.write(str(wav), np.zeros(16000, dtype="float32"), 16000)

labels = {
    "u_short": {"A2S": "ab" * 10},                 # 20 tok + prompt ≈ 27
    "u_long":  {"A2S": "x" * 600},                 # 600 tok > 64 → 必须被过滤
    "u_mixed": {"A2S": "ab" * 10, "AMT": "y" * 600},   # A2S 保留,AMT 超长被剔
}
utts = [{"utt_id": k, "kind": "pdmx", "audio_path": str(wav), "dur_s": 1.0,
         "dialects": list(v), "split": "train", "domain": "synth"}
        for k, v in labels.items()]

print("[1] max_target_len=64:超长 (utt,dialect) 从可用池剔除并记账;短的全保")
ds = RubatoDataset(utts, labels, Tok(), train=False, max_target_len=64)
av = ds._available()
check("short_kept", av.get("u_short") == ["A2S"], av.get("u_short"))
check("long_dropped", "u_long" not in av, av.get("u_long"))
check("mixed_partial", av.get("u_mixed") == ["A2S"], av.get("u_mixed"))
rep = ds.len_filter_report
check("report_counts", rep["dropped_by_dialect"] == {"A2S": 1, "AMT": 1}, rep)
check("plan_excludes_long", all(u != "u_long" for u, _ in ds._plan), ds._plan)

print("[2] __getitem__ 正常取样(保留项),长度守卫不误伤")
item = ds[0]
check("getitem_ok", len(item["input_ids"]) + 1 <= 64, len(item["input_ids"]))
check("audio_loaded", len(item["audio"]) == 16000)

print("[3] 不限长(None):行为与从前完全一致")
ds2 = RubatoDataset(utts, labels, Tok(), train=False, max_target_len=None)
check("nolimit_all", set(ds2._available()) == {"u_short", "u_long", "u_mixed"})

print(f"\n全部通过: {PASS} 项")
