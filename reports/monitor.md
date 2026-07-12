# 训练监控

## 00:42 — Smoke 通过
- final_sem=0.038 < 0.05 ✅
- 直接开全量

## 00:42 — 全量 OOM（跑 batch 太大）
- 超长过滤: AMT=18,527 TAST=5,389 A2S=6,005 A2S_lite=5,369
- OOM: 560s/batch → 降 150s

## 01:25 — 全量 OOM（150s/batch 跑 649 步）
- step 600: loss=2.37, sem=0.068, ts=8.98
- OOM at step 649 (self_attn)
- 降至 100s/batch, 需要 GPU 重启清内存

## 当前
- 无进程存活
- 等 GPU 重启后跑 `build_dataset.py` (max_batch_sec=100)
