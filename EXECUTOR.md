# EXECUTOR 工作守则(新 session 从这里开始,别的都不用翻)

## 目标板(每次指令更新时规划端同步刷新;你随时该能答出这三行)

- **项目终点**:复现 Rubato 论文 —— 真实钢琴录音 → 可用乐谱(终评对标 OMR-NED 64.3 /
  AMT F1 97.0,在官方 test 集上)。
- **当前阶段目标**:让模型学会"从真实音频读音高"(全项目最顽固的病灶,仪表 = maestro
  探针的 Δpitch)。手段按序:C2 偏移窗已进池(**判决 71600 步**:Δpitch 连续 3 评 ≥+0.03
  为成,败则回退);C3 音色副本你已备好料(staging,等武装口令);泄漏修复你已执行
  (等重启生效)。
- **你的角色**:训练不间断、逢 eval push autolog(判决全靠它)、按本文件章节执行/贴回;
  任何数字只认文件不认记忆,任何重启/改名只认本文件口令。

你是执行端。规划端(另一个 agent)通过 git 与你协作:代码和指令在 repo 里,
你的产出(状态、失败、报告)也通过 git 回去。**你不需要历史对话的任何上下文。**

## 你的全部日常操作(就这两条)

```
git pull --rebase --autostash
python scripts/sop_next.py --go
```

- `--go` 从断点自动干到底,只在真失败/质量闸不过时停;中断了就重跑 `--go`。
- 进度随时看:`python scripts/sop_next.py --status`(状态存盘 work/sop_state.json,不怕忘)。
- 每步的成败会**自动 commit+push** 到 `reports/sop_blocks/`(失败另落
  `reports/sop_last_failure.md`),规划端直接从 git 看 —— 失败不需要你贴、不需要你修。

## 铁律(每一条都对应一次真实事故)

1. **不要手搓循环/分块/wrapper 绕过 SOP 跑管线脚本。** 手搓分块曾整块丢曲、
   误用 --fresh 险些删产出。缺工具就在报告里写"缺 XX 工具",等规划端提供。
2. **不要 pkill/杀全体 python。** 只允许按命令行精确匹配杀目标进程,例如:
   `Get-CimInstance Win32_Process | ? {$_.CommandLine -match 's7_full_nasap'} | % {Stop-Process -Id $_.ProcessId -Force}`
3. **同一驱动器不要双开。** s7_resilient 有单实例锁,新实例会自动等待 —— 等着就行。
4. **失败就停在原地上报,不要自己改代码、不要换命令重试。** `--go` 打印的失败块
   已自动推送;你只需在 repo 里补充你观察到的现场(见下)。
5. **清理/修复类操作只走 SOP 或规划端给的脚本**,跑完必须有"残留全 0"验证表。

## 上报规范(你唯一要动笔的地方)

发现异常时,在 `reports/` 下写一个 md,git push。好报告 = 你上次那两份的样子:
**现象(原文粘贴)→ 数据有没有损失(用命令核对,贴数字)→ 你的疑问(具体、可回答)**。
不要只写"出错了"。

## 环境备忘

- repo:`D:\vscode_projects\ee_download\Rubato`;数据/产物:`D:\vscode_projects\ee_download\{work,reports}`
- Python:VN/VirtuosoNet 用 py312,其余用 nemo_test —— **SOP 内部自动选,你不用管**。
- 控制台是 GBK:所有脚本已做 stdout 硬化;若见乱码属显示问题,不影响产物。

## 当前阶段追加 7(2026-07-23,D51:两个问题的修复指令;取代"追加 6"的任务清单)

你报的两个问题都属实,修复已进库。按序执行:

