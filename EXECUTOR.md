# EXECUTOR 工作守则(新 session 从这里开始,别的都不用翻)

## 目标板(每次指令更新时规划端同步刷新;你随时该能答出这三行)

- **项目终点**:复现 Rubato 论文 —— 真实钢琴录音 → 可用乐谱(终评对标 OMR-NED 64.3 /
  AMT F1 97.0,在官方 test 集上)。
- **当前阶段目标**:二轮跑到 100k 不停(61k 判读 D85:教师强制侧在学,病灶=自由生成
  不收口)。pull 之后按**追加 29** 执行:一个暂停窗跑完 解码扫参 + 双杆 100 步安全门,
  然后按门果决定 v4(素跑)或 v5(带新杆)重启。
  **本地运维(内存/性能/路径/存储/磁盘)从此全权归你,不再报备**(D63,用户令)。
- **你的角色**:按本文件章节执行/贴回;后台渲染断点续跑;任何开训/改名只认本文件口令;
  任何数字只认文件不认记忆。

## 当前阶段追加 29(2026-08-03,D86):pull 后的一个暂停窗 —— 解码扫参 + 双杆安全门

**pull 本身零风险**:新代码三样(解码扫参 / 遮上文 / 音频依赖损失)全部缺省 0=关,
不带新旗标的重启行为与 pull 前逐字节相同;追加 28 的 v4 块仍是素跑正典。
运行中的训练进程不受 pull 影响(模块已加载),不必为 pull 停训。

以下三步在**同一个训练暂停窗**做完(总预算 ~3-4 小时;D74 教训:任何解码/评测
不得与训练并发抢 GPU)。每步独立可跳,跳了就在贴回里说一声。

### 第 1 步:解码扫参(零训练风险,~1.5 小时)

同 ckpt 网格比较 重复惩罚 × 终止符加成(DECODE_AB_STEP61200 的既定下一步)。
先停训练:`Stop-Process -Id <训练PID> -Force`(PID 忘了就
`Get-Process python* | Format-Table Id,StartTime`)。然后:

```powershell
$W = "D:\vscode_projects\ee_download\work"
$p = Start-Process -FilePath 'D:\ProgramData\envs\nemo_test\python.exe' `
  -ArgumentList '-u','scripts/build_dataset.py','--decode-abtest','--decode-abtest-beams','1','--decode-abtest-rep','1.0,1.1,1.3,1.5','--decode-abtest-eot','0,1,2,4','--abtest-n','24' `
  -WorkingDirectory 'D:\vscode_projects\ee_download\Rubato' `
  -RedirectStandardOutput "$W\decode_sweep.out.log" `
  -RedirectStandardError  "$W\decode_sweep.err.log" `
  -NoNewWindow -PassThru
"PID = $($p.Id)"
```

16 臂 × 24 样本,自动读 outputs/ckpt/last.pt,不动任何权重。
**贴回**:decode_sweep.out.log 末尾的 16 行"beam=1 rep=… eot=…: parseable=…"汇总 +
`git add reports/DECODE_SWEEP_STEP*.json reports/eval_autolog.md` 后 commit+push。
判读口径(预登记):任一臂 parseable>0 或拒因谱明显移动(DYCK/TS_* 降)= 解码侧有肉,
规划端再发细网格;16 臂全 0 = 曝光偏差结论加固,重心全压训练侧两杆,扫参关案。

### 第 2 步:双杆 100 步安全门(照 EXPERIMENT_AMT_DISTILL 同款,~1-2 小时)

新杆:**1c 遮上文**(--input-dropout,教师强制输入随机遮成 unk,治"只会抄上文")
+ **2c 音频依赖损失**(--audio-dep-weight,批内错配音频第二次 decoder forward,
逼 decoder 真用交叉注意力)。两杆都是温和剂量,按 D81 配方制**打包成一个 B 臂**;
门是**安全门**(不炸/开销/仪表活),不是疗效门(疗效看进正跑后的 pv/id/ad/探针)。

原子分叉(训练已停的状态下):
```powershell
$R = "D:\vscode_projects\ee_download\Rubato"
New-Item -ItemType Directory -Force "$R\outputs\ckpt_ab_d86A" | Out-Null
New-Item -ItemType Directory -Force "$R\outputs\ckpt_ab_d86B" | Out-Null
Copy-Item "$R\outputs\ckpt\last.pt" "$R\outputs\ckpt_ab_d86A\last.pt"
Copy-Item "$R\outputs\ckpt\last.pt" "$R\outputs\ckpt_ab_d86B\last.pt"
```

停步数:先看 `Get-Content "D:\vscode_projects\ee_download\work\train_r2_v4.out.log" -Tail 3`
里最后的 step 数,记作 S;下面两条命令的 `<S+100>` 都换成同一个数字(S+100)。
A 臂(对照,先跑,跑完再跑 B 臂,不并发):

```powershell
$W = "D:\vscode_projects\ee_download\work"
$p = Start-Process -FilePath 'D:\ProgramData\envs\nemo_test\python.exe' `
  -ArgumentList '-u','scripts/build_dataset.py','--clip-norm','25','--lr-dec','3e-4','--eval-decode-every','5000','--augment-acoustic','--pitch-loss-weight','2.5','--ckpt-dir','D:\vscode_projects\ee_download\Rubato\outputs\ckpt_ab_d86A','--stop-after-step','<S+100>' `
  -WorkingDirectory 'D:\vscode_projects\ee_download\Rubato' `
  -RedirectStandardOutput "$W\ab_d86_A.out.log" `
  -RedirectStandardError  "$W\ab_d86_A.err.log" `
  -NoNewWindow -PassThru
"PID = $($p.Id)"
```

B 臂(两杆齐开,其余与 A 一字不差):

```powershell
$W = "D:\vscode_projects\ee_download\work"
$p = Start-Process -FilePath 'D:\ProgramData\envs\nemo_test\python.exe' `
  -ArgumentList '-u','scripts/build_dataset.py','--clip-norm','25','--lr-dec','3e-4','--eval-decode-every','5000','--augment-acoustic','--pitch-loss-weight','2.5','--input-dropout','0.10','--input-dropout-ramp','5000','--audio-dep-weight','0.10','--audio-dep-margin','0.10','--ckpt-dir','D:\vscode_projects\ee_download\Rubato\outputs\ckpt_ab_d86B','--stop-after-step','<S+100>' `
  -WorkingDirectory 'D:\vscode_projects\ee_download\Rubato' `
  -RedirectStandardOutput "$W\ab_d86_B.out.log" `
  -RedirectStandardError  "$W\ab_d86_B.err.log" `
  -NoNewWindow -PassThru
