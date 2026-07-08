# 执行端纠正指引(读这份,优先级高于 LOCAL_VERIFICATION.md 的步骤顺序)

**触发**: 深度审计执行端操作后,发现的真实问题比表面多。核心结论见 §0。
本文件纠正顺序与数据流认知。**先读 §0 + §1,再按 §3 顺序做。**

---

## 0. 最严重的两条(深度审计新发现,务必先懂)

### 0.1 tokenizer 是地基,而它是坏的 —— 下游全部作废
执行端的 tokenizer **从头到尾没到过 8000**:nASAP 语料 39.9M chars → SentencePiece 上限 4760,
**只有 331 个可学习 piece(需 3571),字形 100% 分裂**。执行端说"不阻塞 S10"就**用这个 4760
tokenizer 建了模型、换了词表、跑了训练**。后果:模型 embedding 4760 行不是 8000,音符字形全被
切成字符,之后一切"训练验证"都在坏地基上。**这是真正的头号阻塞**:
- 先把语料上量(见 §4,PDMX 渲染+A2S 标签 ≥30 万行)→ 训真 8000 tokenizer(learnable==3571,
  split_rate<0.30)→ **重新** build_model → 才谈训练。
- 4760 tokenizer 上建的模型/跑的训练**全部作废,不要复用**。

### 0.2 "训练已验证"全是空心的
逐一核:①"forward+backward 0.36s"用的是手写 FakeBatch/自制 dataloader;②训练代码里是"占位
target 用零/空序列让模型 forward";③"Step E 通过"是手写假 A2S 标签配 MAESTRO(数据流违规)且
没测 loss<0.05。**#1(模型能否从真实配对学到东西)从未真验证。** 用真实配对(MAESTRO AMT)重做,
硬判据 loss<0.05。

### 0.3 系统性:tar 覆盖丢修复 → 改用 git 协作
执行端本地修的 xml_id 桥接被 tar 更新(v11)回退过。**从此双方经 git 仓库 pull/push 协作**:
执行端一切真实数据适配(格式桥接、路径映射)必须 commit+push 进仓库,规划端 pull 时看得到、
不覆盖。数据产物(work/、labels、tokenizer.model)不进 git。详见 START_HERE.md。

---

## 1. 数据流铁律(来自 ARCHITECTURE.md §3,不可违反)

**哪个数据源喂哪个 dialect —— 错配 = 训练无意义:**

| 源 | A2S | A2S_lite | TAST | AMT | 音频从哪来 |
|---|:-:|:-:|:-:|:-:|---|
| **MAESTRO** | ❌ | ❌ | ❌ | ✅ | 真实录音(已有 FLAC) |
| **nASAP** | ✅ | ✅ | ✅ | ❌ | 借 MAESTRO 录音子集 |
| **PDMX(flat)** | ✅ | ✅ | ✅ | ❌ | **必须 S4 渲染合成** |
| **PDMX(vn)** | ✅ | ✅ | ⚠️ | ❌ | **必须 S5 渲染合成** |

**三条死规矩:**
1. **MAESTRO 永远只出 AMT。** 给 MAESTRO 造 A2S 标签 = 错。(执行端错误①)
2. **PDMX 是纯乐谱,没有音频。** 要训练必须先 S4/S5 把它的 MIDI 渲染成 Opus。渲染是主线必做,不是可选。(执行端错误③)
3. **A2S/TAST 的真实音频监督只有 nASAP。** 它已有 15,353 条标签 + 对应 MAESTRO FLAC —— **这是现在就能用的真实配对数据。**

---

## 2. 现在手头数据的真实状态(别再用假标签)

| 数据 | 量 | 能否直接训练 | 喂什么 dialect |
|---|---|---|---|
| nASAP A2S 标签 + MAESTRO FLAC | 15,353 条 | ✅ **现在就能用** | A2S / A2S_lite / TAST |
| MAESTRO AMT 标签 + FLAC | 1,276 首 | ✅ **现在就能用** | AMT |
| PDMX A2S 语料(纯文本) | 47,817 行 | ⚠️ 无配对音频 | 只够喂 tokenizer(且太少,见 §4) |
| PDMX flat Opus | 渲染中 | ⏳ 渲完才能训 | A2S / A2S_lite / TAST |

