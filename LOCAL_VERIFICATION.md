# 本地验证与收尾指令(给本地 agent / 有真实数据时执行)

**读者**: 在 Windows + 真实数据 + GPU 环境运行的本地执行者。
**目的**: 沙盒只验证了纯逻辑(15 套件 245 项)。以下每一项**必须在真实数据上判断**——
给出精确命令、**通过/失败判据(带具体数字)**、失败排查。判据不达 = 该项未修复,不得声称完成。

**总原则**: 判据是硬数字,不是"看起来对"。任何一项失败 → 停,按"失败排查"查,修复前不推进下游。

---

## 执行顺序(依赖决定)

```
A. 环境自检 → B. tokenizer 重训(#3/#13/#20) → C. 数据管线产标签(#6/#11/#12/#14/#15)
   → D. 写 dataset.py 并配对(#4/#5,尚未实现) → E. 模型冒烟(#1/#21) → F. 渲染吞吐(#2/#8/#9)
   → G. 推理+评测(#7/#19)
```
B/C 可与 F 并行(F 不占 GPU 时);E 必须在 B/C/D 之后。

---

## A. 环境自检

**命令**
```bash
python -c "import torch; print('cuda', torch.cuda.is_available())"
python -c "from nemo.collections.asr.models import EncDecMultiTaskModel; print('nemo ok')"
python -c "import partitura, sentencepiece, soundfile, mir_eval, mido; print('deps ok')"
# 沙盒逻辑基线(应全绿):
for t in tests_intermo tests_losses tests_train_step tests_infer tests_infer_truncate tests_merge tests_model_build tests_early_stop tests_evaluate tests_tokenizer tests_segment tests_pdmx tests_nasap tests_nasap_timemap tests_maestro; do python $t.py; done
```
**判据(PASS)**: cuda=True;nemo ok;15 套件每个末行"全部通过"。
**FAIL**: NeMo 装不上 → 走 R-S10.5 权重提取路线(build.py 的 `resize_decoder_vocab` 已支持,不必 `change_vocabulary`)。

---

## B. Tokenizer 重训 —— #3 / #13 / #20

**为什么**: 沙盒词表卡在 4760、字形 100% 分裂,根因是语料只有 nASAP 39.9M chars。必须先有 PDMX A2S 语料(见 C 步产出的 `a2s_corpus.txt`),再重训。**本步依赖 C 步先跑完**(或至少产出语料)。

**命令**
```python
from rubato.data.tokenizer import train_unigram, check_glyph_coverage, reconcile, build_vocab_spec
# corpus = C 步产出的 a2s_corpus.txt(A2S + A2S_lite 文本,论文语料仅此二者)
r = train_unigram([r"D:\...\work\a2s_corpus.txt"], r"D:\...\work\rubato_spm", vocab_size=8000)
print(r)
cov = check_glyph_coverage(r"D:\...\work\rubato_spm.model")
print(cov)
```
**判据(PASS,三条全中)**:
1. `r["vocab_size"] == 8000`(不是 4760);`r["warning"] is None`。
2. `r["reconcile"]["ok"] == True` 且 `learnable_semantic == 3571`(A-S9.1 与论文 ~3570 闭合)。
3. `cov["split_rate"] < 0.30`(字形分裂率;沙盒是 ~1.0 的"100% 分裂"病态)。理想 <0.15。
**FAIL**:
- 词表仍 <8000 → 语料还是太小。查 `a2s_corpus.txt` 行数,应 ≥ 数十万行(PDMX 目标 1,002k utterance)。语料不够 = C 步 PDMX 没跑够曲。
- `split_rate` 仍高但词表 8000 → 探针字形没进 user_defined,查 `vocab_spec.json` 与训练 `user_defined_symbols` 是否一致(应由 `build_vocab_spec()` 生成,禁手写)。

---

## C. 数据管线产标签 —— #6 / #11 / #12 / #14 / #15

### C1. PDMX A2S 标签(#11)—— 喂 tokenizer 语料
**命令**: 编辑 `scripts/s5_pdmx_a2s_labels.py` 底部路径,跑 `python scripts/s5_pdmx_a2s_labels.py`。
**判据(PASS)**: 报告 `total_labels` 达数万~数十万级;`total_a2s_chars` 远超 nASAP 的 39.9M(目标量级 ×10+);`failures` 有记录且非静默丢(§2.4)。产出 `a2s_corpus.txt` 非空。
**FAIL**: `total_labels` 很小 → 查 `failures` 里的 top reason:
- 大量 `part_to_ir_failed` → partitura 解析/变 divisions 剔除过多,查 `partitura_adapter.py` 的 staff 假设(A-1:1=PR,2=PL)是否符合你的 PDMX 方言。
- 大量 `segment_failed` → 小节结构异常;浪漫派非标准小节可给 `segment_score` 走 lenient 路径。