"PID = $($p.Id)"
```

(ramp 按全局步计,分叉点已远超 5000 → B 臂立即全率 0.10,门测的就是全率,口径一致。)

**门判据(预登记,先于数据)**:①B 臂 100 步不炸(无 NaN/OOM/越界);②新列活着:
B 臂日志出现 id=(应 ≈0.10)与 ad=(出数即可,量级不判);③开销:B 臂 tc avg
≤ A 臂 ×1.20(音频依赖多一次 decoder forward 的预算);④B 臂 loss avg50 ≤ A 臂 ×1.10
(遮上文抬 loss 属预期,温和即可)。
**贴回**:两臂启动回显里的"遮上文 input_dropout=… | 音频依赖损失 weight=…"行 +
各自最后 5 条训练行(含 id=/ad= 列)+ 两臂 `_finish` 后日志尾 3 行。

### 第 3 步:重启主线训练

- 门全过 → **v5 块**(= v4 + 两杆四旗标,注意日志名换 v5;主 ckpt 目录不动,续
  61k+ 权重,开局必须有"续训:恢复 step=…"行,**没有这行立即停手贴回**):

```powershell
$W = "D:\vscode_projects\ee_download\work"
$p = Start-Process -FilePath 'D:\ProgramData\envs\nemo_test\python.exe' `
  -ArgumentList '-u','scripts/build_dataset.py','--clip-norm','25','--lr-dec','3e-4','--eval-decode-every','5000','--augment-acoustic','--pitch-loss-weight','2.5','--input-dropout','0.10','--input-dropout-ramp','5000','--audio-dep-weight','0.10','--audio-dep-margin','0.10' `
  -WorkingDirectory 'D:\vscode_projects\ee_download\Rubato' `
  -RedirectStandardOutput "$W\train_r2_v5.out.log" `
  -RedirectStandardError  "$W\train_r2_v5.err.log" `
  -NoNewWindow -PassThru
"PID = $($p.Id)"
```

- 任一门不过 → 素跑 **v4 块**(追加 28)原样重启,把两臂日志贴回,规划端拆单变量。
- 开局核对(v5):配置回显四样 + "遮上文 input_dropout=0.1(ramp 5000…)| 音频依赖
  损失 weight=0.1 margin=0.1"行 + "续训:恢复"行 + 训练行有 id=/ad= 两新列。
- 之后节奏不变:每 10k 发 autolog;解码腿每 5000 步自动跑,parseable 与拒因谱
  就是两杆疗效的终审仪表。A/B 分叉目录用完可删(ckpt_ab_d86A/B,各 ~2GB)。

## 【素跑正典;带杆重启见追加 29 第 3 步 v5 块】当前阶段追加 28(2026-07-26,D83):二轮启动·最终版(增广 + 音高加权 ×2.5)

配方钉板:池 v3 + 从零 + C1a 现版 + 音高加权 ×2.5(加强版 C1a 已砍;遮上文 10k 再议)。
四步照抄:
1. 若有训练进程先停:`Stop-Process -Id <PID> -Force`
2. `if (Test-Path "D:\vscode_projects\ee_download\Rubato\outputs\ckpt") { Rename-Item "D:\vscode_projects\ee_download\Rubato\outputs\ckpt" "ckpt_r2trial_79k" }`
3. `git pull --rebase --autostash`(在 D:\vscode_projects\ee_download\Rubato 下)
4. 启动:
```powershell
$W = "D:\vscode_projects\ee_download\work"
$p = Start-Process -FilePath 'D:\ProgramData\envs\nemo_test\python.exe' `
  -ArgumentList '-u','scripts/build_dataset.py','--clip-norm','25','--lr-dec','3e-4','--eval-decode-every','5000','--augment-acoustic','--pitch-loss-weight','2.5' `
  -WorkingDirectory 'D:\vscode_projects\ee_download\Rubato' `
  -RedirectStandardOutput "$W\train_r2_v4.out.log" `
  -RedirectStandardError  "$W\train_r2_v4.err.log" `
  -NoNewWindow -PassThru
"PID = $($p.Id)"
```
开局核对(发回这几行):配置回显行(clip_norm=25.0 / lr_dec=3.0e-04 / eval_decode_every=5000
/ aug_acoustic=开)+ "音高 piece 掩码: … | 加权 ×2.5"行 + **无"续训:恢复"**、首条训练行
step 为小数字。之后每 10k 发一次 autolog,训练期不渲染。训练行新列 pv= 即音高损失,
它降 = 音高在学。

## 【被追加 28 取代】追加 27(2026-07-26,D80):二轮启动命令终版

用户裁决:C1a 声学增广进二轮基线,不再分段进场(理由成立:试验 9,000 步已是无增广实测;
增广本属论文配方)。启动三步不变(停旧 PID → ckpt 目录改名归档 → pull),命令换终版:

```powershell
$W = "D:\vscode_projects\ee_download\work"
$p = Start-Process -FilePath 'D:\ProgramData\envs\nemo_test\python.exe' `
  -ArgumentList '-u','scripts/build_dataset.py','--clip-norm','25','--lr-dec','3e-4','--eval-decode-every','5000','--augment-acoustic' `
  -WorkingDirectory 'D:\vscode_projects\ee_download\Rubato' `
  -RedirectStandardOutput "$W\train_r2_v4.out.log" `
  -RedirectStandardError  "$W\train_r2_v4.err.log" `
  -NoNewWindow -PassThru
"PID = $($p.Id)"
```
开局核对四样:clip_norm=25.0 / lr_dec=3.0e-04 / eval_decode_every=5000 / **aug_acoustic=开**,
且无"续训:恢复"行(step 从小数字起)。发回回显行+头 3 条训练行,之后每 10k 一报。

## 【命令被追加 27 终版取代】追加 26(2026-07-26,D78):试验判败 → 二轮全新热启

判决:主判据(maestro Δpitch 三连正)与副判据在 80,800 前均已不可达 → 失败,按预注册
转全新热启。试验遗产:合成侧被喂活(A2S 2.41→2.32/TAST 1.94),maestro 音高冻结
= 权重级顽疾,数据须从第 0 步在场。

