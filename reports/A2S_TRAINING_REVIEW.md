# A2S 训练链审查与修复方案

日期：2026-07-20  
范围：只审查 **audio → A2S/InterMo → MusicXML** 的训练有效性。AMT、TAST、评测只在它们影响 A2S 训练或推理时讨论。本文不改变正在运行的 D43/61000 试验。

## 结论

当前训练的损失、采样和 batch=50 语义没有发现会使 A2S 学不到的直接错误；但发现了一项**已由代码证实的训练—推理 prompt 不一致**，优先级高于继续调 batch、学习率或混比：

> 训练中每一条样本都带 `<|real|>` 或 `<|synth|>` 域提示；当前 A2S/TAST 自由推理没有带该提示。

这意味着模型从未在“仅 dialect prompt 后直接生成乐谱”的条件下训练，却在实际推理时被要求这样生成。它可直接造成教师强制指标尚可、自由 A2S 生成却低可解析率的落差。该结论是代码事实；“它造成了多少损失”仍须做同 checkpoint 的对照测量，不能凭推断量化。

**建议顺序**：完成当前预登记的 61000 step 观察；随后先做 prompt 对照（不改权重），再实施 prompt API 修复；之后才做数据增广消融。不要在同一轮同时改混比、数据、prompt 和解码。

## 1. 已证实的问题：域提示训练—推理不一致

### 1.1 训练实际输入

`scripts/build_dataset.py` 的四个训练源都声明了域：PDMX 为 `synth`，nASAP 和 MAESTRO 为 `real`。`rubato/data/assemble.py` 将它写入每个 utt；`RubatoDataset.__getitem__()` 将该字段传给 `encode_target()`；后者在 dialect prompt 后追加 `<|real|>` 或 `<|synth|>`。

因此当前 A2S/A2S_lite/TAST/AMT 的所有训练样本都使用：

```
<dialect prompt> <|real|>  <target tokens>
```

或：

```
<dialect prompt> <|synth|> <target tokens>
```

域 token 不计 loss，但它是 decoder 的条件上下文，仍会改变第一步及后续 token 的条件分布。

### 1.2 当前推理实际输入

`rubato/model/infer.py` 的 `build_tast_prompt()` 和 `autoregressive_decode()` 只使用 `DIALECT_PROMPT[dialect]`；`infer_a2s` 走同一条自由解码路径。没有调用方为 A2S/TAST 推理追加 domain token。

所以线上自由生成的前缀为：

```
<dialect prompt> <target tokens>
```

这是训练分布外前缀。更值得注意的是，`teacher_forced_probe()` 为了“与训练同构”会传入 domain；因此它验证的是**带域提示的教师强制条件**，不能证明无域提示的自由 A2S 推理也正常。

### 1.3 影响与修复选择

这不是标签或 loss 错位；checkpoint 仍可使用。优先做推理侧显式修复即可。

**方案 A（产品优先，推荐先验证）**

1. 给 `build_tast_prompt`、`infer_a2s`、`single_window_tast`、长音频入口增加显式 `domain` 参数；
2. prompt 由一个共享函数生成，训练与推理不能各自手写；
3. 真实录音调用 `domain="real"`，渲染音频调用 `domain="synth"`；
4. domain 不明确时不允许静默省略，CLI 明确要求选择或打印强警告。

优点：不需要重训，立即与已训练 checkpoint 的条件一致。代价：这是域条件模型；报告中必须说明，不应称为“无域提示”的原论文复现。

**方案 B（论文 prompt 优先）**

去掉训练中的域提示，并从当前 checkpoint 做带/不带 domain 的受控续训或从头训练。优点是推理接口更简单、若论文确实无此 token 则更贴近论文；代价是破坏当前 56k 步的训练条件，不能与现 run 的曲线直接比较。

先做方案 A 的无权重对照，再决定方案 B 是否值得付出重训成本。

### 1.4 必须先做的判定实验（不改训练权重）

固定同一 checkpoint、同一批 48 条 nASAP real validation 样本、同一解码配置，仅改变 prompt：