### C2. nASAP TimeMap 匹配率(#6)—— 核心验证
**命令**: 跑 `python scripts/s7_full_nasap.py`,看报告 `aggregate_timemap_stats`。
**判据(PASS)**: `matched_xmlid / total_aligned` **远高于 0.37%**——目标 **>80%**。这是 #6 是否真修好的**唯一硬判据**。
**FAIL(匹配率仍很低)**:
- 打印几条真实 TSV 的 `xml_id` 与 partitura `note.id`,看命名到底差在哪。
- `nasap_timemap.match_xmlid` 现有三策略(精确/去前缀/末段)。若你的 TSV 用的是"小节-拍-序号"三段式而 partitura 用连续 id,需在 `match_xmlid` 加一条针对性策略(改那一个函数即可,别动别处)。
- 匹配率上不去 = TAST 标签不可靠,该数据只出 A2S/A2S_lite(降级路径,主线不受损)。

### C3. 保守 split + 黑名单(#14/#15)
**命令**
```python
from rubato.data.nasap import conservative_split
from rubato.data.pdmx import build_blacklist, check_split_leakage
# pieces 从 manifest 读;跑 split 落盘 nasap_split.json
res = conservative_split(pieces, val_segment_target=512)
# 用 test_works 构黑名单,喂给 C1 的 PDMX 选曲
bl = build_blacklist(nasap_test_works=res["manifest"]["test_works"], asap_beyer_works=[...])
```
**判据(PASS)**: `check_split_leakage(all_utts, bl)["ok"] == True`——train 与 val/test 在 work_key/dup_cluster/maestro_id 三维**零交集**(A-S8.3),且 train 无黑名单命中。`val_segments >= 512`。
**FAIL**: `ok==False` → 打印 `violations`,泄漏的 work_key 说明 C1 的 PDMX 选曲没过滤黑名单;回到 C1 传入 `bl` 重跑。

---

## D. dataset.py 配对音频↔标签 —— #4 / #5【已写骨架,需本地填真实路径 + 验证】

**现状**: `rubato/data/dataset.py` **已实现**(encode_target / collate_batch / RubatoDataset /
RubatoDataModule),沙盒逻辑测过(`tests_dataset.py` 33 项:token_types/ts_bins/loss_mask/
teacher-forcing 右移/tiling/collate 契约)。**仍需本地做的**:①填真实 labels.jsonl / 音频路径;
②确认 `load_audio` 的 FLAC/Opus 解码在你环境可用;③tiling×预设链次序(R-S4.5)。

**batch 契约(collate 必须产出)**:
```
audio       (B,S)   16k mono 波形(tiling 补齐后;R-S4.5 先 tile-pad 后预设链)
audio_lens  (B,)
input_ids   (B,L)   [prompt + 标签 tokens + eot] 去掉最后一位(teacher forcing 右移)
input_lens  (B,)
labels      (B,L)   完整序列去掉第一位(与 input_ids 错一位对齐)
token_types (B,L)   0=语义 1=时间戳(与 labels 对齐;时间戳 token id 属 <|tN|>)
loss_mask   (B,L)   bool,prompt 位置 False(R-S10.4)
ts_bins     (B,L)   时间戳位置的 bin 编号(0..3999),其余位置 0
```
**构造要点**:
- prompt 用 `build.DIALECT_PROMPT[dialect]`;`build_target_sequence()` 已产 tokens + loss_mask。
- token 化:`tokenizer.encode(text)`;训练期子词正则用 `tokenizer.encode_with_regularization(sp, text, alpha=0.25)`(R-S9.4);eval 用确定性。
- dialect 采样:每 epoch 调 `sampling.dialect_sampler(available_by_utt, seed, epoch)`;tiling 用 `sampling.tiling_offset(...)`,时间戳整体 +t0 后重新 bin 化。
- bucketing:`train.bucket_batches(samples, max_batch_sec=560)`。
- 音频源:MAESTRO FLAC(AMT)、flat/vn/human Opus、nASAP 借 MAESTRO FLAC。labels 来自 `labels.jsonl`(C 步产出)+ `maestro_amt_labels.jsonl`(gen_amt_labels.py 产出)。

**装配(dataset.py 已提供)**:
```python
from rubato.data.dataset import RubatoDataset, RubatoDataModule
train_ds = RubatoDataset(utts, labels, sp_tokenizer)      # utts=manifest_utts, labels=labels.jsonl
dm = RubatoDataModule(train_ds, nasap_val, maestro_val)
# train.py: for batch in dm.train_batches(epoch): ...(已对接)
```
**判据(PASS)**:
1. 单 batch 冒烟:`training_step_logic(model, next(dm.train_batches(0)), sp)` 返回 `loss.requires_grad==True` 且 `torch.isfinite(loss)`。
2. `batch["input_ids"].shape == batch["labels"].shape`(右移对齐;不齐会在 `training_step_logic` 的 assert 处炸)。
3. 每 dialect 的样本数矩阵与 §1 保留表一致(不得出现 DBD)。
**FAIL**: assert "log_probs 与 labels 未对齐" → collate 的 teacher-forcing 右移错(dataset.encode_target 已做 input=seq[:-1], labels=seq[1:],若改动过此处检查)。

