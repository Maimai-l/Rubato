# REF_EXTERNAL_RECIPES —— 外部训练配方参照(先验,不是事实)

> 背景:Rubato 论文把损失/数据侧钉死(1/√|T|、序数时间戳平滑 0.9±5、α=0.25、tiling、混比),
> 但**优化器侧只字未提**(无 lr/schedule/warmup/batch/步数/裁剪)。我们卡住的超参无从"复现",
> 只能自己定。本文件收集三个最近参照项目的**一手配方**,供设计预登记实验(D20 模式)用。
>
> **铁律**:此处数字全部是外部先验 —— ①只进实验设计,不直接进配置;②每个数字带出处
> (arXiv 编号/文件路径,访问日 2026-07-14,经沙盒代理原文抓取核对);③迁移前先读 §4 折扣声明。

## 1. 参照项目与选取理由

| 项目 | 任务 | 为什么参照 |
|---|---|---|
| **LEGATO**(arXiv 2506.19065) | 多页乐谱图像 → ABC 记谱 | 同源数据(PDMX→PDMX-Synth 214K+)、同构训练形态(跨域预训练 encoder + 全新符号词表 decoder → 紧凑符号谱文本);我们的终评 OMR-NED/musicdiff 契约即来自它 |
| **M2ST**(Beyer & Dai,arXiv 2410.00210) | 演奏 MIDI → 乐谱 token | decoder 侧最近参照(符号谱序列生成),也是论文 Table 2 里我们要打的最强 cascade |
| **Canary**(NVIDIA,arXiv 2406.19674 + NeMo 官方配置) | 语音 → 文本(多任务 AED) | **就是我们热启动的架构**(FastConformer + Transformer decoder);同为"encoder 热启动 + decoder 换新词表"形态,优化器数字在同一架构上被验证过 |

## 2. 配方对照表(空白=该来源未说明)

| 项 | Rubato 论文 | 我们现行 | LEGATO | M2ST | Canary(官方) |
|---|---|---|---|---|---|
| encoder | from scratch | 热启动 canary-180m,enc lr 1e-4 | **冻结**(Llama-3.2-11B-Vision 的视觉 encoder 组件,836M) | 从头(小模型) | **热启动**自家预训练 encoder("helped converge") |
| decoder | from scratch | 换 8000 词表,lr 5e-4 | 101M 从头(L_d=8)+ 5.9M projector | 从头 | 从头 |
| optimizer | — | AdamW β(0.9,0.98) wd 0.01 | AdamW β(0.9,0.99) ε=1e-6 | AdamW | AdamW β(0.9,0.98) wd 1e-3 |
| 峰值 lr | — | enc 1e-4 / dec 5e-4 | **3e-4** | **3e-4** | **3e-4**(单一 lr,不差分) |
| schedule | — | cosine→10%,按 100k | linear,warmup ratio 0.03 | cosine,warmup 4k | Noam/InvSqrt,warmup 2.5k,min_lr 1e-6 |
| **梯度裁剪** | — | 1.0(实验中:25) | 未提 | 0.5(max value) | **0.0 = 不裁剪**(yaml `trainer.gradient_clip_val: 0.0`) |
| sem label smoothing | —(只有 ts 序数平滑) | 0.1(自选) | 未提 | 未提 | **0.0**(yaml `model.label_smoothing: 0.0`) |
| batch | — | 累积至 2000 audio-sec/步 | 32 | 32 × 512 tok | **360 audio-sec/GPU × 128 A100**(动态桶,quadratic_duration 20s,31 桶) |
| 总步数 | — | 100k 计划 | 10 epochs ≈ 67k 步(214K÷32×10) | 40k 步 | 225k 步(stage-1 150k) |
| 精度 | — | bf16 | bf16 | — | bf16-mixed |
| 推理 | beam 4(论文终评) | 贪心(训练期监控) | beam 10 + repetition penalty 1.1(PDMX-Synth 用 beam 3),max_len 2048 | **贪心 top-1(实测优于替代)** | — |
| eval 节奏 | — | 每 1000 步 × 48 样本/源 | 每 5000 步 × 800 val,取最优 ckpt | — | — |
| 终点质量参考 | OMR-NED 64-79% | — | ABC CER 23.3%(214K 样本 × 67k 步的产物) | — | — |