执行(三步):
1. 停当前 PID;`Rename-Item "D:\vscode_projects\ee_download\Rubato\outputs\ckpt" "ckpt_r2trial_79k"`
2. `git pull --rebase --autostash`
3. 正典命令块,日志名改 v4(参数与 v3c 完全相同)。
核对开局:回显 clip_norm=25.0 lr_dec=3.0e-04 eval_decode_every=5000;**必须无"续训:恢复"行**
(从 step 0 起跑,warmup 1500,损失从高处下来属正常,前几万步 parseable 低/NA 属正常)。
发回:回显行 + 头 3 条训练行。之后 autolog 照常;渲染仍禁(训练期干净 GPU)。
二轮里程碑:每 10k 步发一次 autolog 即可,无需守着。

## 【试验判败,见追加 26】追加 25(2026-07-25,D77):双节奏评测上线

v3b 启动验收全对(clip 25/lr_dec 3e-4/缓存 37.3 万条秒装)。**判决点 = 80,800**(70,800+10k)。
应用户要求交付双节奏评测:探针(秒级,主判据)仍每 1000 步;解码腿(~25 分钟)改每
5000 步一跑 —— 试验全程评测开销 ~5 小时 → ~1.5 小时。判据不受影响(主判据只用探针)。

换装(可选,推荐;现在装配有缓存,重启只花几分钟):停当前 PID,pull,然后:
```powershell
$W = "D:\vscode_projects\ee_download\work"
$p = Start-Process -FilePath 'D:\ProgramData\envs\nemo_test\python.exe' `
  -ArgumentList '-u','scripts/build_dataset.py','--clip-norm','25','--lr-dec','3e-4','--eval-decode-every','5000' `
  -WorkingDirectory 'D:\vscode_projects\ee_download\Rubato' `
  -RedirectStandardOutput "$W\train_r2_v3c.out.log" `
  -RedirectStandardError  "$W\train_r2_v3c.err.log" `
  -NoNewWindow -PassThru
"PID = $($p.Id)"
```
核对:配置回显应含 `eval_decode_every=5000`。**判决点不变仍是 80,800**(评测节奏是仪表
不是训练变量,v3b 已跑的步数照算)。不换装也行,就是每千步多等半小时评测。

## 【v3b 启动验收通过;换装见追加 25】追加 24(2026-07-25,D75):配置漂移叫停

抓到两处漂移(对照一轮存档 RESTART_C2.txt 的回显):本次跑成 clip_norm=1.0(应 25.0)
lr_dec=5e-4(应 3e-4)。clip 1.0 把每步更新压到一轮工作点的几十分之一,跑满也是假失败。
两次试验启动都漏了旗标——根因是"例行命令"只存在于旧执行端记忆里,从未入库。今日钉死:

**正典训练启动命令(D76 用户版收编;此后一切重启只用这一块,一个字不改)**:
```powershell
$W = "D:\vscode_projects\ee_download\work"
$p = Start-Process -FilePath 'D:\ProgramData\envs\nemo_test\python.exe' `
  -ArgumentList '-u','scripts/build_dataset.py','--clip-norm','25','--lr-dec','3e-4' `
  -WorkingDirectory 'D:\vscode_projects\ee_download\Rubato' `
  -RedirectStandardOutput "$W\train_r2_v3b.out.log" `
  -RedirectStandardError  "$W\train_r2_v3b.err.log" `
  -NoNewWindow -PassThru
"PID = $($p.Id)"
```
(下次重启只改日志文件名 v3b→v3c…;停进程 = `Stop-Process -Id <上面打印的PID> -Force`,
PID 丢了再用旧的按命令行匹配扫杀。)

执行:
1. 停当前进程(停法同前)。
2. `git pull --rebase --autostash`
3. 跑上面那条正典命令。
4. 发回:配置回显行(**必须见 clip_norm=25.0 lr_dec=3.0e-04**)+ "续训:恢复 step=…"行。
   **判决点 = 该恢复步 + 10,000**(计时重置;之前 ~1,800 步按近冻结作废,不计入)。
5. 跑动中照旧:autolog、评测期间不渲染、到点硬停。

已冻结步的副产品照单全收:70,000 那次评测 = 高质量【基线】评测(权重≈68k 冻结态):
评测机 48/48 全跑通(~13 分钟/集,干净 GPU 下恢复正常 —— 抢占理论实锤);新仪表首秀
即破案(拒样本 n_new=642、stop=eot、fast=True:自然收尾仍 DYCK/MEASURE 败 = 内容伤
不是长度伤);maestro 真pitch 0.17 = 起点冻结区,正是试验要撬的那块。

## 【被追加 24 取代(配置漂移)】追加 23(2026-07-25,D72):尸检结案 → 试验重启

尸检:恢复是成功的(68050 + lr 分毫吻合),judgment VOID——评测只评了 2 条(600s/条
耗尽 1200s 预算),n=2 的 0.00 无统计力(真率 0.10 下 2 条全空概率 81%)。报告验收
通过,自证伪两条如实列出记为样板;唯 #1"停在时间戳一半"系日志显示截断(raw[:160]),
目击证据作废,#4 TAST 长度案立案待新仪表判。评测已加三样仪表(生成长度/停因/快慢
路径、n<12 印 NA)。按序跑:

1. `git pull --rebase --autostash`
2. 定 600s 之谜(有输出=慢路径实锤,整行发回;无输出=当时是渲染抢 GPU,现已空):
   `findstr /C:"解码快路径不可用" D:\vscode_projects\ee_download\work\train_r2_trial.out.log`
3. 定 tokenizer 之谜(两个哈希发回;相同=你的长度表直接有效):
   `certutil -hashfile D:\vscode_projects\ee_download\work\rubato_spm.model SHA256`
   `certutil -hashfile D:\vscode_projects\ee_download\work\rubato_spm_v2.model SHA256`
4. **重启试验**(D61 方案原样;变量=池 v1→v3=753,304;GPU 现已无渲染):一轮例行
   启动命令原样(不加 --augment-acoustic),起点自动 last.pt(68k),**硬顶 起点+10,000
   到点停进程**(停法同追加 15)。启动后发回:恢复行 + config echo(应见 753,304)。
   跑动中 autolog 照常;评测行若出现 `parseable=NA(n=…)` 属正常保护,不是故障。

红线:训练期间不跑任何渲染/大 IO(试验要干净 GPU);到点必停,判决归规划端。

## 【已完成,验收见追加 23】追加 22(2026-07-25,D70):挂载令

