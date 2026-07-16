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
| D18 | 钳制 TAST 的曲【全量定点重渲找回】(推翻规划端"先训、掉队再补"的建议)【已被 D19 撤销】 | 2026-07-12 | 用户拍板:13,082 行被 D16 bug 毁掉的 TAST 必须重渲找回,不接受缩池训练。整曲清场(S5 续跑粒度是曲)+ 修好的 _shift_tmap 重打戳;重渲走当前默认能量归一混音,与存量 legacy 混音并存(用户实听"差不多",D15) | scripts/rerender_tast_clamped.py;P2e 复扫=验证门(应报 0 clamped) |
| D19 | 撤销 D18:【不】重渲,直接开训("本来也只要 A2S") | 2026-07-12 | 用户反悔于清场执行之前(P2c1 未跑,零损失):13,082 行的 A2S/A2S_lite/音频完好在池,仅 TAST 缺席;TAST 池余 ~21.8k(pdmx)+ nASAP,混比 0.20 靠过采样可支撑 | SOP 移除 P2c1;rerender_tast_clamped.py 保留,训后 TAST 指标掉队可随时定点补渲 |
| D20 | 平台期 H1 判决实验预登记:`--clip-norm 25` 续训 ≥500 步;判据(提前声明)ΔA2S(500 步) ≤-0.20 → H1 成立 / ≥-0.12 → 不成立 / 之间 → 续 500 步;不稳(nan 或 avg50 连续 100 步 >90)→ 回滚备份退 `--clip-norm 10` | 2026-07-14 | 前任对 H1 的"判决"建立在编造日志上,作废(HANDOFF §0);重判只认执行端贴回原文。继任规划端预登记先验:优化器为 AdamW,更新量对恒定梯度缩放近似不变 → 理论预期 H1 偏弱,正因如此必须实测关案;实验顺带产出 enc/dec 分组裁剪前范数(train.py 新日志列)= H2 的直接观测,一次跑两案的数据 | EXPERIMENT_H1.md(判据/止损/贴回清单);train.py group_grad_norms + 日志 enc=/dec= 列;build_dataset.py --max-batch-sec 死参数顺手修复(缺省行为不变) |
| D21 | **H1 判决:不成立**。实测 A2S 斜率 -0.113/500 步(基线 -0.086/500,判据线 -0.12/-0.20),放开裁剪没有加速训练;enc/dec 比值 0.79~1.32 同量级,H2a(encoder 缺信号)一并否定。处置:clip 保持 25(官方配方本就不裁),转 H3 观察路线——12000 步复盘,升级 H2(dec lr→3e-4)的条件已提前声明 | 2026-07-14 | 满窗贴回(8050-8500,命令原文确认 --clip-norm 25 生效)+ 按 D20 预登记判据执行,详见 EXPERIMENT_H1 §6-7 | 训练参数不变继续长跑;eval 逐次贴回;下次决策点 step 12000 |

| D22 | step 12000 复盘:训练减速 6 倍(A2S -0.017/500 步 vs 判决期 -0.11/500),AMT 4200 步零进展,触发 H1 §7 预声明的升级条件 → 开 H2 实验:`--lr-dec 3e-4`(decoder 5e-4→3e-4,encoder/clip 不动),判定窗 2000 步,判据写死在 EXPERIMENT_H2.md。配套代码:--lr-enc/--lr-dec CLI + apply_cfg_lrs(CLI 的 lr 必须穿透快照恢复,否则被旧快照静默还原——tests_resume [4] 专门回归这一点) + 日志 lrE/lrD 双列 | 2026-07-15 | 贴回日志 8500-12700(出处:用户粘贴);升级条件是 D21 时预先声明的,非临时起意;lr=3e-4 的选择依据 REF_EXTERNAL_RECIPES(三个参照项目一致值)+ 小 batch 高噪声 | EXPERIMENT_H2.md;train.py apply_cfg_lrs;build_dataset.py --lr-dec/--lr-enc |

| D23 | **H2 判决:无效**(锚点 13000 A2S=3.02 → 14900 仍 3.02;14500 的 2.95 是波动;parseable 0.04→0.02 噪声)。优化器侧三嫌疑(H1 裁剪/H2a encoder 信号/H2 decoder lr)全部实验排除。lr 留 3e-4;转探针路线:eval 内置教师强制探针(infer.teacher_forced_probe,判读阈值预声明:前缀acc≥0.6→解码侧病/≤0.3→模型未熟)+ 单行 eval 汇总防摘录丢证据。并立报告规矩:reports/ 只增不删(cd996eb 删 eval 段事故,已从 git 历史恢复) | 2026-07-15 | reports/H2_steps.txt 满窗数据 + 按 EXPERIMENT_H2 预声明判据;探针是 H2 卡预告的下一步,判读阈值在数据到来前写死 | EXPERIMENT_PROBE.md;rubato/model/infer.py 探针;train.py eval 接线;tests_probe.py |

| D24 | **重大事实修正:eval 的 `'|4/4k0'` 是兜底常量 `_EMPTY_A2S`,不是模型输出**(本轮 eval empty=1.0 坐实)。既往所有"模型只会输出开头"的解读作废;推理管线三处静默吞错(解码异常/validate 拒绝/顶层异常)全部装上现场记录,eval 出现兜底即打印模型真实原始输出与违规项/异常栈;探针 device bug 修复(lp 落 CPU 再比较)。执行端"model generates EOS immediately"说法无数据支撑,不采信。报告规矩升级:reports/ 只写新编号文件,不编辑旧文件(cd996eb/5c48581 两次删证据后) | 2026-07-15 | reports/PROBE_RESULT.txt(empty=1.0 + 探针 device 崩溃)+ infer.py:24 `_EMPTY_A2S="|4/4k0"` 代码事实;empty_rate 诊断量一直存在但从未被打印,盲区因此存活数轮 eval | infer.py 吞错现场三处 + 探针修复;train.py eval 打印现场;tests_probe [7][8];EXPERIMENT_PROBE.md 第二版 |

