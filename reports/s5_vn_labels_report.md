# S5 VN Labels — Schema 差异与缺失字段

## 发现时间
2026-07-11，VN 全量渲染 96% 完成时抽样检查。

## VN 标签实际 schema
```json
{
  "utt_id": "pdmxperf_QmbL9PGbaMppKiinnANtR7pz1pTVfpi_000",
  "piece_id": "QmbL9PGbaMppKiinnANtR7pz1pTVfpi...",
  "kind": "human",
  "audio_path": "D:/vscode_projects/ee_download/work/pdmx_audio/pdmxperf_QmbL9PGbaMppKiinnANtR7pz1pTVfpi_000.wav",
  "A2S": "...",        // ✅ 存在
  "A2S_lite": "...",   // ✅ 存在  
  "TAST": "...",       // ✅ 存在
  "AMT": null          // ✅ 正确
}
```

## S5 文本标签 schema（对比用）
```json
{
  "utt_id": "pdmx_Qmbb..._000",
  "piece_id": "Qmbb...",
  "measure_range": [0, 16],   // ⚠ VN 缺失！
  "A2S": "...",
  "A2S_lite": "...",
  "TAST": null,               // VN 有，文本版无（预期）
  "AMT": null
}
```

## 缺失字段

### 1. `measure_range` — 缺失
- S5 文本标签有：`[0, 16]`（小节范围）
- VN 标签：**完全没有这个 key**
- 影响：无法知道每个音频段对应原曲哪几个小节
- 根因：`s5_vn_render.py` 中 `cpu_stage` 生成的行未包含 `measure_range`

### 2. 额外字段（VN 独有，不是缺失）
- `kind`: "human" — 标注渲染类型
- `audio_path`: 段音频绝对路径

## 数据质量

| 指标 | 值 |
|------|-----|
| 总标签数 | 99,178 |
| <1s 音频占比 | 0.6%（3/500） |
| vn_ok 累计 | ~51,000 |
| vn_fail 累计 | 0 |
| TAST 覆盖率 | 100%（每段都有） |

## 影响评估
- `measure_range` 缺失影响训练时的小节对齐和 bucketing，但不影响 tokenizer 语料（语料只用 A2S 文本）
- `audio_path` 和 `kind` 对 `build_dataset.py` 的 assemble 有用
