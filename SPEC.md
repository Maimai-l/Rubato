# Rubato A2S 主线复刻 —— 工程规格书(SPEC v3)

## 0. 文档约定与角色分工

**分工**:本文档 = 规划(要求与验收);执行者 = 按编号需求实现,自选实现手段;环境配置(OS、venv、二进制安装)= 用户职责,本文档只声明"需要存在什么"。

**给执行者的元指令**:实现顺序按阶段依赖(§2 依赖图);规格未覆盖处,优先级 = 论文原文 > 本规格 > 向用户询问,禁止静默自行发挥。每阶段完成必须产出 `reports/<stage>.report.json`(schema 见 §2.4)并通过全部 A-编号验收。

**标注体系**:
- 【不变量】必须严格如此,改动即算实现错误
- 【自由选择】接口/字形/库的选择自由,但一经选定须全局一致并写入 report
- 【论文明确】出处为论文原文
- 【推断】合理推断,允许被证据推翻(推翻时更新本规格并记录)
- 【用户验证】需用户在其环境确认的外部事实

**平台约定**【不变量】:目标环境 Windows(用户自配)。执行者产出的一切代码遵守三条铁律,
经 `rubato/platform.py` 统一封装,禁止绕过:
1. **文本 IO 强制 UTF-8**:一切读写走 `platform.read_text/write_text/read_jsonl/write_jsonl`。
   禁止裸 `open()` 或 `Path.read_text()`(Windows 默认 cp1252/GBK,乐谱符号/中文/双升号会崩)。
2. **外部程序经解析**:一切外部程序调用走 `platform.run(name, args)`,程序名从 `configs/project.yaml`
   的 `binaries` 段解析(裸名走 PATH,或填绝对路径)。禁止裸 `subprocess.run([程序名, ...])`。
   程序名平台相关(如 MuseScore:Win=`MuseScore4.exe`,Linux/Mac=`mscore`)——只在 config 出现,不硬编码。
3. **纯 Python + pathlib**:不写 bash/PowerShell 依赖;subprocess 永远列表参数、永不 `shell=True`;
   大文件流式(`zipfile`/管道)不落中间盘;路径保持浅(Windows 260 字符限制)。

---

## 1. 范围冻结(A2S 主线)

**主线目标**:音频 → 乐谱(InterMo → MusicXML)。推理产物不含时间戳。

**训练 dialect 保留 4 个**:

| dialect | 内容 | 保留理由(对 A2S 主线的贡献) |
|---|---|---|
| A2S | 乐谱+拼写,无时间戳 | 主线本体 |
| A2S_lite | 同上,MIDI 音高替代拼写 | 与 AMT 共享音高词表,桥接声学↔乐谱表示【论文明确 lite 与 MIDI 共词表】 |
| TAST | A2S + 时间戳 | ①时间戳给解码器细粒度对齐监督;②推理时的分窗信号(§S12);③标签几乎免费(A2S 已有,加戳即得) |
| AMT | 音符事件+时间戳+力度+踏板 | **MAESTRO 159h 真实录音进入训练的唯一通道**。砍掉=A2S 只见合成音频=真实录音鲁棒性崩(论文 ATEPP 分析中 Piano-A2S 的死法)。这是主线依赖,不是可选项 |

**砍掉**:DBD、DBD_plus(节拍任务,对 A2S 耦合弱,小节监督已含在 A2S 内)、TAST_lite、AMT_lite(冗余)。若追求极限精简,进一步可砍 TAST(保 A2S/A2S_lite/AMT),但将失去 §S12 的分窗机制,需另行设计终止准则——不推荐。

> **更新(能力已补齐,默认仍关)**:上述"砍掉"是**训练混比的缺省选择**,不再是"做不了"。
> TAST_lite / AMT_lite / DBD 的投影与 prompt 已实现(`core.project` / `perf_to_amt(lite=)` /
> `ir_to_dbd_units`;`build.DIALECT_PROMPT` 含 7 方言;`tests_dialects.py`)。PDMX→AMT 通路
> 也已打通(`core.score_ir_to_events` + `perf_to_amt`)。要对齐论文全 8 方言/PDMX-AMT,
> 只需把它们并入 `DIALECT_MIX` 与标签生成,无需改架构。DBD_lite 的 full/lite 精确切分待 Fig.2 确认。

**词表布局仍按论文全量保留**【不变量】:4000 时间戳 + 129 MIDI + 1 beat(占位不用)+ 40 prompt + 256 byte-fallback + 3 特殊符 + 3571 可学习语义 = 8000。理由:保持论文核账检查有效、embedding 行数便宜、未来加回 DBD 无痛。

**与论文的偏离清单(冻结)**:D1 热启动(encoder 载 canary 权重,非 from-scratch);D2 音源替换(5 具名免费源 × 16 程序化录音预设);D3 dialect 裁剪(上表);D4 评测缩水(无 ATEPP 全量);D5 编码器帧率接受 canary 默认(见 R-S10.3,不追论文的 40ms)。

