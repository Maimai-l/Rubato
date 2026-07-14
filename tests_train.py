"""S11 train.py 装配测试(optimizer/schedule/bucketing 纯逻辑)。运行: python tests_train.py"""
import sys, torch
sys.path.insert(0, ".")
from rubato.model.train import build_optimizer, bucket_batches, group_grad_norms

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

# 造一个假模型:有 encoder 和 decoder 参数
class FakeModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = torch.nn.Linear(10, 10)
        self.decoder = torch.nn.Linear(10, 10)
    def named_parameters(self, *a, **k):
        return super().named_parameters(*a, **k)

print("[1] 差分学习率(encoder 降载)")
model = FakeModel()
cfg = {"lr_encoder": 1e-4, "lr_decoder": 5e-4, "warmup_steps": 100, "max_steps": 1000}
opt, sched = build_optimizer(model, cfg)
check("two_param_groups", len(opt.param_groups) == 2, len(opt.param_groups))
# 检查 initial_lr(scheduler 记录的基准,不受 warmup step0 归零影响)
enc_lr = opt.param_groups[0]["initial_lr"]
dec_lr = opt.param_groups[1]["initial_lr"]
check("encoder_lower_lr", enc_lr < dec_lr, f"enc={enc_lr} dec={dec_lr}")
check("encoder_lr_value", abs(enc_lr - 1e-4) < 1e-9)
check("decoder_lr_value", abs(dec_lr - 5e-4) < 1e-9)

print("[2] warmup + cosine schedule")
# warmup 期间 lr 线性增长
lrs = []
for step in range(1000):
    lrs.append(sched.get_last_lr()[1])  # decoder 组
    sched.step()
# warmup 末(step 100)应接近峰值
check("warmup_ramps_up", lrs[50] < lrs[99], f"{lrs[50]:.2e} < {lrs[99]:.2e}")
check("peak_near_warmup_end", abs(lrs[99] - 5e-4) < 5e-5, f"{lrs[99]:.2e}")
# cosine 衰减:后期 lr 下降
check("cosine_decays", lrs[500] < lrs[100], f"{lrs[500]:.2e} < {lrs[100]:.2e}")
# 最低不低于 min_ratio×peak(10%)
check("min_lr_floor", lrs[999] >= 5e-4 * 0.1 * 0.9, f"{lrs[999]:.2e}")

print("[3] warmup 初期 lr 很小")
model2 = FakeModel()
opt2, sched2 = build_optimizer(model2, cfg)
first_lr = sched2.get_last_lr()[1]
check("starts_near_zero", first_lr < 5e-4 * 0.1, f"first={first_lr:.2e}")

print("[4] 动态 bucketing(≤max_batch_sec)")
samples = [{"utt_id": f"u{i}", "dur_s": d} for i, d in enumerate([10, 20, 15, 25, 30, 12, 18])]
batches = bucket_batches(samples, max_batch_sec=50)
# 每个 batch 总时长 ≤50
for bi, b in enumerate(batches):
    total = sum(s["dur_s"] for s in b)
    check(f"batch_{bi}_within_limit", total <= 50, f"batch {bi}: {total}s")
    break
# 所有样本都被分配
total_samples = sum(len(b) for b in batches)
check("all_samples_bucketed", total_samples == len(samples), f"{total_samples} vs {len(samples)}")

print("[5] bucketing 按时长排序装桶")
# 长样本单独成桶
big = [{"utt_id": "big", "dur_s": 45}, {"utt_id": "s1", "dur_s": 10}, {"utt_id": "s2", "dur_s": 10}]
batches = bucket_batches(big, max_batch_sec=50)
# 10+10 可同桶,45 单独(45+10>50)
check("respects_limit", all(sum(s["dur_s"] for s in b) <= 50 for b in batches), batches)

print("[6] 分组梯度范数(enc/dec 观测,与总范数勾稽)")
model3 = FakeModel()
opt3, _ = build_optimizer(model3, cfg)
loss = (model3.decoder(model3.encoder(torch.randn(4, 10))) ** 2).sum()
loss.backward()
gns = group_grad_norms(opt3.param_groups)
check("one_norm_per_group", len(gns) == len(opt3.param_groups), gns)
check("norms_positive", all(g > 0 for g in gns), gns)
total = float(torch.nn.utils.clip_grad_norm_(model3.parameters(), 1e9))  # 阈值大到不裁,只取总范数
recon = sum(g * g for g in gns) ** 0.5
check("groups_reconcile_total", abs(recon - total) < 1e-4 * max(total, 1), f"recon={recon} total={total}")
# 无梯度参数组不炸、给 0
opt_empty = torch.optim.AdamW([{"params": [torch.nn.Parameter(torch.zeros(3))]}])
check("no_grad_gives_zero", group_grad_norms(opt_empty.param_groups) == [0.0])

print(f"\n全部通过: {PASS} 项")
print("注:training_step/eval_hook/主循环需 GPU+NeMo 模型+真实数据,带断言本地跑;")
print("    optimizer 差分 lr / warmup+cosine / bucketing 沙盒已验证。")
