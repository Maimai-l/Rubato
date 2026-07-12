# DECISIONS —— 重大决策记录(每条:决策 / 日期 / 理由 / 影响面)

> 规矩:任何偏离论文/SPEC 的选择、任何影响训练数据形态的参数,必须先记在这里再实现。
> 杜绝"你当时为什么这么写"—— 没记录的偏离视为 bug。

| # | 决策 | 日期 | 理由 | 影响 |
|---|------|------|------|------|
| D1 | 热启动(不 from-scratch) | 2026-07 | 没有 ~8.5 万 GPU 小时 | build_model 默认 warm-start |
| D2 | 四方言混比 A2S .35 / A2S_lite .15 / TAST .20 / AMT .30 | 2026-07 | 论文配比 | dialect_sampler |
| D3 | PDMX 全量渲染(S4 直排 + S5 VN 表现性) | 2026-07 | 数据量优先 | S4/S5 管线 |
| D4 | S5 表现性 = 仅 VirtuosoNet,humanize 兜底【删除】 | 2026-07-11 | 用户:不用假恒速演奏顶替;VN 失败即失败重试 | s5_vn_render;humanize.py 已删 |
| D5 | 段最短时长 2.0s(三处统一:S5 守卫 / S4 切割 / repair 扫描) | 2026-07-11 | 用户:<2s 即退化样本 | S5_SEG_MIN_SEC 默认 2.0 |
| D6 | 【PDMX 分段】小节数不设上下限,时间(≤40s)是唯一上限,段尽量长 | 2026-07-11 | 用户拍板,覆盖 SPEC R-S8.1 的 4–32;nASAP 仍按论文 4–32 重叠窗 | segment_score max_measures=None |
| D7 | MXL 编辑错误速度钳制:<20 或 >300bpm → 80bpm(改 MIDI+重渲,不改图) | 2026-07-11 | 用户:"四分音符=1"这类离谱值 | s4_fix_tempo |
| D8 | 非钢琴曲(鼓/吉他/人声…)内容级判定后整曲剔除 | 2026-07-11 | 用户实听抓到鼓谱;n_tracks 代理失效 | s3_instrument_audit + 黑名单 |
| D9 | tokenizer 语料 = 从标签文件确定性重建(不再管线追加) | 2026-07-11 | 可审计、清污染曲后语料自动跟随 | rebuild_corpus(P6c) |
| D10 | 清理只准走审计/cleanup 两个入口,清后必须贴验证表(全 0) | 2026-07-11 | 上次清了 done/音频但 _vn CSV 全漏、无法核实 | 清理章程(SOP) |
| D11 | S4 切割时间源 = 标签自带 score_range(IR 真实位置)直达 MIDI 速度图 | 2026-07-11 | 算术小节网格在弱起曲上静默错位(守卫恰好双过) | s5_pdmx_a2s_labels + s4_slice |

| D12 | tokenizer 语料【不】按 split 过滤,全量文本都进(原 O1) | 2026-07-11 | 用户:能多点数据多点;文本级词表不算泄漏 | rebuild_corpus 不过滤 |
| D13 | nASAP 分段保持论文 4–32 重叠窗(原 O2) | 2026-07-11 | 用户:尊重论文 | nasap 路径不动 |
| D14 | 单小节超窗段(华彩/延音/极慢演绎,实测 ~0.12%)丢弃不产出 | 2026-07-11 | 分段下限是 1 小节切不进小节内部;超训练窗产出即废 | S5_SEG_MAX_SEC 守卫(40+1s),S4 切割器原有同标准 |
| D15 | 混响【不重渲】现网音频(O3 关闭) | 2026-07-12 | 用户实听裁决:"修了听着差不多,还不如不修" | 现网音频保持原状;能量归一混音(wet_mode="energy")保留为今后一切渲染的默认;rerender_presets.py 备而不用 |
| D16 | TAST 绝对戳毒药:代码修 _shift_tmap 秒轴归零;存量标签【文本级修复】不重渲 | 2026-07-12 | 旧版秒轴保持绝对演奏时间:多段曲后续段整体偏移、超 40s 全钳末 bin(过单调校验,纯静默);首戳=段起点秒 → 全体减首戳即精确修复(±1 bin),钳制行信息已丢 → TAST 置 null 退出 TAST 池(A2S/音频保留) | segment._shift_tmap + scripts/repair_tast_labels.py(SOP P2e);nASAP 标签整套重跑自带修复 |
| D17 | nASAP split = conservative_split 后置分配(val≈512 段,work_key 隔离);训练 eval 每次抽 128 段确定性子集 | 2026-07-12 | ASAP metadata 无 split 列,不分配则 nASAP 全 train、eval hook 无 nASAP 可评;R-S7.4 的实现一直没人调用。全量 val×beam 解码每 3000 步一次要小时级,抽子集(hash 排序前 128)保训练吞吐 | scripts/s7_assign_split.py(SOP P5d);train.run_eval_hooks eval_max=128 |

## 待用户拍板(OPEN)
| # | 问题 | 背景 |
|---|------|------|
| (空) | — | O3 已由用户裁决关闭(见 D15) |