> **更新(D1/D3 已降级为开关)**:D1 现为 `build_model(from_scratch=)` 开关——缺省热启动,
> `True` 则全权重随机化对齐论文(encoder hash 核对反向断言"已改变")。D3 见上方方言更新。
> 两者的"偏离"现在只是**缺省值**,不是能力缺口;真正剩下的取舍是**算力/规模**(从头训贵一个量级、
> PDMX-AMT 多一条渲染链),代码不拦。

---

## 2. 全局约定

### 2.1 路径变量(用户在 `configs/project.yaml` 定义,规格中以 `$NAME` 引用)
`$RAW`(原始数据)、`$WORK`(中间产物)、`$AUDIO`(渲染音频)、`$LABELS`、`$SHARDS`、`$CKPT`、`$REPORTS`、`$ASSETS`(音源/IR)、`$TP`(第三方仓库)。

### 2.2 随机性【不变量】
全局种子 20260706。一切逐条随机决策(音源分配、预设分配、作曲家、BPM、tiling 偏移)必须由 `sha256(seed | 决策名 | 实体id)` 派生,禁止全局 RNG 顺序依赖。同输入重跑必须得到 byte 级相同的分配结果。

### 2.3 清单文件 schema【不变量,字段可增不可删改】

`$WORK/manifest_pieces.jsonl` — 每行一个 PDMX 曲目:
```
{piece_id, xml_raw, xml_norm, composer_meta, license, n_measures, n_notes,
 has_tempo_mark, time_sigs: [..], excluded_measures: [..], parse_ok: bool,
 work_key,           # 归一化 (composer,title),用于查重与 split
 dup_cluster,        # 近重复簇 id(见 R-S3.6)
 vn: {status: pending|done|failed|skipped, midi_path, csv_path, composer_used, qpm_used, vel_scale}}
```

`$WORK/manifest_utts.jsonl` — 每行一条训练样本:
```
{utt_id, piece_id|maestro_id|asap_id, kind: flat|vn|human|maestro|nasap,
 measure_range: [a,b] | time_range: [s,e], audio_path, dur_s,
 source_id, preset_id,            # kind∈{flat,vn,human} 时有效
 dialects: [A2S, A2S_lite, TAST?, AMT?],   # 该条可供哪些 dialect
 split: train|val|test}
```

`$LABELS/labels.jsonl` — `{utt_id, A2S: str, A2S_lite: str, TAST: str|null, AMT: str|null}`(值为 tokenizer 前的序列化文本)。

### 2.4 阶段报告契约【不变量】
每阶段写 `$REPORTS/<stage>.report.json`:`{stage, inputs_hash, counts:{...}, failures:[{id, reason}], decisions:[{key, value, tag}], acceptance:{A-x.y: pass|fail|value}}`。失败样本**永不静默丢弃**,必须进 failures 并计数。

### 2.5 阶段依赖图
```
S1(资产) → S2(InterMo) → S3(PDMX池) → S4(直排渲染) ┐
                              └→ S5(表现性渲染) ──┤
S1 → S6(MAESTRO) ─────────────────────────────┼→ S8(分段与标签) → S9(tokenizer)
S1 → S7(nASAP) ───────────────────────────────┘        ↓
S1 → S10(模型构建) ←──────────────────────────────── S9
S10 + S8 → S11(训练) → S12(推理) → S13(评测)
```
S4/S5/S6/S7 相互独立可并行;S5 与 S11 竞争 GPU(资源约束 R-S5.8)。

---

## 3. S1 外部资产与用户配置清单(=「还需要你配置什么」的完整回答)

每项给出"就位判据",执行者在阶段开始时程序化检查并写入 report。

| # | 项 | 就位判据 | 缺失时 |
|---|---|---|---|
| U1 | MAESTRO v3:`maestro-v3.0.0.zip`(~103GB)与 `maestro-v3.0.0-midi.zip` 放 `$RAW/` | 两文件存在,zip 可开 | S6 阻塞 |
| U2 | PDMX(Zenodo 全量)解压至 `$RAW/pdmx/` | 元数据表 + MusicXML 目录存在 | S3 阻塞 |
| U3 | ASAP 仓库 + nASAP 音符对齐至 `$TP/asap-dataset/` | 仓库存在且含 metadata 与对齐文件 | S7 阻塞 |
| U4 | 音源:S1 Salamander SFZ【必须】,S2-S5【可缺,权重自动重归一】,放 `$ASSETS/soundfonts/` | S1 的 .sfz 主文件存在 | S4/S5 阻塞 |
| U5 | Windows 二进制在 PATH:`ffmpeg`、`fluidsynth`、`sfizz_render`(sfizz 官方有 Windows 构建)、MuseScore 4(`MuseScore4.exe`) | `--version` 各自返回 0 | 对应渲染/归一化路线降级或阻塞 |
| U6 | canary-180m-flash checkpoint(HF `nvidia/canary-180m-flash`)至 `$ASSETS/canary/` | .nemo 文件存在 | S10 阻塞 |
| U7 | 主训练环境:torch(cu128, Blackwell)+ lightning + sentencepiece + partitura + soundfile + mir_eval。**NeMo 可安装性【用户验证】**:原生 Windows 装 `nemo_toolkit[asr]` 试一次;失败 → 决策规则:S10 走"权重提取 + 自研模块"路线(R-S10.5),或整个训练侧迁 WSL2(用户二选一,告知执行者) | `import torch; torch.cuda.is_available()==True` | S10/S11 阻塞 |
| U8 | 你的 VirtuosoNet 封装:conda py312 环境可用,`virtuoso --list-composers` 正常 | 命令返回 16 个作曲家 | S5 阻塞 |
| U9 | **`save_csv` 列内容确认【用户验证,5 分钟】**:任选一谱跑 `InferenceModel(..., midi_decode_options={'save_csv':True})`,把 CSV 表头与前 3 行发给执行者 | CSV 每行↔一个乐谱音符,含演奏 onset(秒或可换算) | 决定 R-S5.6 走主路径还是降级路径 |
| U10 | LEGATO(`$TP/legato/`)+ 其 OMR-NED 脚本在你环境可运行【用户验证】:任意两份相同 MusicXML 跑 `compute_OMR-NED.py` 应得 ≈0 | 脚本退出 0 且输出数值 | S13 的 OMR-NED 改用执行者自研树编辑距离(标记为非官方口径) |
| U11 | 10 段自选真实钢琴录音(不同年代/录音质量)放 `$RAW/human_eval/` | ≥10 个音频文件 | S13 人检子集缺失 |
| U12 | (可选)真实 IR wav 放 `$ASSETS/irs/real/<preset_id>.wav` | — | 用程序化 IR(默认,已实现) |

