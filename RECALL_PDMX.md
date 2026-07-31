# RECALL_PDMX —— 补渲 46,740 行 no_audio 的 pdmx 标签(与训练并行,不停训)

## 背景(D33)

装配统计里 pdmx 有 46,740 行标签配不上音频(S4/S5 渲染期缺失/失败/清理),
= 潜在 **+20% 训练数据**(全是 A2S/A2S_lite,主线口粮),一直挂在召回清单。
现在训练健康(38k 步全绿),把它们渲出来;**训练不用停**——渲染吃 CPU,训练吃 GPU。

## 执行(随时可起,断点续跑)

```bat
git pull --rebase --autostash
:: 低并发起步,渲染调度器按内存预算自动定 worker;训练在跑,给系统多留内存:
set S4_RESERVE_GB=10
python scripts/s4_parallel.py
```

- 已渲过的自动跳过,只补缺的;中断了重跑同一条命令即续。
- 观察内存:`python scripts/procmon.py mem`;紧张就 `set S4_WORKERS=4` 再压。
- **若训练日志出现 OOM 或 step 时间明显变长,先停渲染**(procmon kill sfizz),训练优先。

## 铁律

1. **只认过滤后的 manifest**:内容审计拉黑的非钢琴曲、泄漏黑名单曲,不得借补渲复活
   (s4_parallel 本就按 manifest 走,此条为验收口径)。
2. 渲染完成后跑 `python scripts/build_dataset.py --dry-run`,把装配统计整块 push
   (新文件 reports/RECALL_RESULT.txt):验收 = pdmx no_audio 显著下降、kept 相应上涨、
   非钢琴黑名单曲 0 复活。
3. 渲不出来的(真失败)不硬救:s4 的失败记录留着,贴回失败计数即可,规划端分诊。

## 生效时机

新音频在**下一次训练重启**时自动进池(装配器按 resolve_audio 现场发现),
checkpoint 照常续,不从头训。计划:渲染在 50000 步复盘前完成的话,
就借复盘那次重启一并生效;没完成就下一次。

---

## 第二步:切段,不是渲染(2026-07-18,@42bf7f6 执行端分析正确)

执行端查实:整曲 opus 全在(s4_parallel 全跳),缺的是**段级 flac** ——
"整曲渲染 → 按段切割"这一环当年没对全量跑完(s4_slice_segments.py 文档自述此缺口)。
修法降级为切片(轻 CPU 活,比渲染快得多):

```bat
git pull --rebase --autostash
:: 先看磁盘(约需 ~20GB:46,740 段 × ~400KB flac):
python scripts/procmon.py mem
:: 冒烟 20 曲,看 sliced/skip 计数:
python scripts/s4_slice_segments.py --limit 20
:: 计数合理(sliced>0,skip 有理由)→ 全量,已切的自动跳过、断了重跑即续:
python scripts/s4_slice_segments.py
```

预期与验收:
- **不会全部回来**:结构不匹配(已知 ~5,792)和时长越界(<2s / >41s)的段会被
  脚本明确计数跳过,继续留在 no_audio —— 这是设计,不是失败。
- 切完跑 `python scripts/build_dataset.py --dry-run`,连同切割脚本的计数行一起
  push 新文件 reports/RECALL_RESULT_2.txt:验收 = pdmx no_audio 从 46,740 大幅下降,
  残余数 ≈ 脚本 skip 计数之和(账要对上)。
- 内存/训练优先规则同第一步;切片吃 CPU/磁盘 IO,内存压力远小于渲染。

---

## 结案:召回净收成 = 0,46,740 全部是"按设计出局"(2026-07-18,@963ff2d,D34)

切割全量跑完:**sliced=0**,已存段 flac 89,237 个(≈ 现役 76.7k 训练对 + 12.9k 去重行,
账闭合)。46,740 的分解(计数器口径已从代码核实:no_whole_audio/structure_mismatch/no_midi
按曲,seg_* 按段):

| 类别 | 量 | 定性 |
|---|---|---|
| 缺整曲的 3,683 曲的标签行 | 大头 | 见下"诡异"解释,多为清场遗留,勿复活 |
| structure_mismatch 5,792 曲的行 | 中 | 反复展开坐标错位,守卫拒切(防毒),映射修复另议 |
| 段太长(>41s 慢演绎)4,452 段 | 小 | D14 设计出局(超训练窗) |
| 段太短(<2s)1,404 段 | 小 | D5 设计出局(退化样本) |
| no_midi 47 曲 | 微 | 无渲染 MIDI |

**D33 的"+20% 训练数据"预估作废**(规划端之误:拿召回清单毛数当净数,没先分解)。
真正剩余的可回收池只有 structure_mismatch 曲(需谱面侧反复展开映射,中等工程,挂账)。

### "3,683 缺整曲"之谜(执行端问得对)

