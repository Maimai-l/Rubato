# Rubato A2S 复刻 · 架构文档(ARCHITECTURE)

> 本文档是**从 `rubato_spec_v3.md` 提炼的数据流视图**,不是新设计。每个环节标注对应
> 规格编号(R-Sx.y),需要细节时回查规格原文。三者构成单一权威:规格(要求)+
> 本文档(数据流)+ 代码(实现),互相印证。
>
> 一句话概括:**三个数据源 → InterMo 统一表示 → 四路数据在 S8 汇聚成 (音频段, 多 dialect
> 标签) → 换 8000 词表热启动 Canary → 多任务训练 → TAST 内部分窗推理、输出剥时间戳得 A2S。**

---

## 0. 数据流全景(从规格 §2.5 依赖图展开)

```
                          ┌─────────────── 数据源(只读,不搬)───────────────┐
   MAESTRO 103GB zip        PDMX ~4.3GB 乐谱池           nASAP(音频借 MAESTRO)
        │                        │                            │
   [S6 流式转FLAC]          [S3 过滤+归一化]              [S7 谱→InterMo
    zipfile 逐成员            MuseScore4 CLI               nASAP对齐→time_map]
    禁止解压全包              查重+跨集黑名单                    │
        │                        │                            │
        │                   manifest_pieces.jsonl              │
        │                        │                            │
        │              ┌─────────┴─────────┐                  │
        │         [S4 直排渲染]      [S5 表现性渲染]            │
        │          straight MIDI      VirtuosoNet API          │
        │          →4源→16预设        (权重载一次)              │
        │          →peak归一→Opus     CSV时间映射→TAST          │
        │              │                  │                    │
        │              │            humanize兜底(VN失败/超预算) │
        │              │                  │                    │
        ▼              ▼                  ▼                    ▼
   AMT标签         A2S/A2S_lite/TAST   A2S(/TAST)         A2S/A2S_lite/TAST
   (真实域)          (合成域)            (合成域)            (真实域)
        └──────────────┴─────────┬────────┴────────────────────┘
                                 ▼
                    ┌────────────────────────────┐
                    │  S8 分段与标签生成(汇聚点)  │
                    │  · 乐谱类:小节对齐 4-32小节  │
                    │  · AMT:12-25s 智能切点       │
                    │  · project() 生成各 dialect  │
                    │  · validate() 门:违规即废   │
                    │  · 泄漏终检(work_key/dup)   │
                    └────────────┬───────────────┘
                    manifest_utts.jsonl + labels.jsonl + 分片
                                 ▼
              ┌──────────────────┴──────────────────┐
       [S9 Tokenizer]                        [S10 模型构建]
        UnigramLM 8000                        canary.nemo 提取:
        语料=A2S+A2S_lite                      · 前端 mel 配置(不变量)
        核账 3571+4170+256+3                    · encoder 权重热启动
              │                                · 换 8000 词表,重置 emb/softmax
              └──────────────┬──────────────────┘
                             ▼
                      [S11 训练]
                       多任务混比 A2S.35/lite.15/TAST.20/AMT.30
                       loss: 1/√|T| + 语义平滑 + 时间戳序数平滑
                       tiling 在线 + 条件止损
                             ▼
                      [S12 推理]  ← A2S 主线产出形态
                       走 TAST prompt,时间戳内部分窗
                       40s窗/20s hop,小节线合并
                       输出前剥戳 → A2S → MusicXML
                             ▼
                      [S13 评测]
                       OMR-NED(LEGATO脚本) + note F1 + 人检
```

**并行拓扑**(规格 §2.5):S4/S5/S6/S7 相互独立,可同时跑;唯一冲突是 **S5(VirtuosoNet)
与 S11(训练)竞争 GPU**(R-S5.8),二者错峰。

---

## 1. 每阶段 I/O 契约(执行者按此对接)

下表是阶段间的接缝定义。**输入/输出的 schema 见 §2,不得偏离**;"关键不变量"列是最容易踩错的点。

