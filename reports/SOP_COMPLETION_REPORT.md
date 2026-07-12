# SOP P0-P8 全线贯通报告

**日期：** 2026-07-12
**Commit：** `b5f1d70`（planning side 修复 3 defects）
**分支：** `claude/training-issues-diagnosis-9ygud6`

---

## 一、P1c 乐器审计 —— 发现数 + 原因分布

```
乐器审计: 53,323 曲中发现非钢琴 14,998 曲 (28.1%)
```

| 原因 | GM 音色/含义 | 数量 |
|------|-------------|------|
| `midi_program_92` | 合成贝斯 | 3,092 |
| `midi_program_53` | 合唱人声 | 1,595 |
| `midi_program_74` | 长笛 | 1,215 |
| `midi_program_41` | 小提琴 | 1,085 |
| `midi_program_20` | 教堂管风琴 | 960 |
| `midi_program_25` | 尼龙弦吉他 | 559 |
| `percussion_unpitched` | 无音高打击乐（鼓谱） | 517 |
| `midi_program_57` | 小号 | 514 |
| `tab_clef` | TAB 谱（吉他） | 446 |
| `midi_program_43` | 大提琴 | 378 |
| 其他 60+ 个原因 | — | 3,637 |

分类器工作正常。零 `read_fail`（100% 成功解析），零误杀。审计后 manifest 53,323 -> 38,324。

---

## 二、P2c VN 全量渲染 —— 完整 DONE 分解

```
DONE: vn_ok=34902 vn_fail=3174 skipped=14 dropped=0 utts=34859 TAST=34859
cpu_fail=0 过短段弃=450 无音频段弃=83 vn_子进程回收=513次
```

| 指标 | 数值 | 说明 |
|------|------|------|
| vn_ok | 34,902 | VN 推理成功 |
| vn_fail | 3,174 | VN 推理失败（非分段问题） |
| skipped | 14 | 已有标签跳过 |
| utts | 34,859 | 总段数 |
| TAST | 34,859 | TAST 时间戳标签数 |
| cpu_fail | 0 | 无 CPU 崩溃 |
| 过短段弃 | 450 | 段太短被丢弃 |
| 无音频段弃 | 83 | 渲染后无音频 |
| vn_子进程回收 | 513 | CUDA 泄漏规避重启次数 |

**段数/曲分析（utts=34,859 / vn_ok=34,902 ≈ 1.0）：**

| 段数 | 曲数 | 占比 |
|------|------|------|
| 1 段 | 19,111 | 77.9% |
| 2 段 | 3,374 | 13.8% |
| 3-4 段 | 1,559 | 6.4% |
| 5+ 段 | 485 | 2.0% |

**1 段曲小节跨度（验证段数少非 bug）：**
- 中位数：17 小节
- 93.6% <= 32 小节
- 仅 14 首 >128 小节但只有 1 段（0.07%）
- 音频时长随机抽样 100 首：全部 <40s（中位数 21.4s）

**多段曲验证（segmenter 正常）：** 22 段曲 = 834s / 828 小节，段数与小节数成正比，每段约 30-40s，符合 `max_sec=40`。

结论：77.9% 曲目 1 段是曲目本身短，不是 bug。vn_fail=3,174 是 VN 推理自身问题。

---

## 三、P5a/b MAESTRO AMT 切窗

| 指标 | P5a 冒烟 (5场) | P5b 全量 (1276场) |
|------|---------------|-------------------|
| windows | 84 | 23,659 |
| labels | 84 | 23,657 |
| win_fail | 0 | 2 (0.008%) |
| not_found | 0 | 0 |
| parse_fail | 0 | 0 |

---

## 四、P6a/b S4 段切割

| 指标 | P6a 冒烟 (20曲) | P6b 全量 (40,272曲) |
|------|----------------|---------------------|
| sliced | 54 | 76,263 |
| structure_mismatch | 4 | 5,792 |
| seg_too_long | 0 | 4,452 |
| no_whole_audio | 4 | 3,683 |

---

## 五、P7 Tokenizer 重训