任务一 · 恢复 C3 渲染(目录已隔离,不再与训练抢锁):
```bat
:: 若 c3_timbre_copies 还在跑,先按命令行精确匹配停掉它(别 pkill):
:: Get-CimInstance Win32_Process | ? {$_.CommandLine -match 'c3_timbre_copies'} | % {Stop-Process -Id $_.ProcessId -Force}
git pull --rebase --autostash
set S4_RESERVE_GB=10
python scripts/c3_timbre_copies.py --n 12000
```
- 新版输出到独立目录 work\pdmx_audio_s2\(训练永不读它,锁争抢根治);
- 启动时自动把老目录里已渲的 _s2 产物搬过去(已花的 601 曲 CPU 不浪费);
- PermissionError 现自带 3 次退避重试;之后照旧断点续跑 + 每日 push C3_RENDER.md。

任务二 · 泄漏修复(先干跑核数,再执行;只改标签文件,训练不用停不用重启):
```bat
python scripts/fix_split_leakage.py
:: 干跑输出 quarantined 应 ≈1239;数字对得上再:
python scripts/fix_split_leakage.py --apply
git add reports/split_leakage.md && git commit -m "split leakage fix applied" && git push
```
- 隔离方式 = split 改 quarantine_leak(训练/评测两不进,原值可逆,.bak 已备份);
- **生效在下一次重启的装配 —— 重启口令等本文件下一节,勿自行重启**。

任务三 · 红线不变:严禁改名 staging 标签文件;严禁自行重启训练。
任务四 · 照常:逢 eval push autolog(71600 判决在即,这批数据最要紧)。

贴回清单:C3_RENDER.md(每日)、split_leakage.md(含"已执行"节)、autolog。

## 【已被追加 7 取代】当前阶段追加 6(2026-07-22 晚,D50)

**频道规矩(用户令,永久生效)**:你的任务只以本文件为准;用户聊天转述、commit 标题、
口头印象一律不作数。每节任务附完整命令与贴回清单,照抄执行。

任务一 · 泄漏对账(上节欠的,先做,分钟级,不停训):
```bat
git pull --rebase --autostash
python scripts/audit_split_leakage.py
git add reports/split_leakage.md && git commit -m "split leakage audit" && git push
```

任务二 · C3 音色副本后台渲染(M 档 12,000 曲,用户已拍板;CPU 与训练并行,预计 2-4 天):
```bat
set S4_RESERVE_GB=10
python scripts/c3_timbre_copies.py --n 12000
```
- 中断/重启机器后,重跑同一条命令即续(已渲的自动跳过);
- 训练日志若现 OOM 或 step 时间明显变长:先停渲染(按命令行精确匹配杀 c3_timbre_copies),训练优先;
- 内存紧张改 `--workers 2`;
- 每天一次 + 完成时:`git add reports/C3_RENDER.md && git commit -m "c3 render progress" && git push`。

任务三 · 【禁止事项,红线】:
- **严禁**把 `work/pdmx_a2s_labels_s2.staging.jsonl` 改名为 `pdmx_a2s_labels_s2.jsonl`;
- **严禁**在渲染期间重启训练(除非训练自身故障);
- 改名与重启的口令只会写在本文件的后续章节里,不会通过任何其他渠道下达。

任务四 · 照常:逢 eval push autolog(71600 判决数据,最要紧)。

贴回清单:reports/split_leakage.md、reports/C3_RENDER.md(每日)、autolog。

## 【已执行】当前阶段追加 5(2026-07-22,C2 已进池;三件小事)

RESTART_C2 验收:生成/装配/回显全对(skip_nontrain=314 与官方名单分毫不差),但缺第④样
**恢复行**(续训:恢复 step=…)—— 从你本地日志补贴进下一份报告。另:C2_EVAL1.txt 里只有
eval 心跳行,commit 标题里的 Δpitch 数字无文件出处,**不算数**;eval 结束后 autolog 会
自动写探针行,push autolog 即可,**不要手抄数字进标题**。

1. 补贴恢复行(和下一样一起);
2. **泄漏对账**(CPU 分钟级,不停训):
   `python scripts/audit_split_leakage.py` → push reports/split_leakage.md
   (查 nasap-train 是否引用了 maestro val/test 录音;应为 0);
