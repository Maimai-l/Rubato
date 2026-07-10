# OPS —— 跑长任务不炸内存、能监控/杀/续跑(纯命令,不废话)

所有并行脚本已改成:**worker 数按内存自动定**(不再写死 16/24)、**跳过已完成**(可续跑)、**流式写盘不在内存累积**。
监控/救火用 `scripts/procmon.py`。

## 监控进程(另开一个终端一直挂着)
```
python scripts/procmon.py watch --pattern sfizz        # 渲染时:看 sfizz worker 数 + 内存,每 5s 刷新
python scripts/procmon.py watch --pattern virtuoso     # VN 时
python scripts/procmon.py watch --pattern python        # 训练时
python scripts/procmon.py mem                          # 只看系统可用内存
python scripts/procmon.py list --pattern sfizz         # 看一眼当前快照(不 loop)
```

## 内存炸了 / 卡住 → 杀 → 减并发重开(会跳过已完成,不重复)
```
python scripts/procmon.py kill --pattern sfizz --yes   # 杀掉所有 sfizz 渲染进程
python scripts/s4_parallel.py --workers 6              # 用更小的并发重开(已渲的自动跳过)
```

## S4 直排渲染(内存预算调度,【自动不 OOM】、可续跑)
```
python scripts/s4_parallel.py                          # 全量。自动:读每个音源目录大小 + 可用内存,
                                                       # 大音源少并发/小音源多并发,同时运行的音源和 ≤ 预算。
# 不用再猜 worker 数。断了直接重跑,跳过已完成。逐条状态 reports/s4_render.jsonl
# 还是紧(留更多给系统):   set S4_RESERVE_GB=8
# 想更快(承认 sfizz 流式、少留内存):  set S4_MEM_FACTOR=0.5
# 硬封顶进程数(可选):     set S4_WORKERS=8
```
> 原理:权重 = 音源目录总大小(sfizz 常驻内存的安全上限)。ExperienceNY(6.5GB)自动只跑 1-3 个并发,
> Splendid(146MB)可跑很多个 —— 内存占用之和永远 ≤ 预算,**不会再 OOM**。

## S5 表现性渲染(VN)—— GPU/CPU 流水线,不再干等
```
python scripts/s5_vn_render.py --limit 20              # 先 20 曲,确认 vn_ok>0 / TAST>0
python scripts/s5_vn_render.py                         # 全量;.done 标记的曲自动跳过(可续跑)
# VN 权重【自动定位】(GUIDE §1),不用传 --vn-checkpoint;InferenceModel 只加载一次,每曲只前向。
# 【内存预算调度,不 OOM】:准入权重 = 音源目录大小 + 每渲染音频缓冲开销,同时运行的内存和 ≤ 预算。
#   大音源(ExperienceNY 6.5GB)自动少并发、小音源多并发。GPU 推理与 CPU 渲染重叠。
# 还炸内存?只调环境变量(别改代码):
set S5_RESERVE_GB=8            # 多留给系统
set S5_RENDER_OVERHEAD_GB=1.5 # 每渲染音频缓冲估得更足(更保守、更不炸)
set S5_MEM_FACTOR=0.5         # 想更快:承认 sfizz 流式、音源权重打折、多并发
python scripts/s5_vn_render.py
```

## S5 文本标签(PDMX A2S,内存安全、可续跑)
```
python scripts/s5_parallel.py                          # worker 数按内存自动定;合并阶段流式,不 OOM
```

## 判断"要不要减并发"的硬信号
- `procmon watch` 里系统可用内存持续 < 3GB,或脚本打印 `low_mem_events > 0` → 杀掉,`--workers` 减半重开。
- 每个 worker 的 RSS × worker 数 ≈ 总占用;`per_worker_gb` 估准了,`pick_workers` 就不会超。

## 别再犯的坑
- 不要手写 `multiprocessing.Pool(24)` 之类的写死并发 —— 用脚本自带的 `--workers`(默认按内存)。
- 不要在合并阶段把所有 labels/corpus 读进内存再 join —— 用 `rubato.ops.concat_files`(脚本已用)。
- 断了不要从头跑 —— 所有脚本跳过已完成,直接重跑同一条命令。