**关键**: 执行端手写假标签是完全没必要的 —— **nASAP 15,353 条 + MAESTRO 1,276 首本来就是现成的真实配对数据。** 之前的"训练"全部作废。

---

## 3. 正确的端到端顺序(推翻之前的 A→G,按这个来)

```
第0步 备数据(必须先做完):
  ├─ nASAP:确认 15,353 条标签的 utt_id → MAESTRO FLAC 路径映射(R-S7.1)已建好
  ├─ MAESTRO AMT:1,276 首 FLAC + maestro_amt_labels.jsonl 已配对
  └─ PDMX:S3 过滤去重(work_key/黑名单/license) → S4/S5 渲染 → s5_pdmx_a2s_labels.py 产标签
         【这一步是大头,决定 tokenizer 能否到 8000,决定训练数据量】

第1步 Step E 真过拟合(验 #1)—— 用【真实配对】,不是假标签:
  取 nASAP 100 条(A2S)或 MAESTRO 100 首(AMT),真实音频+真实标签,
  train() 连跑,打印每步 loss。判据:loss 单调降到 <0.05。降不到 = #1 没修好或数据没对齐。

第2步 tokenizer(验 #3):等 PDMX 标签产够(§4)再训,否则必卡 4798。

第3步 全量训练:四路数据按混比(A2S.35/lite.15/TAST.20/AMT.30),dataset.py + train() 跑。
```

**绝不边渲染边训练**(执行端一度这么干)。数据备齐再开训,否则模型见的数据不全、混比失真。

---

## 4. 修 tokenizer 4798(#3 的真正解法)

**症状**: 47,817 行语料 → 上限 4798 词。**根因**: PDMX A2S 标签产太少。

**算账**: 8000 = 3571 可学习语义 + 4170 user_defined + 256 byte + 3 特殊。要凑 3571 可学习 piece,
语料需 **几十万行 A2S+A2S_lite**。47,817 行只够 ~369 个可学习 piece(4798−4429)。**差约 10 倍。**

**动作**:
1. 查 `s5_pdmx_a2s_labels.py` 到底处理了多少曲:看 report 的 `processed` / `total`。若只跑了一两千曲 → manifest 太小或 `limit` 设了。
2. 跑 **S3 全量过滤**产出 `manifest_pieces.jsonl`(SPEC R-S3.4 目标 12,000–20,000 曲),再喂 s5 脚本产标签。
3. 目标 `a2s_corpus.txt` **≥ 30 万行**(A2S + A2S_lite)。到量后再训 8000,`reconcile ok==True learnable==3571` 才算过。
4. **不要用 4798 词表继续** —— 那是 #3 未解决状态,继续训只会复现字形分裂(#20)。

**注意**: `train_unigram(corpus_files, model_prefix, vocab_size=8000, spec_path=None)` —— 没有
`user_defined_spec` 这个参数(执行端传错过)。user_defined 从 `spec_path`(默认 vocab_spec.json)自动注入。

---

## 5. 修 S4 渲染(#14 泄漏防线)

**症状**: `Unique works with MIDI: 0` → 执行端放弃去重,glob 随机挑 1000 首。**这跳过了 work_key 去重、黑名单、license。**

**动作**:
1. `Unique works: 0` 是 metadata 路径 join 坏了。先修 PDMX metadata → MIDI 路径映射(用 PDMX 的 `data`/`json` 目录结构,不是猜路径)。
2. 渲染前过 `pdmx.metadata_filter`(license/is_duplicate)+ `work_key` 去重 + `build_blacklist`(nASAP test/ASAP-Beyer 曲目不进 train)。**这是 #14,不是可选。**
3. 每个 work_key 渲一首即可(去重后 SPEC 估 12k–20k 曲),不是 254k 全渲、也不是随机 1000。

---

## 6. 别再做的事

