# EXPERIMENT_C_ROOTCAUSE —— 病 C 已定案,追根因(训练保持暂停)

## 判决(2026-07-16,D27)【出处:eval_autolog @f84ad23,probe-only 干净测量】

**病 C-忽略成立:encoder 工作正常,decoder 完全忽略音频,模型 = 纯 InterMo 文本语言模型。**
证据链(全部自证):rms 三值不同(0.0166/0.0000/0.1075)证输入不同;enc_std 随输入变
(0.10 vs 0.12)证声学前端活着;静音 Δsem=0.00、**换别的曲子的真实音频命中率一字不差**
(0.39/0.49/0.08)、换参照谱命中率立变(0.55/0.66)—— 对文本敏感、对音频彻底不敏感。
回溯解释:loss 停在 ~2.9=文本熵水平、复读机生成、音高全错、amt_f1=0、
冒烟通过(文本记忆即可,从未证明音频通路)。

## 为什么会训成这样(嫌疑排序)

热启动时 cross-attention 是会用的(canary 靠它转写语音)。22k 步把它训到弃用,
最合理的机制:**训练数据里"读音频"不划算** —— 头号嫌疑是音频↔标签系统性对不上
(窗口偏移记错/配错文件/渲染错位):若对不上,忽略音频就是降 loss 最快的路,
模型学得对,数据是错的。次号嫌疑:SpecAugment 掩蔽过狠、或 forward 里 encoder
输出/mask 的喂法有诈(训练与探针走同一 forward,探针 enc 体征正常,此嫌疑靠后)。

## 第一步:对齐审计(执行端现在跑,分钟级,不需要 GPU/模型)

```bat
git pull --rebase --autostash
python scripts/audit_alignment.py
git add reports/alignment_audit.md && git commit -m "alignment audit" && git push
```

工具做的事:每源抽 8 条训练对,用与训练**完全相同**的加载路径读音频窗,
比对"标签写的音符起音时刻"和"音频里的能量起音",互相关扫 ±2s 滞后。
判读(预登记,写在工具 docstring):
- 每对:peak≥0.25 且 |lag|≤50ms → OK;峰值明显但偏移 → SHIFTED(记账错,修账);
  无峰 → UNCORRELATED(配错/坏渲染);|lag|>500ms 的 SHIFTED 按配错同等对待。
- 每源:≥1/3 非 OK → 该源判"对齐故障"。
- **三源全 OK** → 数据洗清,转查训练侧(SpecAugment 配置、cross-attention 权重统计,
  规划端出下一张卡)。

## 结果对应的处置(提前声明)

| 审计结果 | 处置 |
|---|---|
| 某源大面积 SHIFTED(恒定偏移) | 修该源窗口记账 → 小规模验证(冒烟改造:带对齐检查)→ 从当前 ckpt 续训优先 |
| 某源大面积 UNCORRELATED | 配对/渲染管线故障,定位后重产该源数据;续训 vs 重启由"坏数据占比"定(占比高→重启更划算) |
| 全 OK | 数据无罪 → 查训练侧:①执行端贴 model.cfg 的 spec_augment 段;②规划端出 cross-attention 权重统计探针 |

**训练在根因修复并小实验验证之前保持暂停** —— 病 C 下多训的每一步都是白烧。

---

## 审计结果(2026-07-16,@e7cc374)与下一步

**pdmx 8/8 OK,maestro 6/8 OK,nasap 5/8 UNCORRELATED + 1 SHIFTED → nASAP 对齐故障。**

但注意一个关键疑点:nASAP 只占训练对 ~3%,若 pdmx/maestro(90%+)对齐,
单靠它教不出"全局忽略音频"。而此前**所有探针与评测样本恰好全来自 nASAP**
—— 判决可能要收窄为:"nASAP 分支被污染 + 全部评测建在污染源上",
模型在对齐的源上也许一直在读音频(那 22k 步大部分没白训,是好消息)。

### 立即验证:三源探针(git pull 后,一分钟)

```bat
git pull --rebase --autostash
python scripts/build_dataset.py --probe-only
git add reports/eval_autolog.md && git commit -m "3-source probe" && git push
```

对 nasap / maestro / pdmx 各取 2 个训练对,测 真音频 vs 静音 的 Δsem。判读(预登记):

| 结果 | 结论 | 处置 |
|---|---|---|
| pdmx、maestro 的 Δsem ≥0.06 且 nasap ≈0 | 模型在读对齐的音频;病灶=nASAP 数据 + 评测选源 | 修 nASAP 窗口账;eval 参照改用干净源;**从当前 ckpt 续训**,不重启 |
| 三源全 ≈0 | 全局忽略,nASAP 只是帮凶 | 查训练侧:SpecAugment 配置、cross-attention 权重统计(规划端出卡) |
| 介于/混杂 | 逐源细查 | 规划端按数据定 |

### nASAP 病灶假设(修复时先查这里)

症状形态(部分曲 OK、多数不相关、个别大偏移)最像**窗口时间轴混用**:
win=[t0,t1] 的切窗秒轴与 tmap 时间戳秒轴不一致(谱面时间 vs 演奏时间),
恒速曲侥幸对上、rubato 重的曲全乱 —— 查 s7 切窗与 D16 修复的交界处。

另:审计工具顺带发现 maestro 也有 2/8 可疑(-1080ms 偏移 / 不相关),
修完 nASAP 后建议 `--per-source 32` 复扫三源。

---

## 三源探针结果(2026-07-16,@b84b4b5)→ 判决收窄 + 联合仪器

结果:nasap Shi05M 两窗 **Δsem=+0.16/+0.12(在读音频!)**;pdmx +0.03/+0.10;
maestro AMT 0.00/-0.02。而 D27 判"全局忽略"用的 Bult-ItoS02M 恰是审计判 SHIFTED 的错位样本。

**D27 修正(D28)**:"decoder 全局忽略音频"收窄为"**选择性读音频**"——数据对齐处读、
错位处学会闸掉退回文本模式。单点探针以偏概全是规划端的方法失误,记录在案。
好消息:模型读谱能力存活,22k 步大概率大部分有效。

遗留疑点:maestro/AMT 两窗 Δsem=0(audit 显示 maestro 多数对齐)——是这两窗恰好错位,
还是 AMT 分支整体不读音频(其静音 sem 已高达 0.72,文本可预测性强)?需要人群级数据。

### 联合仪器(git pull 后,一条命令,约 5-10 分钟)

```bat
git pull --rebase --autostash
python scripts/build_dataset.py --probe-only --probe-n 8
git add reports/eval_autolog.md && git commit -m "joint probe" && git push
```

对三源各 8 条:每条先测对齐等级(peak/lag),再测 Δsem,输出联合行 + 分桶汇总
(对齐OK vs 错位 的平均 Δsem,再按源拆)。

### 判读(预登记)

| 联合汇总形态 | 结论 | 处置 |
|---|---|---|
| OK 桶 Δsem ≥ +0.06 且 错位桶 ≈0(各源一致) | **统一理论成立**:模型读一切对齐的音频;病灶=数据错位分布+评测建在错位源上 | 修 nASAP 窗口账(+复核 maestro 坏窗)→ 重产该部分标签 → eval 参照换干净子集 → **从当前 ckpt 续训** |
| 唯 maestro/AMT 的 OK 桶也 ≈0 | AMT 分支特有(文本可预测性高挤掉音频/或 AMT 窗账另有错) | 规划端单独查 AMT(窗账复核 + AMT 静音基线分析) |
| 各桶都 ≈0(与三源探针矛盾) | 测量不稳,停判 | 贴回全部行,规划端重新设计 |
