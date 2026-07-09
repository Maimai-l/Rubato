# 语料重生成与 tokenizer 重训指引（书面版）

> 面向本地执行端（Windows + 真实数据 + GPU）。这是一份可直接照做的操作清单。
> 目标：把 **stale（已过期）** 的 tokenizer 语料按最新字形/切分规则全量重生成，
> 重训 tokenizer，通过验收门，才进入模型训练。

---

## 0. 为什么必须重生成（不是可选项）

你之前已经跑了 ~18 万行语料并训了一版 tokenizer。**那份语料和那版 tokenizer 现在都作废了**，
因为在它之后合入了三处**改变文本字形/切分**的修正。tokenizer 学的是"原子字符串"，
只要目标文本变了，旧词表学到的就是错的原子，模型训练会一路带病。

三处 breaking change（都在分支 `claude/training-issues-diagnosis-9ygud6` 上）：

| commit | 改动 | 对文本的影响 |
|---|---|---|
| `7332403` | adapter 再触键 `<=` → `<` | 相邻同音高音符不再被误并成一个长音，A2S 里多出正确的 `xX` 再触键对 → **A2S 文本变了** |
| `7332403` | D-06 小节线收尾 offset 形式 | 跨小节线的收尾 offset 现在挂在小节线**前**的 interval 单元（对齐论文 Fig.1）→ **A2S/TAST 文本变了** |
| `94b5903` | 字形对齐论文 | 时间戳 `<\|t N\|>`→`<\|0.00\|>`（秒）、力度 `<\|vel:N\|>`、踏板 `<\|CC64:on/off\|>` → **TAST/AMT 文本全变了** |

> 结论：**A2S / A2S_lite / TAST / AMT 四种方言的语料全部要重生成**，旧 `a2s_corpus.txt`、
> 旧 labels.jsonl、旧 `*.model/*.vocab` 一律删除或改名归档，不要复用。

先做一件事：**拉最新分支**，确保 `rubato/` 代码和 `configs/vocab_spec.json`（user_defined_symbols
的新字形来源）都是最新的。

```bash
cd D:\vscode_projects\ee_download\Rubato
git fetch origin claude/training-issues-diagnosis-9ygud6
git checkout claude/training-issues-diagnosis-9ygud6
git pull --rebase origin claude/training-issues-diagnosis-9ygud6
python -c "import json;s=json.load(open('configs/vocab_spec.json',encoding='utf-8'));print('ts0=',s['timestamps'][0],'ts_last=',s['timestamps'][-1]);print('perf=',s['midi'][0],s['midi'][-2],s['midi'][-1]);print('counts=',s['counts'])"
# 期望看到新字形：
#   ts0= <|0.00|>  ts_last= <|39.99|>
#   perf= <|vel:1|> <|CC64:on|> <|CC64:off|>      ← 'midi' 段其实存的是 AMT 演奏字形(力度127+踏板2=129)
#   counts= {'timestamps':4000,'midi':129,'beat':1,'prompt':40,'total':4170}
```

---

## 1. 重生成顺序（四方言语料，全量、不丢数据）

顺序无强依赖，但建议按下表。**每一步都要看产出统计，任何一步"处理数远小于输入数"都要停下排查，不许静默吞。**

### 1.0 先产 manifest —— 用对脚本(有坑)

PDMX 过滤有【三个】s3 脚本,别跑错:
- **`scripts/s3_filter_pdmx.py`** ← 【就用这个】。它才真正写出 `work/manifest_pieces.jsonl`
  (过 metadata/license/work_key_or_fallback,缺 composer 用 `__nometa__` 兜底不丢)。
- `scripts/s3_full_filter.py` ← **只写统计 report,不产 manifest**。名字像"全量过滤"但它是诊断用的,
  跑它你会以为过滤完了、其实没有 manifest(这正是 s7 踩过的同一个坑:算了不落盘)。别拿它当产 manifest 的。
- **`scripts/s3_minhash_leakage.py`** ← 【必须在 s3_filter 之后、s5 之前跑一次】。它按内容(MinHash)
  剔除跨数据集近重复(nASAP/ASAP 泄漏),**覆盖写**回 `manifest_pieces.jsonl`。
  ⚠ 跳过它 = **s5 用空 blacklist、没有任何泄漏防护**(s5/s5_parallel 都传空 blacklist,
  依赖的就是 manifest 已被 minhash 洗过)。顺序错 = 测试集污染,评测数字全废。

正确顺序:`s3_filter_pdmx.py` → `s3_minhash_leakage.py` →(下面)`s5`。

### 1.1 PDMX → A2S / A2S_lite（`scripts/s5_pdmx_a2s_labels.py` 或并行版 `s5_parallel.py`）