3. 照常逢 eval push autolog(C2 后首个完整 eval 块最要紧)。

## 【已执行】当前阶段追加 4(2026-07-22,D49:C2 立即进池)

时机改了:**不等 71000,现在就装**(理由见 D49:lr 在衰减,晚一步亏一步)。四步:

```bat
git pull --rebase --autostash
:: 1. 全量生成(几分钟,训练可先不停):
python scripts/s6_amt_windows.py --offset 10
:: 2. 停训 → 原命令重启(与 D44 完全相同,不加新旗子):
cmd /c "D:\ProgramData\envs\nemo_test\python.exe -u D:\vscode_projects\ee_download\Rubato\scripts\build_dataset.py --clip-norm 25 --lr-dec 3e-4 >> D:\vscode_projects\ee_download\reports\train_full.log 2>&1"
```

贴回(新文件 reports/RESTART_C2.txt,四样):① 生成器末行 DONE 统计;② 启动装配统计整块
(maestro rows 应 144,087 → ~26 万,val/test 数不变);③ 配置回显行;④ 续训:恢复… 行。
之后照常 autolog。判决窗 = 本次恢复步 +8000(主判据:maestro Δpitch 连续 3 eval ≥+0.03)。

## 【作废】当前阶段追加 3(2026-07-22,C2 已交付:一次冒烟,武装等 71000)

C2 偏移窗生成器就绪。现在只做**冒烟验证**(1 分钟,不停训,注意必须带 --out 临时名):

```bat
git pull --rebase --autostash
python scripts/s6_amt_windows.py --offset 10 --limit 5 --out D:\vscode_projects\ee_download\work\_c2_smoke.jsonl
```

贴回末行 DONE 统计(新文件 reports/C2_SMOKE.txt):windows/labels 应 >0,skip_nontrain ≥0。
**不要在 71000 之前用默认输出名跑全量**——默认名文件一旦存在,下次任何重启都会自动进池,
会污染 R1 的前后对照。全量生成的口令我在 71000 复盘时和重启指令一起下。

## 当前阶段追加 2(2026-07-22,收尾两件)

RESTART_D44 验收通过,训练照跑不动。剩两件:
1. **QC 全量跑**(你只跑了 --limit 5 冒烟;全量约 20-30 分钟,不停训):
   `python scripts/audit_render_qc.py` → push render_qc.md。
   报告标题请写实:冒烟是 "0/5",不是 "0 truncated renders"。
2. Shr(python.exe 共享 GPU 内存)进入你的常态观察:哪天 ≥1GB,例行重启一次即可
   (不改配置,SPEED 卡补遗)。
之后就是 71000 复盘,照常 autolog。

## 当前阶段追加(2026-07-22,D47:声学审计,与训练并行)

D44 的三步照旧(abtest 已收,谢;**若训练还没按第 3 步重启,现在重启**)。新增一件
不停训的 CPU 活,今天任意时间跑:

```bat
git pull --rebase --autostash
python scripts/audit_render_qc.py
git add reports/render_qc.md && git commit -m "render qc audit" && git push
```

产出三节:时长对账(疑似截断计数)/ 音色分布 / maestro 整曲库存。约 20-30 分钟,只读。
这是声学补救计划(EXPERIMENT_ACOUSTIC)的第一步;C2 切窗生成器规划端在建,数日内到。

## 当前阶段(2026-07-21 深夜,D44:一停一测一重启;此节为唯一现行指令)

你的审查是好工作:**训推前缀不一致经代码核实成立**,判定实验已按你 §1.4 的设计实现;
两个试验(0.22 混比、batch=50)都按预登记判据判了**未达标**,本次重启一并回退。

