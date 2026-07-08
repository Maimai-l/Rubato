# START HERE —— 两 agent 经此 git 仓库协作

本仓库是**规划端(spec/诊断)**与**执行端(本地真实数据+GPU)**的协作面。
双方通过 pull/push 交互,用户随时可在 PR/commit 审阅。

## 你是执行端?按这个来

1. **上分支 + 拉最新**(规划端的修复都在这个分支,不是 main):
   ```
   git fetch origin
   git checkout claude/training-issues-diagnosis-9ygud6
   git pull origin claude/training-issues-diagnosis-9ygud6
   ```
2. **按序读**:`ARCHITECTURE.md` §3(数据流表)→ `DIAGNOSIS.md` → `EXECUTOR_CORRECTIONS.md`
   → `LOCAL_VERIFICATION.md`。你的完整任务指令在 `PROMPT_FOR_EXECUTOR.md`。
3. **干活 → 提交 → 推送**:每完成一步,把**代码/配置/格式适配**提交并推到本分支
   (`git pull --rebase` 后 `git push`)。用户在 PR 审。**数据产物(work/、音频、labels、
   tokenizer.model)不进 git**(已 gitignore),只留本地。
4. **收到规划端更新后**先 `git pull` 再重跑 `tests_*.py`,确认没回退再继续。

## 铁的三条(违反=返工,详见 EXECUTOR_CORRECTIONS.md)
1. **数据流**:MAESTRO 只喂 AMT;PDMX 纯乐谱必须先 S4/S5 渲染;A2S/TAST 真实音频只有 nASAP。
2. **tokenizer 是地基**:必须先有真 8000 词表(learnable==3571),才能建模型、才能训练。
   4760/331-piece 的坏 tokenizer 上建的一切都作废。
3. **硬判据文化**:只认数字(loss<0.05 / vocab==8000 / split_rate<0.30 / match_rate>0.80),
   不认"跑通不报错"。达不到=没做完,按文档 FAIL 排查,不粉饰。

## 为什么用 git 协作(而非 tar 覆盖)
上一轮 tar 更新反复冲掉执行端的本地真实数据适配(如 xml_id 桥接被 v11 回退)。
经 git:执行端的适配提交进仓库 → 规划端 pull 时看得到、不会覆盖 → 从根上消除 churn。

## 文档地图
| 文件 | 内容 |
|---|---|
| `PROMPT_FOR_EXECUTOR.md` | 执行端的完整任务指令(可直接执行) |
| `EXECUTOR_CORRECTIONS.md` | 上一轮的错误 + 正确顺序 + 数据流铁律 |
| `LOCAL_VERIFICATION.md` | 每步的硬判据(通过/失败数字)+ 排查 |
| `DIAGNOSIS.md` | 21 个问题的根因与已修内容 |
| `ARCHITECTURE.md` / `SPEC.md` | 数据流视图 / 工程规格(权威) |