| D25 | 20k 复盘:探针 4 点持平(前缀 0.31-0.38,总 0.40-0.41)、解码现场=复读机(Dyck 断裂被拒,胶水无病)、amt_f1=0.0(全方言生成未熟)、A2S 训练损失 4200 步净零 → 病 A/B 判据均未命中,焦点升级为"decoder 是否在从音频读内容"。探针加【静音对照】+ sem/ts 分型命中率,判据预登记:两次 eval Δsem 均值 ≤0.02 → 病 C(没读音频,转查 encoder/cross-attention)/ ≥0.06 → 病 A(在读,继续训)。执行端"lrD 衰减致 A2S 反弹"说法不采纳(衰减仅 8%,反弹在窗噪声内) | 2026-07-16 | eval_autolog.md(代码自动落盘,4 次 eval)+ PROBE_RESULT_2-5;判据在数据到来前写死 | infer.py 探针分型+静音对照;train.py eval 双样本探针;tests_probe [10];EXPERIMENT_PROBE.md 20k 复盘节 |

| D26 | 22000 静音对照:Δsem=0.00(连 ts 都不随音频变)→ **病 C 升为头号假设但不判**:①三指标逐位相同需自证对照生效;②规划端探针缺长度护栏,第二样本超 1024 → CUDA assert 上下文中毒,本轮 eval 后续数字全作废;执行端"病C confirmed"不采纳。修复+升级:长度截断护栏(_truncate_enc)、探针行带 rms/enc帧/enc_std 自证、新增错配音频第三对照;判定矩阵预登记(enc帧=0→C-结构 / enc_std 分化+Δsem≈0+错配同 acc→C-忽略 / Δsem≥0.06→回病 A)。若 C 坐实,冒烟证书重新解读:32 样本过拟合纯文本记忆即可达标,从未证明音频通路 | 2026-07-16 | eval_autolog @ddf0f20(代码落盘);判定矩阵在数据前写死 | infer.py 护栏+enc 体征;train.py 三对照探针;tests_probe [11];EXPERIMENT_PROBE.md 22000 节 |

| D27 | **病 C-忽略判决成立**(probe-only 干净测量,判定矩阵三条件全中:rms 证输入不同、enc_std 证前端活着、静音 Δsem=0.00 + 错配音频命中率一字不差 + 换参照立变):encoder 正常,decoder 完全忽略音频,模型=纯文本 LM。冒烟证书正式重读:32 样本文本记忆即可达标,从未证明音频通路。**训练暂停**,转根因排查:第一步对齐审计(scripts/audit_alignment.py,判读预登记),处置矩阵见 EXPERIMENT_C_ROOTCAUSE.md | 2026-07-16 | eval_autolog @f84ad23;22k 步"平台期"的统一解释:loss 2.9=语料文本熵、复读机、音高全错、amt_f1=0 | EXPERIMENT_C_ROOTCAUSE 卡;scripts/audit_alignment.py + tests_alignment_audit.py(合成音频回归:对齐/平移/配错三态) |

| D28 | **D27 修正**:三源探针实测 nasap 对齐样本 Δsem=+0.16/+0.12(在读音频)、pdmx +0.03/+0.10、maestro AMT ≈0 —— "全局忽略"收窄为"**选择性读音频**"(对齐处读、错位处闸掉);D27 的判决样本恰是审计判 SHIFTED 的错位样本,单点探针以偏概全属规划端方法失误。对齐审计定位 nASAP 为错位重灾区(5/8 不相关)。升级联合仪器:同批样本 对齐等级×Δsem 二维联判(--probe-only --probe-n),判读矩阵预登记;遗留疑点=maestro/AMT 的 Δsem=0 是窗账还是分支特性。训练继续暂停 | 2026-07-16 | eval_autolog @b84b4b5 + alignment_audit @e7cc374;22k 步的资产评估随判决翻转:模型读谱能力存活,大概率不必重跑 | build_dataset --probe-only v3(联合仪器)+ --probe-n;EXPERIMENT_C_ROOTCAUSE 判读矩阵 |

| D29 | **复训决定:不重跑,从 ckpt 22000 续训(参数不变)**。联合仪器 24 条定局:数据按源分层——pdmx 读音频(Δsem 至 +0.17)、nasap 有真实信号(Δsem +0.07、Δts 强正;能量审计在柔和钢琴上系统性误报,"nASAP 对齐故障"降级)、**唯一真异常=maestro/AMT 音高 Δsem≈0**(7 窗完美对齐仍不读,55% 训练对的音高监督空转)。测量层根治:常规 eval 内置多源 Δsem 探针(固定池,逐 eval 可比)+ probe-only 曲目去重。下次复盘 step 30000,仪表预登记(maestro Δsem 仍 0 → 开 AMT 专项) | 2026-07-16 | eval_autolog @64b9cd8(联合 24 条);重启无益:同样数据会学出同样行为,病灶不在初始化 | train.py probe_utts 多源探针;build_dataset 探针池+去重;EXPERIMENT_C_ROOTCAUSE 终局节 |

## 待用户拍板(OPEN)
| # | 问题 | 背景 |
|---|------|------|
| (空) | — | O3 已由用户裁决关闭(见 D15) |
