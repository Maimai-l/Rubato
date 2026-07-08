# 执行端纠正指引(读这份,优先级高于 LOCAL_VERIFICATION.md 的步骤顺序)

**触发**: 执行端出现四个错误——假标签训练、tokenizer 4798 当通过、数据没备好就开训、S4 绕过去重。
本文件纠正顺序与数据流认知。**先读 §1 数据流铁律,再按 §3 顺序做。**

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

## 7. 一句话给执行端

**你现在就有能训的真实数据(nASAP 15,353 + MAESTRO 1,276)。先用它们跑通 Step E 真过拟合(loss<0.05)证明 #1;同时后台把 S3 过滤+S4 渲染+PDMX 标签做到几十万行语料,再训 8000 tokenizer。数据备齐前不要开全量训练。**
