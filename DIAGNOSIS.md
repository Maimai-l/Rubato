# Rubato 复刻 · 训练问题诊断与修复报告

**日期**: 2026-07-08
**范围**: 对照论文《Rubato: Transcribing Piano Music with Timestamps》与 SPEC v3,诊断 21 个未解决问题,给出根因、修复与验证。

---

## 0. 一句话结论

**架构没有偏离论文,训练公式也是对的。病灶在两处:①把正确零件"串成能训练的循环"的装配层是坏的;②喂给循环的数据(音频↔标签配对、tokenizer 语料)没打通。** 外加一个仓库级隐患:`.gitignore` 把整个 `rubato/data/` 源码包吞掉了,导致核心数据逻辑从未进入版本库。

对照论文逐项核验的结论:

| 论文/SPEC 要求 | 代码现状 | 判定 |
|---|---|---|
| InterMo 表示(§2:moment/interval/Dyck-1/canonical) | `intermo/core.py` 完整实现,往返无损 | ✅ 一致 |
| 8000 词表布局(§3.2:3571 语义+4000 戳+129 MIDI+1 beat+40 prompt+256 byte+3 特殊) | 核账闭合 3571 | ✅ 一致 |
| 损失三件套(§3.3:`1/√|T|` + 语义平滑 0.1 + 时间戳序数平滑 P=0.9/w=5) | 公式数学正确,但**未接入 backward** | ⚠️ 装配错 |
| 热启动契约(SPEC D1:encoder 载 canary,逐层 hash) | `build.py` 逻辑正确 | ✅ 一致 |
| FastConformer 17L + Transformer 4L(§3) | 架构参数正确 | ✅ 一致 |
| 多任务 dialect 投影(§3.1) | 投影正确,但采样退化成数据自然占比 | ⚠️ 采样错 |

**没有一处是"论文理解错了"或"架构设计错了"。** 全部是工程装配缺陷,可修。

---

## 1. 硬阻塞(2)

### #1 training_step 学不到东西 —— 最致命,根因与表象不同

**表象**:以为"NeMo 的 `training_step` 需要 lhotse batch,纯 PyTorch 循环驱动不了"。

**真根因**(`train.py:101-116` 旧版):调 `model.forward(...)` 后用 `isinstance(output, dict)/Tensor` 取 loss,**判不中就静默 fallback 成 `torch.tensor(0.0)`**。而 NeMo `EncDecMultiTaskModel.forward()` 返回 **4 元组** `(transf_log_probs, encoded_len, enc_states, enc_mask)`,永远命不中 → 每步 loss=0 → **训练跑通但零梯度,白烧卡**。三件套损失当时是在 `torch.no_grad()` 里当监控指标算的,根本没进梯度。

**修复**(不需要 lhotse):
- `resolve_log_probs()`:认元组取第 0 个,**认不出直接抛 TypeError,绝不静默归零**。
- `batch_sequence_loss()`:三件套完全向量化,直接在 `log_probs` 上算 `-Σ q·logp`,真正进 backward。
- 加梯度累积到 ~2000 audio-sec/步 + bf16 autocast(R-S11.4 此前缺失)。
- 回归测试 `tests_train_step.py`:mock NeMo(forward 返回 4 元组)端到端验证 loss>0、有梯度、backward 后参数梯度非零。

### #2 Salamander sfizz 渲染卡死

**根因**:渲染调用**无任何超时**;Salamander V3(kinwie 版)三重放大——1.4GB FLAC 采样、每个 note-off 触发弦共鸣/击槌/踏板噪声的 release 采样、`note_polyphony=1` 抢音。钢琴 MIDI 常压 CC64 → 声部爆炸 → sfizz 以远低于实时速度慢渲,表现为卡死。小 SFZ(Splendid/Kamoepiano)无这些附加层故正常。

**修复**(`render/core.py` + `sources.yaml`):渲染加 `timeout`(默认 600s,超时记 failures 重试/标废);`sfizz_flags: [--polyphony 96, --use-eot, --quality 2]`;补 `duration_check` QC 门(R-S4.4 原只实现静音检测一半)。根治建议:先剥 Salamander 的 release/噪声层并 FLAC→WAV 生成瘦身版。

---

## 2. 直接阻塞训练质量(5)

| # | 根因 | 修复 |
|---|---|---|
| **#3** 词表 4760≠8000 | UnigramLM 语料不足自动缩表;nASAP 39.9M chars 太小 | `tokenizer.py` 固化 R-S9.1 不变量(`identity` 归一化防改写 `\|/#/:`);`check_glyph_coverage` 量化字形分裂率(#20 验收);**根治靠 #11 补 PDMX 语料** |
| **#4/#5** 音频无配对标签/无 lhotse manifest | 整个 `rubato/data/` 包缺失(见 §5) | 重建 data 包;`training_step_logic` 的 batch 契约定义了标签插入点;**不依赖 lhotse**,普通 Dataset+collate 即可 |
| **#6** TAST 时间戳匹配率 0.37% | 对齐 TSV 的 `xml_id` 与 partitura note id 命名不一致,精确匹配全丢 | `nasap_timemap.py` 多策略匹配(精确→归一化→末段);非单调锚点剔除;<2 锚点返回 None |
| **#7** 窗合并算法错 | `truncate_after_20s` 用 `rfind("\|")` 会切进 `<\|tN\|>` 内部→过 20s 的窗塌成空谱;`merge_ref` 无匹配时强制丢一个真实小节 | 单元级截断+跨切点延音在边界补 offset(Dyck);merge 改精确→模糊 Jaccard→保留(宁重复不丢失)+接缝延音融合 |

---

