# Smoke test — GPU 链路通过

## 最终结果（commit 3a4c74f，体检三分法修复后）

### CPU 8 utts — 通过
```
体检: tokenizer=8000 位置表最小=None
  token_embedding: 8000 × 1024
  decoder dense_in ×4: 4096 (FFN, 放过)
  log_softmax.mlp.layer0: 8000
  过度长序列 12/1024 >10%
CPU 3 步通过
```

### GPU 100 utts, 800 步 — 通过！零 CUDA crash
```
Embedding 清单:
  token_embedding: 8000 行 × 1024 dim
  无独立 position_embedding（位置表最小=None）

过度长序列: 156/1024（>10%）

训练 800 步完成，无 OOM，无 device assert:
  final_loss=91.88  final_sem=3.83  final_ts=7.52
  sem 趋势: step 1=8.98 → step 800=3.83（下降中）
```

## 结论

1. 词表替换完整（token_embedding 8000 + log_softmax 8000）
2. GPU 代码链路无 bug
3. 位置上限 1024 偏小（156 tok 超限），需要 resize 或确认 canary 用 ALiBi/RoPE 不受限
4. 800 步不够过拟合到 sem<0.05（需要更多步数或更大 smoke 集）
