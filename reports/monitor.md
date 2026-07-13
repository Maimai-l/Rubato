# 训练监控

## Step 3000 eval — 疑似卡死
- 时间: 2026-07-13 23:30 ~ 00:30+
- GPU: 92-95% 持续满载, 15.9 GB
- 进程: 存活 (PID 9740, 6.37 GB)
- Log: 冻结在 step 3000 loss 行 (10,183 bytes), 无 eval 输出
- 症状: eval 阶段 GPU 持续满载但超过 30 分钟无任何 parseable/empty/收尾输出
- 推测: NeMo transcribe 在 nASAP val 上死循环或静默失败