| 组 | prompt | 目的 |
|---|---|---|
| G0 | 当前无 domain | 现状基线 |
| G1 | `domain=real` | 与训练条件一致的真实录音推理 |
| G2 | `domain=synth` | 反向控制，验证不是任意多一个 token 都“变好” |

报告 A2S 可解析率、每条文本 NED proxy、首 token/EOT 分布和 10 个固定样本输出；不要只报平均 loss。若 G1 显著优于 G0 且 G2 不同，立即将真实录音默认改为 G1。该实验只占一次小验证窗口，等当前 61000 试验结束或训练暂停后再跑，避免与正在训练的 GPU 争抢。

## 2. 训练链中已确认正常的部分

以下项目与论文 §3.3 的训练适配一致，当前没有证据要求动它们：

1. **A2S 目标权重并未被边缘化。** 当前 mix 为 A2S 0.390 + A2S_lite 0.167 = **0.557**；直接乐谱目标超过一半。最新 epoch 池/配额为 A2S `108448/87742`、A2S_lite `109009/37604`，均未有放回过采样。
2. **损失实现正确。** `batch_sequence_loss` 对每序列使用 `Σ CE × |T|^(-1/2)`；语义 token 用 0.1 label smoothing；timestamp token 用中心 0.9、±5 bin 二次序数平滑。A2S 不含 timestamp，不受后者干扰。
3. **子词正则化已启用。** 训练 `encode_target(... enable_sampling=True, alpha=0.25)`，与论文设置一致；eval/推理用确定性切分。
4. **batch=50 没有改变优化目标。** 梯度仍累计到约 2000 audio-seconds/step；它只把 micro-batch 切小以消除 WDDM 共享显存溢出。验收已显示共享 GPU 内存约 86 MB，较基线 1576 MB 降低，计算时间仍在预登记上限内。
5. **当前 A2S 曲线不能据 56000 就判失败。** 61000 的 O4 判据已预登记；在该节点前改 mix 会使当前“0.22 AMT + 新召回数据”的观察不可归因。

## 3. A2S 训练的高风险项：合成域多样性不足

论文的关键做法不是只用“有合成音频的 PDMX”，而是同一乐谱内容覆盖多种声学实现：8 个 piano VST × 2 个 room/mic configuration，共 16 个 timbral variants。其目的正是让 A2S 从合成音频迁移到真实钢琴录音。

当前实现有 5 个免费音源和录音预设，覆盖面并非为零；但渲染时 `assign_source_and_preset()` 按 `utt_id/piece_id` 的 hash 固定选一个组合。相同曲/段在后续 epoch 中仍读同一音频文件。`online_room_augment()` 已实现，却没有被 `RubatoDataset.__getitem__()` 调用；当前路径只有 `load_audio()`。

这不是立刻可判为 bug：如果离线资料已为每一 utt 生成多个版本，固定分配可成立。但现有装配统计中的 A2S 可用数约 126k，远低于论文表中 PDMX A2S 的 1002k 增强后 utterances，且代码路径显示一条训练记录只对应一个音频路径。因此应把它视为**必须量化的训练规模/多样性风险**。

### 3.1 先审计，不靠文件名推断

新增只读审计应输出：

- 每个 `piece_id` 的 distinct `audio_path`、source、preset 数；
- PDMX A2S/A2S_lite/TAST 的 distinct score、distinct audio、domain、duration 直方图；
- 训练集与 val/test 的 work_key/dup_cluster 交集（应为 0）；
- 与论文 Table 1 同口径的“增强后 (audio,label,dialect) 对”计数。

若每 score 只有一个 rendered audio，应承认当前是“跨 score 的音色多样性”，不是论文的“同内容多声学视图”。

### 3.2 建议的增广路径

不应在已有湿声上盲目重复加房间 IR；那会制造不真实的双混响。优先级如下：

