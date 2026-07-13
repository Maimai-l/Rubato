"""断点续训快照回归:全状态往返(模型/优化器/调度器/进度)、原子写、损坏兜底。
运行: python tests_resume.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import torch
import torch.nn as nn

from rubato.model.train import build_optimizer, save_snapshot, load_snapshot

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
save_snapshot(snap, m1, opt1, sched1, step=7, epoch=2)
check("snapshot_written", snap.exists() and not snap.with_suffix(".tmp").exists())

m2, opt2, sched2 = mk()
got = load_snapshot(snap, m2, opt2, sched2)
check("restore_progress", got == (7, 2), got)
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

print("[3] 兜底:文件不存在 → None;损坏文件 → None 不炸")
check("missing_none", load_snapshot(tmp / "nope.pt", *mk()) is None)
bad = tmp / "bad.pt"
bad.write_bytes(b"garbage")
check("corrupt_none", load_snapshot(bad, *mk()) is None)

print(f"\n全部通过: {PASS} 项")
