# Round-3 1c 半剂量 A/B：S=51200 冻结判决

- 日期：2026-08-11（Asia/Shanghai）
- 分支：`claude/training-issues-diagnosis-9ygud6`
- 报告前基线提交：`96cb878`
- 结论：**拒绝 1c 半剂量，恢复原配方素跑。** B 臂仅未通过冻结的 loss 门；不得因差距很小而事后放宽阈值。

## 1. 冻结点与分叉

用户明确要求不再等待自然 stopper，立即开始实验。原主训练 PID `36080` 在日志推进到 51275 后被精确停止；其最后一个完整、可加载的源快照为：

- 路径：`D:\vscode_projects\ee_download\outputs\ckpt_r3_v2\last.pt`
- `step=51200`, `epoch=6`, `batch_cursor=1040`
- SHA-256：`57AFA5CAF2EA06059942525DDF74DF60AFEA966F72C2427E8552F5BF9FD2777A`

从该文件独立复制 A/B 两份 `last.pt`，复制后 SHA-256 均与源文件一致。两臂严格串行，未并发占用 GPU。停止时 51200 之后的 75 个未落盘步不进入任何一臂。

## 2. 冻结配方

共同参数：

```text
scripts/build_dataset.py --clip-norm 25 --lr-dec 3e-4 --eval-decode-every 5000 --augment-acoustic --pitch-loss-weight 2.5 --stop-after-step 51300
```

- A，PID `30796`：`--ckpt-dir D:\vscode_projects\ee_download\outputs\ckpt_ab_r3A`
- B，PID `39864`：在共同参数上增加 `--input-dropout 0.05 --input-dropout-ramp 5000 --audio-dep-monitor-every 50`，并使用 `--ckpt-dir D:\vscode_projects\ee_download\outputs\ckpt_ab_r3B`
- 两臂均确认打印 `续训:恢复 step=51200 epoch=6 batch_cursor=1040`，优化器和调度器状态一并恢复。
- 两臂均干净触发 `stop_after_step_reached`；终点 checkpoint 均可加载且 `step=51300`。
- 两臂均无 fatal、NaN、OOM 或步数越界。

## 3. 原始训练证据

实验只有 100 步，而训练每 50 步打印一次完整指标，因此每臂按设计只有两条完整训练行；这里保留全部两条，不虚构“五行”。

### A 臂

```text
step 51250 loss=40.7043 avg50=37.8716 sem=2.0526 ts=1.5890 pv=2.072 gn=9.2/avg7.4 enc=7.5 dec=5.4 lrE=5.43e-05 lrD=1.63e-04 audio=2029s micro=50 seq=70 td=1.1s/avg1.2 tc=8.1s/avg8.0 | A2S=2.10 A2S_lite=2.10 AMT=2.04 TAST=1.75
step 51300 loss=39.7540 avg50=37.8252 sem=1.9946 ts=1.6217 pv=2.074 gn=8.1/avg7.6 enc=6.6 dec=4.7 lrE=5.42e-05 lrD=1.63e-04 audio=2048s micro=49 seq=75 td=1.2s/avg1.1 tc=8.1s/avg7.8 | A2S=2.10 A2S_lite=2.06 AMT=2.02 TAST=1.76
train 收尾: stop_after_step_reached final_loss=37.8252 final_sem=2.0097 final_ts=1.5669
```

### B 臂

```text
step 51250 loss=46.3194 avg50=48.9849 sem=2.2920 ts=2.1642 pv=2.725 ad=+0.445 id=0.05 gn=12.3/avg32.8 enc=9.3 dec=8.0 lrE=5.43e-05 lrD=1.63e-04 audio=2029s micro=50 seq=70 td=1.1s/avg1.2 tc=7.9s/avg7.9 | A2S=2.36 A2S_lite=2.39 AMT=2.20 TAST=1.96
step 51300 loss=44.7792 avg50=42.4470 sem=2.2107 ts=2.0065 pv=2.338 ad=+0.532 id=0.05 gn=9.0/avg9.6 enc=7.1 dec=5.5 lrE=5.42e-05 lrD=1.63e-04 audio=2048s micro=49 seq=75 td=1.1s/avg1.1 tc=7.7s/avg7.8 | A2S=2.32 A2S_lite=2.28 AMT=2.16 TAST=1.95
train 收尾: stop_after_step_reached final_loss=42.447 final_sem=2.2098 final_ts=2.0113
```

## 4. 冻结门判决

| 门 | 冻结规则 | 观测 | 判决 |
|---|---|---:|---|
| 健康 | 两臂无 fatal/NaN/OOM/越界 | 两臂均干净完成 | PASS |
| input dropout | B 的 `id` 在 0.04–0.06 | `0.05` | PASS |
| 速度 | B 最后 50 步 `tc` 均值 ≤ A × 1.08 | A `7.8s`; 上限 `8.424s`; B `7.8s` | PASS |
| 损失 | B 最后 50 步 loss 均值 ≤ A × 1.12 | A `37.8252`; 上限 `42.3642`; B `42.4470` | **FAIL** |

B 的 loss 超出冻结上限 `0.0828`，约为门限的 `0.195%`。差距虽小，规则是“任一门不过即拒绝”，因此不启用 1c，且不事后修改阈值。

## 5. 主线恢复

按拒绝分支，从未被 A/B 修改的源目录 `D:\vscode_projects\ee_download\outputs\ckpt_r3_v2` 恢复原配方：

```text
D:\ProgramData\envs\nemo_test\python.exe -u scripts/build_dataset.py --clip-norm 25 --lr-dec 3e-4 --eval-decode-every 5000 --augment-acoustic --pitch-loss-weight 2.5 --ckpt-dir D:\vscode_projects\ee_download\outputs\ckpt_r3_v2
```

- 新 PID：`740`
- 日志：`D:\vscode_projects\ee_download\work\train_r3_v2_resume_after_1c_reject.out.log` / `.err.log`
- 已确认：`续训:恢复 step=51200 epoch=6 batch_cursor=1040`
- 已确认：`input_dropout=0(关)`，音频依赖损失关闭。
- 首条完整训练指标：

```text
step 51250 loss=40.7586 avg50=37.8960 sem=2.0486 ts=1.5927 pv=2.075 gn=9.1/avg7.5 enc=7.9 dec=4.6 lrE=5.43e-05 lrD=1.63e-04 audio=2029s micro=50 seq=70 td=0.9s/avg1.2 tc=7.7s/avg7.8 | A2S=2.10 A2S_lite=2.11 AMT=2.04 TAST=1.75
```

主线恢复健康，无 fatal、NaN 或 OOM。

