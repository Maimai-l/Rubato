# REF_SYSTEM_CALIB —— 用开源第二名校准我们的评测体系(D54,数据建设期插队任务)

## 背景(用户提议 2026-07-22,核实后立项)

Rubato 闭源;评测第二名 Tkun→M2ST **代码+权重公开**(Transkun pip;
github.com/TimFelixBeyer/MIDI2ScoreTransformer,Releases 有 MIDI2ScoreTF.ckpt),
其公开分数:ATEPP OMR-NED 85.2、ASAP 69.1(论文标灰:训练集含 98/102 测试曲)。
它的训练数据闭源 → 训练法不可抄;它的价值 = **给我们的 OMR-NED 管线一个外部已知答案**。
我们至今所有评测数字从未对过外部锚点 —— 二轮开跑前必须补上这一课。

## 判据(预登记,先于数据)

- **校准通过**:我们管线(LEGATO 官方脚本通道)复算的 Tkun→M2ST OMR-NED,在我们的
  ASAP test 曲集上落在 **60-80 区间且与公开值 69.1 差 ≤5**(集合口径不同放宽到 ±5;
  我们的 test 切分比论文保守,曲单非同一)。
- **校准失败**:差 >10 或管线跑不通 → 我们的评测链有 bug,**修好之前二轮不得开训**
  (测不准就没有判决,教训来自本项目全史)。
- 5-10 之间:灰区,抽 5 曲人工比对 XML 后定。
- 副产品(不判决):Tkun 在我们 maestro 评测段的 note F1(对照其公开 98.3);
  M2ST 输出 XML 存档 5 份(与我们 round1_baseline 输出并排,实物对照)。

## 执行(冒烟已通过 CALIB_SMOKE_7;全量命令见 EXECUTOR 追加 12)

冒烟 3 曲全链路 2026-07-23 通过(Tkun 转写 ✓ → M2ST 转谱 ✓×3)。全量 = 四步脚本流水线:
calib_pairs(枚举 nasap test 配对)→ calib_transkun(断点续转)→ calib_m2st_infer
--all-mids(续跑)→ calib_score(先 ref-vs-ref 自检 ≈0 再逐对打分,报告代码写
reports/CALIB_FULL.txt,判决按本卡判据自动打印)。补充预登记:官方脚本若输出 0-1
口径,×100 换算后对带(写在数据到来之前)。

## 不指望它给的(期望管理)

- Rubato 的训练内幕(多方言/时间戳/混比)—— 没有任何第二名有,仍靠我们自己的实验;
- M2ST 的训练数据(闭源 MuseScore 语料,论文明说其规模对比对它有利);
- Piano-A2S 另案:其合成数据管线代码与我们 C 线同哲学,对表后择优吸收(不阻塞)。
