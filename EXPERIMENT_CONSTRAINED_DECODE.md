# EXPERIMENT_CONSTRAINED_DECODE —— 约束解码(D100/D101 解码线)

## 动机(为什么这一杆确定性最高)

r3-v2 @50k 实测:自由生成内容大体正确(raw_ned 0.677,文本层错误近零),
败在结构收口 —— DYCK 40/48、TERMINAL 30/48、复读到 900 上限。模型"基本会写,
就差收口"时,可以在**解码时**用验证器把会导致非法的候选剪掉,输出按构造合法。
不治模型,但项目终评的硬门是 parseable(不可解析 = OMR-NED 无从计算)。
零训练风险,纯推理侧,与训练线(1c 疗效段)完全正交。

## 已交付(第一块,2026-08-11)

`rubato/intermo/core.py::validate_units_prefix` —— 前缀致命违规判定:
- 即死项:DYCK_DOUBLE_ONSET / DYCK_ORPHAN_OFFSET(事件级,后文救不了)、
  已完成小节的 MEASURE_SUM、TS_NONMONOTONE;
- 前缀豁免:DYCK_UNCLOSED(可后闭)、TERMINAL_BAR_MISSING(结尾未到);
- 性质保证(tests_prefix_validate 4 绿):validate_units 全过的序列,任意单元
  前缀必过;致命类与全量验证器逐项一致。

## 设计(第二块,beam 整合;下轮建)

- **检查粒度 = 原子边界**:SPM piece 是原子(空格分隔单元)的子词;新 piece 以
  空白标记(▁)开头 ⇔ 上一原子完成。原子完成时把该 beam 的累计文本
  text_to_units + validate_units_prefix;报即死 → 该 beam 出局。
- **只做 beam 臂**(beam≥2):greedy 无备选可换,不做(退化为现状)。
- 全部 beam 均被剪时:保留剪除前得分最高的 beam 继续(降级为无约束),
  LAST_GEN_STATS 记 constrained_exhausted 次数 —— 不静默。
- 性能:每原子一次前缀验证,O(n²) 上界(n≤900 原子),eval 场景可接受;
  增量化(状态机)留作后续优化,先正确后快。
- 开关:infer_a2s(..., constrained: bool = False) + build_dataset
  --decode-abtest-constrained,缺省关 —— 不改变现有 eval 口径。

## 判决协议(先于数据)

同 ckpt 双臂(--decode-abtest 扩展):beam=4 无约束 vs beam=4 约束,
同确定性 n=48 子集。判据:约束臂 parseable 绝对提升 ≥15 个样本,且
text_ned_proxy(可解析样本上)不劣化超过 +0.05 —— 防"剪成合法但内容更差"。
过 → 进正式 eval 与终评推理配方;不过 → 记档,等模型侧(1c/后续)把内容
再抬一档后复测。
