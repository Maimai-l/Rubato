# P2c/P2e 状态被重置问题

**日期：** 2026-07-12
**触发 commit：** `85cee9c`（帮手 pull）

## 发生了什么

pull 之后运行 `sop_next.py --status`，之前已完成的两步变成待跑：

```
pull 前: ✅ P2c    ✅ P2d    ✅ P2e    ✅ P3    ...
pull 后: ⬜ P2c    ✅ P2d    ✅ P2c0   ⬜ P2e   ✅ P3    ...
```

## 是数据被删了吗？

**不是。所有数据文件完整无损：**

```
pdmx_perf_labels.jsonl     34,887 行  ← TAST 标签已修复
pdmx_perf_labels.bak        修复前备份
pdmx_audio/pdmxperf_*.wav  34,859 段  ← VN 演奏音频
nasap_labels.jsonl           5,965 标签  ← s7_resilient 产出
a2s_corpus.txt             364,633 行   ← 语料
rubato_spm.model            8,000 词表  ← tokenizer
```

## 根因分析

帮手在 `sop_next.py` 步骤表里：
1. 插入了 **P2c0**（"钳制 TAST 段音频清场" — affected_pieces=0，已过）
2. 改了 P2c/P2e 的 ID 或 `parse`/`require` 判据

`sop_state.json` 存的是 ID 字符串列表 `["P0","P1a",...,"P2c","P2d","P2e",...]`。状态机加载时，如果 `_steps()` 里某步的 ID 或判据变了，可能被当成"新步骤"而未标记完成。

**等价于：** 数据全在，但状态机认为这两步"没跑过"。

## 需要确认

P2c = VN 全量重渲，34,902 首，天级计算。**重跑的代价非常大。**

请确认：
1. P2c/P2e 是有意重置（需要重新渲染），还是 `sop_next.py` 改表时的副作用
2. 如果不需要重跑，是否需要我 `--reset-step` 把 P2c/P2e 再标回去