追加 21 验收**通过**(+1,513 曲/+1,648 行,密度 1.089 与波次一致;败 598=0.47%;
全量核验 138,594 行全 flac 零缺失;手工转换的逐样本校验口径优于工具,追认)。

1. `ren D:\vscode_projects\ee_download\work\pdmx_perf_labels_r3_native.staging.jsonl pdmx_perf_labels_r3_native.jsonl`
2. `python scripts/build_dataset.py --dry-run`
把第 2 条打印的装配统计整块发回。

**预登记期望值(先于数据写死;对上=池 v3 冻结,对不上=停下贴回)**:
- TOTAL = **753,304**(614,710 + 138,594)
- PDMX rows 424,284 / kept 372,122;dup、no_audio 增量应 = 0
- TAST 198,505;AMT 374,084 不变
- train 704,549;**test 25,254 / val 8,932 / validation 13,330 / quarantine_leak 1,239
  四项必须一字不变**(train-only 铁证)
- filtered=3 不变

红线:dry-run 对上之前不训练;对上之后训练也另等口令(悬置的试验判决还没结案)。

## 【已完成,验收见追加 22】追加 21(2026-07-25,D69):r3 收尾五步

交接验收通过(125,633 曲已消费 / 544 终败 / ~2,200 待补;账自洽)。收尾工具已推,
按序跑,在 `D:\vscode_projects\ee_download\Rubato` 目录下:

1. `git pull --rebase --autostash`
2. `python scripts/r3_failures_release.py`
   (清洗失败清单,释放已补回的曲;**它最后会打印第 3 步的完整命令,文件名都替你填好**)
3. 复制第 2 步打印的那条命令运行(补消费;中断可重跑;结束打 DONE 行)
4. `python scripts/wav2flac_labels.py`
   (5 万遗留 wav 逐件转 flac→标签改写→全量核验;可中断重跑,盘上瞬时只多一件)
5. 发回三样:③的 DONE 行原文;④的"相3 核验"行;以及
   `find /c /v "" D:\vscode_projects\ee_download\work\pdmx_perf_labels_r3_native.staging.jsonl` 的数字。

我收到后发最后一步(改名进池 + 总对账 dry-run)的命令——那之前照旧:不训练、不改名。
(挂载线已备好:装配器认 `pdmx_perf_labels_r3_native.jsonl` 武装名,现在文件不存在=零变化。)

## 【已按交接文档执行,收尾见追加 21】追加 20(2026-07-24,D68):r3 全链命令

体检通过(38,252 行/7-12 未动)。以下按序执行;凡"<你的…>"处填你本地实际路径,
其余一字不改。

1. `git pull --rebase --autostash`(守卫补丁)
2. 生成 r3 清单(若已有 manifest_pieces_r3.jsonl 可跳过):
```bat
python scripts/s3_filter_pdmx.py --restore-candidates D:\vscode_projects\ee_download\work\pdmx_dedup_restore_candidates.jsonl --restore-only --train-only --out-manifest D:\vscode_projects\ee_download\work\manifest_pieces_r3.jsonl --out-report D:\vscode_projects\ee_download\Rubato\reports\s3_filter_r3_manifest.json
```
3. 归一化/两道预检/官方 CLI 渲染批:你自己的工具你自己调(D63 自治),照常续跑。
4. 官方批出多少消费多少(可反复跑,断点续):
```bat
python scripts/s5_vn_render.py --native-vn-root <你的官方产物根目录> --manifest D:\vscode_projects\ee_download\work\manifest_pieces_r3.jsonl
```
(守卫自动落 r3 staging 标签/pdmx_audio_r3/失败清单;**产出是 staging 名,改名=进池,
仍等我的挂载指令**——那是最后一道闸。)
5. 消费完贴回两行:DONE 行原文 + staging 行数
   (`find /c /v "" D:\vscode_projects\ee_download\work\pdmx_perf_labels_r3.staging.jsonl`)。

红线不变:不开训、不改名。试验两行仍欠(有余量再给)。

## 【已完成,验收通过;后续见追加 20】追加 19(2026-07-24,D67):流水线审计+体检命令

审计结论:你的三个提交**全部验收通过**(native 转向证据充分、预检门干净、FLAC 合规、
失败隔离清单是好仪表)。守卫补丁已推(pull 即得):restore 流禁写主 manifest;
s5 消费模式强制 r3 staging 命名 + 显式 `--manifest`。

只要一样(一条命令,输出两行,贴回即可):
```bat
powershell -Command "(Get-Item D:\vscode_projects\ee_download\work\manifest_pieces.jsonl).LastWriteTime; (Get-Content D:\vscode_projects\ee_download\work\manifest_pieces.jsonl | Measure-Object -Line).Lines"
```
(判读:行数≈38,371=主 manifest 完好;≈128,585=被 restore 覆写,需重生成——等口令。)

可继续:官方 CLI 渲染批(只产 MIDI/CSV,不碰池文件)。
等口令:s5 消费(--native-vn-root;新守卫会要求 `--manifest work/manifest_pieces_r3.jsonl`
与 r3 staging 输出,届时口令给全)。
仍欠(有余量再给):试验两行(首条训练行 + autolog 首评行)。

## 【已并入追加 19】追加 18(2026-07-23,D65):三样零解释

1. 新渲染流水线**代码 git push**(不写文档不解释,我自己读)。
2. 贴两行:试验运行**第一条训练行** + autolog **首评整行**。
3. 答一个字:渲染路径里 **finalize 预设链**(录音预设+能量归一)在吗?【在 / 不在】
   (不在也别改——若存的是 44.1k,后补跑 finalize 即可,等口令。)

背景周知:token 将尽,29 号才重置;过渡期规矩=**只执行复制粘贴级口令,不自行判断、
不改代码、追认制暂停**。渲染收尾照常(wav→flac 用户已准,容器无碍;磁盘你自己算)。

## 【已并入追加 18】追加 17(2026-07-23,D63):两行 + 一次 push

新规(用户令,永久):①本地运维(内存/性能/路径/存储/磁盘/并发)你全权,不问不报;
②磁盘闸按用户口径(130GB)已过;③规划端问话从此求短,你贴回也求短——只贴要的行,
不写叙述。

只要三样:
1. 试验那次运行的**第一条训练行**原文(一行,含 step=/loss/lr);
2. autolog **首评整行**原文(一行);
3. 新渲染流水线**代码 push 进 repo**(不用写说明文档,我自己读;审的只有
   标签-音频对齐/staging/train-only 三个正确性缝,运维参数不审)。

