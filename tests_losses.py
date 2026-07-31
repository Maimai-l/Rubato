"""S11 loss 三件套 + 采样 + tiling 测试(纯数学,沙盒完整验证)。运行: python tests_losses.py"""
import sys, torch
sys.path.insert(0, ".")
from rubato.model.losses import (
    batch_sequence_loss, ordinal_smoothing_targets,
)
from rubato.model.sampling import dialect_sampler, tiling_offset, DIALECT_MIX

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] 序数平滑分布(R-S11.1)")
q = ordinal_smoothing_targets(100, n_bins=4000, p_center=0.9, w=5)
check("center_090", abs(q[100].item() - 0.9) < 1e-6, q[100].item())
check("sums_to_1", abs(q.sum().item() - 1.0) < 1e-5, q.sum().item())
check("neighbor_decay", q[101] > q[102] > q[103] > q[104] > q[105], "衰减")
check("symmetric", abs(q[99].item() - q[101].item()) < 1e-6)
check("beyond_w_zero", q[106].item() == 0 and q[94].item() == 0)
# 二次衰减:权重比应是 (5:4:3:2:1)²
check("quadratic", abs(q[101]/q[105] - 25.0) < 0.1, (q[101]/q[105]).item())

print("[2] 边界截断归一化")
q0 = ordinal_smoothing_targets(2, n_bins=4000, w=5)   # 左边界截断
check("boundary_still_sums_1", abs(q0.sum().item() - 1.0) < 1e-5, q0.sum().item())
check("boundary_center_preserved", abs(q0[2].item() - 0.9) < 1e-6)

print("[3] 唯一生产 loss:语义/时间戳分流 + 1/sqrt(T)")
# V=8，其中 token 6/7 是两个时间戳 bin。两条等长序列，逐位置都必须进入
# batch_sequence_loss；这是 train.py 真正 backward 的唯一入口。
torch.manual_seed(0)
raw = torch.randn(2, 4, 8, requires_grad=True)
logp = raw.log_softmax(-1)
labels = torch.tensor([[1, 6, 2, 7], [3, 4, 5, 1]])
types = torch.tensor([[0, 1, 0, 1], [0, 0, 0, 0]])
mask = torch.ones(2, 4, dtype=torch.bool)
bins = torch.tensor([[0, 0, 0, 1], [0, 0, 0, 0]])
parts = batch_sequence_loss(
    logp, labels, types, mask, bins, torch.tensor([6, 7]),
    label_smoothing=0.1, p_center=0.9, w=1)
check("production_loss_finite",
      torch.isfinite(parts["loss"]) and parts["loss"].item() > 0, parts)
check("production_counts", (parts["n_sem"], parts["n_ts"]) == (6, 2), parts)
parts["loss"].backward()
check("production_loss_has_grad",
      raw.grad is not None and torch.isfinite(raw.grad).all())

print("[4] 生产 loss 的序列长度归一精确口径")
# 均匀分布时每 token CE=log(V)。长度 1/4 的序列贡献分别 log(V)、2log(V)，
# batch mean = 1.5log(V)。
uniform = torch.full((2, 4, 8), -torch.log(torch.tensor(8.0)))
mask_len = torch.tensor([[1, 0, 0, 0], [1, 1, 1, 1]], dtype=torch.bool)
plain = batch_sequence_loss(
    uniform, labels, torch.zeros_like(types), mask_len, bins,
    torch.tensor([6, 7]), label_smoothing=0.0, w=1)
expected = 1.5 * torch.log(torch.tensor(8.0))
check("length_normalized",
      abs(plain["loss"].item() - expected.item()) < 1e-6,
      (plain["loss"].item(), expected.item()))

print("[5] dialect 采样按混比(R-S11.2)")
# 所有 utt 都可用全部 4 个 dialect → 分布应趋近混比
avail = {f"u{i}": ["A2S", "A2S_lite", "TAST", "AMT"] for i in range(4000)}
samp = dialect_sampler(avail, seed=1, epoch=0)
from collections import Counter
dist = Counter(d for _, d in samp)
total = sum(dist.values())
for dl, target in DIALECT_MIX.items():
    frac = dist[dl] / total
    check(f"mix_{dl}", abs(frac - target) < 0.03, f"{frac:.3f} vs {target}")

print("[6] 采样可复现")
s1 = dialect_sampler(avail, seed=1, epoch=0)
s2 = dialect_sampler(avail, seed=1, epoch=0)
check("sampler_reproducible", s1 == s2)
s3 = dialect_sampler(avail, seed=1, epoch=1)   # 不同 epoch 应不同
check("sampler_epoch_varies", s1 != s3)

print("[7] tiling 偏移(R-S11.3)")
# A2S 不 tiling
check("a2s_no_tiling", tiling_offset("A2S", 10.0, "u1", 0, 1) == 0.0)
# TAST tiling 在 [0, 40-dur]
off = tiling_offset("TAST", 25.0, "u1", 0, 1)
check("tast_tiling_range", 0 <= off <= 15.0, off)
# dur>=40 无空间
check("full_dur_no_room", tiling_offset("TAST", 40.0, "u1", 0, 1) == 0.0)
# 可复现 + epoch 变化
o1 = tiling_offset("TAST", 20.0, "u1", 0, 1)
o2 = tiling_offset("TAST", 20.0, "u1", 0, 1)
o3 = tiling_offset("TAST", 20.0, "u1", 1, 1)
check("tiling_reproducible", o1 == o2 and o1 != o3)

print(f"\n全部通过: {PASS} 项")