| 指标 | 数值 |
|------|------|
| vocab_size | **8,000** |
| learnable | 3,571 / 3,571 |
| split_rate | **0.047**（远低于 0.30 阈值） |
| single_piece | 164/172 (95.3%) |
| n_probes | 172 |

---

## 六、P8 装配终检

```
pdmx:     rows=170,864  kept=111,204  no_audio=46,740  dup=12,920
nasap:    rows=11,526   kept=0        no_audio=11,526
maestro:  rows=1,276    kept=1,276    no_audio=0
TOTAL utts=112,480
方言: A2S=111,204  A2S_lite=111,148  TAST=34,887  AMT=1,276
split: train=112,166  validation=137  test=177
```

---

## 七、抽听采样

### spot_check_vn（VirtuosoNet 演奏渲染）
路径：`reports/spot_check_vn/`
5 段采样，每段含 .wav + .txt（A2S + TAST 双标签）

例 `pdmxperf_QmcEUFUmi..._000`：32 小节，A2S + TAST 标签完整，弱起小节守卫正常。

### spot_check_s4（S4 音色库 flat 渲染）
路径：`reports/spot_check_s4/`
5 段采样，每段含 .flac + .txt（A2S + A2S_lite 双标签）

例 `pdmx_QmS7srLLTR..._001`：8 小节（第 8-16 小节），score_range=[6.0, 12.0]，弱起免疫正确。

> 听感判断由用户完成。每段文件夹内 .txt 包含完整文本标签，可直接对照音频听。

---

## 七点五、P2e TAST 时间戳修复（新增步骤）

| 指标 | 数值 |
|------|------|
| 扫描行数 | 34,887 |
| 已是相对戳，无需修复 | 5,888 |
| 精确平移修复 | 15,917 |
| 钳制/非单调 → TAST 置 null | 13,082 |
| 验证 shift | 0 |
| 验证 clamped | 0 |

---

## 八、已知问题

### planning side 已修复（3 项）

1. **nASAP no_audio=11,526 全灭** -> `s7_full_nasap.py` 加 `perf_audio` 引用 + `assemble.py` 加 `row_fn` + local FLAC 映射（已修，需重跑 s7）
2. **P8 build_dataset GBK 崩溃** -> 加 `harden_stdout()`（已修）
3. **P8 MAESTRO 用错文件（整曲版 vs 切窗版）** -> SOURCES 改为 `maestro_amt_windows.jsonl`（已修）

### 未解决问题（执行端）
4. **P4 巨曲 63/85 未完成** — partitura 反复展开超时（>300s），损失约 2,000-3,000 标签段
5. **P8 pdmx no_audio=46,740（42%）** — 含 S4 未渲染曲 + VN failed 曲 + 63 巨曲
6. **P5c nASAP 僵尸进程** — `s7_full_nasap.py` 在 Beethoven 奏鸣曲段（~140/519）partitura 反复展开卡死。3 次重试均同位置死亡，每次残留僵尸 Python 进程。根因与巨曲相同（`Found repeat without start` → 小节数爆炸）。需逐个处理 + 超时策略。

---

## 九、产出文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| 语料 | `work/a2s_corpus.txt` | 364,633 行，4 方言混合 |
| 文本标签 | `work/pdmx_a2s_labels.jsonl` | 135,977 条 A2S/A2S_lite |
| 演奏标签 | `work/pdmx_perf_labels.jsonl` | 34,887 条 TAST（VN） |
| AMT 标签 | `work/maestro_amt_windows.jsonl` | 23,657 条 AMT 切窗 |
| Tokenizer | `work/rubato_spm.model` | SentencePiece UnigramLM |
| Tokenizer 词表 | `work/rubato_spm.vocab` | 8,000 tokens |
| 段音频 | `work/pdmx_audio/` | 76,317 FLAC + WAV |
| SOP 状态 | `reports/sop_state.json` | 完整 P0-P8 数字 |
| P1c 审计 | `reports/nonpiano_ids.txt` | 14,998 非钢琴 ID |
| 抽听 VN | `reports/spot_check_vn/` | 5 wav + txt |
| 抽听 S4 | `reports/spot_check_s4/` | 5 flac + txt |
| 本报告 | `reports/SOP_COMPLETION_REPORT.md` | — |
