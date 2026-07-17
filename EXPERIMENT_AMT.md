# EXPERIMENT_AMT —— maestro/AMT 音高不读音频,专项排查(训练不用停)

## 触发(2026-07-17,step 30000 复盘,预登记条件命中)

多源探针 8 次 eval(23000-30000):maestro/AMT 的 Δsem 全程 ≈0(+0.00~+0.05 波动),
同期 nasap Δsem 稳在 +0.09~0.16 且 Δts 升到 +0.20。时间对齐审计上 maestro 是好的
(lag -10ms)——所以嫌疑变成**音高内容**:起音审计是音高盲的,"时间齐、音高错"
(移调 / 同节奏错配 / MIDI→事件的音高换算 bug)它抓不到,而这恰是 AMT 最需要排除的。

## 执行(训练照跑,另开终端,分钟级)

```bat
git pull --rebase --autostash
python scripts/audit_alignment.py --per-source 16 --pitch
git add reports/alignment_audit.md && git commit -m "pitch audit" && git push
```

`--pitch` 对 AMT 样本追加 chroma(音级能量)比对:音频的 12 音级分布 vs 标签音符的
音级分布,逐帧余弦;基线 = 标签循环平移半窗(同曲错位)。判读(预登记,合成测试已验证
移调 +3 半音必被抓):
- **PITCH_OK**(Δ≥0.10)占多数 → 音高内容无罪 → AMT 不读音频是**模型侧现象**
  (静音基线已 0.72,文本可预测性挤压音频的边际价值)→ 处置:不动数据,
  继续训练观察(AMT 的音高读取应随训练后期出现);30000+8000 复盘若仍 0,
  再议结构性修正(如 AMT 样本的 label smoothing/混比微调,届时另开卡)。
- **PITCH_MISMATCH 占 ≥1/3** → 数据侧坐实(音高换算/窗账/配对)→ 定位 gen_amt_labels
  / maestro.py 的音高路径,修复后重产 maestro 窗,那时再议受污染步数的处置。

## 同时生效的解码改进(已随本次推送)

step 30000 的前缀acc=0.69 已过预登记 0.60 线:**贪心循环捕获是 parseable 的当前主瓶颈**
(解码现场:开头正确,c5E5↔e5C5 锁死)。自由解码已加 LEGATO 同款**重复惩罚 1.1**
(仅监控解码,近 128 token 窗,近平局才翻转,强预测不受影响;单元测试覆盖)。
预期:parseable/OMR-NED 提前变得可读。它不改训练,指标跳变属仪器变化,读趋势时注意分界。
