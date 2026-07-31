# Tokenizer 训练报告 —— 49.2万行语料，vocab 无法达标

## 语料信息
- `work/tok_corpus.txt`: 491,916 行（PDMX 468,886 + nASAP 23,030）
- 3,295,363 个 distinct space-separated tokens
- 41,555,786 个 total tokens
- 平均 token 长度 13.1 字符，分布在 3-32 字符
- A2S 格式示例: `|6/8k#2PR:A4 1/16a4G4 1/16g4 |6/8k#2F#4 1/8f#4A4`

## 实验 1 (默认参数)
```python
args = {
    'character_coverage': 1.0,
    'split_by_whitespace': True,
    'max_sentencepiece_length': 16,  # default
    # ... other defaults from rubato.data.tokenizer.train_unigram
}
```
- **vocab_size: 5148** (target 8000)
- **learnable_semantic: 719** (target 3571)
- **split_rate: 0.942** (target <0.30)
- sentencepiece 自动 fallback: 语料 distinct 子串不足，触发了 `allow_fallback=True` 中的 "set vocab <= 5148"

## 实验 2 (关闭 split_by_whitespace)
```python
args = {
    'character_coverage': 0.9995,
    'split_by_whitespace': False,  # 跨空格合并
    'max_sentencepiece_length': 32,
}
```
- **vocab_size: 8000** ✅
- **learnable_semantic: 3571** ✅
- **split_rate: 1.0** ❌ (100% 字形分裂)
- 所有 A2S 语义边界被破坏，`1/16A4G4` 和 `|4/4k0` 的片段被随机拼接

## 实验 3 (降低 char_coverage，保留 split_by_whitespace)
```python
args = {
    'character_coverage': 0.9995,
    'split_by_whitespace': True,
    'max_sentencepiece_length': 32,
}
```
- **RuntimeError**: "Vocabulary size too high (8000). Please set it to a value <= 5148."
- 与实验 1 同样的上限：语料支撑的最高 vocab 就是 5148

## 根因分析
`split_by_whitespace=True` 下，sentencepiece 把每个 A2S token（如 `1/16A4G4`=duration+和弦音符列表）当作不可分割的原子单词，只在其内部找子串。A2S 编码将 duration 和音符拼接成紧凑 token，导致 sentencepiece 可探索的子串组合极其有限。49 万行语料也填不满 3830 个可学槽位，Unigram 模型自动收敛到 5148。

如果把 `split_by_whitespace=False`，vocab 能到 8000，但是语义边界全毁——A2S 格式本就是以空格为 token 边界的。

## 等待规划端判断
1. 5148 vocab / 719 learnable 是否可用？如 A2S token 本身已是语义原子，是否足够？
2. 是否需要改 A2S 编码，把 duration 和音符分开（如 `1/16 A4 G4` 而非 `1/16A4G4`），增加可学子串空间？
3. 或者降 vocab_size 到 5000 并接受更小的模型？

## 模型文件
- `work/rubato_spm.model` (v1, vocab=5148)
- `work/rubato_spm_v2.model` (v2, vocab=8000, split_rate=1.0)
- `work/rubato_spm_v2.vocab`
