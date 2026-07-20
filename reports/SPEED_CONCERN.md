# 训练速度问题

## 现状

每 50 步间隔需 20-30 分钟。两个原因叠加：

1. **梯度累积** `grad_accum_to_audio_sec=2000` / `max_batch_sec=60` = **33:1**——每步 optimizer step 需 33 次 fwd+bwd，约 66 秒/步，50 步 = 55 分钟(理想情况)。实际 20-30 分钟说明部分 batch 更短/GPU 打不满。
2. **WDDM 共享内存**——16GB 物理显存，PyTorch 分配 28-29GB，13GB 走系统 RAM。Conformer attention 在系统 RAM 上慢 10x。

## 不做决定，仅提问

- `grad_accum_to_audio_sec` 降到 1000 有没有训练质量风险？54000 步训了太久。
- 有没有减 encoder 内存占用的办法(gradient checkpointing/减小 conformer 层数)？

训练在跑，不阻塞。
