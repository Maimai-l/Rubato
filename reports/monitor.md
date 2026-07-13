# 训练监控

## 2026-07-13 13:00 — 全量训练启动（tiling 修复后）
- PID 17776, GPU 13-16 GB, 52°C

## 13:00-15:48 — 训练正常
- step 1: loss=252.8, sem=9.14
- step 1000: loss=119.2, sem=4.68
- 无 OOM
- 超长过滤: TAST=5,389, A2S=6,005, A2S_lite=5,369, AMT=0

## 15:48 — step 1000 eval: 自动暂停
```
parseable_rate = 0.00 < 0.80 → stopped:pause_unparseable
Chunking is disabled — 推理胶水需适配
```
训练正常、胶水签名需改。等规划端修 `infer_a2s` 的 batch_size=1 处理。
