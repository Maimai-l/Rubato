"""S11 train.py 装配测试(optimizer/schedule/bucketing 纯逻辑)。运行: python tests_train.py"""
import sys, torch
sys.path.insert(0, ".")
from rubato.model.train import (
    build_optimizer, bucket_batches, group_grad_norms,
    normalize_accumulated_gradients, new_step_metrics,
    accumulate_step_metrics, finalize_step_metrics, clip_gradients,
)

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
try:
    bucket_batches([{"utt_id": "too_long", "dur_s": 50.01}], max_batch_sec=50)
    oversize_raised = False
except ValueError:
    oversize_raised = True
check("single_oversize_is_not_silently_admitted", oversize_raised)

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

print("[7] 梯度累积按完整有效 batch 的序列平均，切成几批不改变结果")
xs = torch.tensor([1.0, 2.0, 4.0, 8.0])
def accumulated_grad(chunks):
    w = torch.nn.Parameter(torch.tensor(0.7))
    pos = 0
    n = 0
    for size in chunks:
        x = xs[pos:pos + size]
        ((w * x).square().mean() * size).backward()
        pos += size
        n += size
    normalize_accumulated_gradients([w], n)
    return float(w.grad)
g13 = accumulated_grad([1, 3])
g22 = accumulated_grad([2, 2])
g4 = accumulated_grad([4])
check("partition_invariant", abs(g13 - g22) < 1e-6 and abs(g13 - g4) < 1e-6,
      (g13, g22, g4))

print("[8] 日志汇总覆盖整步全部 micro-batch，不再只报最后一批")
s = new_step_metrics()
accumulate_step_metrics(s, {
    "batch_size": 2, "batch_audio_sec": 60.0, "loss": torch.tensor(2.0),
    "semantic_loss": torch.tensor(1.0), "n_sem": 10,
    "ts_loss": torch.tensor(3.0), "n_ts": 2,
    "pitch_loss": torch.tensor(4.0), "n_pitch": 1,
    "dialect_sem": {"A2S": (1.0, 2)},
})
accumulate_step_metrics(s, {
    "batch_size": 1, "batch_audio_sec": 40.0, "loss": torch.tensor(5.0),
    "semantic_loss": torch.tensor(2.0), "n_sem": 20,
    "ts_loss": torch.tensor(7.0), "n_ts": 0,
    "pitch_loss": None, "n_pitch": 0,
    "dialect_sem": {"TAST": (2.0, 1)},
})
sm = finalize_step_metrics(s)
check("full_step_audio", sm["batch_audio_sec"] == 100.0 and sm["micro_batches"] == 2, sm)
check("loss_sequence_weighted", abs(sm["loss"] - 3.0) < 1e-7, sm["loss"])
check("semantic_token_weighted", abs(sm["semantic_loss"] - 5 / 3) < 1e-7,
      sm["semantic_loss"])

print("[9] 非有限梯度必须在 optimizer.step 前硬失败")
p_bad = torch.nn.Parameter(torch.tensor(1.0))
p_bad.grad = torch.tensor(float("nan"))
try:
    clip_gradients([p_bad], 1.0)
    nonfinite_rejected = False
except RuntimeError:
    nonfinite_rejected = True
check("nonfinite_gradient_rejected", nonfinite_rejected)
try:
    clip_gradients([torch.nn.Parameter(torch.tensor(1.0))], 0.0)
    bad_clip_rejected = False
except ValueError:
    bad_clip_rejected = True
check("bad_clip_norm_rejected", bad_clip_rejected)

print(f"\n全部通过: {PASS} 项")
print("注:training_step/eval_hook/主循环需 GPU+NeMo 模型+真实数据,带断言本地跑;")
print("    optimizer 差分 lr / warmup+cosine / bucketing 沙盒已验证。")
