# EXECUTOR 工作守则(新 session 从这里开始,别的都不用翻)

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

## 当前阶段(2026-07-20 深夜,D40:提速 v2,此节为唯一现行指令)

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
