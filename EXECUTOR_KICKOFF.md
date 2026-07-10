# EXECUTOR_KICKOFF —— 直接粘给执行 agent 的开场白

> 用户:把下面这段整段复制发给本地执行 agent。

```
目标:先训出一个【能用的】模型,不追论文 1:1 复刻,但【不放弃大部分训练数据】。

★ 执行清单只看 RUN.md 一张,按它的命令逐条跑。三条铁律(务必遵守):
  1. scripts/ 和 rubato/ 的代码是【最终版、已测 400+ 项】。你的活是【跑】+【报数字】,不是改代码。
  2. 脚本报错 → 贴完整 traceback,停下等我修。【不要自己改脚本/重写脚本绕过】——
     上次你把内存安全的 s4_parallel 改回 Pool(16) 又 OOM,还和规划端冲突、拖慢进度。
  3. 要更快/更省内存,用脚本自带的 --workers / --limit,不要动源码。

已定的决定(不用再问,照做):
  ① 热启动 warm-start(build_model(from_scratch=False))—— 我们没有从头训所需的算力。
  ② PDMX 全量用:S4 直排 + S5 VirtuosoNet 渲染都上(PDMX 是最大的源,必须进训练)。
  ③ 四方言混比 A2S .35 / A2S_lite .15 / TAST .20 / AMT .30。
  ④ 这轮不铺开的只有:PDMX→AMT、TAST_lite/AMT_lite/DBD(能力已就绪,后续再说)。

先做:git fetch && git checkout claude/training-issues-diagnosis-9ygud6 && git pull。
然后读 PROMPT_FOR_EXECUTOR.md(它会让你去读 CORPUS_REGEN.md 等),读完先把
"哪个源喂哪个 dialect"复述给我,再动手。

范围细节:
- 热启动:build_model(from_scratch=False,默认)。不要从头训(算力差一个量级,我们没有)。
- 四方言混比:A2S .35 / A2S_lite .15 / TAST .20 / AMT .30。
- **PDMX 是主力源,必须渲染音频进训练**:S4 直排(A2S/A2S_lite)+ S5 用【你本地的 VirtuosoNet】
  (`scripts/s5_vn_render.py`,调你的 `virtuoso` CLI,`--csv` 拿时间建 tmap → 表现性音频 + 匹配 TAST)。
  【别漏这步 —— 不渲染 PDMX = 丢掉最大的源,只剩 nASAP+MAESTRO。】
  humanize 仅在 VN 挂掉的曲上兜底(`--allow-humanize-fallback`,SPEC R-S5.9),默认不用。

执行顺序:
1. CORPUS_REGEN.md §0–3:旧语料/词表已作废(字形与切分变了),重生成 →
   装配 tok_corpus.txt(【只 A2S+A2S_lite,不去重】)→ train_unigram(vocab=8000)。
   过两条门才算完:① vocab 逼近 8000(reconcile learnable==3571)② split_rate<0.30。
   注意 §1.1b:**PDMX 要渲染音频**(S4 直排 + S5 `s5_vn_render.py` 调本地 VirtuosoNet),否则 PDMX 训练 0 贡献。
2. build_dataset.py --dry-run 验装配(每源 kept>0;pdmx 的 no_audio 不能占大头)→
   PROMPT_FOR_EXECUTOR.md 第0d→1→2 步:build 模型(热启动)→ 100 首 MAESTRO 验 AMT 收敛
   (loss<0.05)→ 四路全量训练(数据全备齐再开)。

一条红线(守不住就停下抓 bug,不接受降级):
- PDMX 过滤后应 ~5 万曲,不是 1 万几(composer 弱智过滤已删)。
- tokenizer vocab 应逼近 8000;触发 fallback = 语料又被丢了,排查别合理化。
- nASAP xml_id 匹配率应 0.9+,不是 1%。
这些不是为了复刻,是语料/词表一塌模型本身就训不好。

每步用"一句话 + 硬判据数字"汇报,代码/格式适配 commit+push 到分支,然后停下等我确认。
达不到判据就如实说"没达标"并按对应文档 FAIL 排查,不要粉饰成"通过"。
```