这是 tokenizer 语料的大头。**关键：吃全 manifest（~53k 曲），不是被 composer 过滤剩下的 16k。**

- 确认输入 manifest 是**去掉 composer 弱智过滤之后**的池。`work_key_or_fallback` 已让缺
  composer/title 的曲用 `__nometa__|<piece_id>` 兜底，不再被丢。
- s5 默认 `overlap=True, min_measures=2, max_measures=16`（重叠切窗，最大化 tokenizer 语料覆盖）。保持。
- blacklist 只用于 train/val/test 隔离（nASAP test / ASAP-Beyer），**不要**拿它砍 tokenizer 语料以外的东西。

```bash
python scripts/s5_pdmx_a2s_labels.py
# 看输出末尾 DONE 行：processed 应是【几万】而不是【一万几】；
# 若 processed ≈ 16k 或更少 → 停：composer 过滤或 manifest 没换全池，先修再跑。
```

产出：`work/pdmx_a2s_labels.jsonl`（A2S/A2S_lite，**TAST=null**，见下）、`work/a2s_corpus.txt`、`reports/s5_pdmx_a2s.json`。

> §1.1 只产**文本**(给 tokenizer 语料 + A2S 训练标签),**故意不产 TAST**。原因见 §1.1b。

### 1.1b PDMX 渲染音频（训练必须，别漏）—— S4 直排 + S5 表现性

**PDMX 是最大的源(论文 2071h);不渲染音频 = PDMX 训练 0 贡献,只剩 nASAP(30h)+MAESTRO(159h)。**
这一步此前被我的文档漏掉了,补回:

- **S4 直排(恒速)**:`scripts/s4_batch_render.py` / `s4_parallel.py` → PDMX 直排音频 → 配 §1.1 的 A2S/A2S_lite。
- **S5 表现性(含 TAST)—— 用你本地的 VirtuosoNet**:`scripts/s5_vn_render.py`。
  它调你的 `virtuoso` CLI(VIRTUOSO_GUIDE §2/§4)`--csv` 拿音符级时间(xml_idx,start,…),
  据此建 tmap(SPEC R-S5.6 主路径,复用 `build_timemap`),再把 VN 演奏 MIDI 渲成音频、按段切。

```bash
python scripts/s5_vn_render.py \
  --out-labels work/pdmx_perf_labels.jsonl --out-corpus work/a2s_corpus.txt \
  --out-audio-dir work/pdmx_audio
# 产:每段 work/pdmx_audio/<utt>.opus + 标签行(含 audio_path + A2S/A2S_lite/【TAST】)。看末行 vn_ok / TAST 应 >0。
# CLI 每曲一次;要复用 172MB 模型实例(R-S5.1)可把 vn_infer 换成 GUIDE §5 的 InferenceModel 循环。
```

> **关键不变量:TAST 时间戳与音频必须同源(同一 tmap)。** 所以 TAST 只在渲染处产(用 VN 的 CSV 时间),
> 不能用 §1.1 的恒速估算 —— 那与真实音频不匹配 = 时间戳噪声。这就是 §1.1 的 TAST 恒 null 的原因。
>
> **为什么之前"没有 VN 管线":SPEC 设计了 S5(R-S5.1-5.9)却从未落地脚本,历史上只有 S4 直排。**
> `s5_vn_render.py` 现在补上,直接调你本地的 virtuoso(不是重写它)。
> humanize(`rubato/render/humanize.py`)**只是 SPEC R-S5.9 的失败兜底**(VN 超时/非零退出/无 CSV 的曲),
> 用 `--allow-humanize-fallback` 才启用,默认关。它不是 VN 的替代,VN 就是管线。

### 1.2 nASAP → A2S / A2S_lite / TAST（`scripts/s7_full_nasap.py`）

真实音频对齐得到 tmap，产出带时间戳的 TAST（和无戳 A2S/A2S_lite）。**问题#6 的 xml_id 匹配已修**
（剥和弦后缀 `n2-1`→`n2` + LIS 单调化 + 锚点密度门）。

> **⚠ 必须带输出参数**：s7 早期版本只写 report、【不落 labels 到盘】(执行端已发现并补了
> `--out-labels`/`--out-corpus`)。所以务必带上输出路径,否则跑完只有统计、没有 labels：

