# ATTRIBUTION_ANALYSIS —— 复现失败的归因分析(2026-09-09)

> 读者:用户。目的:对"复现困难"做归因,逐项评估用户提出的三个假设
> (①论文数据失真 ②参数完全偏离正常方法 ③数据量不足导致模型坍塌),并给出证据支持度更高的替代假设。
> 证据来源全部标注文件名;本文不含估算数字,凡是数字均可在所引文件中找到。

## 0. 结论摘要

| 假设 | 证据支持度 | 一句话判定 |
|---|---|---|
| ① 论文数据失真 | 低 | 无任何证据;论文数字与同期文献一致;最显著的失败(AMT F1=0)发生在一个完整、公开、与论文相同的数据集(MAESTRO)上,与论文数据无关。 |
| ② 参数偏离正常方法 | 中(但不是"超参数",是"结构性偏离") | 优化器侧三个实验(H1 裁剪、H2 decoder lr、H2a encoder 信号)均判无效;真正的偏离是热启动语音编码器、SpecAugment 在不知情下始终开启、80ms 帧率。其中 SpecAugment 一项是本次新发现的代码级事实。 |
| ③ 数据量不足→坍塌 | 中低 | 没有经典坍塌(eotP0≈0、无 NaN、损失持续下降、合成侧探针持续改善);数据量差距真实存在(1/8→1/4),它解释 A2S/TAST 的泛化差,但解释不了 AMT 分支的失败。 |
| **替代假设 A:AMT 分支存在管线/模型侧缺陷** | **高** | 同一批真实录音(nASAP 音频即 MAESTRO 音频),TAST 方言能读出音高(验证集 Δpitch +0.44~+0.60),AMT 方言读不出(验证集 Δpitch ≈0,连续 25+ 次评测)。变量只剩"任务/标签/窗口构造/训练期扰动",不是音频域,不是数据量。 |
| **替代假设 B:评测集被训练集污染(反向泄漏未审计)** | **中高** | nASAP val/test 录音是否落在 MAESTRO 官方 train 切分(AMT 窗)从未对账;只审计过反方向。论文明确采用了比标准切分更保守的保留策略。 |

**最重要的一条结论**:项目所有评测与判决都建立在"模型读不读音频"这个探针上,而 SpecAugment 在训练期实际开启(见 §3.2)这一事实从未被核实。它直接作用于"读音频的性价比",是所有"抄近路"症状的共同上游候选,且核实成本为一行代码。

## 1. 症状清单(全部有出处)

| 症状 | 数值 | 出处 |
|---|---|---|
| 自由解码可解析率(48 条 nASAP val) | 0.04~0.15,68k 步无上行趋势 | reports/eval_autolog.md 38000-67000 |
| 通过样本的文本差异代理(omr_ned proxy,越低越好) | 0.81~0.95 | 同上 |
| AMT 音符 F1(MAESTRO val) | 0.0(全程,唯一例外一次 0.34 未复现) | 同上,`eval 指标` 行 |
| maestro/AMT 探针 Δpitch(真音频−静音) | −0.06~+0.01,25+ 次评测贴零;真pitch 0.15~0.20 | 同上,`多源探针 maestro/AMT` 行 |
| nasap/TAST 探针 Δpitch(验证集样本) | +0.23~+0.60;真pitch 0.69~0.72 | 同上,`多源探针 nasap/TAST` 行 |
| pdmx 合成探针 Δpitch(训练集样本) | +0.24~+0.54 | 同上 |
| AMT 静音条件下语义 token 命中率(静sem) | 0.72 | 同上 |
| 训练损失 A2S 滚动均值 | 3.21@7600 → 2.59@53050 → 2.32(二轮试验 79k) | HANDOFF.md §4;EXPERIMENT_O4_MIX.md;DECISIONS D78 |
| 二轮试验(池 v3,68k→79k)maestro Δpitch | −0.05/−0.04/+0.04/+0.03/−0.01/+0.00/−0.05/+0.00 | DECISIONS D78 |
| 拒因直方图(48 样本) | DYCK 34 / MEASURE 24 / parse_error 22 / TERMINAL 21 | EXPERIMENT_PROMPT.md 判决节 |

关键对照:**nASAP 的音频就是 MAESTRO 的录音**(scripts/s7_full_nasap.py 按 `maestro_audio_performance` 取 flac;scripts/audit_split_leakage.py 首段文档亦说明两者共用整曲录音库)。因此"maestro 读不出、nasap 读得出"不是音频域差异,而是方言/标签/窗口/训练条件差异。

## 2. 假设①:论文数据失真 —— 不成立(无证据)