红线只剩两条:不开训;新流水线等我审完的口令再跑(其余全自治)。

## 【已被追加 17 取代】追加 16(2026-07-23,D62):证据令

先记账:VN-unknown 冒烟**验收通过**(带证据的主张,好);train-only 过滤**验收通过**
(128,585 曲,val/test=0,评测冻结落实)。

现状认定:试验首评 parseable=0 被用户停训。**统计上这不是"数据没用"的样子**——
一轮 68k 的 parseable 稳定 0.08-0.12,真续训(同权重同评测集)首评恰为 0 的概率 <2%。
两大主嫌:恢复未发生(全新权重首评=0 是正常现象)/ 评测链故障(异常→兜底)。
**判决悬置**,以下五项全是"贴回",一项都不许少,也不许附带任何新动作:

任务一 · 试验证据(判别件,决定两嫌哪个成立):
  ① 启动时控制台的**恢复横幅行原文**(有"resume/恢复 @ step N"字样的那行;若当时
    没存,把 outputs/ 下本次运行日志的头 30 行贴回);
  ② **config echo 整段**(mix=/aug_acoustic=/池总数);
  ③ autolog 的**首评整行**(要完整行:parseable/empty=/静动 sem/拒因直方图都在里面);
  ④ 本次运行**头 10 行 + 停前末 10 行训练行**(loss 量级 ≈60 级=全新权重,2-3 级=真续训,
    一眼定案)。
  全部写进 reports/R2_TRIAL_EVIDENCE.txt,push。

任务二 · 新渲染流水线:**整套代码 push 进 repo**(不许只在本地跑),并附一页
  reports/PIPELINE_RATIONALE.md:为什么不用既有 s4_parallel / s5_vn_render
  (它们自带内存准入/截断守卫/断点续跑/与现池同机纪律)——差距逐条写。
  **审计通过前该流水线禁止运行。**

任务三 · 磁盘盘点(追加 14 任务二,仍欠着):DISK_INVENTORY.txt。你自己的预检写着
  91.38GB < 需 120GB —— 在它交回并清出空间之前,**任何 restore 渲染都是禁跑的**;
  若现在有渲染进程在跑,立即停,并在贴回里写明已产出多少文件、占了多少 GB。

任务四 · 若新流水线已经产出过任何文件:目录名 + 文件数 + 总 GB 一并写进任务三的贴回。

任务五 · 红线重申:不开训(判决悬置中)、不渲染、不改 repo 代码;这五项交齐之前
  没有任何别的活。

## 【试验已停,判决悬置见追加 16】追加 15(2026-07-23,D61):二轮试验开训口令

裁决:O6 = 用户方案"68k 续训试验,硬顶 +10,000 步,不行转全新热启";O8 = 训中进池
(restore 线照旧等三闸,与本节无关)。试验预注册细则在 ROUND2_DATA.md O6 节,判据
已钉死,判决归规划端 —— 你只管跑、贴、到点停。

启动(现在就可以,与追加 14 两小任务并行):
```bat
git pull --rebase --autostash
:: 用你一轮【例行重启】的同一条启动命令,一个 flag 都不加不减 ——
:: 特别是【不加】--augment-acoustic(C1a 本试验必须保持关)。
:: 装配会自动挂上池 v2 全部来源(含 pdmx_perf_labels_s2),恢复自动从 outputs/ckpt/last.pt。
```
启动后立刻 push 一次,内容(reports/R2_TRIAL_START.txt):
① 恢复横幅行原文(含起点步数 —— 判决点 = 该数 + 10,000,你据此知道停点);
② config echo 整段(规划端要用它核验 mix=D2 / aug_acoustic=False / 池总数 614,710)。

跑动中:autolog 照常;在 起点+2,000 / +5,000 / +8,000 各 push 一次(autolog + 最近训练行)。

到点停(硬顶,分钟级误差无妨,宁早勿晚):
```bat
powershell -Command "Get-CimInstance Win32_Process | ? {$_.CommandLine -match 'build_dataset'} | % {Stop-Process -Id $_.ProcessId -Force}"
```
停后最后一次 push(autolog 全量 + 末 20 训练行,写 reports/R2_TRIAL_END.txt)。

红线:到点必停,**不自行判决、不自行续跑**;C1a 不开;restore 渲染无口令不启动;
本节与追加 14 的"不开训"冲突处,以本节为准(那两个小任务照做)。

## 【验收+小任务仍有效;"不开训"红线已被追加 15 取代】追加 14(2026-07-23,D60)

验收:s2 渲染合格(30,607 行,账三向闭合,评测池不变),**池 v2 = 614,710 钉板**;
去重审计是重大发现(98.56% 假去重),方法和证据链验收通过,lenient 接线追认
(规划端已补 3 项判决测试)。干得好。但两笔账必须记:

- **违规 #1(严重):擅自武装。** 追加 13 白纸黑字"staging 名,严禁改名,武装另有口令",
  你引用的"武装授权"是追加 8 里 **C3 那个文件** 的授权——跨文件挪用授权无效。这次
  实质零损害(没开训、可逆、评测池自证不变)所以池成分追认;**下不为例:武装授权
  永远逐文件点名,今后再越此线,当轮所有产物按无效处理重做。**
- **违规 #2:去重扫描器是追加 12 明文"勿自行造轮子"的活。** 你造了,造得好,追认;
  但"追认制"三条件里的"阻塞真实"你不满足(当时无阻塞,是排队抢活)。追认制不是
  抢活许可证 —— 空闲时想到高价值活,写进 PARALLEL_WORK_SUGGESTIONS 等批复,就像你
  上次做的那样。那次的规矩这次忘了。

新任务(都是分钟级,做完 push 即可,**别的一律不动**):

任务一 · VN "unknown" 冒烟(你 composer 映射的前提主张,先验证再谈 restore):
```bat
D:\ProgramData\envs\py312\Scripts\virtuoso.exe D:\vscode_projects\ee_download\work\xml_norm\<任选一个现有 xml> -c unknown --pedal --no-plot --csv -o D:\vscode_projects\ee_download\work\vn_unknown_smoke.mid
dir D:\vscode_projects\ee_download\work\vn_unknown_smoke.mid*
```
贴回(reports/VN_UNKNOWN_SMOKE.txt):命令原文(含你选的 xml)、退出码、dir 输出、
任何报错整段。**若 VN 拒绝 unknown,你的 composer 映射需要返工——先贴回,勿自行改。**

