# Step 61200 解码 A/B 实验

时间：2026-08-03

## 问题

当前 nASAP eval 的 parseable 长期为 0，判定它主要来自 greedy 解码、900-token
上限/验证器误杀，还是模型自由生成仍未学会闭合。

## 有效实验设置

- checkpoint：`outputs/ckpt/last.pt`，step 61200
- 样本：与训练 eval 同源的 4 条确定性 nASAP val 样本
- prompt：`domain=sample.domain`，四条均为 `real`，与正式 eval 一致
- 两臂：greedy (`beam=1`) 与真实 beam search (`beam=4`)
- beam→greedy 自动回退关闭，避免两臂混样
- 模型权重、音频、prompt、截断器与验证器完全相同

## 结果

| 解码 | parseable | fallback | 8 个窗口中撞 900-token cap | EOT | 耗时 |
|---|---:|---:|---:|---:|---:|
| greedy | 0/4 | 4/4 | 7/8 | 1/8 | 45.6 s |
| beam=4 | 0/4 | 4/4 | 6/8 | 2/8 | 123.4 s |

beam=4 减少了一部分 DYCK/终止符错误并略微增加 EOT，但没有救出任何合法样本，
且耗时约为 greedy 的 2.7 倍。

## 900-token 与验证器核验

四条标准 TAST 用同一 `truncate_after_20s` 截断后的 tokenizer 长度分别为：

- Bult-Ito：300 token
- Hou：830 token
- Lee：447 token
- Wang：228 token

四条截断参照均通过同一套 A2S + TAST timestamp 验证器。因此：

- 900-token cap 对这四条标准的 20 秒目标足够；
- 验证器不会误杀对应的合法标准答案；
- 模型生成到 900 token 是循环/不闭合的结果，不是标准答案先天过长。

## 判定

当前 parseable=0 不能主要归因于 greedy、无域 prompt、cap 太短或验证器过严。
输出已经学到局部音符/时间戳外形，但自由生成仍频繁循环、漏时间戳、重复 onset、
不闭合与不输出终止小节线。这更符合尚未收敛的自回归结构学习/暴露偏差。

本实验不支持把正式 eval 改为 beam=4；它没有质量收益且明显更慢。主训练已从
step 61200 的完整模型、优化器、调度器与 batch cursor 快照恢复。下一项最小实验应是
固定 checkpoint 比较 repetition penalty / EOT 校准，而不是继续扩大 beam。

逐样本原始输出、拒因与生成停止原因见 `DECODE_AB_STEP61200_DOMAIN.json`。另有一轮
无域 prompt 的先导试验 `DECODE_AB_STEP61200.json`，不作为正式结论依据。

随提交保留的原始运行证据：

- `decode_ab_step61200_domain.out.log` / `.err.log`
- `train_resume_step61200_startup.out.log` / `.err.log`（续训启动快照）

## 正式 parseable 与训练侧 pv 补充判读

- 最新一次正式完整解码评测是 step 60000：`n=48`、`eval_complete=True`、
  `parseable=0/48`。这是**真 0**，不是 NA。
- step 61000 只运行教师强制探针，日志明确写着“仅探针；解码腿跳过”；该步没有
  parseable 观测，应记为 **NA**，不能沿用指标 dict 的初始化值 0。
- step 61200 的本实验为 `0/4`，它证明这四条在 greedy/beam4 下均失败，但因为
  `n=4<12`，不能替代正式 48 条评测的总体比率。

`pv` 是训练时近 50 optimizer steps 的音高 token 交叉熵，越低越好。由 step
36250–61300 的 502 条日志点按 5k 步分箱：

| step 范围 | pv 均值 |
|---|---:|
| 35000–39999 | 2.78 |
| 40000–44999 | 2.71 |
| 45000–49999 | 2.65 |
| 50000–54999 | 2.60 |
| 55000–59999 | 2.56 |
| 60000–61300 | 2.54 |

最早 10 个日志点均值为 2.81，最近 10 个为 2.54：音高教师强制损失确实持续改善，
但 60k 后下降已趋平。`pv` 只说明给定正确历史时更会预测音高 token；它不能抵消本
实验观察到的自由生成循环/不闭合，也不能单独证明模型正在正确使用音频。
