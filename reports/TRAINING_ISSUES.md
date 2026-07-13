# 训练问题报告

## 1. AMT 丢弃数反而翻倍——需规划端处理

| 切窗版本 | AMT 窗口数 | 超长丢弃 |
|----------|-----------|----------|
| 旧 (s6_amt_windows 原始) | 23,659 | 18,527 |
| 新 (segment.py 修复后) | 42,118 | **32,930** |

新切窗翻倍但每个窗口 token 序列没缩短，超 1024 位置上限的反而翻倍。
**需要规划端缩短 AMT 窗口的目标秒数或 resize 位置表。**

## 2. 执行端本地 patch: max_batch_sec=60 防止 OOM

commit a4607ae 的 `build_dataset.py` 未限制全量训练的 batch 大小。
16GB 卡上首个 batch 272s 立即触发 OOM。
执行端在 `build_dataset.py` 第 341-342 行加了 `dm.max_batch_sec = 60`。

每次 git pull 后需要确认这个 patch 是否被覆盖。
**需要规划端把这个限制写入上游，或暴露为命令行参数。**

## 3. 持久 OOM——batch 39s 仍爆显存

commit d2ba970，max_batch_sec=60，单 batch 仅 39s 音频：

```
torch.OutOfMemoryError: 29.53 GiB allocated on 15.92 GiB GPU
at transformer_decoders.py line 109: third_sub_layer (FFN)
```

模型 180M × BF16 = 360MB，AdamW = 720MB，共 ~1GB。但 PyTorch 分配了 29.5GB。
问题不在 batch 大小——即使 39s 也 OOM。Conformer encoder + decoder 的激活内存远超预期。
**需要 gradient checkpointing / activation recomputation，或减少 encoder 层数。**
16GB 卡跑不了当前配置的全量训练。