任务二 · 磁盘盘点(restore 渲染的 120GB 前置;只盘点,**一个字节都不删**):
```bat
powershell -Command "Get-PSDrive D | Select-Object Used,Free"
powershell -Command "Get-ChildItem D:\vscode_projects\ee_download -Directory | ForEach-Object { '{0,12:N0} MB  {1}' -f ((Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1MB), $_.FullName }"
```
贴回(reports/DISK_INVENTORY.txt):两条输出原文 + 你认为**可以安全腾挪**的目录清单
(只列名字和理由,等口令再动)。

红线:restore 渲染没有口令不得启动;不开训;不再改任何 repo 代码(现在没有阻塞)。
O6/O8 用户拍板后,开训口令随下一节下发。

## 【已完成,验收见追加 14】追加 13(2026-07-23,D59):追加 12 验收 + pdmxperf 二音色渲染

验收先记账,全部**通过**:
- **校准闸过了。** 34/34 对、自检 0.0、均值 63.40 → 预登记灰区 → 用户亲自比对 5 对 XML
  放行(CALIB_MANUAL_REVIEW)。你的零配对停止判断、根因定位(s7 漏写 xml_score 是
  规划端生成器的 bug)、回填器的门条件(唯一性+存在性+拒部分写+备份)全部正确。
- **四项红区自改全部追认**:s7 补字段、回填器、calib_score LEGATO 适配器(你说得对,
  规划端原来的调用形式是猜的;你的适配器已被规划端补进沙盒测试覆盖 tests_calib_full 5/5)、
  时长隔离 3 段(584,106−3=584,103 账闭合)。**池 v2 钉板 584,103。**
- 规矩更新(D59 追认制,今后照此办):主线被阻塞时,你可以"先改后报"repo 代码,
  但必须三条件齐:①阻塞真实(有停止条件触发的报告);②改动有报告文件自证
  (你这次的 CALIB_FULL_PAIRS_1 + NASAP_XML_SCORE_BACKFILL 就是范本);③可回滚(备份/git)。
  规划端逐项追认或回滚;**追认前不做下一步**。环境(非生产 venv)仍按 D57 三区制,不变。

新任务 · pdmxperf 二音色渲染(后台,断点续跑;GPU 给 VN 用,训练未启动正好空闲):
```bat
git pull --rebase --autostash
python scripts/s5_vn_render.py --second-timbre
```
说明,板上钉钉:
- 用一轮跑 s5 的同一环境(py312,virtuoso 在位),命令就这一条,其余全是默认:
  入选圈=一轮已出标签曲 × train(评测集冻结),标签写
  work/pdmx_perf_labels_s2.staging.jsonl(**staging 名,严禁改名,武装另有口令**),
  音频写 work/pdmx_audio_s2(与训练目录隔离,D51 教训),语料不写。
- 断点续跑 = 中断后原命令重跑即可(按 staging 标签文件判断已完成曲)。
- 预期量级:一轮 pdmxperf TAST 22,206 段(ROUND2_POOL_4 的 29,304−7,098),
  二音色 ≈ 略少于此(val/test 曲被排除)——**以脚本自己打印的"入选 N/总数"为准**,
  该行必须贴回。
- 显存/内存:内存准入已按第二源计权,S5_RESERVE_GB 等环境旋钮与一轮同。

贴回清单:①启动时"二音色输出:"与"二音色模式:基线已标注…入选 N/M"两行原文;
②每日一份 reports/S5_S2_RENDER.md(DONE 行原文 + 最近几条 [mem] 行);
③完成后 staging 文件行数(`find /c /v "" work\pdmx_perf_labels_s2.staging.jsonl`)。
红线重申:不改名、不开训、C3_RENDER.md 若仍有尾巴照常push。

## 【已完成,验收见追加 13】追加 12(2026-07-23,D58):全量 M2ST/LEGATO 校准比分

先记账:①冒烟通过(CALIB_SMOKE_7 三个 ✓)验收**通过**;②你的绿区环境自治首战
(ENV_LOG.md:bs4/lxml、venv 重建 py3.13→3.11 留 .bak、torch 钉 2.5.1 并写明理由)
**验收通过,这就是 D57 三区制想要的样子,保持**;③三条并行建议批复:第 1 条=本节口令;
第 2 条(151,439 去重审计)批准立项,**扫描工具由规划端在建,下一批下发,勿自行造轮子**;
第 3 条(音频-标签 QC)批准为**封池审计**,排在本节评分完成之后(见任务五),按你自己
写的资源边界:评分期间不并发大规模扫盘。

另:C1a 声学增广已合入主干(`--augment-acoustic`,默认关,开训口令才会带上)——
你现在**无需任何动作**,写在这里只为对齐信息。

四步流水线,每步一个脚本,报错整段贴回、不自行修复。所有脚本已 push,先:
```bat
git pull --rebase --autostash
```

任务一 · 枚举配对(任意环境,秒级;nemo_test 的 python 即可):
```bat
python scripts/calib_pairs.py
```
它会打印:test 单元数 / 配对成功 / 缺音频 / 缺参考谱 + 逐对清单,并写
work/calib_pairs.jsonl。**配对成功=0 或缺失占多数 → 停,整段贴回,后面不要跑。**

任务二 · Transkun 批量转写(transkun 所在现有环境,即冒烟用的那个;断点续跑,GPU):
```bat
python scripts/calib_transkun.py
```
中断重跑即可续(已存在非空 .mid 自动跳过)。transkun 不在 PATH 就加
`--transkun <它的完整路径>`。

任务三 · M2ST 批量转谱(venv_m2st,与冒烟同 venv;断点续跑,CPU):
```bat
venv_m2st\Scripts\python.exe D:\vscode_projects\ee_download\Rubato\scripts\calib_m2st_infer.py --m2st-dir D:\vscode_projects\ee_download\m2st --ckpt D:\vscode_projects\ee_download\m2st\MIDI2ScoreTF.ckpt --all-mids --in-dir D:\vscode_projects\ee_download\work\calib_full --out-dir D:\vscode_projects\ee_download\work\calib_full_xml
```
(在 m2st 目录下执行;`--all-mids` 是新参数,已存在的输出 xml 自动跳过。)