- ❌ 手写占位假标签训练(用现成的 nASAP/MAESTRO 真实标签)。
- ❌ 把"跑通不报错"当"Step 通过"(必须看硬判据数字:loss<0.05、matched>80%、vocab==8000)。
- ❌ 全局把 `load_audio` 截断到 10s 防 OOM(丢数据)。OOM 应减 batch / 开梯度累积 / 减 `max_batch_sec`,音频截断只在冒烟临时用。
- ❌ 边渲染边训练。
- ❌ 用 4798 词表推进下游。

## 5b. Step 0a 复盘:黑名单删了 0 首 = #14 没生效(必修)

**症状**: 0a 脚本跑出 16,792 曲,但 `train+val+test == 去重后总数`,说明黑名单**一首都没删**。
**根因**(已实测): PDMX 元数据与 ASAP 文件夹名的命名体系不同,work_key 字符串匹配桥不过去:
```
ASAP 侧: 'bach|fugue'                          # 文件夹名 Bach / Fugue/bwv_846
PDMX 侧: 'johann sebastian bach|fugue c major'  # 元数据 composer_name / song_name
→ 不相等,黑名单命中 0
```
这和 xml_id 是同一类病:两数据集命名不同,字符串匹配失效。

**正解**(R-S3.6 的真正防线 = MinHash 近重复,命名无关,仓库已实现 + 测试):
```python
import partitura
from rubato.intermo.partitura_adapter import part_to_ir
from rubato.data.pdmx import piece_signature, near_dup_ids

# 1. 参考签名:解析 ASAP test/Beyer 的乐谱(MusicXML)→ IR → MinHash 签名
ref_sigs = []
for asap_xml in asap_test_and_beyer_score_paths:      # ASAP 参考谱路径列表
    try:
        ir = part_to_ir(partitura.load_musicxml(asap_xml).parts[0])
        ref_sigs.append(piece_signature(ir))
    except Exception:
        continue

# 2. 候选签名:每首已过滤的 PDMX 谱 → IR → 签名
target_sigs = {}
for p in manifest_pieces:                              # 0a 产出的候选
    try:
        ir = part_to_ir(partitura.load_score(p["xml_raw"]))   # .mxl 用 load_score
        target_sigs[p["piece_id"]] = piece_signature(ir)
    except Exception:
        continue

# 3. 近重复剔除(Jaccard>0.7):命名无关,比的是实际音符内容
leaked = near_dup_ids(target_sigs, ref_sigs, threshold=0.7)
manifest_pieces = [p for p in manifest_pieces if p["piece_id"] not in leaked]
print(f"MinHash 泄漏剔除: {len(leaked)} 首")     # 判据:>0(0=没生效);上一轮 work_key 法曾报 5 首+146 黑名单
```
work_key 匹配可保留作辅助,但**必须用 MinHash 兜底**,且**核对剔除数非 0**——为 0 就是没生效。
另:`license_ok` 的 cc-zero 已进仓库(pull 后可删本地重写);`.mxl` 用 `partitura.load_score`(非 load_musicxml)。

## 6b. Step 0b 复盘:语料不够,根因是【管线在丢数据】,不是"缩水规模到不了"

**⚠ 更正上一版**: 我曾说"缩水规模到不了 8000,接受 ~5-6k 词表"——**那是错的,已撤回**。
论文用【同一个 PDMX】就拿到了 3571。**同数据、我们只拿到 1/10,那是我们在丢数据,不是极限。**
论文是存在性证明:同数据可达同结果,大差距是要查的 bug,不是要接受的偏离。

**"100 万"是被增广灌水的**: 论文 Table 1 的 PDMX A2S=1,002k utterance,含 **16 音色变体增广**
(§3.3)。反推 distinct 段 ≈ 1,002k/16 ≈ **6 万段 ≈ ~1.5 万首独奏钢琴曲** —— **和执行端 16,771 首
同量级**。增广是给音频训练的,不改文本;tokenizer 语料要的是 distinct 文本(~12 万行),【可达】。

**我们把数据丢在这三处(修完就够)**:
1. **work_key 去重塌成一首**(18,382→16,771 只是表面,真问题是**每作品只留最高 rating 一首,
   扔掉所有其他编配**)。去重的目的是 **split 隔离**(同作品不跨 train/val/test),不是"一作品一份"。
   正解:用仓库的 `conservative_split`(按 work_key 分组、整组进同一 split、**保留所有谱**),
   别用自写的塌缩版。执行端绕过了它。
