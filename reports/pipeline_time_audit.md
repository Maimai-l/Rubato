# 全管线时间源审计 —— 120bpm 同类问题清查(2026-07-11)

触发:用户听音频抓出 S5 分段用假 120bpm。本审计按四种"同类气味"过了 scripts/ + rubato/ 全部代码:
① 有真时间源可用却用恒速假设;② 标签时间戳与音频时间源不一致;③ 配对约定产出方/消费方对不上;
④ tick→秒换算没读 set_tempo。

## 发现并已修(本次提交)

| # | 位置 | 问题 | 修复 |
|---|------|------|------|
| A | `s5_pdmx_a2s_labels.py` | 文本标签分段仍恒速 2s/whole,快曲切碎/慢曲超窗(分布偏置,与 S5 VN 同病) | 从该曲渲染 MIDI 提真 tmap(`midi_time`),结构守卫不匹配→回退恒速并计 `tempo_fallback` |
| B | `s4_retry.py`(N_WORKERS=24 裸池)、`s4_retry_worker.py`、`s4_batch_render.py` | 早期无预算渲染脚本留在仓里,误跑=重现 OOM 事故 | 截断为硬退出守卫(exit 2 + 指向 s4_parallel),原文在 git 历史 |
| C | `segment_amt`/`make_amt_label` **无任何调用方** | MAESTRO AMT 只有整曲文本(几分钟),训练窗 ≤40s → 占混比 0.30 的 AMT **配不成训练对**(与"S4 段音频没实现"同类缺口) | 新 `s6_amt_windows.py`(12–25s 智能切窗);行带 `win=[t0,t1]`;`assemble` 直通 win 且 dur_s=窗长;`load_audio` 帧级按窗读整曲 FLAC(不切文件不占双倍盘) |
| D | `segment_score_overlap` | tmap 与 sec_per_whole 都缺时 `_seg_seconds` 返回 0 → **max_sec 约束静默失效** | 加 `sec_per_whole` 直通;双缺时兜底 2.0(可见,不再静默) |
| E | `score_ir_to_events`(恒速 PDMX→AMT 桥,休眠无调用方) | 若将来接到 S4 真速度音频上=时间戳错位地雷 | docstring 加"时间源一致性铁律":S4 音频配 AMT 必须用 `midi_to_events(渲染所用 MIDI)`,禁用本函数 |
| F | `humanize_timemap` base=2.0 | 兜底路径(默认关)标签↔音频自洽但音乐上全是 ~120bpm | docstring 声明限制 + 启用前从 `midi_time` 取真实平均速度 |

## 查过、确认干净

| 位置 | 结论 |
|------|------|
| `rubato/data/maestro.py midi_to_events` | ✅ tick→秒标准写法:500000 只是 spec 默认初值,set_tempo 实时更新、增量用变更前 tempo |
| `scripts/gen_amt_labels.py` | ✅ 真演奏 MIDI→真秒→perf_to_amt;MAESTRO MIDI 与录音同步采集,天然对齐(但整曲行仅供统计,训练用 s6_amt_windows 产物) |
| `scripts/s7_full_nasap.py` | ✅ `segment_score_overlap(ir, tmap)` 传了真对齐 tmap,且正确处理 score_offset |
| `scripts/s6_convert_all.py` | ✅ FLAC 命名 base+".flac" 与 build_dataset maestro 分支一致 |
| `rubato/render/core.py events_to_midi` | ✅ tempo_bpm=120 只是 tick 标度,秒→tick 且写配套 set_tempo,时序无损 |
| `scripts/s5_parallel.py` / `verify_corpus.py` | ✅ 纯文本合并/校验,无时间语义 |

## 结论
同类问题共 6 处(3 处活跃、1 处静默失效、2 处休眠地雷),全部处理;干净处 6 处留档为证。
执行端影响:文本标签(S4 侧)需用新分段重生成(CPU-only);MAESTRO AMT 跑 `s6_amt_windows.py`;
其余按 HANDOFF 顺序。
