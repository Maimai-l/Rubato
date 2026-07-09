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

## 第二轮(用户追问"为什么不用 VN/PDMX 了")

| # | 隐患 | 严重度 | 状态 |
|---|---|---|---|
| 7 | **S5 表现性渲染管线从未落地脚本**:SPEC 设计了 S5(R-S5.1-5.9),但历史上**只有 S4 直排**,没有任何调 VirtuosoNet 的代码。后果:PDMX 只能供 A2S/A2S_lite,**TAST 恒 null**,音频全恒速,模型学不到"从表现性演奏恢复乐谱"(论文 PDMX-TAST 511k 全缺) | 高 | 补 `scripts/s5_vn_render.py`,调【本地 virtuoso CLI】(GUIDE §2)`--csv`→tmap(R-S5.6,复用 build_timemap)→渲 VN MIDI→按段切。humanize(`rubato/render/humanize.py`)仅作 R-S5.9 失败兜底(默认关) |
| 8 | **我的"精简路径"文档把 PDMX 渲染漏成"可跳过"**:CORPUS_REGEN 只写文本/tokenizer 半程,没带 S4/S5 音频渲染;kickoff 又承诺了四方言混比(含 PDMX-TAST),而脚本产不出 —— 承诺与能力对不上 | 高 | CORPUS_REGEN 补 §1.1b(S4+S5 渲染 + audio↔TAST 同源不变量);EXECUTOR_KICKOFF 改成"PDMX 必须渲染";点明 humanize 是 CPU 兜底、VN 可选 |
| 9 | **audio↔TAST 必须同源**:若用 §1.1 的恒速估算 TAST 配 S4 直排音频,时间戳与音频不匹配 = 训练噪声 | 中(隐蔽) | 钉死:TAST 只在渲染处(s5_vn_render)产,与音频用同一 tmap;文本 s5 故意 TAST=null 并注释说明 |

**对用户问题的正面回答**:不是"不用 VN/PDMX"—— 设计一直要用。真相是 (a) VN/humanize 根本没被实现过(只 S4),
(b) 我的精简文档把 PDMX 音频渲染漏成了可选。两处都已纠:humanize 补齐并测,VN 驱动写好(执行端 py312 跑),
文档把"PDMX 必须渲染 + audio↔TAST 同源"钉死。

## 结论
s7 是这一类里"最先被踩到"的一个,不是唯一。会拦住训练的是 #4(装配胶水)和 #7(S5 从未实现);
两者都已补齐并测。#2/#3/#8/#9 是过程/文档坑,靠点名脚本 + 钉死顺序与不变量消除。
所有改动只碰脚本/文档/新增带测纯逻辑模块,测试 20→22 套件全绿。
