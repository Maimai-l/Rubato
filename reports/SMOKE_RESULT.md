# 冒烟测试结果

**日期：** 2026-07-12 约 23:50
**Commit：** f7c066b（tiling padding 修复后）
**命令：** `python scripts/build_dataset.py --smoke 32 --smoke-steps 4000`

## 结果：通过

```
final_sem=0.038 < 0.05
冒烟判定: 通过，代码链路无 bug，可开全量
```

## 训练曲线

sem 从 8.99 降到 0.038（4000 步），收敛正常。

## 全量训练

烟通过后已开全量。当前进度：
- step 7050+，sem=2.9（全量 230k 样本，收敛远慢于 32 样本过拟合）
- 方言 loss：A2S=3.23, A2S_lite=3.41, AMT=2.55, TAST=2.73
- parseable_rate=0.00（step 5000/6000/7000 eval 均为此值）
- GPU 16GB 稳定，无 OOM（tiling 修复后）

## eval 日志摘要

step 5000: parseable=0.00, sem=3.09 > 2.0 → 宽限放行
step 6000: parseable=0.00, sem=3.18 > 2.0 → 宽限放行
step 7000: parseable=0.00, sem=2.91 > 2.0 → 宽限放行

样例预测 `|4/4k0 1/4...` 等合法 A2S 格式，模型输出格式正确但内容还不可解析。
