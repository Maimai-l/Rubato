# InterMo 表示规格(S2 详规)—— 已验证版

> 状态:本规格的参考实现位于 `rubato/intermo/core.py` + `partitura_adapter.py`,
> 经 22 项单测 + 100 份随机乐谱属性测试 + 真实 MusicXML 六段往返
> (XML→IR→InterMo→IR→XML→IR 首尾相等)验证。**规格与实现有出入时,以通过测试的实现为准并回改本文档。**
> 执行者剩余职责见 §8。

---

## 1. 三层结构

```
MusicXML/MIDI ↔ [适配层 partitura_adapter] ↔ ScoreIR ↔ [core] ↔ InterMo 文本
```
- **ScoreIR**【不变量】:`notes: [(staff∈{PL,PR}, SPitch(step,alter,octave), onset, dur)]` +
  `measures: [(start, num, den, fifths)]` + `score_end`。一切时间为 `fractions.Fraction`,
  单位=全音符。**禁止浮点**(小节求和校验要求精确)。
- 适配层只做搬运与剔除,不做任何 InterMo 语义。

## 2. 冻结决策表(D-01…D-10)

| # | 决策 | 测试锚点 |
|---|---|---|
| D-01 | 单元间=恰一空格;单元内致密无空格。空格即 tokenizer 预切分边界 | golden.exact |
| D-02 | 拼写音高 `[A-Ga-g](--\|-\|#\|##)?[0-8]`,大写 onset 小写 offset(论文字形);排序键=(midi, step序, alter) | double_accidentals |
| D-03 | MIDI 音高 `N{0..127}`/`n{...}`,lite 与 AMT 共用【论文明确共词表】 | lite_midi_glyphs |
| D-04 | 小节线 `\|{m}/{n}k{sig}`,sig∈{0, #1..#7, -1..-7}(五度圈) | sig_change |
| D-05 | 文档最后单元必须是终止小节线(复用末小节签名),携带终止 offset | golden.exact |
| D-06 | 落在小节线时刻的事件归属**小节线单元**;其前若有时间推进,先发空 moment 补齐 interval。与首小节线携带开头 onset 对称 | golden.exact |
| D-07 | 时间戳 `<\|t{0..3999}\|>`(10ms bin);TAST 每单元恰一枚;单调钳制(bin≥前枚),钳制数上报 | ts_per_unit |
| D-08 | 力度 `<\|v{1..127}\|>` 紧跟所属 onset;踏板 `<\|ped1\|>/<\|ped0\|>` 置于单元 moment 最前 | amt_has_vel_ts |
| D-09 | AMT 最短音长 1 bin(off_bin≥on_bin+1),量化下限计数上报 | amt_min_dur_floor |
| D-10 | 首小节(弱起)与末小节允许短于声明拍号;内部小节必须精确相等。**华彩/延长小节(本地反馈问题4):`lenient_measures=True` 放开此约束,允许内部小节 ≠ 声明拍号(仅要求 interval 和 >0),用于真实浪漫派曲目;严格模式仍是默认,保护合成数据** | pickup / validator_measure_sum / cadenza_lenient |

## 3. 金标示例(冻结语法的唯一真源)

3/4 拍、4 降号;PL: A♭2 附点二分;PR: C4 四分 → (E♭4,G4) 二分和弦:

```
|3/4k-4PL:A-2PR:C4 1/4c4E-4G4 1/2 |3/4k-4PL:a-2PR:e-4g4
```

逐单元:①起始小节线携带全部 t=0 onset,PL 先于 PR;②`1/4` 推进后 moment=
`c4`(offset,先)`E-4G4`(onset 和弦,音高升序);③`1/2` 空 moment 补齐至小节
和 = 3/4(D-06);④终止小节线携带全部终止 offset(D-05)。staff 标记跨单元持久,
只在切换时发出。

## 4. 序列化算法(ir_to_units)

1. 断言:首小节 start=0;音符 ∈ [0, score_end];内部小节长度==声明拍号(D-10 豁免首末)。
2. 时间点集合 = 所有 onset ∪ offset ∪ 小节起点 ∪ {score_end},升序遍历:
   - 该点是小节起点或 score_end → 若距上点有推进,先发空 moment 的 metric 单元(D-06),再发小节线单元(score_end 复用末小节签名,D-05);
   - 否则发 metric 单元,frac = 与上点之差。
3. 单元 moment 排序【不变量】:staff PL→PR;每 staff 内 offset(音高升序)先、onset(音高升序)后。
4. 文本发射:单元致密拼接,单元间单空格;staff 状态机跨单元持久。

**Canonical 唯一性**:同一 IR 只有一种合法文本;`parse→serialize` 为不动点
(测试 canonical_idempotent)。

## 5. 解析(text_to_units → units_to_ir)

- 原子分类:`^<\|t\d+\|>$` 时间戳(附着前一单元)→ `^\|m/nk(sig)` 小节线 → `^\d+/\d+`
  metric → 其余整体按 AMT 无头单元的 moment 解析。
- moment 用单一正则交替全覆盖扫描,任何解析间隙即 ParseError(不静默跳过)。
- 重建:开音符表 (staff,pitch)→onset;offset 弹出成 Note;onset 重复(Dyck 深度>1)
  即 ParseError;流尽仍有开音符即 ParseError;缺终止小节线即 ParseError。

## 6. 校验器契约(validate_units)

返回违规字符串清单(空=通过):`DYCK_ORPHAN_OFFSET / DYCK_DOUBLE_ONSET /
DYCK_UNCLOSED / TERMINAL_BAR_MISSING / MEASURE_SUM:{i} / TS_NONMONOTONE`。
用途:S8 标签生成的门(任一违规→整样本废弃入 failures)、S12 推理输出的可解析性统计。

## 7. Dialect 投影

| dialect | 定义 | 入口 |
|---|---|---|
| A2S | 单元流原样 | `project(ir,"A2S")` |
| A2S_lite | 音高字形→MIDI(D-03),结构不变 | `project(ir,"A2S_lite")` |
| TAST | A2S + 每单元后一枚时间戳(D-07) | `project(ir,"TAST",tmap)` |
| AMT | 无乐谱结构;10ms bin 分组的无头单元 = [pedal][offsets][onsets+vel] + ts | `perf_to_amt(notes,pedal)` |

**已测不变量**:strip_ts(TAST)==A2S(论文:时间戳不改变切分边界);TAST 时间戳数==单元数;lite 往返后 MIDI 音高集合与拼写投影一致。

**TimeMap**(TAST 的时间来源):分段线性 乐谱位置→秒。构建来源:
- VN 主路径:CSV 按 `xml_idx` join 乐谱音符 → **逐行校验 CSV.pitch == 乐谱音符 MIDI**,
  不匹配行丢弃其锚点(映射正确性可验证,不靠信任);锚点=(乐谱 onset 位置, CSV.start)。
- humanize 路线:抖动时自生成真值锚点。
- 非表现性:速度直算。
- nASAP:官方音符级对齐。
小节线/休止等无事件位置经分段线性插值取时(每单元必有戳,D-07)。

## 8. 执行者剩余职责(沙盒未能覆盖的)

1. **A-S2.1 nASAP 全量往返**:真实乐谱上跑 `part_to_ir→project→parse→ir_to_part`,
   OMR-NED≈0(LEGATO 官方脚本已确认可用);剔除率<25%,失败清单入 report。
2. **A-S2.2 论文 Fig.1 金标**:持论文原图逐 token 构造期望序列,替换/并列本规格 §3 金标。
3. 适配层在真实 PDMX 上加固:staff 编号方言(A-1)、变 divisions 剔除率(A-2)、
   反复展开(partitura unfold,R-S2.4)、装饰音/连音>7/声部>2 的按小节剔除接线。
4. `vocab_spec.json` 仅从 **D-07/08** 生成固定 token(4000 时间戳 + 129 MIDI + 1 beat + 40 prompt = 4170 special),与 S9 核账联动。**D-02/03/04(拼写音高/MIDI音高/小节线字形)定义的是文本格式,不产生固定 token**——它们由 UnigramLM 从语料学习为 subword。**待补验收(本地反馈问题6)**:训后枚举所有 D-02(~630拼写音高)/D-03(256 MIDI音高)/D-04(小节线)字形,验证常见字形是单 token 而非 subword 分裂;稀有变体(`B--3`/`|11/8k#5`)分裂可接受,但需统计分裂率。
5. 已知裁剪(偏离 D6′):v0 不承载演奏法/力度记号等乐谱属性;往返验收以
   strip-attributes(原谱) 为基线,保证同口径。
