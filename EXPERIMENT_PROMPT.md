# EXPERIMENT_PROMPT —— 训推前缀不一致【判决:无实质伤害,结案】(D46)

## 判决(2026-07-21,abtest @63000,autolog @3031bcb)

- G0(无域)parseable 5/48,NED中位 0.801;G1(real)5/48,0.877;G2(synth)4/48,0.941。
- **G1−G0 = 0.00 < +0.05 → 预登记判据命中:"不一致存在但无实质伤害" —— 结案,缺省不改。**
  代码事实成立但代价为零:模型对域 token 不敏感(它不计 loss,模型显然学会了无视它)。
- 副产品(价值大于主案):拒因直方图 v2 首读 —— 48 样本中 **DYCK=34、MEASURE=24、
  parse_error=22、TERMINAL=21**(一样本多类)。**声部配对(Dyck)是 parseable 的头号
  拦路虎,小节时值第二**。这是 30k 步以来第一次知道"卡在哪",后续解码约束/训练观察
  以此为靶。
- 记账修正:通过=3 vs parseable=5 系 beam 首试残留污染,已修(通过样本无条件记「通过」)。

---

# 以下为原案卡(判决过程留档)

# EXPERIMENT_PROMPT —— 训推前缀不一致(域提示)判定实验(D44)

## 发现(执行端 A2S_TRAINING_REVIEW 提出,规划端逐条代码核实,2026-07-21)

- 训练:每条样本的 decoder 前缀 = 方言 prompt + **<|real|>/<|synth|>**(dataset.py:74-77,
  四源全部声明 domain)。
- 自由推理:只用方言 prompt(infer.py 原 build_tast_prompt/infer_a2s/infer_amt 均无 domain)。
- 教师强制探针:特意"与训练同构"**带** domain(infer.py teacher_forced_probe)——
  所以探针指标好、自由解码差的落差,恰好探不到这个洞。

即模型从未在"无域提示"前缀下训练过,却一直被要求这样自由生成。这是代码事实;
**"它造成多少伤害"必须实验测量,不许推断定罪**(执行端此点措辞正确,采纳)。

## 已实施的管线改动(本卡实验的前置,不改变现状行为)

- `infer.build_prompt(dialect, domain)` 单点收口,与训练布局逐 piece 相同(tests 钉死);
  infer_a2s/infer_amt/single_window_tast 全线增加 `domain` 参数,**缺省 None = 现状(G0)**。
  判决前任何调用方(含 eval)不得擅改缺省。
- 附带修复拒因直方图 v1 缺陷(规划端之误):校验拒绝发生在 infer 层内部,eval 只见兜底
  常量,直方图退化成 empty 率(58000-61000 实测"兜底=4x"无一拒类)。v2:infer 层
  `LAST_VIOLS` 全窗累积真实违规,eval/abtest 按它计类。

## 实验设计(同 ckpt、同确定性 48 条 nasap 子集、同解码,仅 prompt 不同)

```bat
python scripts/build_dataset.py --prompt-abtest
```

| 臂 | prompt | 意义 |
|---|---|---|
| G0 | 方言 prompt(现状) | 基线 |
| G1 | + <|real|>(与训练一致) | 主假设 |
| G2 | + <|synth|>(反向) | 排除"多个 token 都变好"的前缀效应 |

产出:每臂 parseable、兜底数、NED 中位(通过样本)、拒因直方图、前 10 条输出;自动进 autolog。

## 预登记判据(数据到来之前写死)

- **G1.parseable − G0.parseable ≥ +0.10(绝对)且 G2 − G0 < +0.10** → 域缺失是实质伤害:
  修复采纳 —— 真实音频推理默认 domain="real",渲染音频 "synth";eval 的 infer_a2s 改传
  样本 domain(随下次重启生效,autolog 标注口径变化点,此后 parseable 与历史不可直比)。
- **G1 − G0 < +0.05** → 不一致存在但无实质伤害:结案,缺省不改,记录在案。
- 0.05~0.10 → 灰区:辅判 = 共同通过样本上 G1 的 NED 中位比 G0 低 ≥0.05;仍不明 →
  `--abtest-n 96` 重跑一次;再不明按"无实质伤害"保守关案。
- **G2 ≈ G1 且都显著 > G0** → 前缀长度/格式效应,另立案,不采纳 real 缺省。
- 副观察(不判决):拒因分布是否移动(如 DYCK 减少)、兜底数、输出可读差异。

## 时机与成本

训练暂停窗内跑(≈30-50 分钟 GPU);跑完 push 即可**立即重启训练,不必等规划端判决**
(重启配置由 O4/溢出两案决定,与本实验无关;见 EXECUTOR.md D44 节)。
