"""dataset.py 逻辑测试(mock tokenizer;真实音频/spm 需本地,见 LOCAL_VERIFICATION.md D)。
运行: python tests_dataset.py"""
import sys
import re
import numpy as np
sys.path.insert(0, ".")
import rubato.data.dataset as dataset_mod
from rubato.data.dataset import (
    encode_target, apply_tiling_text, collate_batch, N_BINS,
)
from rubato.model.build import DIALECT_PROMPT

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)


class MockTok:
    """
    确定性 mock:每个空格分隔的 piece 一个 id(不再子词切分),便于精确核对逻辑。
    id 分配:prompt/eot/时间戳给固定 id,其余按出现顺序。piece_to_id 稳定。
    """
    def __init__(self):
        self._map = {}
        self._next = 1000
        # 预留 prompt/eot
        for p in ["<|sot|>", "<|score|>", "<|noscore|>", "<|spell|>", "<|nospell|>",
                  "<|ts|>", "<|nots|>", "<|midi|>", "<|nomidi|>", "<|eot|>",
                  "<|real|>", "<|synth|>"]:
            self._alloc(p)

    def _alloc(self, p):
        if p not in self._map:
            self._map[p] = self._next
            self._next += 1
        return self._map[p]

    def encode(self, text, out_type=str, **kw):
        # 不做子词切分:按空格切,piece 即 token(时间戳 token 保持原子)
        assert out_type is str
        return [t for t in text.split(" ") if t]

    def piece_to_id(self, p):
        # 时间戳 token(秒·两位小数)→ 高位段 id = 1e6 + bin,便于反查 bin
        m = re.match(r"^<\|(\d+\.\d{2})\|>$", p)
        if m:
            return 1_000_000 + int(round(float(m.group(1)) * 100))
        return self._alloc(p)


print("[1] encode_target:token_types / ts_bins / loss_mask / 右移")
tok = MockTok()
# TAST 文本:两个单元各带一个时间戳
text = "|4/4k0PR:C4 <|0.05|> 1/1 <|1.50|>"
enc = encode_target(tok, "TAST", text, sample=False)
prompt = DIALECT_PROMPT["TAST"]
# 完整序列 = prompt(5) + label pieces + eot;右移后长度 = 完整-1
pieces = tok.encode(text)
full_len = len(prompt) + len(pieces) + 1
check("shift_len", len(enc["input_ids"]) == full_len - 1, f"{len(enc['input_ids'])} vs {full_len-1}")
check("labels_len_match", len(enc["labels"]) == len(enc["input_ids"]))
for k in ("token_types", "loss_mask", "ts_bins"):
    check(f"{k}_aligned", len(enc[k]) == len(enc["labels"]))

# 时间戳位置:labels 中值在 [40,40+N_BINS) 的位置,token_type 应为 1,ts_bin 对应
ts_positions = [i for i, t in enumerate(enc["labels"]) if t >= 1_000_000]
check("has_ts_positions", len(ts_positions) == 2, ts_positions)
for i in ts_positions:
    check(f"ts_type_1_at_{i}", enc["token_types"][i] == 1)
    check(f"ts_bin_matches_{i}", enc["ts_bins"][i] == enc["labels"][i] - 1_000_000,
          f"bin={enc['ts_bins'][i]} label={enc['labels'][i]}")
# 语义位置 token_type=0
sem_positions = [i for i in range(len(enc["labels"])) if i not in ts_positions]
check("sem_type_0", all(enc["token_types"][i] == 0 for i in sem_positions))

print("[2] prompt 位置 loss_mask=False(R-S10.4)")
# 右移后 labels = seq[1:];prompt 占 seq[0..4],labels 里 prompt 部分是 seq[1..4](4 个)
# 这些位置 loss_mask 应为 False
n_prompt_in_labels = len(prompt) - 1
check("prompt_masked", not any(enc["loss_mask"][:n_prompt_in_labels]),
      enc["loss_mask"][:n_prompt_in_labels])