任务四 · LEGATO 官方脚本逐对打分(U10 验证 compute_OMR-NED.py 用的那个环境):
```bat
python scripts/calib_score.py
```
它先做**自检**(参考谱 vs 参考谱应 ≈0,与你 U10 的验证同款)——自检不过它会打印
两条命令,把那两条的完整输出整段贴回,**勿自行改造调用方式**。自动找不到脚本就加
`--legato-script <你 U10 用的 compute_OMR-NED.py 完整路径>`。
通过后它逐对打分并**由代码写** reports/CALIB_FULL.txt(含均值与预登记判决,判据出自
REF_SYSTEM_CALIB.md,不许手改该文件)。

任务五 · 封池审计(批复建议第 3 条;**任务四完成后**再跑,均为既有只读工具):
```bat
python scripts/audit_render_qc.py
python scripts/audit_split_leakage.py
python scripts/build_dataset.py --dry-run
```
第三条的装配统计整块写 reports/ROUND2_POOL_4.txt。

红线重申:本节全程**不启动任何训练**;环境预期零安装(四步全用现成环境),真缺包按
D57 三区制走,绿区先斩后奏必须当轮写 ENV_LOG.md。

贴回清单(全部要):①任务一 stdout 整段;②任务二末尾汇总行(新/跳过/失败+失败清单);
③任务三末尾"完成: N/N"行;④reports/CALIB_FULL.txt(代码已写好,commit+push 即可,
标题只写文件名)+ 任务四 stdout 末 6 行;⑤ROUND2_POOL_4.txt;⑥C3_RENDER.md 照常每日。

## 【现行任务清单已移至追加 12;本节仅任务五(C3 渲染续跑+每日 push)仍然有效】追加 8(2026-07-22,D53)

任务一 · 停训 + 归档一轮基线(权重是对照组,不许删):
```bat
powershell -Command "Get-CimInstance Win32_Process | ? {$_.CommandLine -match 'build_dataset'} | % {Stop-Process -Id $_.ProcessId -Force}"
mkdir D:\vscode_projects\ee_download\outputs\round1_baseline
copy D:\vscode_projects\ee_download\Rubato\outputs\ckpt\last.pt D:\vscode_projects\ee_download\outputs\round1_baseline\
copy D:\vscode_projects\ee_download\Rubato\outputs\ckpt\best.pt D:\vscode_projects\ee_download\outputs\round1_baseline\
```

任务二 · 武装 C3(M 档)副本(本口令即红线解除,仅此一次):
```bat
git pull --rebase --autostash
ren D:\vscode_projects\ee_download\work\pdmx_a2s_labels_s2.staging.jsonl pdmx_a2s_labels_s2.jsonl
```

任务三 · 生成第三组 AMT 偏移窗(分钟级):
```bat
python scripts/s6_amt_windows.py --offset 5
```

任务四 · 装配对账(不训练;这是二轮池的第一次点名):
```bat
python scripts/build_dataset.py --dry-run
```
把装配统计整块写进新文件 reports/ROUND2_POOL.txt 并 push。预期:pdmx kept ≈153,600、
maestro rows ≈373k(o10+o5)、nasap train 比上轮少 1,239(隔离生效)。

任务五 · C3 扩至全池(后台渲,~4-6 天,断点续跑,与一切并行):
```bat
set S4_RESERVE_GB=10
python scripts/c3_timbre_copies.py --n 34503
```
每日 push reports/C3_RENDER.md。**注意:它完成时会重写 staging 文件——完成后把新 staging
再次改名覆盖正式名(此项授权随本节生效,是任务二的延续),然后再跑一次任务四对账 push。**

任务六 · 红线:除上述任务外不启动任何训练;开训口令在本文件下一节。

任务七 · 【追加 9,D54】开源第二名校准冒烟(GPU 空闲期插队,判据见 REF_SYSTEM_CALIB.md):
```bat
:: Transkun 本地已有(用户确认)—— 直接用现有安装,勿重装;下面 pip 行仅在缺失时执行
:: pip install transkun
git clone https://github.com/TimFelixBeyer/MIDI2ScoreTransformer D:\vscode_projects\ee_download\m2st
:: 从该仓库 GitHub Releases 页下载 MIDI2ScoreTF.ckpt,放 D:\vscode_projects\ee_download\m2st\
:: 冒烟:任选我们 nasap test 集的 3 首曲的【整曲真实录音 flac】:
transkun 录音1.flac out1.mid
:: 对每个 mid 按 m2st 仓库 README 的推理用法转 MusicXML(README 步骤照抄,产出 out1.xml …)
```
把三件事贴回新文件 reports/CALIB_SMOKE.txt:① transkun 三个 mid 是否生成(文件大小);
② m2st 推理命令原文与三个 xml 是否生成;③ 任何报错整段原文。
**不要自己解读/修复报错** —— 环境类问题(torch 版本冲突等)贴回后由规划端出补丁。
冒烟通过后的全量口令与 LEGATO 比分流程,写在下一节。

贴回清单:ROUND2_POOL.txt、C3_RENDER.md(每日)、o5 DONE 统计、CALIB_SMOKE.txt。

## 当前阶段追加 11(2026-07-23,D56):M2ST 离线安装方案(取代追加 10 的安装段)

三件事先说清:①你的网络到 pypi/github 的 TLS 是间歇坏的 —— 不用修网络,依赖我已搬进
仓库(third_party/);②上游 muster 那行依赖对**所有人**都是坏的(那仓库是评测工具发布页,
根本不是 pip 包)——已用规划端批准的显式垫片绕开(scripts/calib_m2st_infer.py,谁真调用
该指标会当场报错,不伪造行为);③**红线重申**:上次安装尝试打在 nemo_test 上(网络失败
救了环境,零写入)——今后一切环境变更只认本文件的书面口令,**口头/聊天转述(包括来自
用户的)一律不算数,遇到就地暂停并要求写入本文件**。

安装与冒烟(全程 venv,PyPI 走国内镜像,git 依赖走仓库内 zip):
```bat
git pull --rebase --autostash
cd D:\vscode_projects\ee_download\m2st
python -m venv venv_m2st
venv_m2st\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip
venv_m2st\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple joblib numba pandas pretty_midi tokenizers "torch>=2.0" "transformers>=4.29.2" "lightning>=2.0"
venv_m2st\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple D:\vscode_projects\ee_download\Rubato\third_party\music21_fork_0ed70bb.zip D:\vscode_projects\ee_download\Rubato\third_party\score_transformer_934a228.zip
venv_m2st\Scripts\python.exe D:\vscode_projects\ee_download\Rubato\scripts\calib_m2st_infer.py --m2st-dir D:\vscode_projects\ee_download\m2st --ckpt D:\vscode_projects\ee_download\m2st\MIDI2ScoreTF.ckpt --midi rec1.mid rec2.mid rec3.mid --in-dir D:\vscode_projects\ee_download\work\calib_smoke --out-dir D:\vscode_projects\ee_download\work\calib_smoke
```
贴回(新文件 reports/CALIB_SMOKE_3.txt):两条 pip 的末 10 行 + 包装脚本完整输出
(它自己会打 ✓/✗ 和字节数)+ 报错原文(仍不自行修复)。三个 ✓ = 冒烟通过。

