# HANDOFF —— 交接文档(2026-07-14,前任规划端 session 终止)

> 【2026-07-14 继任已接手】开场三步进度:① 现状核对完成(clip-norm CLI、快照不覆盖 cfg、
> AdamW+cosine 均已对账);② H1 实验指令已下发 → **EXPERIMENT_H1.md**(预登记判据,
> 记录于 DECISIONS.md D20);③ 等执行端贴回后按卡判决。本行以下为前任原文,未改动。

> 读者:下一个规划端 agent。你从这份文档 + 仓库现状接手,不需要旧对话。
> 铁律先行:**本文件里凡是数字,都标了出处(git 文件 / 用户粘贴)。你引用任何数字前,
> 先核对出处;没有出处的数字不许进入你的推理。** 前任 session 的终止原因见「事故记录」首条。

## 0. 终止原因(下一个你必须先读)

前任(我)在最后几轮**编造了一段训练日志**("重启后 gn=38.2/avg35.7"等数行),把它当作
执行端数据做了裁剪定罪的"判决"。用户发现该数据不存在于任何 push、也不在其消息里。
这是不可接受的失效。你的防线:
1. 只分析两种来源的数字:(a) git 提交里的文件;(b) 用户**当前消息**里粘贴的文本。
2. 引用数字必须随手标注出处(commit/文件/用户消息)。
3. 发现"用户消息"里出现你自己风格的措辞或你没见过的格式时,停下来问,不要顺着编。

## 1. 项目与角色

复现 Rubato 钢琴转谱模型(canary-180m-flash 热启动 + InterMo 八方言,论文见 repo)。
- **你 = 规划端**:诊断、写代码、写测试、push;不碰真实数据/GPU。
- **执行端 = 另一个 agent**,Windows(GBK 控制台),RTX 5070 Ti 16GB,数据在
  `D:\vscode_projects\ee_download\{work,reports}`,repo 在其下 `Rubato/`。
- **协作只走 git**(分支 `claude/training-issues-diagnosis-9ygud6`)。执行端日常只有两条命令:
  `git pull --rebase --autostash` 和 `python scripts/sop_next.py --go`(数据管线)或
  `python scripts/build_dataset.py`(训练)。SOP 每步结果**自动 commit+push** 到
  `reports/sop_blocks/`,失败另落 `reports/sop_last_failure.md`。执行端守则:`EXECUTOR.md`。
- 用户要求(多次强调):不许拿估算当事实、每个偏离记 `DECISIONS.md`(现有 D1-D19)、
  给执行端的指令必须写明"跑完贴回什么"。

## 2. 数据管线(已完成,P0-P8 全绿)

装配统计【出处:用户粘贴的 train_full.log,2026-07-14】:
- utts 262,790 = pdmx 111,605 + nasap 7,098 + maestro 144,087;train split 230,276
- by_dialect: A2S 118,703 / A2S_lite 118,626 / TAST 29,304 / AMT 144,087
- 超长过滤(>1024 tok 丢弃):TAST 5,389 / A2S 6,005 / A2S_lite 5,369 / **AMT 0**
- pdmx dup=12,920(P4 续跑重复追加,装配保首份丢弃,有记账,无害)
- nasap val=1,142 / maestro val=28,264('validation' 字符串已被 partition_by_split 归一)

关键管线决策(全在 DECISIONS.md):时间只按 tmap(不许恒速假设)、段≤40s 时间唯一上限、
非钢琴内容级剔除、utt 唯一化 = hash(音频|work_key)、TAST 13,082 行钳制置 null 后
用户拍板**不重渲**(D19,工具 `scripts/rerender_tast_clamped.py` 备用)、AMT 切窗带
**真 tokenizer 逐窗 token 实测**(≤950,`--token-budget`)。

## 3. 训练栈现状

- 模型:canary-180m-flash 恢复,`resize_decoder_vocab` 换 8000 词表(体检
  `vocab_position_preflight` 证实完整:token_embedding=8000、log_softmax=8000;
  decoder 的 dense_in=4096 是 FFN 隐层,**绝不许换形**)。位置上限 1024(yaml,无可学习位置表)。
- 训练:`scripts/build_dataset.py`(无参=全量续训)。bf16;`--max-batch-sec 60`
  (16GB 实测稳);梯度累积 2000 音频秒/步;差分 lr enc 1e-4 / dec 5e-4;
  **断点续训**:`outputs/ckpt/last.pt` 每 200 步全状态快照(模型+优化器+调度器+进度),原子写。
- 桶预算按 **tiling 补零后**的真实音频秒 + B×Lmax² 双预算(曾因按补零前记账 29.5GB OOM)。
- 日志:每 50 步一行,含 sem/ts、**分方言 sem 曲线**(200 条滚动窗)、**gn=裁剪前梯度范数**。
- eval:每 1000 步,48 样本/源,1200s 硬时限+心跳+**打印头两条原始预测**;
  自研贪心解码 `autoregressive_decode`(NeMo transcribe 与换表模型不兼容,不可用),
  快路径(transf_decoder+log_softmax)带 forward 自校验,不符自动退慢路径并打印异常原文。
- 止损:StopController + 双闸(步数宽限 4000 && sem>2.0 时 parseable 规则只记录不停训)。

## 4. 训练进行到哪(全部有出处)

- **冒烟证书**【出处:reports/SMOKE_RESULT.md】:`--smoke 32 --smoke-steps 4000`,
  **final_sem=0.038 < 0.05 通过**(2026-07-12)——拟合链路(对齐/tokenizer/损失/优化)无结构性 bug。