---

## 4. S2 InterMo 核心库(全项目最高优先级实现)

**目的**:乐谱 ↔ InterMo 文本的无损双向转换 + dialect 投影 + 校验器。是所有标签的来源。

**输入**:MusicXML(经 S3 归一化)/ MIDI(MAESTRO)。**输出**:Python 库 `intermo`,API 见 R-S2.1。

### 需求

R-S2.1 【不变量】公开 API:
```
score_to_intermo(part, time_map=None) -> IntermoDoc     # time_map: 乐谱位置→秒,给 TAST 用
intermo_to_score(doc) -> partitura Part                  # 反向,渲染与往返测试用
midi_to_amt(midi, cc64=True) -> IntermoDoc               # MAESTRO 路线
project(doc, dialect: A2S|A2S_lite|TAST|AMT) -> str      # 投影为序列化文本
validate(doc) -> list[Violation]                         # 三类校验,见 R-S2.5
```

R-S2.2 【论文明确,不变量】表示语义:
- Moment:音高状态变化。onset 大写 / offset 小写;`#` 升 `-` 降,支持重升重降(`##`/`--`);示例 `A-3`=A♭3 onset,`c5`=C5 offset。
- Metric interval:相邻 moment 间记谱时值,分数形式(`1/8`)。**内部一律 `fractions.Fraction`,禁止浮点**【不变量】。
- Structural interval:小节线,零时值,携带拍号+调号(示例 `|3/4 k-4` = 3/4 拍 4 个降号)。每小节自包含。
- Canonical 顺序:①谱表低→高(PL: 先于 PR:);②同 moment 内 offset 先于 onset,各按音高升序;③谱表标记仅在切换时发出;④小节内 metric interval 之和 == 拍号 m/n(运行时断言)。
- Dyck-1:每 (staff, pitch) 的 onset/offset 严格配对;跨小节延音 = 音保持 open 越过小节线。

R-S2.3 【自由选择,选定后冻结】token 字形:拼写音高、MIDI 数字音高(A2S_lite 与 AMT **必须共用**同一套音高 token【论文明确】)、时间戳(4000 个,10ms 粒度,0-40s)、力度(127 个)、踏板(on/off 共 2 个,合计 129 MIDI 词【论文明确】)、prompt。所有字形写入 `intermo/vocab_spec.json` 作为唯一真源。

R-S2.4 【推断,冻结】边界策略表:
| 情形 | 策略 |
|---|---|
| 装饰音/颤音/倚音、>7 连音、单谱表 >2 声部 | **按小节剔除**(整曲保留,剔除小节记入 manifest.excluded_measures) |
| 反复/跳房子 | partitura 展开(unfold)后按展开时间线处理;无法无歧义展开的曲目整曲剔除 |
| 跨剔除边界的延音 | 在段边界截断该音(offset 补在边界),计数进 report |
| 无拍号小节 | 整曲剔除 |

R-S2.5 校验器三件套【不变量】:Dyck 平衡;逐小节 interval 求和==拍号;canonical 幂等(serialize→parse→serialize 不动点)。

R-S2.6 dialect 投影定义【论文明确】:TAST=全量;A2S=删全部时间戳 token;lite=拼写音高→MIDI 音高;AMT=仅 moments+时间戳+力度+踏板(无 interval/小节线/谱表标记),MAESTRO 的 offset 用 **KeyOff** 约定(键释放,非踏板延长)。

### 验收
A-S2.1 nASAP 全部乐谱往返:`score → InterMo → score`,与原谱 OMR-NED ≈ 0(排版无关差异豁免);转换失败率 <25%,失败清单入 report。
A-S2.2 论文 Fig.1 两小节金标测试:按论文图手工构造期望 token 序列,逐 token 相等,入库为单测。
A-S2.3 属性测试:随机生成 500 份合法 IntermoDoc,三校验器全过;注入 10 类破坏(删 offset、改 interval 等)全被抓。
A-S2.4 `project()` 四个 dialect 对同一 doc 的输出满足:A2S ⊂ TAST(删戳即等)、lite 与 AMT 音高 token 集合一致。