## 3. 对我们各悬案的先验读数(全部"先验",判决仍归预登定实验)

- **H1(裁剪)**:我们热启动的架构,**原生配方就不裁剪**(clip_val 0.0)——`--clip-norm 25`
  (≈基本不裁)是在向原生配方靠拢,不是冒险偏离;实验的失稳风险先验很低。同时 M2ST 用 0.5
  也能训好:裁剪阈值必须对着**各自的损失量纲**读(逐 token 均值 CE 的 gn 天然 ~1;
  我们 ΣCE×T^{-½} 的 gn 实测 ~25),跨项目抄阈值无意义。H1 判决仍只认 EXPERIMENT_H1 贴回。
- **H2(lr / encoder 适应)**:三家峰值 lr 全是 **3e-4**。我们 dec 5e-4 偏高 1.7×、enc 1e-4 偏低;
  LEGATO encoder 完全冻结仍 SOTA、Canary 对 warm-enc + fresh-dec 用**单一** 3e-4 不差分 →
  "encoder lr 太小是平台期主因"的先验被压低。若 H2 开案,第一格实验应是
  「dec→3e-4 ± enc 冻结/低 lr」,而不是加大 enc lr。
- **H3(耐心/规模)**:外部步数视野 40k / 67k / 225k;我们 7.6k 步 = 计划的 7.6%,
  且仍在降(A2S -0.06/350 步)。LEGATO 在 21.4 万样本上花 6.7 万步才把 ABC CER 压到 23% ——
  符号谱生成的绝对难度如此,**不应指望 1 万步内 parseable 脱 0**。"平台期"在外部视野下
  更像"早段慢坡"。
- **sem label smoothing**:Canary 官方 0.0,我们 0.1(自选,给 sem 读数垫了下界,冒烟为此关平滑)。
  暂不动;读 sem 曲线时记住这层地板。要动就走预登记实验。
- **eval/解码**:M2ST 实测贪心优于替代 → 训练期贪心监控成立。论文终评需 beam
  (Rubato 论文 beam 4;LEGATO beam 10 + rep penalty 1.1 可作实现参考)——beam 未实现仍是未结事项。
- **batch**:Canary 每步 46k audio-sec(360×128),我们 2000 audio-sec,差 23×。
  小批 + 不低的 lr = 梯度噪声更大;将来动 lr 时把这一格算进去。

## 4. 迁移性折扣(引用本表前必读)

模态不同(图像/MIDI/语音 vs 音频→谱);损失归一不同(它们逐 token 均值,我们 ΣCE×T^{-½},
梯度量纲差 ~20×,一切与梯度绝对值挂钩的数字不可直迁);规模不同(数据量、算力、模型大小:
LEGATO encoder 836M 冻结 vs 我们 180M 全调)。结论:**表中数字用于挑实验格点,不用于免实验改配置**。

## 5. 更正记录(相对此前 chat 中的搜索摘要转述)

- "冻结 11B encoder" → 原文实为 Llama-3.2-11B-Vision 的**视觉 encoder 组件,836M 参数**(§4.2.2)。
- 其余摘要数字(10 epochs / batch 32 / lr 3e-4 / β₂ 0.99 / ε 1e-6 / linear + warmup 0.03 /
  vocab 4097 / >214K 样本)已过原文核对,一致。

## 6. 来源(访问日 2026-07-14)

- LEGATO:arxiv.org/abs/2506.19065(html v1 全文抓取;§4.2-4.3、§5、§6.1)
- M2ST:arxiv.org/abs/2410.00210(html v1;§2.4、§3.1)
- Canary 论文:arxiv.org/abs/2406.19674(html v1;Methods/训练段)
- Canary 官方训练配置:github.com/NVIDIA/NeMo — examples/asr/conf/speech_multitask/fast-conformer_aed.yaml
  (main 分支 raw;optim/sched/trainer.gradient_clip_val/model.label_smoothing 四段)
- canary-180m-flash 模型卡:huggingface.co/nvidia/canary-180m-flash(README;85K 小时训练数据构成)
