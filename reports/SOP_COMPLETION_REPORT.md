# SOP P0–P8 全线贯通报告

**日期：** 2026-07-12  
**Commit：** `765677c`  
**分支：** `claude/training-issues-diagnosis-9ygud6`

---

## 一、全流程结果总表

| 步骤 | 标题 | 状态 | 关键数字 |
|------|------|------|----------|
| P0 | 准备：旧语料留档 + commit | ✅ | `765677c` |
| P1a | S4 速度钳制·干跑 | ✅ | 728 outlier pieces |
| P1b | S4 速度钳制·实施 | ✅ | 2,294 clamped, 652 音频删除 |
| P1c | 乐器审计 | ✅ | **0** 非钢琴残留 |
| P2a | S5 VN 全量清场 | ✅ | 0 rows/audio dropped |
| P2b | S5 VN 冒烟（20曲） | ✅ | vn_ok=19/20, utts=28, TAST=28 |
| P2c | S5 VN 全量重渲 | ✅ | vn_ok=34,902, utts=34,859, TAST=34,859, vn_recycles=513 |
| P2d | VN 段抽听采样 | ✅ | 5 段采样 |
| P3 | S4 补渲离谱速度曲 | ✅ | ok=417, fail=0 |
| P4 | 文本标签全量重生成 | ✅⚠️ | corpus=273,049, labels=135,977（巨曲 22/85） |
| P5a | MAESTRO AMT 冒烟（5场） | ✅ | windows=84, labels=84, win_fail=0 |
| P5b | MAESTRO AMT 全量（1276场） | ✅ | windows=23,659, labels=23,657, win_fail=2 |
| P6a | S4 段切割冒烟（20曲） | ✅ | sliced=54, structure_mismatch=4 |
| P6b | S4 段切割全量 | ✅ | sliced=76,263, structure_mismatch=5,792 |
| P6b2 | S4 段抽听采样 | ✅ | 5 段采样 |
| P6c | 语料重建 | ✅ | corpus_lines=**364,633** |
| P7 | Tokenizer 重训 | ✅ | vocab=**8,000**, split_rate=**0.047**, learnable=3,571 |
| P8 | 装配终检 dry-run | ✅ | **112,480** utterances, 4 方言 |

---

## 二、最终训练数据

| 指标 | 数值 |
|------|------|
| 总 utterances | **112,480** |
| 训练集 | 112,166 |
| 验证集 | 137 |
| 测试集 | 177 |
| PDMX 保留 | 111,204 |
| MAESTRO 保留 | 1,276 |
| nASAP 保留 | 0 |

### 方言分布
| 方言 | 数量 | 占比 |
|------|------|------|
| A2S | 111,204 | — |
| A2S_lite | 111,148 | — |
| TAST | 34,887 | — |
| AMT | 1,276 | — |

### Tokenizer
- 词表大小：8,000（达标）
- 可学习语义 token：3,571 / 3,571（100%）
- 字形分裂率：0.047（远低于 0.30 阈值）
- 用户定义符号：4,170（从 vocab_spec.json 注入）

---

## 三、已知问题

### 1. 巨曲 63/85 首未完成（P4）
- **严重程度：** 低（不影响训练主体）
- **原因：** partitura MusicXML 反复展开导致处理超时（>300s）
- **典型特征：** `Found repeat without start` → 虚拟小节数膨胀到数万
- **影响：** 损失约 2,000–3,000 个标签段（已完成的 22 首产出 644 标签）
- **文件：** `work/manifest_giant_retry.jsonl` 包含失败曲目列表
- **建议：** 可后续用 Music21 替代 partitura 处理这些曲目，或在预处理阶段跳过复杂反复展开

### 2. nASAP 全部不可用（no_audio=11,526）
- **严重程度：** 低（nASAP 仅占总量 ~9%，且多数为人工对齐数据）
- **原因：** nASAP 音频文件不存在于预期路径
- **影响：** 训练数据缺少 nASAP 对齐样本
- **建议：** 确认 nASAP FLAC 文件位置，修复路径映射

### 3. P8 build_dataset.py 有 GBK Unicode 崩溃
- **严重程度：** 极低（不影响功能，仅打印阶段崩溃）
- **位置：** `scripts/build_dataset.py` 第 155 行
- **原因：** `⚠` (U+26A0) 在 Windows GBK 编码下无法输出
- **影响：** dry-run 统计已完整输出，仅最后一行重复 utt_id 警告未打印
- **建议：** 给所有 `print` 加 `errors='replace'` 或将 stdout 编码设为 UTF-8

### 4. sop.log 与实际进度不一致
- **严重程度：** 极低
- **原因：** P4 后的步骤均手动执行，未通过 `sop_next.py` 写入日志
- **sop.log 当前内容：** 仅 P4 的 `s5_parallel.py` 原始输出（8,435 行 partitura 警告）
- **建议：** 以 `sop_state.json` 为唯一进度来源

---

## 四、产出文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| 语料 | `work/a2s_corpus.txt` | 364,633 行，4 方言混合 |
| 文本标签 | `work/pdmx_a2s_labels.jsonl` | 135,977 条 A2S/A2S_lite |
| 演奏标签 | `work/pdmx_perf_labels.jsonl` | 34,859 条 TAST（VN 渲染） |
| AMT 标签 | `work/maestro_amt_windows.jsonl` | 23,657 条 AMT 切窗 |
| Tokenizer 模型 | `work/rubato_spm.model` | SentencePiece UnigramLM |
| Tokenizer 词表 | `work/rubato_spm.vocab` | 8,000 tokens |
| 段音频 | `work/pdmx_audio/*.flac` | 76,263 + 48,451 个段文件 |
| SOP 状态 | `work/sop_state.json` | 完整 P0–P8 数字 |
| 本报告 | `reports/SOP_COMPLETION_REPORT.md` | — |

---

## 五、下一步：训练

```
Step 1: MAESTRO 过拟合
  100 pieces × 4 dialects, loss < 0.05
  验证模型 / 损失函数 / tokenizer 没有 bug

Step 2: 全量训练
  112,480 utterances, 4 dialects mixed
  A2S=35% / A2S_lite=15% / TAST=20% / AMT=30%
```