---

## 5. S3 PDMX 乐谱池

**目的**:从 PDMX 筛出可用钢琴谱,归一化,建曲目清单,完成查重与 split 隔离。

**输入**:`$RAW/pdmx/`。**输出**:`manifest_pieces.jsonl`、`$WORK/xml_norm/`。

### 需求
R-S3.1 过滤条件【推断,冻结】:单 part 双谱表(G+F 谱号);乐器名 ∈ {piano, pianoforte, klavier, 钢琴, fortepiano};有拍号;小节 ≥8;音符密度 ∈ [0.5, 15] 音/秒(按谱面速度或 92BPM 估);partitura 可解析。PDMX 元数据 schema 以实际文件为准【执行者适配】,首行字段名写入 report。
R-S3.2 许可白名单:PDMX license 字段 ∈ {public domain, CC0, CC-BY 系}。训练可放宽,再分发不可(PDMX README 自曝过版权元数据不一致)。
R-S3.3 归一化:每份 XML 过 MuseScore 4 CLI(`platform.run("musescore", ["-o", out, in_])`,
程序名由 `binaries.musescore` 解析——Win=`MuseScore4.exe`,不硬编码;超时 60s/份);
MuseScore 不可用(U5 缺)→ 降级 music21 读写往返归一,并在 report 标注降级。
R-S3.4 目标池规模【自由选择,预算依据】:12,000–20,000 曲(预计产 6–9 万段)。超出则按 work_key 去重后随机截取。
R-S3.5 work_key:`normalize(composer)+"|"+normalize(title)`(去大小写/标点/编号词)。
R-S3.6 近重复检测【新增,防泄漏】:每曲取展开后 (pitch, dur) 序列的 8-gram 集合,MinHash 聚类,Jaccard>0.7 判同簇写 dup_cluster。**约束:val/test 的任何 work_key 或 dup_cluster 不得出现在 train**;nASAP 测试曲目与 ASAP-Beyer 曲目的 work_key 全量列入 train 黑名单(跨数据集泄漏防线)。

### 验收
A-S3.1 report 含:过滤各条件的淘汰计数漏斗、最终曲数、段数预估、license 分布、dup 簇统计。
A-S3.2 抽 50 份归一化 XML 全部被 partitura 与 intermo 解析成功。
A-S3.3 黑名单核验:train 集与 {nASAP test, ASAP-Beyer} 的 work_key 交集为空。

---

## 6. S4 直排渲染(非表现性)

**目的**:每曲一版"照谱直弹"音频,提供无演奏偏差的基准训练对。

**输入**:`manifest_pieces`(parse_ok 且未整曲剔除)。**输出**:`$AUDIO/flat/{piece_id}.opus` + manifest_utts(kind=flat,先整曲后 S8 切段)。

### 需求
R-S4.1 straight MIDI 生成【推断,冻结】:partitura 展开时间线 → MIDI。速度=谱面标记;无标记则 BPM = logU[63,132] 按 §2.2 派生(每曲一值,写入 manifest)。力度=动态标记映射 {ppp:28, pp:40, p:52, mp:60, mf:68, f:80, ff:92, fff:104},无标记恒 64。踏板=谱面记号直译 CC64(on=127/off=0),无记号则无踏板。
R-S4.2 音源/预设分配【不变量】:`(source_id, preset_id) = hash(seed, piece_id)` 按 configs 权重(实现已存在:rubato/render/core.assign_source_and_preset;缺失音源时权重重归一并入 report)。
R-S4.3 渲染链【不变量】:引擎(sfizz_render / fluidsynth)@44.1kHz → 重采样 16k mono → 录音预设链(卷积混响/EQ/带限/噪底/增益,实现已存在:rubato/render/irgen.apply_preset)→ Opus(预设带 codec 用其低码率,否则 64k)。sfizz_render 的确切 flag【用户验证 U5 附带】以 `--help` 为准,首次核实后写死进代码常量。
R-S4.4 QC 门【不变量】:每条输出过 ffmpeg volumedetect,max_volume > -60dB;时长与 MIDI 末音 offset 差 <1.5s;不过者进 failures 重渲一次,再败标废。
R-S4.5 tiling 与在线增强的次序【不变量】:凡 apply_online=true 的项(预设链)必须与 S11 的 tiling 补齐(TAST/AMT 的 0-40s 平移补零)按「先 tile-pad、后预设链」顺序作用,使噪底覆盖补零区,避免"补零段绝对安静"这一泄漏切分点的伪线索。

### 验收
A-S4.1 首批 100 条全过 QC 后才允许放开全量;report 含渲染吞吐(条/分,供 S5 排程与 S11 预算)。
A-S4.2 抽 10 条人耳抽检:踏板可闻、动态标记段落有响度差(pp vs ff 段 RMS 差 ≥8dB)。

---

## 7. S5 表现性渲染(VirtuosoNet,按用户封装重写)