# eot 位置(最后)应计入 loss
check("eot_in_loss", enc["loss_mask"][-1] is True or enc["loss_mask"][-1] == True)

print("[3] A2S 无时间戳 → 全 token_type 0")
enc_a2s = encode_target(tok, "A2S", "|4/4k0PR:C4 1/1 |4/4k0c4", sample=False)
check("a2s_no_ts", all(t == 0 for t in enc_a2s["token_types"]))
check("a2s_bins_zero", all(b == 0 for b in enc_a2s["ts_bins"]))

print("[4] tiling:时间戳整体 +t0,钳到上界")
shifted = apply_tiling_text("|4/4k0 <|0.05|> 1/1 <|1.50|>", t0_bins=100)
check("tiling_shifts", "<|1.05|>" in shifted and "<|2.50|>" in shifted, shifted)
clamped = apply_tiling_text("<|39.90|>", t0_bins=50)
check("tiling_clamps", "<|39.99|>" in clamped, clamped)
check("tiling_zero_noop", apply_tiling_text("<|0.05|>", 0) == "<|0.05|>")

print("[5] AMT domain 前缀")
enc_dom = encode_target(tok, "AMT", "N60<|vel:80|> <|0.03|>", sample=False, domain="real")
# domain 加在 prompt 末,loss_mask 仍 False;序列比无 domain 长 1
enc_nodom = encode_target(tok, "AMT", "N60<|vel:80|> <|0.03|>", sample=False)
check("domain_adds_token", len(enc_dom["input_ids"]) == len(enc_nodom["input_ids"]) + 1)

print("[5b] encode_target 必须调用唯一目标序列构造器")
_real_builder = dataset_mod.build_target_sequence
_calls = []
def _spy_builder(dialect, label_pieces, domain=None):
    _calls.append((dialect, list(label_pieces), domain))
    return _real_builder(dialect, label_pieces, domain)
dataset_mod.build_target_sequence = _spy_builder
try:
    dataset_mod.encode_target(tok, "A2S", "C4 1/4", sample=False, domain="synth")
finally:
    dataset_mod.build_target_sequence = _real_builder
check("production_builder_called",
      len(_calls) == 1 and _calls[0][0] == "A2S" and _calls[0][2] == "synth",
      _calls)

print("[6] collate:padding + batch 契约键")
def mk_item(L, S):
    return {"audio": np.ones(S, dtype="float32"),
            "utt_id": f"u{L}",
            "input_ids": list(range(1, L + 1)), "labels": list(range(2, L + 2)),
            "token_types": [0] * L, "loss_mask": [True] * L, "ts_bins": [0] * L}
batch = collate_batch([mk_item(5, 100), mk_item(8, 160), mk_item(3, 80)])
import torch
for k in ("audio", "audio_lens", "input_ids", "input_lens", "labels",
          "token_types", "loss_mask", "ts_bins"):
    check(f"has_{k}", k in batch)
check("batch_B", batch["input_ids"].shape[0] == 3)
check("batch_Lmax", batch["input_ids"].shape[1] == 8, batch["input_ids"].shape)
check("audio_Smax", batch["audio"].shape[1] == 160)
check("input_lens", batch["input_lens"].tolist() == [5, 8, 3])
check("utt_ids_preserved", batch["utt_ids"] == ["u5", "u8", "u3"])
# padding 位 loss_mask=False
check("pad_masked", not batch["loss_mask"][2, 3:].any())
check("input_labels_same_shape", batch["input_ids"].shape == batch["labels"].shape)

print(f"\n全部通过: {PASS} 项")
print("注:真实 FLAC/Opus 解码、spm 真实模型、tiling×预设链次序需本地验证(LOCAL_VERIFICATION.md D);")
print("    token_types/ts_bins/loss_mask/右移/tiling/collate 逻辑沙盒已验证。")
