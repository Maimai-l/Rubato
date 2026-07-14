# 训练监控 2026-07-13/14

## 训练最终状态 — 已暂停

**StopController 触发：** `parseable_rate=0.00 < 0.80`

| 指标 | 值 |
|------|-----|
| final_step | 4000 |
| final_loss | 69.62 |
| final_sem | 3.39 |
| final_ts | 2.36 |
| parseable_rate | 0.00 |

## 关键事件时间线

1. tiling 修复前：39s batch OOM（padding 记账 bug）
2. tiling 修复后：训练正常，GPU 13-16 GB 稳定
3. Tee-Object 卡死 → 换 `>` 重定向
4. step 3000 eval：parseable=0.00，但放行（<4000 宽限）
5. step 4000 eval：parseable=0.00，StopController 正式暂停

## 根因

`parseable_rate=0.00` — infer_a2s 胶水在 Windows/NeMo 上不工作。
训练本身正常（sem 9→3, loss 252→69）。

## AMT

AMT 丢弃 32,930→0（重切窗 144k 后）。超长过滤仅剩 TAST/A2S/A2S_lite。

## 阻塞

等规划端修 `rubato/model/infer.py` 的 NeMo transcribe 适配后继续。