**目的**:同曲第二版"有人味儿"音频 + 可选的逐音符演奏时间(供 TAST)。

**输入**:S3 归一化 XML。**输出**:`$AUDIO/vn/{piece_id}.opus`、`{piece_id}.mid`、`{piece_id}.csv`(若启用)、humanize 兜底产物 `$AUDIO/human/`。

### 需求
R-S5.1 【不变量】批量驱动必须走 Python API 而非 CLI:`InferenceModel` **构造一次、循环 infer_xml**。理由:CLI 每次调用重载 172MB checkpoint,批量下是纯浪费。conda py312 环境经 subprocess 调一个批量驱动脚本、或执行者在该环境内直接跑,均可【自由选择】。
R-S5.2 【不变量】midi_decode_options 冻结为 `{bool_pedal: True, no_plot: True, save_csv: True}`(save_csv 待 U9 确认后可关)。
R-S5.3 作曲家策略【不变量,实现已存在 rubato/data/composer_alias.py】:三级(元数据命中 / shuffle_p=0.15 洗牌 / 加权 fallback 偏浪漫派),high_data 集合 = 用户指南标"多"的 8 位(与源码核实一致)。所选 composer 写入 manifest.vn.composer_used。
R-S5.4 速度:谱面有标记 → `qpm_primo=None`(封装文档:None=用谱面);无标记 → 传 S4 同一 BPM 值(两版渲染速度一致,便于对照)。
R-S5.5 力度增广【新增,来自你的封装能力】:`velocity_multiplier` 每曲从 {0.85, 1.0, 1.25} 按 {0.25, 0.5, 0.25} 派生采样——白拿的动态范围多样性。
R-S5.6 TAST 时间戳来源(依 U9 结果二选一):
- 主路径:save_csv 每行↔乐谱音符且含演奏 onset → 直接构成 time_map 喂 `score_to_intermo(part, time_map)`,VN 产物全 dialect 可用。
- 降级路径:CSV 不含映射 → VN 产物仅供 A2S/A2S_lite;TAST 时间戳由 humanize 路线(时间自生成,天然有真值)与 nASAP 承担。**主线不因此受损**。
R-S5.7 【已废除,2026-07-11 用户拍板:只要 VirtuosoNet,不要恒速假演奏。humanize 模块已删除;VN 失败=该曲失败,按标签续跑重试。原文留档:】humanize 兜底【推断,冻结参数】:对 straight MIDI 施加 ①逐拍速度因子 OU 过程 φ_{k+1}=φ_k+0.2(1−φ_k)Δt+0.05√Δt·ε,截断 [0.90,1.10];②onset 抖动 N(0,12ms) 截 ±35ms,off 同步平移保时值;③力度 +U[−10,10] 截 [20,120];④踏板照谱。覆盖对象:VN failed/timeout 的曲 + 按预算未进 VN 队列的曲。
R-S5.8 资源约束【不变量】:VN 批量与 S11 训练不得同时占 GPU。依 U8 环境实测单曲耗时(你的指南:5070Ti ≈3–5s/曲)确定 VN 队列曲数上限 = 训练开始前可完成的量;溢出部分自动划给 humanize。队列进度记 ledger(jsonl),中断可续。
R-S5.9 VN 失败判据:进程非零退出 / 超时 timeout=300s / 输出 .mid 缺失或 0 音符。失败入 failures,【2026-07-11 起不转 humanize(已废除)】,由按标签续跑机制重试。

### 验收
A-S5.1 首批 20 曲:输出 .mid 音符数 ∈ [0.8, 1.2]×谱面音符数(展开后);抽 3 曲人耳对比 flat 版,可闻 rubato。
A-S5.2 (主路径时)CSV 行数==乐谱音符数,onset 列单调不降比例 >99%。
A-S5.3 report:VN 成功率 p、humanize 覆盖占比、composer_used 分布(应与策略权重吻合)。

---

## 8. S6 MAESTRO(AMT 数据)

**目的**:159h 真实录音 → AMT 训练对。这是真实域声学监督的全部来源。

**输入**:U1 两个 zip。**输出**:`$AUDIO/maestro/*.flac`(16k mono)+ AMT 标签。

### 需求
R-S6.1 流式转换【不变量,Windows 原生】:python `zipfile.ZipFile.open(member)` 逐成员流式读 wav → soundfile/soxr 转 16k mono FLAC 落盘。**禁止整包解压**;峰值磁盘 = zip(103GB)+ FLAC(~10GB)。midi zip 先处理(小,标签管线不等音频)。
R-S6.2 标签:MIDI → `midi_to_amt`,KeyOff 约定【论文明确】,CC64 以 64 为阈值二值化,力度原值。
R-S6.3 切窗【推断,冻结】:目标窗长 U[12,25]s;切点在候选点 ±1.0s 内找"无发声音符且踏板抬起"时刻;找不到则硬切并丢跨界音符(onset 在窗前者连同其 offset 一并不标),丢弃率入 report(预期 <3%)。
R-S6.4 split【不变量】:沿用 MAESTRO 官方 train/val/test 划分字段。

### 验收
A-S6.1 时长核算:FLAC 总时长 ∈ [155,163]h;test 段数与官方一致。
A-S6.2 抽 20 窗:AMT 标签经 validate() 的 Dyck 检查全过(窗内 onset/offset 配对完整)。

