# 隐患审计 —— "算了不落盘 / 落了不对接"这一类缺陷的全量排查

触发:执行者跑 nASAP 没得到 labels。根因不是单点,而是一类缺陷:**脚本算出结果却不持久化,
或产物之间对不上、无人对接**。下面把这一类在整条流水线里全部查一遍(不只补 s7)。

## 审计方法
- grep 全部 `scripts/*.py` + `rubato/**` 的落盘点(write_jsonl/write_text/open(w|a)/json.dump/sf.write)。
- 逐脚本核对:它宣称的产物是否真写盘;文档承诺的产物名/路径是否与脚本一致。
- 追产物下游:labels → tokenizer 语料 → 数据集 → 训练,每个交接点是否有代码真正对接。

## 发现与处置

| # | 隐患 | 严重度 | 状态 |
|---|---|---|---|
| 1 | **s7 只写 report 不落 labels**;而 CORPUS_REGEN 却写"产出 nasap_labels.jsonl"(承诺了不存在的产物) | 高(报的就是它) | 执行者加 `--out-labels/--out-corpus`;我把循环内 `setdefault(open())` 提到循环外(每首曲重开文件的 churn),文档改成带参调用 |
| 2 | **s3 三脚本歧义**:`s3_full_filter.py` 只写统计 report、**不产 manifest**,名字却像"全量过滤";真正产 `manifest_pieces.jsonl` 的是 `s3_filter_pdmx.py` | 高(同 s7 的坑) | 文档点名:产 manifest 用 `s3_filter_pdmx.py`;`s3_full_filter.py` 是诊断 |
| 3 | **泄漏防护会被绕过**:`s5`/`s5_parallel` 都传【空 blacklist】,泄漏防护全靠 `s3_minhash_leakage.py` 先把 manifest 洗过。跳过它 = 零泄漏防护 = 测试集污染 | 高 | 文档把顺序钉死:`s3_filter → s3_minhash_leakage → s5`,并解释为何不能跳 |
| 4 | **labels→数据集的胶水完全缺失**:三份 labels.jsonl schema 不一致(maestro 用 `midi_file`/`amt_text`,pdmx/nasap 用 `utt_id`/`AMT`),且都不带音频路径;没有任何代码把它们合成 `RubatoDataset(utts, labels)`。训练代码有、入口没有 → 语料/词表全对了也训不起来 | **最高(下一个必踩)** | 新增 `rubato/data/assemble.py`(纯逻辑,`tests_assemble.py` 22 项)+ `scripts/build_dataset.py`(带 `--dry-run` 装配自检 + 训练入口) |
| 5 | **assemble 的 nASAP 音频未对接**:s7 标签行不带音频引用,`resolve_audio` 会把 nASAP 全判 no_audio | 中 | `build_dataset.py --dry-run` 会显示 `nasap kept=0`;resolver 里 **【EXECUTOR】** 注释指明补 nASAP↔FLAC 映射 |
| 6 | `s5_parallel.merge_outputs` 把全部 corpus+labels 读进内存再 join | 低(规模,非正确性) | 记录;53k 量级通常可承受,爆内存再改流式 |

## 已核对为【没问题】的(排除)
- `s6_convert_all.py`:确实写 FLAC(`stream_wav_to_flac`),report 只是附带。✓
- `gen_amt_labels.py`:确实写 `maestro_amt_labels.jsonl`("w")。✓(但 schema 是 `midi_file`/`amt_text`,见 #4)
- `s5_parallel` 的 `"".join(corpus_lines)`:每个 chunk 文件以 `\n` 收尾,拼接不会粘行。✓
- `write_text/write_jsonl`:都 `mkdir(parents=True)`,目录缺失会建而非静默失败。✓
- `s3_filter_pdmx` / `s3_minhash_leakage`:都真写 manifest。✓

## 结论
报出来的 s7 是这一类里"最先被踩到"的一个,不是唯一。真正会拦住训练的是 #4(胶水缺失),
已补齐并测。#2/#3 是过程顺序坑,靠文档点名 + 顺序钉死消除。所有改动只碰脚本/文档/新增纯逻辑模块,
19→21 个测试套件全绿。