```bash
python scripts/s7_full_nasap.py \
  --out-labels D:\vscode_projects\ee_download\work\nasap_labels.jsonl \
  --out-corpus D:\vscode_projects\ee_download\work\a2s_corpus.txt      # 追加,与 s5 的语料并到同一文件
# 输出参数是 append 模式:整轮重跑前先删旧 labels/corpus,别二次追加。
# 看报告匹配率诊断(diagnose_match):match_rate 应【远高于】早期 0.37%/1%,正常 0.9+。
# 看末行打印的 successful/segments:必须 > 0,否则 labels 是空的(timemap/匹配挂了,别继续)。
```

产出：nASAP labels.jsonl（含 A2S/A2S_lite/TAST）、追加进 `a2s_corpus.txt` 的 A2S/A2S_lite、`reports/s7_full_nasap.json`。
> 注:s7 的 `--out-corpus` 只写 A2S+A2S_lite(与论文 §3.2 一致),不写 TAST。

### 1.3 MAESTRO MIDI → AMT（`scripts/gen_amt_labels.py`）

真实演奏 MIDI → AMT 事件文本（新字形 `<|0.00|>` / `<|vel:N|>` / `<|CC64:on/off|>`）。

```bash
python scripts/gen_amt_labels.py
# 看统计：处理曲数应 ≈ 1276（全 MAESTRO）。
```

产出：MAESTRO AMT labels.jsonl。

---

## 2. 装配 tokenizer 语料（**只 A2S + A2S_lite**，对齐论文 §3.2）

> **更正（重要）**：论文 §3.2 明确 UnigramLM **只在 A2S 和 A2S_lite 文本上拟合**
> （"fit on A2S and A2S$_{lite}$ text, with timestamps and prompt tokens added as
> predefined vocabulary"）。时间戳/力度/踏板/beat 都是 **预定义 user_defined_symbols**，
> UnigramLM 不会去 merge 它们；把 TAST/AMT 文本塞进语料只会**扰动 merge 的频率统计**、
> 偏离论文，不会带来新的可学 piece。所以 tokenizer 语料 **只收 A2S + A2S_lite**
> （来自 PDMX **和** nASAP —— nASAP 也产 A2S/A2S_lite）。TAST/AMT/DBD 文本用于**训练模型**，
> 不用于**训练 tokenizer**。

`s5` 已把 PDMX 的 A2S/A2S_lite 写进 `a2s_corpus.txt`；nASAP 的 A2S/A2S_lite 在其 labels.jsonl 里，
需要抽出来一起并入。用下面这段一次性装配（无需新脚本）：

```python
# assemble_corpus.py —— 只抽 A2S + A2S_lite 成 tokenizer 语料行(对齐论文 §3.2)
import json, io
OUT = r"D:\vscode_projects\ee_download\work\tok_corpus.txt"
LABEL_JSONLS = [
    r"D:\vscode_projects\ee_download\work\pdmx_a2s_labels.jsonl",   # PDMX A2S/A2S_lite
    # nASAP labels.jsonl 路径,                                       # nASAP 也含 A2S/A2S_lite
]
DIALECTS = ("A2S", "A2S_lite")          # ← 只这两个;TAST/AMT/DBD 不进 tokenizer 语料
n = 0
with io.open(OUT, "w", encoding="utf-8") as w:
    for path in LABEL_JSONLS:
        for line in io.open(path, encoding="utf-8"):
            if not line.strip():
                continue
            row = json.loads(line)
            for d in DIALECTS:
                t = row.get(d)
                if t and t.strip():
                    w.write(t.strip() + "\n"); n += 1
print("corpus lines:", n, "->", OUT)
```

> 注意 1：**tokenizer 语料不做 work_key 去重**。去重只服务 train/val/test 隔离，
> 拿它砍 tokenizer 语料 = 白白丢 distinct 子串、把词表压小。论文没这么干。
>
> 注意 2：`s5` 的 `a2s_corpus.txt` 已是 A2S+A2S_lite；若直接用它 + nASAP 的 A2S/A2S_lite，
> 效果等同上面脚本。别把 TAST/AMT 混进来。

---

## 3. 重训 tokenizer + 验收门

```python
from rubato.data.tokenizer import train_unigram, check_glyph_coverage, reconcile
res = train_unigram(
    corpus_files=[r"D:\vscode_projects\ee_download\work\tok_corpus.txt"],
    model_prefix=r"D:\vscode_projects\ee_download\work\rubato_spm",
    vocab_size=8000,                # 与论文同量级语料 → 8000 应可达
    spec_path="configs/vocab_spec.json",
)
print(res)
cov = check_glyph_coverage(r"D:\vscode_projects\ee_download\work\rubato_spm.model")
print(cov)
```

**验收（两条并列，都要过）：**