---

## 9. S7 nASAP(真实音频的乐谱监督)

**输入**:U3。**输出**:nasap 段 + A2S/A2S_lite/TAST 标签 + 保守 split。

### 需求
R-S7.1 音频映射:ASAP 演奏音频来自 MAESTRO 子集,按 ASAP metadata 映射到 S6 已转 FLAC,**不重复转换**。无对应音频的演奏跳过(计数)。
R-S7.2 标签:乐谱 → InterMo;nASAP 音符级对齐 → time_map → TAST。对齐置信度低的音符(nASAP 有标记时)其时间戳略去(该音仍在 A2S 中)。
R-S7.3 切窗:小节对齐 4–32 小节 ≤40s,**重叠步长=段长一半**【论文明确 nASAP 用重叠窗】。
R-S7.4 保守 split【不变量】:按 work_key 划分;val=固定 512 段所属的曲目集合,test=其余保留曲;train 曲目与 val/test 曲目零交集,且与 S3 黑名单联动(A-S3.3)。split 曲目清单落盘 `$WORK/nasap_split.json`(可复现、可发给作者比对)。

### 验收
A-S7.1 val/test 段全部往返 OMR-NED≈0(它们是 A-S2.1 的子集,但在切窗后复跑)。
A-S7.2 report:曲目数、段数、重叠系数、与 MAESTRO test 的录音交集(应记录以便解读指标)。

---

## 10. S8 分段与标签生成(汇聚点)

**目的**:四路数据 → 统一的 (音频段, 多 dialect 标签) 样本集与分片。

**输入**:S4/S5/S6/S7 产物。**输出**:`manifest_utts.jsonl`、`labels.jsonl`、`$SHARDS/`(训练分片)。

### 需求
R-S8.1 乐谱类切段【不变量;2026-07-11 用户修订:PDMX 训练数据小节数不设上下限,时间(≤40s)是唯一上限,段尽量长(min_measures=1, max_measures=None),质量下限由 ≥2s 时长守卫把守;nASAP 仍按 R-S7.3 论文明确的 4–32 重叠窗】原文:小节对齐,贪心聚合连续小节,约束 4≤小节数≤32 且渲染时长 ≤40s;段起点必在小节线;piece 末不足 4 小节的尾巴向前并入(仍 ≤40s)否则弃。**禁止任意时间点切乐谱类样本**(会破坏 Dyck 与小节自包含)。
R-S8.2 每段渲染时长来源:flat/humanize 由生成的 MIDI 时间;vn 由输出 MIDI;时长与音频实测差 >1.5s 判废。
R-S8.3 dialects 可用性规则:flat/humanize → {A2S, A2S_lite, TAST, (无 AMT:合成域不做 AMT【推断:力度/踏板系人造,监督价值低,省序列长度】)};vn → 依 R-S5.6;maestro → {AMT};nasap → {A2S, A2S_lite, TAST}。
R-S8.4 标签文本生成:调 `project()`;每条样本每个可用 dialect 一份文本;任何 validate() 违规 = 该样本整条废弃入 failures。
R-S8.5 分片【自由选择】:webdataset tar 或 lhotse cuts;每片 ≤2GB;shuffle 以 work_key 为粒度打散(防同曲聚簇)。
R-S8.6 tiling 的落点【不变量】:不在本阶段固化。TAST/AMT 的 0–40s 平移偏移由训练 dataloader 每 epoch 在线采样(§S11),标签中时间戳以"段内相对时间"存储,加载时统一 +t0。

### 验收
A-S8.1 全集标签可解析率(validate 三件套)>99%;各 kind × dialect 的样本数矩阵入 report,与 §1 保留表一致(不得出现 DBD 等已裁项)。
A-S8.2 抽 30 段:audio 时长与标签末事件时间差中位数 <0.3s。
A-S8.3 split 泄漏终检:train 与 val/test 在 {work_key, dup_cluster, maestro 曲目} 三个维度交集均为空。

---

## 11. S9 Tokenizer

**输入**:labels.jsonl 的 A2S + A2S_lite 文本【论文明确:tokenizer 语料仅此二者】。**输出**:spm model + `vocab_spec.json` 联动校验。

### 需求
R-S9.1 【不变量】SentencePiece UnigramLM,vocab_size=8000;`normalization_rule_name=identity`(默认 NFKC 会改写 `|`/`#`/`:` 等符号,是已知致命陷阱);`byte_fallback=true`;`character_coverage=1.0`;`split_by_whitespace=true`。
R-S9.2 【不变量】序列化文本约定:语义单元(interval+moment 组)之间恰一个空格,单元内无空格 → 空格即 Interval-Piece 预切分边界(合并不得跨越)。
R-S9.3 user_defined_symbols = 4000 时间戳 + 129 MIDI + 1 beat(占位)+ 40 prompt = 4170,从 vocab_spec.json 生成,禁止手写第二份清单。
R-S9.4 训练期子词正则【论文明确】:α=0.25 采样式切分;实现为每 epoch 对标签缓存离线重采样(CPU 任务,与 GPU 训练并行)。

