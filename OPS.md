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

## S4 直排渲染(全量、内存安全、可续跑)
```
python scripts/s4_parallel.py --limit 500              # 先 500 试吞吐 + 看内存
python scripts/s4_parallel.py                          # 全量,worker 数按内存自动定
python scripts/s4_parallel.py --workers 6              # 内存吃紧就手动封顶
python scripts/s4_parallel.py --per-worker-gb 2.0      # 音源更大就调高单 worker 估算(worker 数会自动降)
# 逐条状态: reports/s4_render.jsonl   断了直接重跑上面任一条,跳过已完成
```

## S5 表现性渲染(VN)—— GPU/CPU 流水线,不再干等
```
python scripts/s5_vn_render.py --limit 20              # 先 20 曲,确认 vn_ok>0 / TAST>0
python scripts/s5_vn_render.py                         # 全量;.done 标记的曲自动跳过(可续跑)
python scripts/s5_vn_render.py --workers 8             # 手动定 CPU 渲染并发(内存吃紧就调小)
python scripts/s5_vn_render.py --vn-checkpoint 你的/checkpoint_best.pt   # VN 模型只加载一次
# VN:默认用 InferenceModel【只加载一次】(GUIDE §5),每曲只前向,不再每曲重载 172MB(R-S5.1)。
#     --vn-checkpoint 路径不对会打印提示并退回 CLI(每曲重载,慢);传 --vn-checkpoint "" 强制 CLI。
# 机制:主进程顺序跑 VN 推理(GPU,~0.5s),非阻塞把渲染(~5s)交给 CPU worker 池 →
#       CPU 渲染第 N 曲时 GPU 已在推理 N+1...,GPU 不再干等 CPU(旧版顺序跑 GPU 空转 ~90%)。
# 中间产物 perf.mid/whole.opus 每曲用完即删(不撑磁盘);--workers 默认按内存自动定。
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