按顺序做,一共三步:
1. **停训** → `git pull --rebase --autostash`;
2. **跑判定实验**(GPU ~40 分钟):
   `python scripts/build_dataset.py --prompt-abtest`
   结束后 `git add reports/eval_autolog.md && git commit -m "prompt abtest" && git push`;
3. **立即重启训练,不等规划端判决**(配置回退到:混比 D2 纸面、批 60):
   `... build_dataset.py --clip-norm 25 --lr-dec 3e-4 >> train_full.log 2>&1`
   (**不带** --amt-mix、**不带** --max-batch-sec —— 两案已判,少一个旗子都是对的)
   贴回新文件 reports/RESTART_D44.txt:回显行(应含 mix=D2纸面 batch_sec=60.0 prefetch=关)
   + 恢复行 + **补贴 60900-61100 的三行训练日志**(O4 判决存档,从你本地 train_full.log 搜)。
之后照常逢 eval push autolog(拒因行从此有真实类别,不再恒"兜底=4x")。
下次节点:abtest 数据到 = prompt 判决;例行复盘 71000。

## 上一阶段存档(2026-07-21 晚,D43)【已被 D44 取代】

你的两份材料都收了:显存数合格(共享 1,576MB → 溢出坐实,试验开庭);仪表提议采纳一半
(拒因直方图 + 探针音高分型,已进代码),缓办一半(时间戳 MAE/逐方言 F1,可解析样本
太少撑不起统计,parseable>0.5 再议)。本轮报告合规,保持这个标准。

操作(唯一变化 = 加 `--max-batch-sec 50`):
1. 停训 → `git pull --rebase --autostash`;
2. 重启:`... build_dataset.py --clip-norm 25 --lr-dec 3e-4 --amt-mix 0.22 --max-batch-sec 50 >> train_full.log 2>&1`
3. 贴回(新文件 reports/MAXBATCH_50.txt):回显行(应含 batch_sec=50.0)+ 恢复行 +
   跑 1 小时后 5 行 td=/tc=(避开 eval)+ **复测 Get-Counter 的专用/共享两个数**;
4. 之后照常:逢 eval push autolog(新 eval 块会多「拒因」行和 Δpitch 字段,属正常);
   等 61000 复盘。
规矩补充:不要把 train_full.log 整个 commit(这次 16K 无妨,日志会长大)——报告里贴
需要的片段即可。

## 上一阶段存档(2026-07-21,D41)【已被 D42 取代】

**⚠ pull 完必须重读本节。D39/D40 两版预取都已判负收益召回,预取默认已关。**
核对:启动回显必须是 `prefetch=关`(出现 proc:3 或裸 3 = 旧代码,先 pull)。

操作(命令仍与 D38 相同,无新旗子):
1. 停当前训练(它还在跑 18s/步的坏版本,停了就是赚);
2. `git pull --rebase --autostash`;
3. 原命令重启(--clip-norm 25 --lr-dec 3e-4 --amt-mix 0.22);
4. 启动日志的【执行端贴回】行照办,写新文件 reports/SPEED_TIMING.txt:
   回显行 + 恢复行 + **跑 1 小时后连续 5 行带 td=/tc= 的日志(避开 eval 窗口)** +
   **任务管理器→详细信息→python.exe 的「专用 GPU 内存」「共享 GPU 内存」两个具体数(必贴,
   上两轮都没贴)**;
5. 之后正常跑,逢 eval push autolog,等 61000 复盘。

## 上一阶段存档(2026-07-20 深夜,D40)【已被 D41 取代,勿执行】

**⚠ pull 完必须重读本节。上一版(D39 线程预取)已判有害并召回 —— 你若按旧记忆跑,
等于跑已知坏版本。核对方法:启动日志第一行回显必须是 `prefetch=proc:3`;
若是 `prefetch=3`(无 proc)= 旧坏代码,停下先 pull。**