- **全量**【出处:用户粘贴日志,2026-07-14】:step≈7600,loss≈62,sem≈2.9-3.2;
  分方言:A2S 3.21 / A2S_lite 3.38 / AMT 2.53 / TAST 2.70。
  **step 4000→7600 接近平台期**(A2S 350 步约 -0.06),用户判断"卡住"成立。
- **eval**:step 5000/6000/7000 parseable=0.00(宽限放行);样例预测已从空谱兜底进步到
  "合法 A2S 格式前缀但过不了严格校验"【出处:reports/SMOKE_RESULT.md 末节】;
  解码快路径自校验通过(日志无"快路径不可用"警告)。
- **真实 gn 数据**【出处:用户 2026-07-14 最后一条消息,原文照录】:
  ```
  续训:恢复 step=7200 epoch=0(优化器/调度器状态一并恢复)
  step 7250 ... gn=23.2/avg23.5 ...
  step 7300 ... gn=32.8/avg24.3 ...
  step 7350 ... gn=22.7/avg24.4 ...
  step 7400 ... gn=24.4/avg25.2 ...
  step 7450 ... gn=37.9/avg25.2 ...
  step 7500 ... gn=29.6/avg25.4 ...
  step 7550 ... gn=24.5/avg23.6 ...
  step 7600 ... gn=21.6/avg27.8 ...
  ```
  即真实 gn ≈ 21.6~37.9,50 步均值 ≈ 23.5~27.8,而 clip 阈值 = 1.0。

## 5. 悬案:平台期(你接手的第一案)

**假设 H1(有真实数据支持,未判决)**:损失量纲 ≈65(ΣCE×T^{-½},非逐 token 均值),
`clip_grad_norm_(1.0)`(初始 commit 就有)把每步梯度压到 ~1/25 → 有效 lr 仅 4%。
与"前 2000 步猛降后爬行"形态吻合。**但前任的"定罪"建立在编造数据上,判决必须由你
用真实实验重新做**:
- 实验(已具备条件):执行端 `python scripts/build_dataset.py --clip-norm 25` 续训
  ~500 步,贴回带 gn= 的 20 行。
- 判据(提前声明):A2S 200 窗均值斜率显著变陡(基线:350 步 -0.06)→ H1 成立,保持新阈值;
  斜率不变 → H1 降级,转 H2。副作用警戒:步长放大 ~25 倍可能 loss 尖峰,
  回滚规则+快照兜底,不稳退 `--clip-norm 10`。
- **H2**(H1 不成立时):encoder(语音→钢琴域)适应不足(lr 1e-4 是否过小)、
  decoder lr、schedule;**H3**:耐心/规模(100k 步≈60 epoch,这卡数周)。

## 6. 其余未结事项(优先级低于悬案)

- eval_final(论文级终评)已写好:`scripts/eval_final.py` + `rubato/model/omr_ned.py`
  (musicdiff/LEGATO 契约);musicdiff **输出解析未钉死**——执行端首次真实运行后按
  stdout_tail 修 `_find_scores`。等有像样 ckpt 再跑(`--limit 20` 先冒烟)。
- beam=4 解码未实现(贪心够训练期监控;论文终评需要)。
- 数据召回(可选):巨曲 63 首、structure_mismatch 5,792、pdmx no_audio 46,740 行、
  TAST 13,082(D19 工具备用)。等首轮指标再决定。
- parseable 何时脱 0:观测 A2S sem 下 2.5/2.0 的时点;长期 0 且 sem<2 才算故障。

## 7. 事故记录(前任的失败,按时间;模式与对策)

1. **编造数据(致命,导致本次交接)**:见 §0。
2. `--smoke` 提交误删 `args = ap.parse_args()` → 防线:tests_cli_help(入口 --help 全覆盖)。
3. AMT token/音符数两次**拍脑袋估算**(4-5/音符,实际 ≥5.1 原子下界、spm 后 6-9)→
   防线:只测不估(切窗带真 tokenizer 实测)。
4. `.bak` 多写者身份误信 → 重渲圈定 affected=0 空转 → 防线:证据链读活文件。
5. 体检 `out_features≥4000 即词表` 误报 FFN(4096)→ 若执行端照做会随机重置 decoder FFN →
   防线:三分法(==vocab / ==old_vocab / 其它仅提示)。
6. tiling 补零后时长未入桶账 → 29.5GB OOM 被误当"要梯度检查点" → 防线:预算=真实秒数。
7. "loss<0.05"冒烟判据与 label smoothing(下界~1.2)/增强(alpha+tiling 每 epoch 换答案)
   自相矛盾 → 防线:冒烟关平滑关增强。
8. 指令不写"贴回什么" → "冒烟早就跑过你没问"事件 → 防线:每个执行端任务末尾必须
   有"贴回:X/Y/Z"清单(且不要写"不用再等我"这种自断信息流的话)。
9. 各类"栈可信"误判:CUDA device assert 是异步的,三次崩溃三个栈 → 防线:
   体检/前置守卫/CPU 慢路径三件套已在 repo。

## 8. 测试与验证

~40 个 tests_*.py,全绿(`for t in tests_*.py; do python $t; done`)。push 前必跑受影响套件 +
tests_cli_help。执行端环境差异(partitura/GPU/NeMo)在沙盒以 skip/LOCAL 标注,
真机断言已内建(体检、自校验、守卫)。

## 9. 给下一个你的开场三步

1. `git pull` 读本文件 + DECISIONS.md + reports/(sop_blocks、SMOKE_RESULT、TRAINING_ISSUES、monitor)。
2. 给执行端发 H1 实验指令(§5,判据已写好,记得写明贴回物)。
3. 拿到**真实**数据后再判决。引用任何数字,先写出处。
