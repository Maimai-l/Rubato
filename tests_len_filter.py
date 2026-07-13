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

print("[4] augment 开关:冒烟(关)→ 同一样本跨 epoch 恒等;训练(开)→ tiling 会动时间戳")
lab_t = {"u_t": {"TAST": "<|1.00|>ab <|3.50|>cd"}}
utt_t = [{"utt_id": "u_t", "kind": "pdmx", "audio_path": str(wav), "dur_s": 5.0,
          "dialects": ["TAST"], "split": "train", "domain": "synth"}]
ds_off = RubatoDataset(utt_t, lab_t, Tok(), train=True, augment=False)
ds_off.set_epoch(0)
ids0 = ds_off[0]["input_ids"]
ds_off.set_epoch(3)
check("smoke_deterministic", ds_off[0]["input_ids"] == ids0)   # 关增强:答案固定,可背诵
ds_on = RubatoDataset(utt_t, lab_t, Tok(), train=True)         # 缺省=开(论文 R-S9.4/R-S11.3)
changed = False
for e in range(6):
    ds_on.set_epoch(e)
    if ds_on._plan and ds_on[0]["input_ids"] != ids0:
        changed = True
        break
check("train_tiling_varies", changed)   # 开增强:时间戳随 epoch 平移 —— 背不下来是设计属性

print("[5] 桶预算 = 补零后的真实音频秒(29.5GB OOM 回归):batch 实载音频 ≤ 预算")
from rubato.data.dataset import RubatoDataModule
lab5 = {f"t{i}": {"TAST": f"<|{i}.00|>ab <|{i}.50|>cd"} for i in range(20)}
utt5 = [{"utt_id": k, "kind": "pdmx", "audio_path": str(wav), "dur_s": 1.0,
         "dialects": ["TAST"], "split": "train", "domain": "synth"} for k in lab5]
ds5 = RubatoDataset(utt5, lab5, Tok(), train=True)          # 增强开 → tiling 会膨胀到 ≤40s
dm5 = RubatoDataModule(ds5, nasap_val=[], maestro_val=[], max_batch_sec=60.0)
budget_ok = True
loaded_ok = True
n_batches = 0
for batch in dm5.train_batches(epoch=1):
    n_batches += 1
    actual_sec = float(batch["audio_lens"].sum()) / 16000.0
    if actual_sec > 60.0 + 0.5:
        loaded_ok = False
        break
check("post_tiling_budget_respected", loaded_ok, actual_sec)
check("tiling_inflates_batches", n_batches >= 3, n_batches)   # 旧账法 20×1s=1 批;膨胀后必须分多批

print("[6] B×Lmax² 预算:长文本批被限条数(短音频长文本从这个口子爆显存)")
from rubato.model.train import bucket_batches
long_samples = [{"utt_id": f"u{i}", "dialect": "AMT", "dur_s": 2.0, "tok": 1024}
                for i in range(30)]
bs = bucket_batches(long_samples, max_batch_sec=600.0, max_attn_sq=8 * 1024 * 1024)
check("attn_cap_bites", all(len(b) <= 8 for b in bs), [len(b) for b in bs])
check("attn_cap_all_kept", sum(len(b) for b in bs) == 30)
bs2 = bucket_batches(long_samples, max_batch_sec=600.0, max_attn_sq=None)
check("attn_cap_optional", len(bs2) == 1, len(bs2))           # 不传 = 旧行为

print(f"\n全部通过: {PASS} 项")