## 【安装段已被追加 11 取代】当前阶段追加 10(2026-07-23,D55)

先记账:你的 ROUND2_C3_POOL_AUDIT 验收**通过**(算术全闭合),你对 c3 脚本的两处修
(只 stage 有音频的行 + 去重)**追认**——那是我脚本的真 bug,修得对,备份链也干净。
二轮池 v1 钉板:**584,106 utts**(pdmx kept 202,924 / maestro 374,084 / 隔离 1,239 可见)。
两条重申:①commit 标题连续两次与文件相反("529827"无出处、"generated three MusicXML"
实为均未生成)——标题以后只写文件名,数字一律不写;②报告本体质量很好,保持。

**M2ST 修复(muster 是作者自有包,PyPI 同名包是无关物,勿 pip install muster!)**:
```bat
cd D:\vscode_projects\ee_download\m2st
python -m venv venv_m2st
venv_m2st\Scripts\python.exe -m pip install --upgrade pip
venv_m2st\Scripts\python.exe -m pip install -r requirements.txt
:: 【红线】全程用 venv_m2st,nemo_test 环境一个包都不许动
cd midi2scoretransformer
..\venv_m2st\Scripts\python.exe -c "from utils import quantize_path; from models.roformer import Roformer; import torch; m=Roformer.load_from_checkpoint(r'D:\vscode_projects\ee_download\m2st\MIDI2ScoreTF.ckpt'); m.to('cuda' if torch.cuda.is_available() else 'cpu').eval(); [quantize_path(rf'D:\vscode_projects\ee_download\work\calib_smoke\rec{i}.mid', m).write('musicxml', fp=rf'D:\vscode_projects\ee_download\work\calib_smoke\rec{i}.xml', makeNotation=False) for i in (1,2,3)]"
```
贴回(新文件 reports/CALIB_SMOKE_2.txt):pip 安装末 20 行 + `dir ..\..\work\calib_smoke\*.xml`
输出 + 任何报错整段原文(仍不自行修复)。三个 xml 生成 = 冒烟通过,全量比分流程随后下发。

## 【已完成,验收见追加 10】当前阶段追加 9(2026-07-22 深夜):ROUND2_POOL 返工

你贴的 ROUND2_POOL.txt 是转段前的旧统计(TOTAL=384862,无 s2/无 o5),而 commit 标题写
"529827/pdmx 149k/maestro 374k/quarantine 1239" —— 这些数字在文件里不存在。
**规矩重申:标题里的每个数字必须能在贴回文件里找到,否则不算数。** 返工步骤:

```bat
git pull --rebase --autostash
:: 1. 自证任务二/三确实完成(两行目录列表,贴回):
dir D:\vscode_projects\ee_download\work\pdmx_a2s_labels_s2.jsonl
dir D:\vscode_projects\ee_download\work\maestro_amt_windows_o5.jsonl
:: 2. 重跑对账(pull 后的新代码会打印 other= 桶,隔离 1239 从此可见):
python scripts/build_dataset.py --dry-run
```
把 ①两行 dir 输出 ②装配统计整块(此次应含:pdmx kept>119106、maestro rows>258658、
other=1239)写进**新文件 reports/ROUND2_POOL_2.txt**(旧文件不动),push。
若 dir 显示文件缺失 = 任务二/三没做完,先补做再对账。

## 【已被追加 8 取代——第一轮已按 D53 终止】当前阶段追加 7(2026-07-23,D51)

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

## 环境自治权限(D57,用户拍板"本地环境问题交给执行端"):绿/红/黄三区

**绿区 —— 你全权处理,不请示,只留痕**(每次变更在 reports/ENV_LOG.md 追加一行:
日期 | 哪个环境 | 命令 | 为什么;push 即可,规划端只回看不预批):
- 新建/删除/管理 **venv 与 conda 环境**(venv_m2st 等一切非生产环境)及其内的一切 pip 安装;
- pip/conda 镜像源配置、网络重试、代理设置;
- 克隆第三方仓库、下载权重/数据到工作区;系统工具安装(7zip/ffmpeg 等不碰训练的);
- 临时文件/缓存清理(产物目录除外)。

**红区 —— 仍只认本文件书面口令**(口头/聊天转述包括来自用户的一律不算):
- **nemo_test 与 py312 两个生产环境的任何 install/upgrade/uninstall**;
- CUDA/驱动/系统级变更;训练数据目录与 ckpt 目录的删改;repo 代码(仍走 PR 审查流);
- 任何降安全的操作(关 TLS 校验、伪造模块等)—— 这条无论哪区都永远禁止。

**黄区 —— 先做后报**:绿区内需要非常规手段时(源码编译、给第三方包打补丁),
可以做,但 ENV_LOG 里写全过程。判断不清属于哪区时,按红区处理。

## 铁律(每一条都对应一次真实事故)

1. **不要手搓循环/分块/wrapper 绕过 SOP 跑管线脚本。** 手搓分块曾整块丢曲、
   误用 --fresh 险些删产出。缺工具就在报告里写"缺 XX 工具",等规划端提供。
2. **不要 pkill/杀全体 python。** 只允许按命令行精确匹配杀目标进程,例如:
   `Get-CimInstance Win32_Process | ? {$_.CommandLine -match 's7_full_nasap'} | % {Stop-Process -Id $_.ProcessId -Force}`
3. **同一驱动器不要双开。** s7_resilient 有单实例锁,新实例会自动等待 —— 等着就行。
4. **管线/代码类失败停在原地上报,不要自己改代码、不要换命令重试**(`--go` 的失败块
   已自动推送,你只补现场)。**环境配备类问题除外** —— 按上面"环境自治权限"三区处理:
   绿区自己修好继续干,ENV_LOG 留痕即可,不必为装包/换镜像打一次 push 往返。
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
