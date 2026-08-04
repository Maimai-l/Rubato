# EXPERIMENT_PREPRETRAIN —— decoder 形式语言预训练(D91)

## 出处(为什么早该做)

论文 §2 表示章节原文:音高状态是 k-Shuffle-Dyck 语言,"the formal language for which
**pre-pretraining** yields the largest token-efficiency gains"(引 Hu et al. 2025, ACL:
在人造形式语言上先预训练,再训下游,白得层级结构偏置)。这条暗示用户读论文时就查过
引文,规划端两轮通读都没识别为配方候选(检索失误,D91 认领)。三向汇聚:
real 头号拒因 = DYCK(开闭配对),synth 头号 = MEASURE(小节算术)——
恰是该表示的两条形式性质;论文自己训练 **from scratch**(§3),预训练语法 decoder
与从零权重是一个自洽包。

## 工具链(已建成,全测试绿;零音频零渲染,不碰主线训练)

1. `scripts/gen_formal_corpus.py` —— 随机采样 ScoreIR → 生产序列化器出文本
   (A2S/TAST 各半,变拍号/调号/和弦/跨时刻长音=真嵌套),**逐条过生产验证器,
   违规即崩**。20 万条 ≈ 8 分钟 CPU。tests_formal_corpus 4 绿
   (确定性/全合法/嵌套占比>30%/多样性)。
2. `scripts/pretrain_decoder.py` —— 只训 transf_decoder+log_softmax(其余全冻结),
   交叉注意力喂零上下文 = decoder-only 纯 LM;目标序列经**生产同一个** encode_target
   (prompt+标签+eot 格式零漂移)。产出 decoder_init.pt。tests_pretrain_decoder 3 绿
   (同构批/只有 decoder 学且 loss 降/存载往返+strict 崩)。
3. `build_model(decoder_init=)` + `build_dataset --decoder-init` —— 词表换形后
   strict 载入,回显 "decoder 预训练初始化已载入" 行自证。

## 预注册判据(先于数据)

**预训练自身健康门**(20k 步,语料 20 万条):
- loss 起点应 ≈ ln(8000) ≈ 9.0 附近,曲线整体单调下行;
- 末 avg50 ≤ 1.5 = PASS(形式语法高度可学,Hu et al. 近零);1.5–3.0 = 灰区贴回判读;
  > 3.0 = 预训练无效,查 bug 不入 round-3。

**round-3 入场判读**(若 100k 判读触发 round-3,D88⑦/D90④):
- round-3 基线 = encoder 热启(D90 判定安全)+ decoder **from scratch 语义由
  decoder_init 取代**(载入语法预训练权重,覆盖 canary 文本先验);
- 对照 = round-2 已入库的同步数曲线(历史对照,不再烧一整条 A/B 跑):
  10k/20k 处比三样 —— 解码腿拒因谱里 **DYCK 占比**(应结构性低)、
  **raw_ned**(应更低)、探针 sem(不应更差超过 +5%)。
- 三样两胜 = 预训练留在配方;否则回退 canary decoder 热启,记档关案。

## 风险与已知让步

- decoder_init 覆盖 canary decoder 层 = 放弃其文本先验 —— 这是本设计的目的
  (三家参照 decoder 全从零;我们的病全在 decoder 侧),不是副作用。
- 语料无真实音乐统计(音高/节奏分布是均匀随机)—— 预训练教语法不教音乐,
  音乐由正训教;Hu et al. 实证此类迁移为正。
- TAST 时间戳恒速伪造 —— 只练"时间戳存在+单调"的形式,真实节奏形变归正训。
