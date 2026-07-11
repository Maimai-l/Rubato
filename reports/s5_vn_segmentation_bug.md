# S5 VN 分段 BUG — segment_score 未使用真实 tmap

## 位置
`scripts/s5_vn_render.py:488`

## 当前代码
```python
segment_score(ir, min_measures=2, max_measures=16, max_sec=40.0, sec_per_whole=2.0)
```

**未传 `tmap` 参数**。`segment_score` 退化为恒定速度估算：`sec_per_whole=2.0`（全音符=2秒，即 120bpm）。

## 实际行为 vs 预期

### VN 有真实 tmap
- virtuoso CSV → `csv_to_tmap()` → TimeMap（音符级演奏秒）
- `make_labels()` 用了 tmap ✅ — TAST 时间戳正确
- `_slice_audio()` 用了 tmap ✅ — 音频切片边界正确（`tmap(bounds[a])`）

### 分段没用 tmap
- `segment_score` 用 **假速度 120bpm** 估算时长 ❌
- 分段边界 (a, b) 由假速度决定
- 音频切片又用真 tmap——两个时间源不一致！

## 后果

| 真实速度 | 假速度 120bpm | 后果 |
|---------|-------------|------|
| 快曲（如 presto, 全音符≈1s）| 高估 2x | 一段本应 8 小节，被切成 4 小节 → 段太碎 |
| 慢曲（如 adagio, 全音符≈4s）| 低估 2x | max_sec=40 在假速下允许 20 个全音符，实际需 80s → 超长段 |
| rubato（弹性速度）| 完全忽略 | 加速段被高估、减速段被低估 → 段长随机 |

## 实际数据佐证
- 中位时长 13.1s 看起来正常，但极值异常：最短 0.2s（快曲被过度切碎）、最长 93s（慢曲超 max_sec=40）
- 93s 的段：假速允许 max_sec/2.0 = 20 个全音符 = 80 个四分音符 = 20 小节 4/4，但真速慢一半 → 160 个四分音符 → 96s

## 修复
```python
# 应该传 tmap:
segment_score(ir, min_measures=2, max_measures=16, max_sec=40.0, tmap=tmap)
```
`segment_score` 内部会用 tmap 计算真实时长，不再依赖恒速估算。

## 影响范围
- S5 VN 全部 ~100k 段都受此 bug 影响
- 段长分布扭曲（快曲碎、慢曲长）
- TAST 时间戳和标签文本本身是正确的（用了 tmap）
- 训练可用但段长不合理——快曲浪费 token 分段太多，慢曲段太长可能 OOM
