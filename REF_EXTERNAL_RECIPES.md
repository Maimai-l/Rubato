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

## 6. LEGATO 开源代码抽取(2026-08-04,github.com/guang-yng/legato 全库逐文件读)

> 用户问"LEGATO 开源了,有什么训练技巧?"。答案出乎意料也极有信息量:**几乎零技巧**。
> 全库 ~1,400 行核心代码,逐文件核对如下(引用为仓库内路径)。

- **训练器 = 原版 HF Seq2SeqTrainer**(legato/trainer.py):子类只改三件事 —— 存档时跳过
  冻结视觉塔参数、DeepSpeed 排除冻结参数、gen_ 前缀输入路由给 generate。
  **没有 scheduled sampling、没有课程表、没有序列级损失、没有任何自定义训练步**。
- **损失 = 纯逐 token 均值 CE**(legato/models/modeling_legato.py 直通 Mllama forward;
  configs/legato.json 无 label_smoothing_factor ⇒ HF 缺省 0.0)。无辅助头、无加权。
- **数据增广 = 零**(legato/models/image_processing_legato.py 仅做高页切块:高≤4×宽整页,
  否则按 4×宽高度、3×宽步距切 = 25% 重叠窗)。图像原样进模型。
- **超参全靠 HF 缺省**:config 未设 max_grad_norm ⇒ 裁剪 1.0(它们 CE 量纲下 gn~O(1),
  等效温和);lr_scheduler 缺省 linear + warmup_ratio 0.03;AdamW;bf16 + ZeRO-2 +
  torch.compile;10 epochs,batch = 2/卡 × grad_accum 4。
- **训练里真正的"招"只有一个 = 评测制度**(scripts/train.py + configs/legato.json):
  每 5000 步对 mini-val 做**自由生成**(predict_with_generate,beam 3,max_length 2048),
  算 SER(符号错误率,编辑距离类),**best ckpt 按自由生成 SER 选**(metric_for_best_model
  = eval_SER,load_best_model_at_end)。训练目标是纯教师强制,但选优眼睛始终盯着自由生成。
- **指标全是优雅降级,没有硬门归零**:SER/CER 是编辑距离;TEDn/OMR-NED 只在 ABC→XML
  转换成功的样本上算,配 fail_mask 单独报失败率(scripts/compute_TEDn_convert.py 专为此存在)
  —— **LEGATO 也有不可解析输出**,只是不用二值 parseable 把全部进步藏在悬崖后面。
- **推理**:域内 beam 3;OOD/单图脚本 beam 10 + repetition_penalty 1.1 + max_length 2048
  (scripts/inference.py:37)。与我们已建的 beam/rep 路线一致。
- **训练目标截断**:collate 里 truncation=True(max 2048)—— 多页长谱直接截断监督,
  不是过滤丢弃。

**对我们的三条直接启示**(判决仍归各自实验):
1. 纯 CE + 足量步数在符号谱 seq2seq 上**足以**长出自由生成能力(它 101M decoder 从零,
   无任何曝光偏差处理)—— 1c 是合理加速器而非必需品,步数与逐 token 精度才是主变量。
2. 我们的 parseable 硬门与它的优雅指标是**不同测量制度**:同一水平的模型,在它的制度下
   读作"CER 23.3%",在我们的制度下可能读作"parseable=0"。→ 已交付 val_text_ned_raw
   (D89):拒绝样本用逐窗原文剥戳拼接对参照算 NED,全样本进分母,给自由生成一根连续针。
3. 它最强的一张牌不可复制:836M 预训练视觉 encoder 冻结白嫖。我们 encoder 只有 ~130M
   且来自语音模态 —— encoder 侧质量差距是结构性的,不是技巧能补的。

## 7. 来源(§1-5 访问日 2026-07-14;§6 为 2026-08-04 仓库抓取)

- LEGATO:arxiv.org/abs/2506.19065(html v1 全文抓取;§4.2-4.3、§5、§6.1)
- M2ST:arxiv.org/abs/2410.00210(html v1;§2.4、§3.1)
- Canary 论文:arxiv.org/abs/2406.19674(html v1;Methods/训练段)
- Canary 官方训练配置:github.com/NVIDIA/NeMo — examples/asr/conf/speech_multitask/fast-conformer_aed.yaml
  (main 分支 raw;optim/sched/trainer.gradient_clip_val/model.label_smoothing 四段)
- canary-180m-flash 模型卡:huggingface.co/nvidia/canary-180m-flash(README;85K 小时训练数据构成)