1. `res["vocab_size"]` **逼近 8000**，且 `res["warning"] is None`（没触发回退）。
   - 若 `res["fell_back"] == True` 或 vocab 明显小于 8000（比如 ~5k）→ **红旗，不是可接受终态**。
     论文用同一 PDMX 达到 3571 可学习 piece，我们全池语料应同量级。回退触发 = 语料八成又在某处被丢：
     - s5 是否真的吃了全 manifest（processed ≈ 几万）？
     - tokenizer 语料是否被误去重？
     - 是否漏并了 nASAP / MAESTRO 的文本？
     排查完再重跑，**不要合理化一个偏小的词表**。
2. `cov["split_rate"] < 0.30`（常见字形——音高 `C4/A-3/F##5`、MIDI `N60/n60`、时间戳 `<|0.00|>`、
   力度 `<|vel:82|>`、踏板 `<|CC64:on|>`、小节线 `|3/4k-4`——大多是**原子单 piece**，不被切碎）。
3. `reconcile(res["vocab_size"], 4170)` 的 `learnable` 与预期一致（8000 时 learnable = 8000−4170−256−3 = 3571）。

**只有两条都过，才用这份 tokenizer 去 encode 标签、训模型。** 任一不过就是数据/装配问题，先修。

---

## 3.5 装配数据集（此前缺失的胶水，别跳）

三份 labels.jsonl 落盘后,【没有】现成代码把它们 + 音频喂进 RubatoDataset —— 而且三份 schema 不一样
(maestro 用 `midi_file`/`amt_text`,pdmx/nasap 用 `utt_id`/`AMT`),且都不带音频路径。
这层胶水现在补上了:`rubato/data/assemble.py` + `scripts/build_dataset.py`。

**先干跑验证装配(无 GPU 也能跑)**:

```bash
python scripts/build_dataset.py --dry-run
# 打印每源 kept / no_audio / no_dialect / bad_schema,加总守恒。
# 盯:每源 kept 都 >0;no_audio 不能占绝大多数(占大头=音频路径没对上,先修 resolve_audio)。
```

`scripts/build_dataset.py` 里 `resolve_audio()` 的三处路径约定(pdmx 渲染产物 / maestro FLAC via CSV /
nASAP↔FLAC)带 **【EXECUTOR】** 注释 —— 按你的真实目录核对。特别是 **nASAP**:s7 的标签行目前
不带音频引用,`resolve_audio` 会把 nASAP 全判 no_audio。要么在 s7 标签行里补上 `audio_path`,
要么在 `resolve_audio` 里按你的 nASAP→MAESTRO-FLAC 映射补全。dry-run 的 `nasap kept=0` 就是这个信号。

装配 OK(kept 合理)后,去掉 `--dry-run` 即建模型 + 训练(见 §5 从头训开关)。

---

## 4. 反"丢数据"总标准（贯穿全程）

论文用**相同的数据集**达到 Table 3 的水平。所以任何"复现比论文少一大截数据"的现象，
默认判定为**我们的 bug，不是数据的问题**——去抓 bug，不要接受降级结果。具体红线：

- PDMX 进入语料的曲数应在 **~5 万量级**，不是 1 万几（composer 过滤已删，别让它复活）。
- nASAP xml_id 匹配率应 **0.9+**，不是 0.37%/1%（已修，跑出来验证）。
- tokenizer vocab 应**逼近 8000**；触发回退 = 红旗，排查而非合理化。
- 每个批处理脚本的 `skipped/failures` 计数要**看**——大批量 skip 必须逐类归因，`§2.4 失败永不静默丢弃`。

---

## 5. 剩余工作清单（本轮 review 后的状态）

### §三 稳健性修正（代码侧，已全部完成并推送 `244dab1`）
- [x] nASAP TimeMap 单调化改**最长非降子序列**（LIS），单个早期错锚不再连累其后全部正确锚点；保留锚点密度门。
- [x] `build_optimizer` 按点分路径的 `encoder` 段归组（兼容 NeMo `model.encoder.*`），encoder 组为空**炸响不静默**（否则热启动差分 lr 失效）。
- [x] `train_batches` 每 epoch **确定性打乱桶顺序**（桶内仍长度同质），消除固定短→长课程与跨 epoch 零随机。
- [x] `dialect_sampler` 支持注入 mix + 输出小池**过采样倍数报告**（`RubatoDataset.last_mix_report`），AMT 小池反复采样不再静默。
- [x] `evaluate.note_f1` 增加 **onset+offset** 变体（offset_ratio=0.2），对论文 Table 3 不再系统性偏乐观。

### §一 与论文的偏离 —— 我已把**能力都补上**（代码沙盒已验证），开关留给你

