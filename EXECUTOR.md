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

## 当前阶段(2026-07-14)

数据管线已全绿收尾(P0-P8),冒烟已通过(final_sem=0.038,reports/SMOKE_RESULT.md),
全量训练已至 step≈7600。**当前任务 = `EXPERIMENT_H1.md` 那一张卡**(平台期判决实验):
备份 last.pt → `python scripts/build_dataset.py --clip-norm 25` → ≥500 步 → 按卡上清单贴回。
不用再跑 sop_next(数据期命令);训练期日常 = `git pull --rebase --autostash` + 按当前实验卡跑。
