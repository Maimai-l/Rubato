"""分方言损失曲线回归(用户建议):collate 带 dialect、逐序列 sem/ts、按方言聚合正确。
运行: python tests_dialect_loss.py"""
import sys

sys.path.insert(0, ".")
import torch
import torch.nn as nn

from rubato.data.dataset import collate_batch
from rubato.model.losses import batch_sequence_loss
from rubato.model.train import training_step_logic

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


V = 32

print("[1] collate 携带 dialects(list,不进张量搬运)")
items = [{"audio": [0.0] * 80, "input_ids": [1, 2], "labels": [2, 3],
          "token_types": [0, 0], "loss_mask": [True, True], "ts_bins": [0, 0],
          "dialect": d} for d in ("A2S", "AMT", "A2S")]
batch = collate_batch(items)
check("dialects_carried", batch["dialects"] == ["A2S", "AMT", "A2S"], batch.get("dialects"))

print("[2] batch_sequence_loss 逐序列 sem/ts:掩码正确、无戳序列 has_ts=False")
B, L = 3, 4
lp = torch.log_softmax(torch.randn(B, L, V), dim=-1)
labels = torch.randint(0, V, (B, L))
types = torch.zeros(B, L, dtype=torch.long)
types[1, 2] = 1                                    # 只有第 1 条有时间戳位
mask = torch.ones(B, L, dtype=torch.bool)
bins = torch.zeros(B, L, dtype=torch.long)
ts_ids = torch.arange(16, dtype=torch.long)
parts = batch_sequence_loss(lp, labels, types, mask, bins, ts_ids)
check("seq_sem_shape", parts["seq_sem"].shape == (B,))
check("has_ts_flags", parts["seq_has_ts"].tolist() == [False, True, False])
# 第 0 条全语义:seq_sem = 该行逐 token NLL 均值(与手算一致)
nll0 = -(lp[0].gather(-1, labels[0].unsqueeze(-1)).squeeze(-1))
smooth0 = -lp[0].sum(-1) / V
manual0 = (0.9 * nll0 + 0.1 * smooth0).mean()
check("seq_sem_value", abs(float(parts["seq_sem"][0]) - float(manual0)) < 1e-5,
      (float(parts["seq_sem"][0]), float(manual0)))

print("[3] training_step_logic 按方言聚合:均值/条数正确,加权合成 = 总体")


class Stub(nn.Module):
    def __init__(self):
        super().__init__()
        self.w = nn.Parameter(torch.zeros(1))

    def parameters(self, *a, **k):
        return iter([self.w])

    def preprocessor(self, input_signal, length):
        return input_signal, length

    def forward(self, processed_signal, processed_signal_length, transcript, transcript_length):
        B2, L2 = transcript.shape
        logits = torch.zeros(B2, L2, V) + self.w    # 带梯度
        return torch.log_softmax(logits, dim=-1)    # Tensor 形态(resolve_log_probs 支持)


S = 80
mkrow = lambda d: {"audio": [0.0] * S, "input_ids": [1, 2, 3], "labels": [2, 3, 4],
                   "token_types": [0, 0, 1], "loss_mask": [True] * 3, "ts_bins": [0, 0, 5],
                   "dialect": d}
batch3 = collate_batch([mkrow("A2S"), mkrow("A2S"), mkrow("TAST"), mkrow("AMT")])
ts_ids2 = torch.arange(10, dtype=torch.long)
parts3 = training_step_logic(Stub(), batch3, None, ts_token_ids=ts_ids2,
                             guards={"vocab": V, "max_pos": 512})
ds = parts3["dialect_sem"]
check("dialect_keys", set(ds) == {"A2S", "TAST", "AMT"}, ds)
check("dialect_counts", ds["A2S"][1] == 2 and ds["TAST"][1] == 1 and ds["AMT"][1] == 1, ds)
total_n = sum(n for _, n in ds.values())
weighted = sum(v * n for v, n in ds.values()) / total_n
# 均匀 logits 下逐条 sem 相同 → 加权合成应等于任一条(自洽)
check("weighted_consistent", abs(weighted - ds["A2S"][0]) < 1e-6, (weighted, ds))
check("dialect_ts_only_ts_rows", set(parts3["dialect_ts"]) == {"A2S", "TAST", "AMT"},
      parts3["dialect_ts"])   # 每条都有 1 个 ts 位(构造如此)
check("loss_has_grad", parts3["loss"].requires_grad)

print(f"\n全部通过: {PASS} 项")