1. 论文真实存在:arXiv 2605.24291(2026-05-22),作者 Tamer/Ebert/Yang/Smith(UW/AI2)。
2. 论文数字与同期公开系统一致,不存在离群值:AMT note F1 97.0 低于 Tkun 98.3、Aria 97.6,略高于 Bytedance 96.8、MT3 95.7(论文 Table 3);beat F1 与 Beat-This 同一区间。OMR-NED 是新指标,无法交叉核对,但 Table 2 里的级联基线数与各自论文口径相符。
3. 论文声明"We release the score excerpts and synthesized utterances for reproducibility"(§3.3)。本仓库全文检索(`nctamer|released|官方数据`)零命中 —— **复现从未尝试获取论文放出的合成数据**,而是自建了 5 个免费音源 × 程序化预设的替代管线(SPEC D2)。这意味着"数据失真"假设在本项目里从未被测试过,它的可测试性很高。
4. 最强反证:AMT 分支的训练数据 = MAESTRO v3 全量(159 小时,与论文 Table 1 相同),没有任何论文私有成分。单独在 MAESTRO 上训练的公开 AMT 系统(Onsets and Frames 及其后继)均达 95+ F1。本项目该分支 F1=0,与论文数据无关。

判定:该假设优先级最低。若仍想排除,最便宜的做法是拿到论文放出的合成 utterances 直接替换 PDMX 自渲染池(见 §6 E4)。

## 3. 假设②:参数偏离正常方法 —— 超参数不偏离,结构性偏离有三处

### 3.1 已被实验排除的超参数嫌疑

| 嫌疑 | 实验 | 判决 | 出处 |
|---|---|---|---|
| 梯度裁剪 1.0 压死步长 | clip 1.0 → 25 续训 500 步 | 不成立(斜率 −0.113 vs 基线 −0.086,判据线 −0.20) | EXPERIMENT_H1.md §6 |
| encoder 收不到梯度 | enc/dec 范数比 0.79~1.32 | 不成立 | 同上 |
| decoder lr 过高 | 5e-4 → 3e-4 续训 2000 步 | 无效(锚点 3.02 → 3.02) | EXPERIMENT_H2.md 判决节 |
| AMT 混比过高 | 0.30 → 0.22 跑 8000 步 | 未达标 | EXPERIMENT_O4_MIX.md |
| 训推前缀不一致(域 token) | G0/G1/G2 同 ckpt 对照 | 无实质伤害 | EXPERIMENT_PROMPT.md |

现行配置(configs/train.yaml + 正典命令):AdamW β(0.9,0.98) wd 0.01、cosine warmup 1500、lr enc 1e-4 / dec 3e-4、bf16、有效批 2000 音频秒/步。与 Canary 官方配方(lr 3e-4、AdamW、不裁剪)和 LEGATO/M2ST(lr 3e-4)在同一区间(REF_EXTERNAL_RECIPES.md)。**论文本身未给出任何优化器参数**,"参数完全偏离论文"这一说法无法成立,因为论文没有可偏离的参数。

### 3.2 结构性偏离(这三处才是真正与论文不同的地方)

**(1) SpecAugment 在训练期实际开启,而配置声称关闭 —— 本次新发现,未经运行时核实。**

- configs/train.yaml:`specaugment: false`;scripts/build_dataset.py:732 只拒绝 `specaugment: true`,不做任何关闭动作。
- 全仓库检索 `spec_augmentation` 零命中:没有任何代码把恢复模型的 `model.spec_augmentation` 置空。
- rubato/model/train.py 训练步直接调用 `model.forward(processed_signal=..., transcript=...)`,且 train.py:1208 处于 `model.train()` 模式。
- NeMo 源码(nemo/collections/asr/models/aed_multitask_models.py,main 分支)`EncDecMultiTaskModel.forward`:
  ```python
  if self.spec_augmentation is not None and self.training:
      processed_signal = self.spec_augmentation(input_spec=processed_signal, length=processed_signal_length)
  ```
- Canary 官方训练配置(examples/asr/conf/speech_multitask/fast-conformer_aed.yaml)的 spec_augment:`freq_masks: 2, time_masks: 10, freq_width: 27, time_width: 0.05`;`.nemo` 恢复时会按模型内嵌配置实例化该模块。

含义:若 canary-180m-flash 的内嵌配置含 spec_augment(canary 系列训练均使用),则一轮 68k 步、二轮试验、二轮全新热启,**所有训练步的 mel 输入都经过了 2 条最宽 27/128 的频带掩蔽和 10 条各最长 5% 时长的时间掩蔽**。而所有探针与评测在 `model.eval()` 下运行,不受掩蔽 —— 训练与评测看到的输入分布不同。

