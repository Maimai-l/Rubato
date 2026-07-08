"""S11 loss 三件套 + 采样 + tiling 测试(纯数学,沙盒完整验证)。运行: python tests_losses.py"""
import sys, torch
sys.path.insert(0, ".")
from rubato.model.losses import (
    ordinal_smoothing_targets, timestamp_loss, semantic_loss, sequence_loss,
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

print("[3] 时间戳 loss")
torch.manual_seed(0)
logits = torch.randn(4, 4000)
targets = torch.tensor([100, 200, 50, 3999])
tl = timestamp_loss(logits, targets)
check("ts_loss_positive", tl.item() > 0)
check("ts_loss_finite", torch.isfinite(tl))
# 完美预测(logit 集中在目标)应 loss 更低
logits_good = torch.full((1, 4000), -10.0); logits_good[0, 100] = 10.0
tl_good = timestamp_loss(logits_good, torch.tensor([100]))
tl_bad = timestamp_loss(torch.zeros(1, 4000), torch.tensor([100]))
check("ts_good_lower", tl_good < tl_bad, f"{tl_good.item()} vs {tl_bad.item()}")

print("[4] 语义 loss(label smoothing)")
sl = semantic_loss(torch.randn(8, 3571), torch.randint(0, 3571, (8,)))
check("sem_loss_positive", sl.item() > 0 and torch.isfinite(sl))

print("[5] 序列级长度归一化(R-S11.1)")
# 两条序列,长度差 100 倍,归一化后长序列不应主导
ce = torch.tensor([10.0, 100.0])          # 短序列 CE 和=10,长序列=100
lens = torch.tensor([5, 500])             # |T|=5, 500
L = sequence_loss(ce, lens)
# 归一化:10/√5=4.47, 100/√500=4.47 → 两者贡献相当
norm0 = 10.0 / (5 ** 0.5)
norm1 = 100.0 / (500 ** 0.5)
check("length_normalized", abs(norm0 - norm1) < 0.01, f"{norm0} vs {norm1}")
check("seq_loss_is_mean", abs(L.item() - (norm0 + norm1) / 2) < 0.01, L.item())

print("[6] dialect 采样按混比(R-S11.2)")
# 所有 utt 都可用全部 4 个 dialect → 分布应趋近混比
avail = {f"u{i}": ["A2S", "A2S_lite", "TAST", "AMT"] for i in range(4000)}
samp = dialect_sampler(avail, seed=1, epoch=0)
from collections import Counter
dist = Counter(d for _, d in samp)
total = sum(dist.values())
for dl, target in DIALECT_MIX.items():
    frac = dist[dl] / total
    check(f"mix_{dl}", abs(frac - target) < 0.03, f"{frac:.3f} vs {target}")

print("[7] 采样可复现")
s1 = dialect_sampler(avail, seed=1, epoch=0)
s2 = dialect_sampler(avail, seed=1, epoch=0)
check("sampler_reproducible", s1 == s2)
s3 = dialect_sampler(avail, seed=1, epoch=1)   # 不同 epoch 应不同
check("sampler_epoch_varies", s1 != s3)

print("[8] tiling 偏移(R-S11.3)")
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