之前这三条我推给"用户拍板"。这轮按"做所有力所能及的"，我把**机器都造好了**，
你只需在配置里拨开关；不再是"缺失"，而是"默认关、可开"。

1. **PDMX → AMT（论文 436k，之前为 0）—— 能力已实现。**
   - `core.score_ir_to_events(ir, sec_per_whole, default_vel)`：乐谱 IR → 恒速演奏事件；
     接 `perf_to_amt(...)` 即得 PDMX 的 AMT / `perf_to_amt(..., lite=True)` 得 AMT_lite。
   - `DIALECT_PROMPT` 已含 `AMT_lite`；`build_target_sequence("AMT",...)` 可训。
   - **执行端要做**：非表现性渲染的音频用**同一** `sec_per_whole`/`default_vel`，AMT 目标才与音频对齐；
     表现性(VirtuosoNet)渲染则用 VN 产出的演奏 MIDI 直接喂 `perf_to_amt`（已有）。
2. **补齐方言 TAST_lite / AMT_lite / DBD —— 已实现（DBD_lite 待定）。**
   - `project(ir,"TAST_lite",tmap)` / `perf_to_amt(...,lite=True)` / `project(ir,"DBD",tmap,beats=...)`。
   - `DIALECT_PROMPT` 已含三者；`tests_dialects.py`(28 项) + `tests_model_build.py` 已锁。
   - **DBD_lite**：论文 Fig.2 对 DBD 的 full/lite 精确切分没有文字定义，我按『下拍+拍号 vs 纯拍流』
     做了 `core.ir_to_dbd_units(...,lite=True)` 的合理实现，但**没有**放进训练 prompt 表——
     等你看一眼 Fig.2 图示确认后再定是否入训。这是唯一一个我留白的点。
   - **执行端要做**：DBD 的拍点最好用 **nASAP 人工标注**传 `beats=[(score_pos,is_downbeat),...]`；
     没标注时 `project` 会从拍号按 `1/den` 推导（乐理缺省，见 `_derive_beats`）。
3. **热启动 vs 从头训（D1）—— 已做成开关。**
   - `build_model(..., from_scratch=False)`：缺省热启动（载 canary encoder，hash 核对**已载入**）。
   - `from_scratch=True`：`reinit_all_parameters` 把**全部**权重随机化，hash 核对**已改变**（防误用预训练 encoder）。
   - **执行端要做**：若开 `from_scratch=True`，训练把差分 lr 关掉（`lr_encoder == lr_decoder`）——
     差分 lr 是给热启动降载 encoder 用的，从头训应统一 lr。

> 剩下真正要你/用户拍板的只有两点**规模/算力**取舍，代码不拦：
> (a) PDMX 要不要真的开 AMT 渲染（+一条渲染链的算力）；(b) 从头训还是热启动（算力差一个量级）。
> 能力都在，随时可开。

---

## 6. 一句话流程

拉最新分支 → 删旧语料/词表 → **s3_filter_pdmx → s3_minhash_leakage** → s5(全池) + s7(带 --out-labels) + gen_amt →
装配 `tok_corpus.txt`（**只 A2S+A2S_lite**，不去重）→ `train_unigram(vocab=8000)` → 过两条验收门（vocab≈8000 且 split_rate<0.30）→
**`build_dataset.py --dry-run` 验装配**（每源 kept>0）→ 才建模型、训练。
任何一步数据量"莫名变少"就停下抓 bug，别接受降级。

---

## 7. 本轮新增能力速查（执行端可直接调用）

| 能力 | 入口 | 说明 |
|---|---|---|
| PDMX→AMT | `core.score_ir_to_events` + `perf_to_amt` | 乐谱恒速→演奏事件→AMT；`lite=True` 出 AMT_lite |
| TAST_lite | `project(ir,"TAST_lite",tmap)` | TAST 去拼写(MIDI 音高)+时间戳 |
| AMT_lite | `perf_to_amt(notes,lite=True)` | 音高事件+时间戳，无力度/踏板 |
| DBD | `project(ir,"DBD",tmap,beats=None)` | 拍点/小节+时间戳，无音高；`beats` 可传 nASAP 标注 |
| DBD_lite | `core.ir_to_dbd_units(ir,lite=True)` | 纯拍流(待 Fig.2 确认，未入训练 prompt) |
| 从头训 | `build_model(...,from_scratch=True)` | 全权重随机化，对齐论文 |
| 方言 prompt | `build.DIALECT_PROMPT` | 已含 7 方言(除 DBD_lite)，多重集互异 |
| 装配数据集 | `data.assemble.assemble` / `scripts/build_dataset.py --dry-run` | 三份 labels(schema 不一)+音频 → RubatoDataset;不静默计数 |
