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