---

## E. 模型冒烟 —— #1 / #21【#1 是否真修好的终判】

**命令**
```python
from rubato.model.build import build_model
model, report = build_model(nemo_path, spm_model, vocab_spec,
                            frontend_wav_paths=[3 段真实 wav])  # #21:必须传,别再漏
print(report["encoder_verify"], report["frontend_verify"], report["param_count"])
# 100 条真实样本过拟合(A-S10.2):
```
**判据(PASS,四条全中)**:
1. `report["encoder_verify"]["ok"] == True`(encoder 权重逐层 hash 匹配,无静默随机初始化,R-S10.2)。
2. `report["frontend_verify"]` 不报结构错(mel 数/hop 一致;归一化差异会给 note 说明,不算失败,R-S10.3)。#21 在此被验证。
3. `report["param_count"]` 的 backbone 与原始 canary 一致(A-S10.1,tied/untied 任一吻合)。
4. **#1 终判**:100 条样本连训,**loss 单调下降到 <0.05**,且生成序列 100% 过 `validate()`。**若 loss 卡在常数不降 = #1 没修好**(回到 `training_step_logic`,确认 `resolve_log_probs` 认出了 forward 的 4 元组、`loss.requires_grad==True`)。
**FAIL**:
- loss 恒定不动 → forward 图断了或又落回零 loss 分支。打印 `type(model.forward(...))`,确认是 4 元组且 `resolve_log_probs` 取到第 0 个。
- encoder_verify.ok==False → change_vocabulary 误伤了 encoder;改用 `resize_decoder_vocab`(build.py 已默认走它)。

---

## F. 渲染吞吐 —— #2 / #8 / #9

**命令**: 用 `render/core.render_midi_to_wav44` 渲一首典型 PDMX MIDI(带踏板),Salamander 音源。
**判据(PASS)**: 单曲渲染在 timeout(600s)内完成且过 `duration_check`(时长与 MIDI 末音差 <1.5s);批量吞吐记入 report(条/分)。
**FAIL(仍超时/极慢)**:
1. 先确认 `sfizz_flags` 生效:`sfizz_render --help` 核对 `--polyphony`/`--use-eot`/`--quality` 的**真实 flag 名**(不同版本可能是 `--max-voices` 等),改 `sources.yaml` 的 `sfizz_flags`。
2. 仍慢 → 生成 Salamander 瘦身版:剥掉 SFZ 里 `trigger=release` 的弦共鸣/击槌/踏板噪声组(那三个 `#include` 段)+ 把 FLAC 采样转 WAV。源路径换成瘦身版,吞吐应提一个量级。
3. 实在不行 → 该曲权重重归一到 Splendid/Kamoepiano(它们已验证正常),Salamander 占比临时下调。

---

## G. 推理 + 评测 —— #7 / #19

### G1. 窗合并(#7)—— A-S12.1
**命令**: 取 10 段真实长曲,`infer.infer_a2s(model, audio, tokenizer)`;与整曲一次性解码(截 40s 内短曲)对照。
**判据(PASS)**: 合并后 `validate()` 全过;**重叠区小节一致率 >95%**(A-S12.1)。
**FAIL**: 一致率低 → 打印相邻窗的重叠小节,看 `merge_ref._concat_ir` 的 Jaccard 匹配是否把该重叠的小节判成了不重叠(强制保留导致重复)。跨窗延音断裂 → 查接缝延音融合(offset 恰在缝上 + onset 恰在缝上是否配上对)。

### G2. 评测端到端(#19)
**命令**: `evaluate` + LEGATO OMR-NED 脚本(U10),对 nASAP test / MAESTRO test。
**判据(PASS)**: 跑通产 `eval_report.md`;数字对照论文(用**修正后**的 `PAPER_NUMBERS`:MAESTRO AMT F1 97.0、OMR-NED 64.3/78.7/75.9)。差距标注"可缩/结构性"用的是对的指标方向(OMR-NED 越低越好,F1 越高越好)。
**FAIL**: `omr_ned_via_legato` 需注入 LEGATO 调用(`legato_fn`);未注入会报缺函数,不是 bug。

---

## 判据速查表(硬数字)

| 项 | 硬判据 | 沙盒病态值 |
|---|---|---|
| B tokenizer | vocab==8000, learnable==3571, split_rate<0.30 | 4760, — , ~1.0 |
| C2 xml_id 匹配 | matched/total > 80% | 0.37% |
| C3 泄漏 | leakage ok==True, val_segs≥512 | 未跑 |
| D dataloader | loss.requires_grad==True, input/labels 同形 | 未实现 |
| E #1 终判 | 100 条过拟合 loss<0.05 | loss 恒 0 |
| E #21 前端 | frontend_verify 无结构错 | 未传 wav |
| G1 窗合并 | 重叠区小节一致率>95% | 未跑 |

**任何一项不达 = 未修复。** 不达时按对应"FAIL"排查,修好再推进下游。