1. **最安全的在线增广**：增益、轻度 EQ、背景噪声、动态范围变化等不改变音符/时间标签的变换；固定 seed `(utt_id, epoch)` 以可复现；验证真实样本与合成样本都不过削。
2. **更贴近论文的路径**：保存干声或 MIDI 渲染源；离线生成少量不同音色（例如 4 个 source），训练时再在线采样 room/mic 预设，形成近似 4×4 的多视图，避免把 16 倍波形全部常驻磁盘。
3. **验证准则**：保持 prompt、loss、mix 不变，仅扩声学变体；以固定 nASAP real A2S 集的可解析率/NED proxy 为主指标，而不是合成 train loss。

## 4. TAST 与 AMT 只作为 A2S 的辅助，不应被误删

目标虽是 A2S，但当前长音频路线使用 TAST 的 timestamp 作为窗口终止和小节拼接信号；TAST 不是独立 KPI，却是 A2S 推理机制的一部分。当前 TAST pool 为 `20742`、quota `50138`、过采样 `2.42×`，说明它的**内容多样性**是风险，而不是其名义 mix 太低。

AMT 也不是终点，但 MAESTRO 是大规模真实钢琴音频进入 encoder 的主要通道。当前 MAESTRO 探针的 `Δsem/Δpitch` 近零，表明该辅助任务还未稳定把音高声学信号传给 decoder。不能据此直接把 AMT 配额砍到零：那会使 A2S 几乎只依赖合成 PDMX 与较小的 nASAP real score 对。正确顺序是先修 prompt 一致性、审计真实域增广，再依据 A2S real-audio 结果判断 AMT 是否值得保留或改为更轻的共享音高辅助。

## 5. 不建议现在做的事

- 不因自由解码可解析率低而立刻调大/调小学习率；当前 prompt 不一致尚未排除。
- 不中断正在运行的 `--max-batch-sec 50` 训练；该变更已验收且不改学习语义。
- 不在 61000 前再改 AMT mix、TAST mix、数据集和解码策略；这会毁掉已预登记的 O4 比较。
- 不把 AMT F1 当作项目终点，也不把它完全忽略；它只作为 A2S 真实域声学辅助是否工作的一项证据。

## 6. 建议执行顺序与验收

### 阶段 A：当前 run 不动

继续至 61000，按既定 O4 判据记录 A2S 曲线。batch=50 固定。

### 阶段 B：prompt 对照与修复（最低成本，最高优先）

1. 实现统一 prompt builder，训练和推理共享；
2. 为推理添加强制显式 `domain` 参数；
3. 用 G0/G1/G2 跑固定 real A2S 样本；
4. 通过条件：G1 相对 G0 在可解析率或 NED proxy 有可复现改善，且 G2 不呈同样改善；
5. 通过后，真实 A2S 推理默认 `real`，合成诊断使用 `synth`；报告注明域条件。

### 阶段 C：数据多样性审计与单变量消融

1. 先生成 §3.1 的计数报告；
2. 只添加一种安全声学增广或一种额外声学视图；
3. 从同一 checkpoint 分两支、固定训练步数、固定 mix；
4. 比较 real A2S 指标，确认收益后再扩大渲染规模。

### 阶段 D：严格论文复现（可选，成本高）

若目标从“最佳可用 A2S”改为“论文数值复现”，再单独启动 from-scratch、完整 dialect、论文数据规模和无域提示/论文原始 prompt 的 run。它不应覆盖当前热启动 A2S 工程 run。

## 7. 代码与证据索引

- 论文训练适配与 16 声学变体：`Rubato_Transcribing_Piano_Music_with_Timestamps-2.md` §3.3。
- 训练源域字段：`scripts/build_dataset.py:32-39`。
- 域字段写入 utt：`rubato/data/assemble.py:50-103`。
- 训练 prompt 追加 domain：`rubato/data/dataset.py:53-79, 332-338`。
- 自由推理使用基础 prompt：`rubato/model/infer.py:170-245` 与 `build_tast_prompt()`。
- 教师强制探针显式带 domain：`rubato/model/infer.py:494-508`。
- 当前混比/池大小：`reports/RESTART_O4.txt`；当前 batch=50 验收：`reports/MAXBATCH_50.txt`。
