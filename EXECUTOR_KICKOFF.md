# EXECUTOR_KICKOFF —— 直接粘给执行 agent 的开场白

> 用户:把下面这段整段复制发给本地执行 agent。

```
目标:先训出一个【能用的】模型,不追论文 1:1 复刻。所以走精简路径,别铺开。

先做:git fetch && git checkout claude/training-issues-diagnosis-9ygud6 && git pull。
然后读 PROMPT_FOR_EXECUTOR.md(它会让你去读 CORPUS_REGEN.md 等),读完先把
"哪个源喂哪个 dialect"复述给我,再动手。

这轮的范围(照此,别扩张):
- 热启动:build_model(from_scratch=False,默认)。不要从头训。
- 四方言混比:A2S .35 / A2S_lite .15 / TAST .20 / AMT .30。
- 不要开 PDMX→AMT、TAST_lite/AMT_lite/DBD —— 那些是对齐论文用的,能力已就绪,这轮先不碰。

执行顺序:
1. CORPUS_REGEN.md §0–3:旧语料/词表已作废(字形与切分变了),重生成 →
   装配 tok_corpus.txt(【只 A2S+A2S_lite,不去重】)→ train_unigram(vocab=8000)。
   过两条门才算完:① vocab 逼近 8000(reconcile learnable==3571)② split_rate<0.30。
2. PROMPT_FOR_EXECUTOR.md 第0d→1→2 步:build 模型(热启动)→ 取 100 首 MAESTRO 验
   AMT 训练能收敛(loss<0.05,贴最后 10 步数字)→ 四路全量训练(数据全备齐再开)。

一条红线(守不住就停下抓 bug,不接受降级):
- PDMX 过滤后应 ~5 万曲,不是 1 万几(composer 弱智过滤已删)。
- tokenizer vocab 应逼近 8000;触发 fallback = 语料又被丢了,排查别合理化。
- nASAP xml_id 匹配率应 0.9+,不是 1%。
这些不是为了复刻,是语料/词表一塌模型本身就训不好。

每步用"一句话 + 硬判据数字"汇报,代码/格式适配 commit+push 到分支,然后停下等我确认。
达不到判据就如实说"没达标"并按对应文档 FAIL 排查,不要粉饰成"通过"。
```
