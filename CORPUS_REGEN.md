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

### 1.1 PDMX → A2S / A2S_lite（`scripts/s5_pdmx_a2s_labels.py`）

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

产出：`work/pdmx_a2s_labels.jsonl`（A2S/A2S_lite，TAST/AMT=null）、`work/a2s_corpus.txt`、`reports/s5_pdmx_a2s.json`。

### 1.2 nASAP → A2S / A2S_lite / TAST（`scripts/s7_full_nasap.py`）

真实音频对齐得到 tmap，产出带时间戳的 TAST（和无戳 A2S/A2S_lite）。**问题#6 的 xml_id 匹配已修**
（剥和弦后缀 `n2-1`→`n2` + LIS 单调化 + 锚点密度门）。

```bash
python scripts/s7_full_nasap.py
# 看报告里的匹配率诊断（diagnose_match）：match_rate 应【远高于】早期的 0.37%/1%，
# 正常应到 0.9+。若仍很低 → 停：打印两侧 id 样本看格式，别产出错锚点的坏 TimeMap。
```

产出：nASAP labels.jsonl（含 A2S/A2S_lite/TAST）、`reports/s7_full_nasap.json`。

### 1.3 MAESTRO MIDI → AMT（`scripts/gen_amt_labels.py`）

真实演奏 MIDI → AMT 事件文本（新字形 `<|0.00|>` / `<|vel:N|>` / `<|CC64:on/off|>`）。

```bash
python scripts/gen_amt_labels.py
# 看统计：处理曲数应 ≈ 1276（全 MAESTRO）。
```

产出：MAESTRO AMT labels.jsonl。

---

## 2. 装配 tokenizer 语料（四方言合一）

tokenizer 语料 = **训练侧全部非空方言文本，每条一行**（A2S + A2S_lite + TAST + AMT）。
`s5` 已经把 PDMX 的 A2S/A2S_lite 写进 `a2s_corpus.txt`；nASAP 的 TAST 和 MAESTRO 的 AMT 还在
各自的 labels.jsonl 里，需要抽出来。用下面这段一次性装配（无需新脚本）：

```python
# assemble_corpus.py —— 把所有 labels.jsonl 的非空方言文本抽成语料行
import json, glob, io
OUT = r"D:\vscode_projects\ee_download\work\tok_corpus.txt"
LABEL_JSONLS = [
    r"D:\vscode_projects\ee_download\work\pdmx_a2s_labels.jsonl",
    # nASAP labels.jsonl 路径,
    # MAESTRO AMT labels.jsonl 路径,
]
DIALECTS = ("A2S", "A2S_lite", "TAST", "AMT")
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

> 注意：**tokenizer 语料不做 work_key 去重**。去重只服务 train/val/test 隔离，
> 拿它砍 tokenizer 语料 = 白白丢 distinct 子串、把词表压小。论文没这么干。

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

### §一 与论文的偏离（需**你/用户拍板**的设计决策，不是 bug）
这些当前按 SPEC 的 deviation 记录，但外部 review 认为与论文正面冲突，请确认是否要改回论文做法：

1. **PDMX 不喂 AMT**：论文有 PDMX AMT（436k）。PDMX 是纯乐谱，要产 AMT 需先渲染成 MIDI/音频再抽事件。
   - 决策：要不要把 PDMX 也渲染进 AMT 通路？（工作量：接一条 score→MIDI→AMT 的渲染链）
2. **DBD / *_lite / TAST_lite / AMT_lite 方言未实现**（记为 deviation D3）。review 视其为论文能力缺失。
   - 决策：补齐还是保持精简方言集？
3. **热启动 vs 从头训**（deviation D1）：我们从 Canary-180M warm-start，论文从头训。
   - 决策：保持 warm-start（省算力、已记为有意偏离）还是对齐论文从头训？

> 这三条我不擅自改——它们改变训练规模与数据通路，属于你和用户的规划决策。上面每条都给了取舍，等你定。

---

## 6. 一句话流程

拉最新分支 → 删旧语料/词表 → s5(全池) + s7 + gen_amt → 装配 `tok_corpus.txt`（不去重）→
`train_unigram(vocab=8000)` → 过两条验收门（vocab≈8000 且 split_rate<0.30）→ 才 encode 标签、训模型。
任何一步数据量"莫名变少"就停下抓 bug，别接受降级。
