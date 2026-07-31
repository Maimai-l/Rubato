# S5_S2_RENDER — pdmxperf 第二音色渲染完成记录

日期：2026-07-23

启动回显：

```text
二音色输出:labels=D:\vscode_projects\ee_download\work\pdmx_perf_labels_s2.staging.jsonl audio=D:\vscode_projects\ee_download\work\pdmx_audio_s2 corpus=(不写)
二音色模式:基线已标注 24829 曲;入选 22501/38252(仅一轮成功曲 × train)
```

运行方式：`py312` 环境执行 `scripts/s5_vn_render.py --second-timbre`。输出在完成后按武装
授权由 `.staging.jsonl` 改为 `work/pdmx_perf_labels_s2.jsonl`；音频始终位于隔离目录
`work/pdmx_audio_s2/`。

## DONE

```text
DONE: vn_ok=22499 vn_fail=2 skipped=0 dropped=0 utts=30607 TAST=30607 cpu_fail=0 过短段弃=348 超长段弃=140 无音频段弃=21 vn_子进程回收=0次
```

正式标签文件行数：**30,607**。

资源观察（运行中）：

```text
[mem] 已完成 11,700 曲 | 主进程(VN)RSS=0.1GB | 系统可用=18.6GB
[pipeline] 11,700 完成 ok=11700 fail=0 inflight=0 used≈-0.0GB mem=18.6GB
[mem] 已完成 13,025 曲 | 主进程(VN)RSS=0.1GB | 系统可用=18.8GB
```

结论：渲染完成，CPU 阶段零失败；2 首 VN 推理未成功，未进入可用输出。该副本仅含 train
曲，评测集未被写入。