### 验收
A-S9.1 词表核账:可学习语义 piece = 8000−4170−256−3 = **3571**,与论文 ~3570 闭合;不合=切分或符号清单有 bug,阻塞。
A-S9.2 高频 piece 抽检:出现和弦块/节拍片段类合并(对照论文列举的模式);时间戳插入不改变语义单元边界(单测:同一 A2S 文本加/不加戳,去戳后 piece 序列一致)。

---

## 12. S10 模型构建

**目的**:得到"encoder 载 canary 权重、decoder 主体载入、embedding/softmax/prompt 全新、词表 8000"的可训练模型,参数量 ≈180M。

### 需求
R-S10.1 【不变量】架构:FastConformer encoder 17 层 d512 + Transformer decoder 4 层 hidden=1024(encoder→decoder 间有 `Linear(512→1024)` 投影;此维度经本地 canary-180m-flash 实测核实,以 .nemo 内 cfg 为唯一真源,不得手抄)。
R-S10.2 【不变量】热启动契约:encoder 全部权重从 checkpoint 载入并**逐层 hash 核对**(防静默随机初始化);decoder 自注意/FFN 形状匹配层载入;embedding、输出投影、prompt 相关全新初始化(词表全换,复用无意义——与 NVIDIA 时间戳论文同做法)。
R-S10.3 【不变量】前端一致性:mel 前端(n_mels/窗长/hop/归一化)必须与 canary checkpoint 的 preprocessor 配置逐项一致——热启动的 encoder 只认它训练时的前端。验收:对 3 段 wav,自建前端 vs checkpoint 配置重建前端,特征 max|diff|<1e-4。帧率接受该配置默认值(偏离声明 D5,不追论文 40ms)。
R-S10.4 目标序列结构【自由选择,冻结】:`[sot][结构 flag][拼写 flag][时间戳 flag][MIDI flag][标签 tokens...][eot]`;loss 仅计标签与 eot 位置(prompt 位置 mask)。
R-S10.5 实现路线【自由选择,给定决策规则】:U7 若 NeMo 原生 Windows 可装 → 允许 NeMo 模块直用;不可装 → 从 .nemo(tar)提取 state_dict + cfg,以最小依赖重建模块并进入自研 Lightning 循环。**禁止**为绕环境问题而改变 R-S10.1/10.2/10.3 的任何不变量。

### 验收
A-S10.1 参数量验收【修正:相对基准,非固定绝对数】。原始 canary 实测 182.64M @ 5248 vocab。
换 8000 词表后,embedding+softmax 按 (8000−5248)×(emb_dim) 增长,是**预期正确行为**不是 bug。
验收改为两条:①非词表部分(encoder + decoder 主体,即 total − embedding − softmax)与原始模型
一致(±0.5%);②词表增长量 = (8000−5248)×emb_dim × (1 或 2,取决于 emb/softmax 是否共享),
与实测吻合。**不再用固定 [176.4M,183.6M] 红线**——那是基于错误的 d512 估算,会误伤正确模型。
A-S10.2 encoder 权重 hash 全匹配;100 条真实样本过拟合到 loss<0.05 且生成序列 100% 过 validate()。
A-S10.3 实测训练吞吐(audio-sec/s)写入 report → 据此填 train.yaml 的 max_steps(总样本额=吞吐×可用 GPU 时,由用户给出预算数,规格不含时间计划)。

---

## 13. S11 训练

### 需求
R-S11.1 损失【不变量,公式冻结】:
- 序列级:L_seq = (Σ_t CE_t) · |T|^(−1/2),batch 内对序列取平均【论文明确 1/√|T|】。
- 语义 token:label smoothing 0.1。
- 时间戳 token:序数平滑,目标 bin q(y)=0.9,0<|i−y|≤5 时 q(i)=(1−0.9)·(6−|i−y|)²/Z_y,Z_y 为窗内(边界截断后)权重和并重归一【论文明确 P=0.9, w=5, 二次衰减】。
R-S11.2 dialect 混比【推断,冻结】:A2S .35 / A2S_lite .15 / TAST .20 / AMT .30(DBD 份额并入主线)。采样按混比,不按数据集自然占比。
R-S11.3 tiling【论文明确】:TAST/AMT 每 epoch 每样本 t0~U[0, 40s−dur],时间戳整体 +t0,音频按 R-S4.5 次序补齐。A2S/A2S_lite 不受影响。
R-S11.4 优化【推断,冻结初值,允许按 pilot 调并记录】:AdamW β(0.9,0.98) wd 0.01;lr_decoder 5e-4 / lr_encoder 1e-4(热启动降载);warmup 1500 步;cosine 至峰值 10%;bf16;动态 bucketing,每 batch 音频总时长 ≤560s,梯度累积至有效 ≈2000 audio-sec/步。
R-S11.5 监控与评测钩子【不变量】:每个 eval 周期(按步数,非时间:例如每 3000 步)在 nASAP val 512 段跑:生成可解析率、OMR-NED(U10 可用时官方脚本,CPU 并行)、A2S note F1;在 MAESTRO val 256 段跑 AMT note F1。全部入 tensorboard/jsonl。
R-S11.6 checkpoint:每 eval 周期存;滚动保留 6;最终选 val OMR-NED 最低者【与 LEGATO 选点习惯一致】。
R-S11.7 条件触发止损【不变量,替代原时间制 Gate】:
- 任一 eval:可解析率 <80% → 暂停,排查 prompt/EOS/投影,修复前不烧卡。
- 步数 ≥8000 后任一 eval:MAESTRO val AMT F1 <70 → 停训,回查标签管线(此象限继续训练无意义)。
- loss 尖峰 >3×滑动中位数 → 回滚上一 ckpt,lr×0.5 续。
- 连续 3 个 eval 的 val OMR-NED 无改善(<0.2 绝对)→ 视为收敛平台,允许终止。