这与已观察到的病理精确吻合:模型在训练时被系统性地教导"音频不可靠,文本先验更稳"。对 TAST/A2S,乐谱结构冗余使模型仍能部分读音频;对 AMT,音高是唯一需要音频的信息、且每个音符只在少数帧上有证据,时间掩蔽直接抹掉证据,梯度转向文本先验(静sem 0.72 说明 AMT 七成语义 token 本就可由文本预测)。项目早在 EXPERIMENT_C_ROOTCAUSE.md 就把"SpecAugment 掩蔽过狠"列为次号嫌疑并要求"执行端贴 model.cfg 的 spec_augment 段",但账本(DECISIONS D27-D31)显示该项从未被贴回、从未被核实,数据侧被判"无罪"后此线索被搁置。

**(2) 热启动语音编码器(论文 from scratch)+ 80ms 帧率(论文 40ms)。**

- DECISIONS D1:热启动的理由是"没有 ~8.5 万 GPU 小时"。SPEC D5:接受 canary 默认帧率,Canary 官方配置 `subsampling_factor: 8` 即 80ms/帧,论文 §3.3 明确写"encoder's 40 ms frame rate"。
- 语音 ASR 编码器的训练目标是对说话人基频不变;钢琴转谱恰恰需要精确的基频/谐波信息。encoder lr 1e-4 且梯度范数与 decoder 同量级,只能说明 encoder 在动,不能说明它学会了音高表征。二轮试验 D78 的结论"一轮权重对真实音频的聋是权重级顽疾"与此一致,但项目把它归因于"数据不在场",未检验编码器本身。
- 80ms 帧对 10ms 时间戳的影响是时间精度,不是音高;此项对 AMT F1 有影响但不是 F1=0 的原因。

**(3) 其它偏离(影响较小,列出备查)**:语义 token label smoothing 0.1(论文只有时间戳序数平滑;Canary 官方 0.0)使 sem 曲线有 ~1 nat 地板;decoder 位置上限 1024 导致超长样本丢弃(HANDOFF §2:TAST 5,389 / A2S 6,005 / A2S_lite 5,369);有效批 2000 音频秒(Canary 官方 46,000)。

判定:用户所说"参数完全偏离"在超参数层面不成立,在结构层面有一项已证实的、未经核实运行时效果的偏离(SpecAugment),和一项论文明确不同但项目主动接受的偏离(热启动 + 帧率)。

## 4. 假设③:数据量不足导致坍塌 —— 部分成立,但不是主因

### 4.1 没有"坍塌"

- eotP0(首位终止符概率)全程 0.0000~0.0001(reports/eval_autolog.md 每个 `eval 汇总` 行);
- 无 NaN、无损失上翘(H1/H2 卡止损未触发);
- 合成侧探针持续改善(pdmx 真pitch 0.49→0.64、0.77→0.79);
- 教师强制总命中率 0.58→0.68 上行;
- 复读循环是自由解码未成熟的生成端症状(D25),不是表征坍塌。

### 4.2 数据差距真实,但解释不了核心症状

| 项 | 论文 | 本项目一轮 | 二轮 v3 | 出处 |
|---|---|---|---|---|
| 总 utterances(扣 DBD) | 3,181k | ~270k(1/8 以下) | 753k(≈1/4) | REF_DATA_SCALE.md;ROUND2_POOL_7_R3.txt |
| PDMX 原始小时 | 2,071h | ≈700h | 同 | REF_DATA_SCALE.md |
| TAST | 725k | 29k(1/25) | 199k | 同上 |
| 每份内容声学视角 | 16 音色 | 1(二轮部分 2) | | 同上 |
| MAESTRO AMT | 159h / 804k | 159h / 144k | 374k | 同上 |

一轮 68k 步 × 2000 音频秒 ≈ 13 个 epoch(ROUND2_DATA.md、EXPERIMENT_LISTEN.md 均记"13 epoch 高重复池");单一渲染 + 高重复 → 背题风险成立。这能解释 **A2S/TAST 在验证集上可解析率不上行、通过样本仍粗糙**。

它解释不了 AMT:MAESTRO 是完整的,AMT 不需要 PDMX 的音色多样性(paper 的 PDMX 合成 AMT 436k 是补充,不是必要条件;单独 MAESTRO 训练的公开系统均可达 95+ F1)。二轮试验把池扩到 2.8 倍后 maestro Δpitch 仍为零(D78),也说明"加数据"不是该症状的杠杆。

判定:数据量是 A2S/TAST 泛化差距的次要原因,不是 AMT 失败的原因,也不构成"坍塌"。

## 5. 证据支持度更高的替代假设

### A. AMT 分支缺陷(管线或模型侧),优先级最高

