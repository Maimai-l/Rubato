# 训练监控状态板(规划端维护;历史见 git log 本文件)

**更新:2026-07-14(继任规划端接手)**

## 当前状态 —— 训练中,悬案 = 平台期

| 指标 | 值 | 出处 |
|------|-----|------|
| step | ≈7600 | 用户粘贴日志 2026-07-14(原文存 HANDOFF.md §4) |
| loss(avg50) | ≈62 | 同上 |
| sem | ≈2.9-3.2 | 同上 |
| 分方言 sem | A2S 3.21 / A2S_lite 3.38 / AMT 2.53 / TAST 2.70 | 同上 |
| gn(裁剪前) | 21.6~37.9,avg50 23.5~27.8(clip=1.0) | 同上,原文照录 HANDOFF §4 |
| parseable | 0.00 @ step 5000/6000/7000(宽限放行) | reports/SMOKE_RESULT.md |
| 样例预测 | 已从空谱兜底进步到合法 A2S 格式前缀 | reports/SMOKE_RESULT.md 末节 |

## 当前动作

**EXPERIMENT_H1.md** 对照实验已下发(`--clip-norm 25` × ≥500 步,预登记判据见卡/D20),
等执行端贴回。贴回后由规划端按卡判决 H1,并用同批数据的 enc=/dec= 列分流 H2/H3。

外部配方参照已入库:**REF_EXTERNAL_RECIPES.md**(LEGATO / M2ST / Canary 一手配方,
2026-07-14 原文核对)。要点:我们架构的官方配方 `gradient_clip_val: 0.0`(不裁剪)、
`label_smoothing: 0.0`;三家峰值 lr 一致 3e-4;外部步数视野 40k-225k(H3 佐证)。
仅作实验设计先验,判决仍归贴回数据。

## 旧状态更正(2026-07-13 版说"训练最终状态—已暂停"已过时)

- step 4000 的 `parseable_rate=0.00` 暂停:已被双闸策略取代(步数宽限 + sem>2.0 门,
  commit b683a/HANDOFF §3),训练已续至 7600+。
- "等规划端修 infer.py 的 NeMo transcribe 适配":已解决 —— NeMo transcribe 与换表模型
  不兼容,走自研贪心解码 autoregressive_decode(commit af84a7f),快路径带 forward 自校验。
- AMT 超长丢弃 32,930 → 0(重切窗 144k,commit 3a0e82f / d2ba970)。