操作(与 D38 命令完全相同,无新旗子):
1. 停当前训练进程(按命令行精确匹配,别 pkill);
2. `git pull --rebase --autostash`;
3. 原命令重启:`... build_dataset.py --clip-norm 25 --lr-dec 3e-4 --amt-mix 0.22 >> train_full.log 2>&1`
4. 启动后日志会自动打印一行【执行端贴回】清单 —— 照它办,写新文件 reports/SPEED_RESTART_2.txt。
   额外盯一样:日志中任何「预取:」开头的行 = 预取回退了,原样贴回(训练不会停,但要报)。
5. 之后 27 小时正常跑:逢 eval push autolog,不做任何其它操作。

## 上一阶段存档(2026-07-20 晚,D39:提速重启)【已被 D40 取代,勿执行】

上一节的 O4 重启已完成验收(RESTART_O4.txt 四项全过)。新任务一件:**再重启一次拿提速**
(GPU 空转 ~45% 的修复已进库,重启即生效;命令与上次完全相同,不加新旗子):

停训 → `git pull --rebase --autostash` → 原命令重启(--clip-norm 25 --lr-dec 3e-4 --amt-mix 0.22)。
**贴回(新文件 reports/SPEED_RESTART.txt)**:
① 配置回显行(应见 `prefetch=3`;没有 = 旧代码,先 pull);② `续训:恢复 step=…` 行;
③ 重启 ≥30 分钟后:`nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv -l 5`
采 ≥10 行 + **任务管理器 → 详细信息 → 添加列"专用 GPU 内存"/"共享 GPU 内存" →
python.exe 一行的两个具体数**(你 SPEED_CONCERN 里的 28-29GB 需要这个出处才能定案;
面板上的"共享 GPU 内存 16GB"是容量不是占用,别贴那个);
④ 此后逢 eval 照常 push autolog。异常(nan/卡死/日志断流)→ 同命令加 `--prefetch 0` 重启并上报。
你的两个提问已答,见 EXPERIMENT_SPEED.md"答执行端"节(accum 不降,减层否决,checkpointing 备选)。

## 上一阶段存档(2026-07-20,D38:一次重启,三事同车)

50000 复盘已裁决(用户拍板):**AMT 混比 0.30→0.22**。操作 = 停当前训练 →
`git pull --rebase --autostash` → 用下面命令重启(唯一变化 = 加 `--amt-mix 0.22`):

```bat
cmd /c "D:\ProgramData\envs\nemo_test\python.exe -u D:\vscode_projects\ee_download\Rubato\scripts\build_dataset.py --clip-norm 25 --lr-dec 3e-4 --amt-mix 0.22 >> D:\vscode_projects\ee_download\reports\train_full.log 2>&1"
```

checkpoint 自动续(~53050),不从头训。重启同时会把召回的 +7,501 段装进池(自动)。
**贴回清单(写新文件 reports/RESTART_O4.txt,缺一不可)**:
① 启动装配统计整块(=== 到 train=… 行;这是 RECALL 终验收,pdmx kept 应 +7,501 上下);
② 配置回显行(应含 `mix=A2S:0.390,…,AMT:0.220`;若显示 `mix=D2纸面` = 旗子没生效,停下贴回);
③ `epoch0 混比报告` 行(quota 自证);④ `续训:恢复 step=…` 行。
此后日常照旧:逢 eval push autolog。下次复盘 **61000**(判据已预登记 EXPERIMENT_O4_MIX.md)。

## 报告规矩补充(2026-07-15,对应 cd996eb / 5c48581 两次事故)

- **不要编辑任何已存在的 reports/ 文件。每次新报告写新文件**,编号递增
  (如 PROBE_RESULT_2.txt、PROBE_RESULT_3.txt),旧文件一个字都不动。
  (cd996eb 删了 eval 段、5c48581 又删了 49 行旧步 —— 证据都靠 git 历史找回。)
- 摘录训练日志时,所有以 `  eval` 开头的行必须保留(探针/样本预测/解码现场/汇总都在里面)。