### 验收
A-S11.1 训练结束 report:最终/最优 ckpt 的全部钩子指标、触发过的止损事件、各 dialect loss 终值。

---

## 14. S12 推理(A2S 主线的产出形态)

### 需求
R-S12.1 【不变量,主线设计】长音频推理走 **TAST prompt**,时间戳仅在内部使用,输出前剥离:
1. 40s 编码窗、50% 步长(20s hop)【论文明确】;
2. 解码中首个时间戳 >20s 视作该窗 EOS【论文明确】——这就是为什么主线保留 TAST;
3. 每窗保留完整落在前 20s 的小节;窗间在小节线合并,跨小节延音靠 Dyck open 状态跨窗延续【论文明确 小节自包含使然】;
4. 合并后剥离全部时间戳 token → A2S 文本 → `intermo_to_score` → MusicXML。
R-S12.2 beam=4【论文明确】;不可解析输出(validate 违规)按窗重试 1 次(温度 0→greedy),再败该窗标废并在产物中留占位小节,计入 n_fail。
R-S12.3 短音频(≤40s)直接单窗 TAST,同样剥戳输出。

### 验收
A-S12.1 10 段 val 长曲:窗合并后 validate 全过;与整曲一次性解码(截 40s 内的短曲)对照,重叠区小节一致率 >95%。

---

## 15. S13 评测

### 需求
R-S13.1 指标与口径【不变量】:AMT note F1(mir_eval,onset 50ms 容差)@ MAESTRO test;A2S/TAST 的 OMR-NED @ nASAP test(U10 官方脚本;bootstrap 95% CI,10k 重采样;n_fail 单列);TAST note F1 @ nASAP test。
R-S13.2 人检协议 @ U11 十段:渲染成五线谱(Verovio 或 MuseScore 打开 MusicXML),按 checklist 逐段评:小节结构正确率、调号/拍号正确、双手分配合理、可读性 1-5 分;评分表入 report。
R-S13.3 归因分类【不变量】:每个失败样本标注 {解析失败 | 分段/合并伪影 | 音乐内容错误} 三选一——前两类是工程 bug,只有第三类是模型能力问题。
R-S13.4 报告 `outputs/eval_report.md`:每指标对照论文数字(MAESTRO AMT 97.0、TAST 87.1/91.0 等)+ 差距标注为「继续训练可缩」或「结构性」。

---

## 16. 本版新增补齐的细节(=「还有哪些没说」的显式回答)

1. **VN 逐音符对齐问题**(R-S5.6/U9):TAST 时间戳需要乐谱音符↔演奏时间映射,.mid 丢失该映射;save_csv 是候选解,含验证与降级路径。此前所有版本未触及。
2. **反复/跳房子展开策略**(R-S2.4):unfold 后处理,无法无歧义展开则剔除。此前未定义。
3. **PDMX 近重复与跨数据集泄漏防线**(R-S3.6, A-S8.3):MinHash 簇 + work_key 黑名单;nASAP/ASAP-Beyer 曲目不得进 train。此前未定义,直接影响评测可信度。
4. **前端一致性不变量**(R-S10.3):热启动 encoder 必须复用 canary 的 mel 配置,含数值级验收。此前未声明,踩中即白训。
5. **tiling×在线增强的作用次序**(R-S4.5):先补零后加噪,消除"静音补零"这一切分点伪线索。此前未定义。
6. **A2S 主线的推理形态**(R-S12.1):TAST 内部分窗、输出剥戳——解决了"纯 A2S 推理无终止信号"的设计空洞。此前未闭环。
7. **velocity_multiplier 增广**(R-S5.5):来自你封装的能力,白拿的动态多样性。
8. **合成域不做 AMT**(R-S8.3):省序列长度,监督价值低,显式决策而非默认。
9. **VN 批量必须走 Python API 复用模型实例**(R-S5.1):CLI 逐曲重载 172MB 是隐性巨坑。
10. **失败样本永不静默丢弃**(§2.4):全管线统一的 failures 契约。

## 17. 仍然开放(诚实清单)
- U9 结果未定 → TAST 数据面二态,两态均已规格化。
- U7 NeMo-on-Windows 未验 → 两条路线均合法,不变量不受影响。
- sfizz_render flag 名待 U5 首次核实后写死。
- PDMX 元数据实际 schema 待执行者首读适配(R-S3.1)。
- 论文 8 VST / 40ms 帧率 / from-scratch 超参:永久未知,已由偏离声明 D1/D2/D5 吸收,不再阻塞任何阶段。
