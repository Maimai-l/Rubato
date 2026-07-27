"""断点续训快照回归:全状态往返(模型/优化器/调度器/进度)、原子写、损坏兜底。
运行: python tests_resume.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import torch
import torch.nn as nn

from rubato.model.train import build_optimizer, save_snapshot, load_snapshot, apply_cfg_lrs

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


class M(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Linear(4, 4)      # 命中 build_optimizer 的 encoder 组
        self.decoder = nn.Linear(4, 4)


def mk():
    torch.manual_seed(0)
    m = M()
    opt, sched = build_optimizer(m, {"warmup_steps": 10, "max_steps": 100})
    return m, opt, sched


tmp = Path(tempfile.mkdtemp())
snap = tmp / "last.pt"

print("[1] 训 7 步存快照 → 新实例恢复:权重/优化器动量/lr 进度/step/epoch 全一致")
m1, opt1, sched1 = mk()
for _ in range(7):
    loss = m1.encoder(torch.randn(2, 4)).sum() + m1.decoder(torch.randn(2, 4)).sum()
    loss.backward()
    opt1.step()
    sched1.step()
    opt1.zero_grad()
save_snapshot(snap, m1, opt1, sched1, step=7, epoch=2, batch_cursor=11)
check("snapshot_written", snap.exists() and not snap.with_suffix(".tmp").exists())

m2, opt2, sched2 = mk()
got = load_snapshot(snap, m2, opt2, sched2)
check("restore_progress", got == (7, 2, 11), got)
check("weights_equal", all(torch.equal(a, b) for a, b in
                           zip(m1.state_dict().values(), m2.state_dict().values())))
check("lr_equal", abs(opt1.param_groups[0]["lr"] - opt2.param_groups[0]["lr"]) < 1e-12,
      (opt1.param_groups[0]["lr"], opt2.param_groups[0]["lr"]))
s1 = opt1.state_dict()["state"]
s2 = opt2.state_dict()["state"]
check("adam_momentum_equal",
      all(torch.equal(s1[k]["exp_avg"], s2[k]["exp_avg"]) for k in s1), "动量不一致")

print("[2] 恢复后继续训 3 步:两条时间线(不断 vs 断点续)逐位一致")
m3, opt3, sched3 = mk()
load_snapshot(snap, m3, opt3, sched3)
torch.manual_seed(42)
for _ in range(3):
    loss = m1.encoder(torch.randn(2, 4)).sum() + m1.decoder(torch.randn(2, 4)).sum()
    loss.backward()
    opt1.step(); sched1.step(); opt1.zero_grad()
torch.manual_seed(42)
for _ in range(3):
    loss = m3.encoder(torch.randn(2, 4)).sum() + m3.decoder(torch.randn(2, 4)).sum()
    loss.backward()
    opt3.step(); sched3.step(); opt3.zero_grad()
check("timelines_identical", all(torch.equal(a, b) for a, b in
                                 zip(m1.state_dict().values(), m3.state_dict().values())))

print("[3] 文件不存在 → None；损坏文件必须中止，绝不静默从头重训")
check("missing_none", load_snapshot(tmp / "nope.pt", *mk()) is None)
bad = tmp / "bad.pt"
bad.write_bytes(b"garbage")
try:
    load_snapshot(bad, *mk())
    corrupt_raised = False
except RuntimeError:
    corrupt_raised = True
check("corrupt_aborts", corrupt_raised)

print("[3b] 旧快照缺 cursor 默认拒绝；只有显式授权才从 epoch 头恢复")
legacy = tmp / "legacy.pt"
torch.save({"model": m1.state_dict(), "optimizer": opt1.state_dict(),
            "scheduler": sched1.state_dict(), "step": 10, "epoch": 3}, legacy)
try:
    load_snapshot(legacy, *mk())
    legacy_raised = False
except RuntimeError:
    legacy_raised = True
check("legacy_default_rejected", legacy_raised)
check("legacy_explicit_epoch_start",
      load_snapshot(legacy, *mk(), allow_legacy_cursor=True) == (10, 3, 0))

print("[4] CLI 改 lr 必须穿透快照:恢复后 apply_cfg_lrs 重刷,否则被旧快照静默还原")
m4 = M()
opt4, sched4 = build_optimizer(m4, {"lr_encoder": 1e-4, "lr_decoder": 3e-4,
                                    "warmup_steps": 10, "max_steps": 100})
load_snapshot(snap, m4, opt4, sched4)   # 快照里是默认 lr(enc 1e-4 / dec 5e-4)
restored_dec = opt4.param_groups[1]["initial_lr"]
check("snapshot_clobbers_cli_lr", abs(restored_dec - 5e-4) < 1e-12, restored_dec)  # 证明必须重刷
applied = apply_cfg_lrs(opt4, sched4, {"lr_encoder": 1e-4, "lr_decoder": 3e-4})
factor = sched4.lr_lambdas[1](sched4.last_epoch)
check("dec_lr_reapplied", abs(applied[1] - 3e-4 * factor) < 1e-12, (applied[1], factor))
check("base_lrs_reapplied", abs(sched4.base_lrs[1] - 3e-4) < 1e-12, sched4.base_lrs)
check("enc_lr_untouched", abs(sched4.base_lrs[0] - 1e-4) < 1e-12, sched4.base_lrs)
# cfg 与快照相同 → 数值无操作(默认续训行为不变)
m5, opt5, sched5 = mk()
load_snapshot(snap, m5, opt5, sched5)
before = [g["lr"] for g in opt5.param_groups]
apply_cfg_lrs(opt5, sched5, {})   # 默认 cfg = 快照里的值
check("noop_when_cfg_unchanged",
      all(abs(a - b) < 1e-12 for a, b in zip(before, (g["lr"] for g in opt5.param_groups))),
      (before, [g["lr"] for g in opt5.param_groups]))
# 快照+无操作重刷+3 步(seed 42)必须和测试[2]的 m3(快照+3 步,seed 42,无重刷)逐位一致:
# 重刷相同 lr 不得以任何方式扰动训练轨迹
torch.manual_seed(42)
for _ in range(3):
    (m5.encoder(torch.randn(2, 4)).sum() + m5.decoder(torch.randn(2, 4)).sum()).backward()
    opt5.step(); sched5.step(); opt5.zero_grad()
check("timeline_identical_after_noop_reapply",
      all(torch.equal(a, b) for a, b in zip(m3.state_dict().values(), m5.state_dict().values())))

print(f"\n全部通过: {PASS} 项")
