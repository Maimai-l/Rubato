# 本地反馈响应(2026-07-07 status_and_pipeline.md)

逐条处理本地边界检测报告的 7 个问题。🔴 阻塞项全部修复并测试。

## 🔴 阻塞训练

### 问题 1:TimeMap 非单调,19/19 全坏 → 已修复
**根因**:`nasap_loader.build_time_map()` 用音高匹配建锚点,钢琴同音高重复音符错位匹配。
**修复**:新增 `rubato/data/nasap_timemap.py`,用对齐 TSV 的 `xml_id` 精确定位乐谱音符(不猜音高),
并强制单调不变量——回跳锚点剔除而非静默产坏图,锚点不足返回 None。
**验证**:`tests_nasap_timemap.py` 13 项,含针对原 bug 的回归测试(5 个同音高 C4 现在时间单调、无负时长)。
**执行者接线**:用 `build_xmlid_map(part)` 建 xml_id→乐谱位置(需按实际 partitura note.id 与
nASAP xml_id 格式适配),再 `build_timemap(alignment, xmlid_map)`。

### 问题 2:SPEC 解码器维度写错(512 应为 1024)→ 已修复
**根因**:我 SPEC R-S10.1 写 decoder d512,实际 canary hidden=1024(中间 Linear(512→1024))。
**修复**:SPEC R-S10.1 改为 hidden=1024 并注明投影层;`estimate_params()` 默认 dec_d=1024 并加 projection 项;
估算从错误的 91.9M 修正到合理量级。

### 问题 3:换词表后参数量超范围触发断言失败 → 已修复
**根因**:A-S10.1 的固定红线 [176.4M,183.6M] 基于错误的 d512 估算;换 8000 词表的 embedding 增长
(正确行为)会撞线。
**修复**:A-S10.1 改为**相对基准**——`check_param_count()` 验证非词表 backbone 与原始一致(±0.5%),
词表增长量按 (8000−5248)×emb_dim 理论值核对。既能抓 backbone 搭错,又不误伤换词表的正常增长。
**验证**:`tests_model_build.py` 更新,17 项(检测 backbone 错误 + 无基准只报告)。

## 🟡 会丢数据

### 问题 4:华彩/延长小节被拒,5/19 失败 → 已修复
**根因**:`ir_to_units` D-10 要求内部小节精确等于声明拍号,华彩/延长号产生非标准长度。
**修复**:`ir_to_units(lenient_measures=True)` 与 `validate_units(lenient_measures=True)` 配对模式,
放开"小节==声明拍号"约束(仅要求 interval 和 >0),保持 Dyck 与自包含。严格模式仍是默认,保护合成数据。
**验证**:华彩 5/4 小节在 3/4 曲中往返无损;严格模式仍正确拒绝;原 22 项 InterMo 测试不受影响。
**执行者用法**:真实浪漫派数据用 lenient=True,记录 lenient 样本占比。

### 问题 5:verify_frontend 未接入 build_model → 已修复
**修复**:`build_model()` 新增 `frontend_wav_paths` 参数,在 encoder hash 核对后强制调用
`verify_frontend()`,R-S10.3 前端一致性不变量现被执行。结构性错误(mel 数/hop 不符)会抓;
归一化方式差异导致的 diff 偏大则结论为"复用 NeMo preprocessor"(不误报)。

### 问题 6:词表字形覆盖率未验证 → 已补验收工具
**修复**:`tokenizer.enumerate_glyphs()` 枚举 D-02(630 拼写)/D-03(256 MIDI)/D-04(360 小节线)全字形;
`check_glyph_coverage(sp_model)` 训后统计各类单 token 分裂率。稀有变体分裂可接受但被统计。
**执行者**:训完 tokenizer 后调用,分裂率过高(常见字形分裂)需增大 vocab 或调整预切分。

### 问题 7:InterMo SPEC §8 item4 文档不准确 → 已修正
**修复**:SPEC 改为"vocab_spec.json 仅从 D-07/08 生成固定 token;D-02/03/04 定义文本格式,
由 UnigramLM 学习为 subword",与问题 6 的覆盖率验收联动。

## 采纳的本地事实(更新进规格/代码)

- MAESTRO 实际 198.65h(非 SPEC 的 159h)、1276 WAV、官方 split 962/137/177 → 数字以本地实测为准。
- canary 实测 182.64M @ 5248 vocab → 作为 A-S10.1 相对基准的原点。
- nASAP xml_id 格式 "n{measure}-{idx}" 可直接映射乐谱 → TimeMap 修复的基础。
- PDMX 43 列含 tier_a_star/quality_label/is_duplicate/split → S3 过滤可直接用这些列(执行者实现 S3 时采纳)。
- frontend mel:128 mel / 512 n_fft / 10ms hop(从 .nemo 提取)→ verify_frontend 的目标值。

## 仍待执行者完成(非本轮阻塞)

- S3 PDMX IO、S6 MAESTRO 流式、S7 nASAP IO 外壳(用修复后的 nasap_timemap)
- S11 train.py 主循环装配、S12 infer.py、S13 evaluate.py
- 跨数据集泄漏检测实跑(work_key 黑名单 + MinHash;leakage_check 逻辑已在 segment.py)