| 阶段 | 输入 | 输出 | 关键不变量 | 规格锚点 |
|---|---|---|---|---|
| **S2 InterMo** | MusicXML / MIDI | `intermo` 库 | Fraction 精确算术;canonical 唯一;往返无损 | R-S2.1~2.6 ✅已实现 |
| **S3 PDMX池** | `$RAW/pdmx/` | manifest_pieces | 单part双谱表;MuseScore4归一化;跨集黑名单 | R-S3.1~3.6 |
| **S4 直排渲染** | manifest_pieces | `$AUDIO/flat/*.opus` | 音源分配=hash可复现;peak归一在preset前 | R-S4.1~4.5 |
| **S5 表现性** | 归一化XML | `$AUDIO/vn/*.opus`+csv | Python API复用模型;CSV按xml_idx核对pitch | R-S5.1~5.9 |
| **S6 MAESTRO** | zip×2 | `$AUDIO/maestro/*.flac`+AMT标签 | **流式转FLAC禁解压**;KeyOff约定 | R-S6.1~6.4 |
| **S7 nASAP** | ASAP仓库 | nasap段+标签+split | 音频借MAESTRO映射;保守split落盘 | R-S7.1~7.4 |
| **S8 汇聚** | S4/5/6/7产物 | manifest_utts+labels+分片 | 乐谱类小节对齐切;validate门;泄漏终检 | R-S8.1~8.6 |
| **S9 Tokenizer** | labels(A2S+lite) | spm模型 | identity归一化;词表核账闭合 | R-S9.1~9.4 |
| **S10 模型** | canary.nemo | 可训练模型 | 前端配置逐项一致;encoder权重hash核对 | R-S10.1~10.5 |
| **S11 训练** | 模型+分片 | checkpoint | loss三件套公式;条件止损非时间制 | R-S11.1~11.7 |
| **S12 推理** | checkpoint+音频 | MusicXML | TAST内部分窗;输出剥戳;小节线合并 | R-S12.1~12.3 |
| **S13 评测** | 模型+测试集 | eval_report | OMR-NED用LEGATO脚本;归因三分类 | R-S13.1~13.4 |

---

## 2. 数据契约(manifest schema,规格 §2.3 逐字)

三个 jsonl 是阶段间传递的血液。**字段可增不可删改**(不变量)。

### manifest_pieces.jsonl(S3 产出,每行一 PDMX 曲目)
```json
{"piece_id":"", "xml_raw":"", "xml_norm":"", "composer_meta":"", "license":"",
 "n_measures":0, "n_notes":0, "has_tempo_mark":false, "time_sigs":[],
 "excluded_measures":[], "parse_ok":true,
 "work_key":"composer|title",   "dup_cluster":0,
 "vn":{"status":"pending|done|failed|skipped", "midi_path":"", "csv_path":"",
       "composer_used":"", "qpm_used":0, "vel_scale":1.0}}
```

### manifest_utts.jsonl(S8 产出,每行一训练样本)
```json
{"utt_id":"", "piece_id|maestro_id|asap_id":"", "kind":"flat|vn|human|maestro|nasap",
 "measure_range":[0,0], "time_range":[0.0,0.0], "audio_path":"", "dur_s":0.0,
 "source_id":"", "preset_id":"",
 "dialects":["A2S","A2S_lite","TAST?","AMT?"], "split":"train|val|test"}
```

### labels.jsonl(S8 产出,tokenizer 前的序列化文本)
```json
{"utt_id":"", "A2S":"", "A2S_lite":"", "TAST":"null|str", "AMT":"null|str"}
```

### 每阶段报告(§2.4,不变量)
每阶段写 `$REPORTS/<stage>.report.json`:
```json
{"stage":"", "inputs_hash":"", "counts":{}, "failures":[{"id":"","reason":""}],
 "decisions":[{"key":"","value":"","tag":""}], "acceptance":{"A-x.y":"pass|fail|value"}}
```
**失败样本永不静默丢弃**——必进 failures 并计数。

---

## 3. 四路数据 → 哪些 dialect(规格 R-S8.3,最易混淆处)

| 数据源 kind | A2S | A2S_lite | TAST | AMT | 为什么 |
|---|:-:|:-:|:-:|:-:|---|
| flat(直排) | ✅ | ✅ | ✅ | ❌ | 合成域不做AMT:力度/踏板人造,监督价值低,省序列长度 |
| vn(表现性) | ✅ | ✅ | ⚠️ | ❌ | TAST依CSV映射(R-S5.6):主路径可用/降级则否 |
| human(兜底) | ✅ | ✅ | ✅ | ❌ | humanize自生成真值时间戳 |
| maestro | ❌ | ❌ | ❌ | ✅ | **真实录音进encoder的唯一通道**——A2S主线鲁棒性的命根 |
| nasap | ✅ | ✅ | ✅ | ❌ | 真实录音+官方对齐 |

这张表是整个训练数据结构的核心。读法:**AMT 只从 MAESTRO 来,它撑起真实域声学监督;
乐谱类 dialect 从合成(flat/vn)+ 真实(nasap)两边来,合成管量、真实管域。**