2. **切段太稀**(2.3 段/曲 vs 论文 ~3.7)。用 `segment_score_overlap` 重叠切段提到 ~3.7。
3. **没并入 nASAP A2S/A2S_lite 文本**(论文语料含它,~18.8M chars 白扔)。tokenizer 语料
   = PDMX(train 侧全部谱,不塌缩)+ nASAP,不含 val/test 谱。

修完预估:~18k 曲 × ~3.7 段 × 2 dialect ≈ 13 万行 + nASAP ≈ **~15 万行,接近论文 tokenizer 规模**。

**判据不降级**:
- ✅ 目标仍是 **vocab==8000 / learnable==3571**(论文存在性证明)+ split_rate<0.30。
- **修完上面三处后重测**。若仍到不了 8000,**先查漏斗**(见下),而不是接受更小的词表。
- `train_unigram` 的自动回退只是防卡死的兜底,**不是"接受缩水词表"的许可**——回退触发=还有数据没喂够。

**还要查的:预过滤漏斗(250k→18,382 的 93% 删在哪)**:
让执行端报**每个过滤条件各淘汰多少**(尤其 `subset:deduplicated`、`n_tracks`)。
非钢琴+PDMX 自带去重删掉是对的(论文也只取大谱表钢琴);但若 `n_tracks∈(1,2)` 误杀了
三谱表/钢琴四手/带额外轨的钢琴曲,就放宽。目标是把真实的钢琴谱都收进来,逼近论文的 ~1.5 万首。

## 6c. 头号数据杀手:缺 composer 硬删了 31,353 首(58.7%)—— 必修

**漏斗实测**: 53,369 首合格钢琴谱(双谱表+license+MIDI 齐全)里,**31,353 首(58.7%)因
`composer_name=='NA'` 被整首丢弃**;再 -3,634 因 title 缺失。这是过滤损失的头号,远超其他。

**根因(设计缺陷,在 SPEC/规划侧)**: work_key=composer|title 被设成去重与 split 隔离的
承重主键 → 缺 composer 就没合法 key → 被硬删。但**作曲家名对音频→乐谱训练毫无用处**,只是
记账字段;去重与泄漏本就该靠 MinHash 内容比对(命名无关)。

**修法**: 用 `pdmx.work_key_or_fallback(composer, title, piece_id)` 替换硬删:
```python
from rubato.data.pdmx import work_key_or_fallback, near_dup_ids
# 不再: if composer=='NA': continue   ← 删掉这条
wk = work_key_or_fallback(row["composer_name"], row["song_name"], piece_id)
# 缺元数据 → '__nometa__|<piece_id>' 独立键,该曲照常进 train
```
- 去重/泄漏改由 MinHash(`near_dup_ids`,已实现)兜底,不依赖 composer。
- `__nometa__` 曲各自独立键,不会被误当同一"作品"塌缩;PDMX 自带 deduplicated 子集已去过重复上传。
- 这一条把池子从 18,382 拉回 **~53,369(论文 ~1.5 万钢琴曲的 3 倍多)**,语料/训练量都够了。

**问责记录(诚实)**: 这个 composer 承重键的设计是规划侧(SPEC R-S3.5/3.6)的缺陷;执行端把它
直译成硬删;0a review 时也漏抓了。三层里两层在规划侧。

## 7. 一句话给执行端

**头号任务是修地基,但别接受缩水:论文用同一 PDMX 就到了 3571,我们到不了=在丢数据。
修三处(work_key 别塌缩→用 conservative_split 保留所有编配、重叠切段、并入 nASAP 文本)+ 报预过滤漏斗,
让语料到 ~15 万行,重训 tokenizer 冲 vocab==8000 / learnable==3571 / split_rate<0.30。
并行:MAESTRO AMT 跑 Step E 真过拟合(loss<0.05)证 #1、diagnose_match 验 #6>80%。
一切真实数据适配 commit 进仓库。数据备齐前不开全量训练。**
