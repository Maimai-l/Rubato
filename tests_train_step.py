"""训练步回归测试(修复问题#1:NeMo forward 返回元组导致静默零 loss)。
运行: python tests_train_step.py"""
import sys
import torch
sys.path.insert(0, ".")

from rubato.model.losses import (
    ordinal_smoothing_targets, batch_sequence_loss, _per_token_semantic_nll,
    _per_token_ordinal_nll,
)
from rubato.model.train import training_step_logic, resolve_log_probs

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

V, NBINS, W = 64, 16, 5          # 小词表便于沙盒验证;时间戳 token 占 id 40..55
TS_IDS = torch.arange(40, 40 + NBINS)

print("[1] 向量化序数 NLL == 参考实现(逐 bin 对照)")
torch.manual_seed(0)
logits = torch.randn(6, V)
logp = torch.log_softmax(logits, dim=-1)
bins = torch.tensor([0, 3, 8, 14, 15, 1])          # 含两侧边界截断
vec = _per_token_ordinal_nll(logp, bins, TS_IDS, p_center=0.9, w=W)
for i in range(6):
    q = ordinal_smoothing_targets(int(bins[i]), n_bins=NBINS, p_center=0.9, w=W)
    ref = -(q * logp[i, TS_IDS]).sum()
    check(f"ordinal_match_bin{int(bins[i])}", abs(vec[i].item() - ref.item()) < 1e-5,
          f"{vec[i].item()} vs {ref.item()}")

print("[2] 语义 NLL == F.cross_entropy(label_smoothing=0.1)")
tgt = torch.randint(0, V, (8,))
lp2 = torch.log_softmax(torch.randn(8, V), dim=-1)
mine = _per_token_semantic_nll(lp2, tgt, 0.1)
ref = torch.nn.functional.cross_entropy(lp2, tgt, label_smoothing=0.1, reduction="none")
# cross_entropy 直接吃 log_probs 等价于吃 logits(log_softmax 幂等)
check("semantic_match", torch.allclose(mine, ref, atol=1e-5),
      f"{mine[:3]} vs {ref[:3]}")

print("[3] 1/√|T| 序列归一(短序列不被长序列淹没)")
B, L = 2, 10
lp3 = torch.log_softmax(torch.randn(B, L, V), dim=-1)
labels = torch.randint(0, 40, (B, L))
types = torch.zeros(B, L, dtype=torch.long)
tsb = torch.zeros(B, L, dtype=torch.long)
mask = torch.zeros(B, L, dtype=torch.bool)
mask[0, :2] = True                  # 序列0 只有 2 个有效 token
mask[1, :] = True                   # 序列1 有 10 个
parts = batch_sequence_loss(lp3, labels, types, mask, tsb, TS_IDS)
# 手工:每序列 masked CE 求和 × T^-0.5,取均值
per_tok = torch.nn.functional.cross_entropy(
    lp3.reshape(-1, V), labels.reshape(-1), label_smoothing=0.1,
    reduction="none").reshape(B, L)
ce0 = per_tok[0, :2].sum() * (2 ** -0.5)
ce1 = per_tok[1, :].sum() * (10 ** -0.5)
manual = (ce0 + ce1) / 2
check("seq_norm_match", abs(parts["loss"].item() - manual.item()) < 1e-4,
      f"{parts['loss'].item()} vs {manual.item()}")

print("[4] prompt mask:mask=False 位置不影响 loss")
lp4 = lp3.clone()
labels4 = labels.clone()
labels4[0, 5:] = 63                 # 改动 mask 外位置
mask4 = mask.clone()
p1 = batch_sequence_loss(lp3, labels, types, mask4, tsb, TS_IDS)
p2 = batch_sequence_loss(lp4, labels4, types, mask4, tsb, TS_IDS)
check("masked_positions_ignored", abs(p1["loss"].item() - p2["loss"].item()) < 1e-6)

print("[5] resolve_log_probs:元组/dict/Tensor/未知")
t = torch.randn(1, 2, V)
check("tuple_first", resolve_log_probs((t, None, None, None)) is t)
check("dict_logprobs", resolve_log_probs({"log_probs": t}) is t)
check("bare_tensor", resolve_log_probs(t) is t)
try:
    resolve_log_probs("garbage")
    check("unknown_raises", False, "应抛 TypeError")
except TypeError:
    check("unknown_raises", True)

print("[6] 端到端:mock NeMo 模型(forward 返回 4 元组)梯度可回传 —— 问题#1 回归")
class MockPreprocessor(torch.nn.Module):
    def forward(self, input_signal, length):
        # (B, S) → (B, 8, S//160) 假 mel
        B, S = input_signal.shape
        return input_signal.new_zeros(B, 8, max(S // 160, 1)), length // 160
    def __call__(self, *, input_signal, length):
        return self.forward(input_signal, length)

class MockNemo(torch.nn.Module):
    """模仿 EncDecMultiTaskModel:forward 返回 (log_probs, enc_len, enc_states, enc_mask)。"""
    def __init__(self):
        super().__init__()
        self.preprocessor = MockPreprocessor()
        self.emb = torch.nn.Embedding(V, 16)
        self.out = torch.nn.Linear(16, V)
    def forward(self, processed_signal=None, processed_signal_length=None,
                transcript=None, transcript_length=None):
        h = self.emb(transcript)
        logp = torch.log_softmax(self.out(h), dim=-1)
        return logp, processed_signal_length, None, None

class MockTok:
    def piece_to_id(self, p):
        # "<|tN|>" → 40+N;其余 0
        if p.startswith("<|t") and p.endswith("|>"):
            return 40 + int(p[3:-2])
        return 0
    def unk_id(self):
        return -1

model = MockNemo()
B, L = 2, 12
full = torch.randint(0, 40, (B, L + 1))
full[:, 6] = 45                      # 一个时间戳 token(bin 5)
batch = {
    "audio": torch.randn(B, 16000),
    "audio_lens": torch.tensor([16000, 16000]),
    "input_ids": full[:, :-1],
    "input_lens": torch.tensor([L, L]),
    "labels": full[:, 1:],
    "token_types": (full[:, 1:] >= 40).long(),
    "loss_mask": torch.ones(B, L, dtype=torch.bool),
    "ts_bins": (full[:, 1:] - 40).clamp(min=0),
}
ts_ids = torch.arange(40, 40 + NBINS)
parts = training_step_logic(model, batch, MockTok(), ts_token_ids=ts_ids)
check("loss_positive", parts["loss"].item() > 0, parts["loss"].item())
check("loss_has_grad", parts["loss"].requires_grad)
parts["loss"].backward()
gnorm = sum(p.grad.abs().sum().item() for p in model.parameters() if p.grad is not None)
check("gradients_flow", gnorm > 0, f"grad_norm={gnorm}")
check("ts_counted", parts["n_ts"] == 2, parts["n_ts"])   # 每条序列 1 个时间戳位置

print(f"\n全部通过: {PASS} 项")
