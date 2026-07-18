# RECALL_PDMX —— 补渲 46,740 行 no_audio 的 pdmx 标签(与训练并行,不停训)

## 背景(D33)

装配统计里 pdmx 有 46,740 行标签配不上音频(S4/S5 渲染期缺失/失败/清理),
= 潜在 **+20% 训练数据**(全是 A2S/A2S_lite,主线口粮),一直挂在召回清单。
现在训练健康(38k 步全绿),把它们渲出来;**训练不用停**——渲染吃 CPU,训练吃 GPU。

## 执行(随时可起,断点续跑)

```bat
git pull --rebase --autostash
:: 低并发起步,渲染调度器按内存预算自动定 worker;训练在跑,给系统多留内存:
set S4_RESERVE_GB=10
python scripts/s4_parallel.py
```

- 已渲过的自动跳过,只补缺的;中断了重跑同一条命令即续。
- 观察内存:`python scripts/procmon.py mem`;紧张就 `set S4_WORKERS=4` 再压。
- **若训练日志出现 OOM 或 step 时间明显变长,先停渲染**(procmon kill sfizz),训练优先。

## 铁律

1. **只认过滤后的 manifest**:内容审计拉黑的非钢琴曲、泄漏黑名单曲,不得借补渲复活
   (s4_parallel 本就按 manifest 走,此条为验收口径)。
2. 渲染完成后跑 `python scripts/build_dataset.py --dry-run`,把装配统计整块 push
   (新文件 reports/RECALL_RESULT.txt):验收 = pdmx no_audio 显著下降、kept 相应上涨、
   非钢琴黑名单曲 0 复活。
3. 渲不出来的(真失败)不硬救:s4 的失败记录留着,贴回失败计数即可,规划端分诊。

## 生效时机

新音频在**下一次训练重启**时自动进池(装配器按 resolve_audio 现场发现),
checkpoint 照常续,不从头训。计划:渲染在 50000 步复盘前完成的话,
就借复盘那次重启一并生效;没完成就下一次。
