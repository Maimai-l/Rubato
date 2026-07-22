# CALIB_MANUAL_REVIEW — 灰区人工复核

日期：2026-07-22

背景：`CALIB_FULL.txt` 对 nASAP 保守 test 切分的 34 个 Tkun→M2ST 配对得出
OMR-NED 均值 63.40。该集合与论文 ASAP 曲单不同，论文的 69.1 只作量级锚点，
不作逐点通过线。

抽样：按原始 OMR-NED 从低到高的 0%、25%、50%、75%、100% 分位，审核包位于
`work/calib_manual_review_5/`；每个目录包含 `estimate_m2st.xml` 和
`reference_asap.xml`。

人工复核结论（用户，2026-07-22）：五个样本“挺不错的”，预测谱与参考谱在整体上能对上。

判定：未见系统性错配、空谱或评分链错误的证据。此次校准确认 LEGATO 评分链及
Tkun→M2ST 产物可用于后续对照；不将不同曲单的 63.40 对 69.1 的 5.70 差额作为训练闸门。
`CALIB_FULL.txt` 保持代码生成内容，未作人工改写。