推理链:①音频相同(nASAP ⊂ MAESTRO);②TAST 在验证集样本上读出音高,AMT 在验证集样本上读不出;③AMT 对齐审计与色度审计判 OK(D31),但审计粒度是 100ms 色度相似度,只能排除"配错文件/大偏移",不能排除训练条件差异。剩余候选按可检验性排序:

1. **SpecAugment 隐性开启**(§3.2(1))。对 AMT 的伤害最大:AMT 无结构冗余、证据帧稀疏。
2. **AMT 序列的损失构成**:静sem 0.72 说明 AMT 语义 token 中力度/踏板/音符关闭大多可由文本预测;音高 token 是唯一依赖音频的部分,又被 1/√T(T≈900)稀释。D82 的音高加权 ×2.5 方向正确,但已在二轮与其它变量打包,无法单独归因。
3. **热启动语音编码器的音高分辨能力**(§3.2(2)):对 AMT 的要求最高(逐帧、多音)。可用线性探针直接检验(§6 E2)。

### B. 反向泄漏未审计,评测口径可能偏乐观

scripts/audit_split_leakage.py 只检查"nasap-train 是否引用 maestro val/test 录音"(D51 查出 78 场/1,239 行并隔离)。**反方向 —— nasap val/test 的录音是否作为 AMT 窗出现在 maestro-train —— 没有任何脚本检查。** nASAP 按 work_key 划分(rubato/data/nasap.py conservative_split),MAESTRO 按官方切分(s6_amt_windows.py `skip_nontrain`),两者独立,交集几乎必然存在。

后果:(a)48 条 nASAP val 的可解析率、探针 Δpitch 可能含"训练期听过该录音"的成分,真实泛化能力低于日志读数;(b)论文 §3.3 明确"conservative split that holds out more recordings than the standard partition",本项目未复现这一点,终评数字将不可与论文比较。

### C. 论文放出的合成数据未被使用(与假设①同源的免费杠杆)

见 §2 第 3 条。

## 6. 建议的判决实验(按成本升序,每项单变量、判据预先写死)

**E1 · SpecAugment 核实与关闭(成本:分钟级 + 一次 AMT 冒烟)**
- 启动时打印 `model.spec_augmentation` 与 `model.cfg.get("spec_augment")`;非 None 即证实 §3.2(1)。
- 在 build_model 后加 `model.spec_augmentation = None`(或 cfg 显式置空),把 train.yaml 的 `specaugment: false` 变成真实行为。
- 判决实验:从 canary 热启,**只训 AMT**(混比 AMT=1.0),64 条 MAESTRO 窗、关 tiling/关 alpha/关 C1a,过拟合 2000 步;再从同起点在完整 MAESTRO-train 上训 5k 步。判据:过拟合组真pitch ≥0.9(证明音频→音高通路机械可学);5k 步组 maestro val Δpitch ≥ +0.10。两组分别对照 SpecAugment 开/关。若"关"组通过、"开"组不通过 → 一轮/二轮的核心症状归因于此。

**E2 · 编码器音高线性探针(成本:CPU/单卡小时级,不训主模型)**
- 冻结编码器,对 MAESTRO 帧级 88 维多标签(由 MIDI 对齐生成)训一个线性层,分别测:原始 canary 编码器、一轮 68k 编码器、二轮编码器。判据:帧级音高 F1。若原始 canary 编码器的线性可读音高 F1 明显低于从零训练的小型 CQT 基线 → 热启动是结构性瓶颈,应启用 `build_model(from_scratch=True)`(代码已在 rubato/model/build.py)并用统一 lr。

**E3 · 反向泄漏审计(成本:CPU 分钟级)**
- 复制 audit_split_leakage.py 逻辑,方向反转:nasap val/test 引用的 flac ∩ maestro-train AMT 窗。非零则从 AMT 训练窗中移除这些录音(train-only 原则,评测集不动),与论文保守切分对齐。

**E4 · 获取论文放出的合成 utterances(成本:下载 + 装配适配)**
- 若可获取,用它替换 PDMX 自渲染池做一次同配置对照;这是对假设①的直接检验,同时消除 16 音色 vs 1 音色的差异。

**E5 · 帧率(成本:高,最后做)**
- 仅在 E1/E2 通过、AMT 起音 F1 仍受 50ms 容差限制时,再考虑改 subsampling 为 4(与论文 40ms 对齐),此时必须从零训练。

## 7. 对"几乎放弃"的判断

项目已投入的诊断把优化器侧和数据对齐侧都排除了,剩下的两个未核实项(SpecAugment 运行时状态、编码器音高可读性)恰好都便宜,且都直接指向核心症状。在这两项有结果之前,放弃的依据不充分;在它们都通过而症状不变之后,再讨论数据规模才是有意义的顺序。