s4_parallel 按 **manifest(过滤后)** 名单干活,切割器按 **标签文件** 名单干活 ——
3,683 = 在标签里、不在(或已被清出)manifest 的曲:非钢琴清场/黑名单/清理的**遗留标签行**。
两个工具都没错,名单不同而已。按铁律它们**必须留在池外**。
证据不靠推理:跑对账脚本,逐曲定性(A 清场遗留/B·D 无害/C 矛盾类应为 0):

```bat
git pull --rebase --autostash
python scripts/recall_explain.py
git add reports/recall_explain.md && git commit -m "recall explain" && git push
```

若报告出现 C 类(在 manifest 且段缺)→ 那才是真问题,贴回待查;A/B/D 全覆盖 = 结案。

---

## 第三步:真渲染(D35 —— D34"净收成 0"部分作废,对账脚本抓到真 bug)

recall_explain @ea8b6f6 的定性推翻了上一节的推断:清场遗留只有 **A=11 曲/699 行**,
而 **C=3,150 曲/12,014 行在 manifest 里、整曲缺、段也缺** —— s4_parallel 建名单时
要求 `split=="train"` 才渲,把 split 缺失的曲(装配端默认按 train 用)和 val/test 曲
**静默漏渲**。两端口径不一致,一行代码之误。已修:渲染资格 = 有 MIDI,与 split 无关
(val/test 也要音频才能被评;泄漏防护在装配端黑名单,不靠不渲)。

净收益修正:**+12,014 训练行(≈+5%)+ pdmx val/test 首次获得音频**(此后 pdmx 可作干净评测源)。

```bat
git pull --rebase --autostash
:: 真渲染(~3,150 曲,sfizz CPU,数小时;训练优先,内存规则同第一步):
set S4_RESERVE_GB=10
python scripts/s4_parallel.py
:: 渲完切段(只会切新渲的曲,旧段自动跳过):
python scripts/s4_slice_segments.py
:: 验收:装配统计 + 切割计数,push 新文件 reports/RECALL_RESULT_3.txt
python scripts/build_dataset.py --dry-run
```

验收判据:pdmx no_audio 从 46,740 降 ≈12,014;渲染 ok≈3,150(fail 贴回分诊);
sliced ≈ 12,014 ±(段时长守卫会拦掉少量)。对账残差 ~522 曲(切割器 3,683 vs
对账 3,161)属两工具统计口径差,渲后复跑 recall_explain 应归零或可解释,一并贴回。

---

## 第四步:全崩分诊(2026-07-18,@b2cf3e1)

3,480 曲渲染 **100% CalledProcessError**。"全崩"不是内存争抢(那是间歇杀手,不会齐崩),
是系统性前置条件坏了。执行端"内存争抢/环境问题"两个猜测先不采纳 —— 取证再判。

头号嫌疑(与这批曲的身世自洽):它们**历史上从未被渲过**,如果产 MIDI 的上游步骤
(D7 tempo 钳制重写)当年也按 `split=="train"` 过滤,这批曲的 midi_path 就是
"记了账没造货" —— 文件缺失/零字节,sfizz 必崩且恰好 100% 崩。

```bat
git pull --rebase --autostash
python scripts/s4_diag.py
git add reports/s4_diag.md && git commit -m "s4 diag" && git push
```

脚本三件事(分钟级):① stat 全部待渲 MIDI(缺失/零字节/实存计数,≥90% 缺 → 当场定案);
② 环境对照:重渲 1 首当年成功过的曲到临时目录(它也崩=环境坏,成功=环境无罪);
③ 对 2 首 MIDI 实存的失败曲打印【完整 stderr】(渲染报告 80 字符截断一直在丢证据)。
三份证据齐了按矩阵走:MIDI 缺 → 修上游产 MIDI 步骤;环境崩 → 修 sfizz/音源路径;
stderr 指向具体 flag/音源 → 对症修。训练不受影响,继续跑。

---

## 终局:对账闭合,召回完成(2026-07-18 深夜,@d866756,D37)

渲染修复后复跑对账:缺整曲音频的曲从 3,161 降到 **11**,且四类分布 =
**A 清场遗留 11 曲/699 行(按设计留在池外)、B=0、C=0(矛盾类清零)、D=0** —— 无悬案。

召回最终战果:
- 渲染 +3,480 曲整曲音频(含 pdmx val/test 首次获得音频,评测源资格解锁);
- 切段 +7,501 个训练段;
- 12,104 vs 7,501 的差 = 新增 structure_mismatch 618 曲的行 + 时长守卫(与守卫计数自洽);
- 残余 no_audio = 清场遗留 699 行 + structure_mismatch 全量 + 时长/无 MIDI 守卫,全部有名有姓。

新段进池时机:50000 步复盘的例行重启(装配器现场发现,checkpoint 续,启动打印的
装配统计即最终 --dry-run 验收,届时 push 即可)。structure_mismatch(现 6,410 曲)
仍是唯一挂账的可回收池(谱面侧反复展开映射,中等工程,待议)。
