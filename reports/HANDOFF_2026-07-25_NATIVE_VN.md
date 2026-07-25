# Native Virtuoso R3 恢复交付（2026-07-25）

## 当前结论

本轮官方 Virtuoso 原生恢复流水线与 S5 音频/标签消费者均已结束：日志分别以 `NATIVE_BATCH_DONE` 和 `NATIVE_CONSUME_DONE` 结尾；当前没有 `virtuoso.exe`、`native_vn_full.ps1`、`native_vn_consume_loop.ps1` 或 `s5_vn_render.py` 进程。

**禁止训练。** 当前 staging 仍需失败重算、WAV 压缩和最终装配 dry-run。

## 最终快照

统计时间：2026-07-25。

| 项目 | 数量 | 口径 |
| --- | ---: | --- |
| MusicXML 输入 | 127,765 | `work/xml_norm_r3_train` |
| 官方批次记录中已生成 MIDI | 126,412 | 从每个叶目录的最大持久 `midi` 计数汇总；不要用目录中现存 MIDI 计数 |
| 已记录叶目录 | 993 / 1,000 | `work/native_vn_full.*.batches.jsonl` |
| S5 完成 piece 标记 | 125,659 | `work/pdmx_audio_r3_native/*.done` |
| staging 标签行 | 136,946 | `work/pdmx_perf_labels_r3_native.staging.jsonl` |
| 最终 FLAC 段 | 87,235 | 新消费者写入的无损最终段 |
| 遗留 WAV 段 | 49,711 | 切换 FLAC 以前生成；仍被标签引用 |
| D: 空闲空间 | 58.5 GB | 需先压缩 WAV 再做任何额外大规模输出 |
| failures JSONL 行 | 1,153 | **不是最终失败数** |
| 其中旧 `native_missing_*` | 942 | 先前 CUDA 批污染留下的状态，需与最终官方状态重算 |
| 其他解析/渲染失败 | 211 | 保留为审计候选，逐首复核后才定案 |

标签数与完成 piece 数不相同是正常的：一首 piece 可切出多个训练片段（`utt_id`）。

## 已完成的技术改动

1. 官方 Virtuoso CLI 目录模式用于 `MusicXML -> 演奏 MIDI + CSV`；Bach 作为所选 composer。
2. `scripts/s5_vn_render.py` 增加官方产物消费模式：`--native-vn-root` / `--native-ready-leaves`，不再在 S5 内加载自写 VN 推理桥。
3. S5 合成仍复用既有 `render_midi_to_wav44` 与 `finalize` 录音预设链；最终**片段**已从 WAV 改为无损 FLAC（提交 `467a9ed`）。
4. S5 采用 12 CPU workers 和内存加权准入；没有训练进程。
5. 官方批处理修复了 CUDA assert 污染范围：目录批完成后，缺 MIDI/CSV 的谱使用全新官方 CLI 逐首补跑。
6. 发现 `15/57` 在异常拍号 `44` 后卡死约 9 小时：119/128 初始成功，逐首补跑救回 8 首，1 首被 45 秒超时隔离。之后为运行时官方批处理加入：目录 5 分钟超时、逐首 45 秒超时。

运行时编排文件（`work/` 被 gitignore，不作为产品代码提交）：

- `work/native_vn_full.ps1`
- `work/native_vn_consume_loop.ps1`
- `work/native_vn_full.*.batches.jsonl`（**唯一可信的官方生成状态账本**）
- `work/leaf15_57_isolated.jsonl`（卡死叶目录的逐首审计）

## 重要口径与陷阱

- S5 会清理已经消费的官方 MIDI/CSV。因此 `work/vn_native_r3_train` 的现存文件数会下降，**绝不能**当作生成进度或失败率。
- 不要仅根据 `pdmx_vn_failures_r3_native.jsonl` 的 `native_missing_*` 数量判定失败；它包含旧批次中、后来可能已补出的 MIDI。
- `audio_path` 在标签行内。新行指向 `.flac`，旧行仍指向 `.wav`；在转换旧 WAV 前不可删除 WAV。
- `finalize` 在当前 S5 `render_midi()` 路径内，录音预设与能量归一没有被绕过。

## 下一步（按顺序）

1. **失败重算，不训练。** 以 `native_vn_full.*.batches.jsonl`、逐首隔离审计和标签/音频实际存在性重建最终 failure 清单；将已补回的旧 `native_missing_*` 从隔离集合释放，并只重消费这些已恢复 piece。
2. **压缩旧 WAV。** 逐文件 WAV -> FLAC；确认每个 FLAC 可读后，原子地将标签 `audio_path` 改为 `.flac`，最后删除同名 WAV。逐文件处理，避免同时保留两份而耗尽 D:。
3. **最终 staging 核验。** 检查标签行、音频可读性、FLAC/WAV 路径、split/去重与真实 failures；再执行仅 `build_dataset.py --dry-run` 的装配统计。
4. 只有 staging 被明确武装并且 dry-run 通过，才允许讨论训练；本交付不授权训练。

## 相关提交与分支

当前分支：`claude/training-issues-diagnosis-9ygud6`，已同步到远端。

- `1b1047d` Consume native Virtuoso outputs in S5
- `467a9ed` Store S5 segment audio as FLAC
- `5bcca83` Add PDMX normalization and VN preflight tools
- `ef9884c` 当前远端审计/执行指令基线