## 3. 数据管线不完整(8)

| # | 根因 | 修复 |
|---|---|---|
| **#8/#9** S4/S5 产出远低于目标 | Salamander 超时(#2) | 见 #2;超时不再挂死管线 |
| **#10** 表现性渲染全用 Chopin | batch 脚本写死 `--composer Chopin` | `composer_alias.py` 三级策略(元数据命中→shuffle_p 0.15→加权 fallback),全由 `hash(seed,piece_id)` 派生。自检:8 个作曲家,可复现 |
| **#11** PDMX A2S 标签从未生成 | 逻辑有,但无批量脚本 | `scripts/s5_pdmx_a2s_labels.py`:`part_to_ir→segment→project(A2S/lite)`,产 labels.jsonl + tokenizer 语料 |
| **#12** S6 AMT 标签未接入训练 | 无配对代码 | `segment.py` + data 包;**AMT 窗用窗内相对时间**(否则 40s 后音符全钳到末 bin) |
| **#13** Tokenizer 语料只有 nASAP | PDMX 标签缺失(#11) | 由 #11 产出的 `a2s_corpus.txt` 补齐 |
| **#14** 黑名单未应用于选曲 | 泄漏检测建了黑名单但选曲不过滤 | `pdmx.build_blacklist/check_split_leakage`;S5 脚本选曲前过滤 |
| **#15** 保守 split 未执行 | `conservative_split` 实现却从不调 | `nasap.conservative_split` 重建;val≥512、按 work_key 隔离、落盘 manifest |

---

## 4. 代码/兼容性 + 已写未跑(6)

| # | 根因 | 修复 |
|---|---|---|
| **#16** Windows 混合斜杠 | `os.sep` 拼接 vs glob 正斜杠 | `platform.posix_path()`;`run()` 容忍 Path 对象 |
| **#17** `platform.run()` 路径解析不稳 | `configs/project.yaml` 相对 CWD 解析 | 锚定仓库根,与 CWD 无关 |
| **#18** render/core.py 本地改动未回传 | peak_normalize 等只在本地 | 已在提交的 core.py 中(peak 归一化位置正确:sfizz 后、噪底前) |
| **#19** evaluate.py 从未跑真实评测 | 无 checkpoint;且 `PAPER_NUMBERS` 把 note F1 误标成 OMR-NED | 修正对照数字(真 OMR-NED 64.3/78.7/75.9);补 `amt_text_to_notes` 供 eval hook |
| **#20** 字形覆盖验收未跑 | 等 tokenizer 重训 | `check_glyph_coverage` 已实现,待 #11 语料重训后跑 |
| **#21** verify_frontend 未接入 | build_model 从不传 `frontend_wav_paths` | 已在 build_model 强制接入(R-S10.3) |

---

## 5. 仓库级隐患(诊断中发现,非 21 项之一)

**`.gitignore` 的 `data/`(未锚定)吞掉了 `rubato/data/` 源码包。** 这是"整个 data 包只在本地存在"的真凶——不是漏提交,是 git 一直静默拒绝加入。同时 `_*` 匹配 `__init__.py`;经核实全仓用命名空间包(无 `__init__.py`),已对齐。修复:`data/` → `/data/`(只忽略根级数据集目录)。

---

## 6. 顺手修掉的隐蔽 bug(诊断副产品)

- `rollback_lr` 的 `lr×0.5` 被 LambdaLR 下一步覆盖(改 `param_groups[lr]` 但 sched 用 `base_lrs×λ` 重算)→ 同时改 `base_lrs`。
- 可解析率被空谱兜底钉在 ~1.0 → R-S11.7 的 `<80%` 止损永不触发 → 空谱按不可解析计。
- MAESTRO AMT F1 eval hook 是注释,但"步≥8000 且 AMT F1<70 停训"依赖它 → 接通 `infer_amt`。
- `dialect_sampler` 逐 utt 按可用性选 → epoch 分布退化成数据自然占比(MAESTRO 只有 AMT 占大头)→ 改全局配额贴合混比。
- config:`mix` 残留 `DBD 0.10`(SPEC 已裁)→ 改回 `.35/.15/.20/.30`;`eval_every_hours` 违反按步数制 → `eval_every_steps: 3000`。
- 长音频末窗被无条件截断 → 丢每曲最后 20s → 末窗不截断。

---

## 7. 验证状态

- **15 个测试套件全绿(245 项检查)**,含 2 个新增回归测试(`tests_train_step.py` 复现 #1、`tests_infer_truncate.py` 复现 #7)。
- 所有需 GPU/NeMo/真实数据的部分写成**带断言的函数**,本地首跑即抓错,不静默跑歪。
- 沙盒不跑真实训练(按用户要求,本地 Windows 跑)。

## 8. 剩余给用户的动作

1. **补 PDMX 语料重训 tokenizer**:跑 `scripts/s5_pdmx_a2s_labels.py` 产 `a2s_corpus.txt` → `tokenizer.train_unigram` → `check_glyph_coverage` 验收词表是否闭合到 8000(#3/#13/#20 的终检)。
2. **本地接 dataloader**:按 `training_step_logic` 的 batch 契约(`input_ids/labels/token_types/loss_mask/ts_bins` + teacher-forcing 右移)把 FLAC/Opus 音频与 labels.jsonl 配对(#4/#5)。
3. **Salamander 瘦身**:剥 release/噪声层 + FLAC→WAV,吞吐提一个量级(#2/#8/#9)。
4. **首次 GPU 冒烟**:`build_model` 载 canary → 100 条过拟合到 loss<0.05(A-S10.2),确认 #1 修复在真实 NeMo 上成立。