---

## 4. 状态盘点(当前进度)

| 状态 | 阶段 | 位置 |
|---|---|---|
| ✅ 已实现+测试 | S2 InterMo | `intermo/`(22测试+100随机谱+真实XML六段往返) |
| ✅ 渲染核心已实现 | S4/S5 引擎层 | `render/core.py`+`irgen.py`+`data/composer_alias.py` |
| ✅ 环境就位 | S1 | NeMo可装/LEGATO可跑/4源9变体/canary加载通过 |
| ✅ 逻辑层完成+测试 | S8 分段器 | `data/segment.py`(22测试) |
| ✅ 逻辑层完成+测试 | S9 tokenizer | `data/tokenizer.py`(13测试;vocab_spec.json已落盘) |
| ✅ 逻辑层完成+测试 | S10 模型构建 | `model/build.py`(17测试;GPU部分带断言) |
| ✅ 逻辑层完成+测试 | S11 loss/采样/止损 | `losses/sampling/early_stop.py`(33测试) |
| ✅ 逻辑层完成+测试 | **S6 MAESTRO 流式** | `data/maestro.py`(16测试:MIDI→AMT/KeyOff/CC64;FLAC流式带结构) |
| ✅ 逻辑层完成+测试 | **S3 PDMX 过滤** | `data/pdmx.py`(20测试:work_key/MinHash查重/跨集黑名单/license) |
| ✅ 逻辑层完成+测试 | **S7 nASAP IO** | `data/nasap.py`+`nasap_timemap.py`(12+13测试:重叠切窗/保守split/xml_id对齐) |
| ✅ 装配完成+测试 | **S11 train.py 主循环** | `model/train.py`(12测试:差分lr/warmup+cosine/bucketing;GPU循环带断言) |
| ⬜ 待写(需GPU) | S12 推理 / S13 评测 | `model/infer.py` / `model/evaluate.py` |

**测试总计 180 项,零失败。** 从表示到训练装配的全部纯逻辑已在沙盒用合成数据验证。

**已验证 vs 待本地验证的边界**:
- 沙盒已验证(合成数据):InterMo 往返、小节对齐切段、词表核账、loss 三件套数学、
  采样混比、止损触发、MIDI→AMT 事件、work_key/MinHash 查重、重叠切窗、保守 split、
  optimizer 差分 lr、schedule、bucketing。
- 待本地验证(真实数据/GPU,已写成带断言的结构):zipfile 流式转 FLAC、PDMX 真实解析、
  MuseScore4 归一化、canary 加载 + encoder hash + 前端比对、训练主循环的 forward/backward、
  评测钩子的实际生成。断言失败即抛,本地跑第一次就抓错。

**剩余**:S12 infer.py(TAST 分窗剥戳,SPEC §14)+ S13 evaluate.py(OMR-NED 复用 LEGATO + note F1)。
二者是 train.py 的 run_eval_hooks 依赖项,需真实模型验证,故留待垂直切片时与 GPU 一起接。

## 5. 关键设计决策速查(规格 §16,防遗忘)

1. **FLAC 流式转换**(R-S6.1):MAESTRO 103GB 用 zipfile 逐成员转 16k FLAC,禁止解压全包,峰值磁盘=zip+10GB。**这不是可选优化,是不变量**。
2. **合成域不做 AMT**(R-S8.3):显式决策,省序列长度。
3. **VN 批量走 Python API**(R-S5.1):复用模型实例,CLI 逐曲重载 172MB 是巨坑(你的封装已支持目录批量)。
4. **CSV 时间映射可验证**(R-S5.6):按 xml_idx join 后逐行核对 pitch,不靠信任(你的 CSV 有 xml_idx+pitch 列)。
5. **peak 归一化位置**(R-S4.3+用户修复):sfizz 后、加噪底前,-1dBFS,用 peak 非 LUFS 保动态。
6. **A2S 主线推理走 TAST**(R-S12.1):时间戳内部当分窗信号,输出前剥离——解决"纯 A2S 无终止信号"空洞。
7. **前端一致性**(R-S10.3):热启动 encoder 只认 canary 训练时的 mel 配置,逐项核对否则白训。
8. **泄漏防线**(R-S3.6+A-S8.3):nASAP/ASAP-Beyer 曲目 work_key 列入 train 黑名单,MinHash 查近重复。
9. **条件止损非时间制**(R-S11.7):按步数与指标触发(如步≥8000后AMT F1<70停训),不按 wall-clock。
10. **失败永不静默丢弃**(§2.4):全管线统一 failures 契约。
