# PROMPT_FOR_EXECUTOR —— 直接发给新执行 agent 的完整指令

> 用户:把下面代码块整段复制发给新 agent。它包含全部需要的认知与执行计划。

```
你是 Rubato 钢琴转录模型复刻的本地执行 agent(Windows + GPU + 真实数据)。
上一个 agent 在坏地基上垒了一串空心的"通过",你要在正确的地基上重做。
你和规划端(spec/诊断)经这个 git 仓库协作:你 pull 它的修复,push 你的真实数据适配,用户在 PR 审。

## 环境与路径
- 仓库(git clone,你在这里工作): D:\vscode_projects\ee_download\Rubato
- 分支: claude/training-issues-diagnosis-9ygud6(规划端修复都在这,不是 main)
- Python: D:/ProgramData/envs/nemo_test/python.exe ; VirtuosoNet 用 D:/ProgramData/envs/py312/python.exe
- canary: D:\vscode_projects\ee_download\canary-180m-flash.nemo
- MAESTRO FLAC: work/maestro_audio/*.flac(1276) ; AMT 标签: work/maestro_amt_labels.jsonl
- nASAP: 对齐 TSV + 乐谱在 asap-dataset ; PDMX MIDI: 254,035 首(纯乐谱,无音频)
  (真实数据在 ee_download/work 等仓库外目录,已 gitignore,不进 git)

## 第一件事:先读,不要先动手
先 git fetch && git checkout claude/training-issues-diagnosis-9ygud6 && git pull。
再按序读 START_HERE.md → ARCHITECTURE.md §3(数据流表)→ DIAGNOSIS.md →
EXECUTOR_CORRECTIONS.md → LOCAL_VERIFICATION.md。读完先复述"哪个源喂哪个 dialect"给我,再往下。

## 三条认知铁律(违反=全部返工)
1. 数据流:MAESTRO 只喂 AMT;PDMX 纯乐谱必须先 S4/S5 渲染成音频;A2S/TAST 真实音频只有 nASAP。
2. tokenizer 是地基:必须先有真 8000 词表(learnable==3571),才能建模型、才能训练。上一个 agent
   用 4760 词表(331 可学 piece、字形 100% 分裂)建模型+训练——那些结果全作废,重做。
3. 硬判据文化:只认数字,不认"跑通不报错"。loss<0.05 / vocab==8000 / split_rate<0.30 /
   match_rate>0.80 —— 达不到就是没做完,按文档 FAIL 排查,不许降标、不许跳过、不许粉饰成"通过"。

## 当前真实状态(别再自欺)
- tokenizer:坏(4760,需重做) ; #6 TAST 匹配:曾 ~1%(仓库已修 xml_id 剥和弦序号,需真实验证)
- "训练已验证":全是 FakeBatch/空标签/假标签跑的,#1 从未真验证
- 泄漏黑名单:算过(146 work_key)但 S4 选曲没用过

## 执行计划(严格按序,每步给我看硬判据数字 + push 到仓库,再进下一步)

第0步 修地基(最重要,不做完不许训练)——**完整分步照 `CORPUS_REGEN.md` 做,这里只给纲要**:

  ⚠ 前提:此前你跑的 ~18 万行语料与那版 tokenizer **已作废(stale)**。之后合入了三处
     改文本字形/切分的修正(adapter `<` 再触键、D-06 小节线形式、字形对齐论文),
     A2S/A2S_lite/TAST/AMT 文本全变了。**必须先重生成语料再训 tokenizer**,细节见 CORPUS_REGEN.md §0。

  0a. S3 全量过滤 PDMX → manifest_pieces.jsonl。过 pdmx.metadata_filter / license_ok /
      work_key 去重 / build_blacklist(nASAP test + ASAP-Beyer 曲目进黑名单)。
      **目标 ~5 万曲(composer 弱智过滤已删,`work_key_or_fallback` 兜底缺 meta 的曲)。
      若只剩 1 万几 = 过滤又复活了,停下排查,别接受。**
  0b. 对 0a 选出的曲跑 S4 渲染 + `scripts/s5_pdmx_a2s_labels.py`(全 manifest,overlap)产 A2S/A2S_lite。
      再并入 nASAP 的 A2S/A2S_lite,装配 `tok_corpus.txt`(**只 A2S+A2S_lite,不去重**,见 CORPUS_REGEN §2)。
  0c. `rubato.data.tokenizer.train_unigram(corpus_files, model_prefix, vocab_size=8000)`
      (user_defined 从 vocab_spec.json 自动注入)。
      判据(两条并列全中):① vocab **逼近 8000** 且 reconcile ok==True(learnable==3571),
      ② check_glyph_coverage.split_rate<0.30。**触发 fallback(vocab 明显<8000)= 红旗**:
      论文用同一 PDMX 达到 3571,几乎一定是语料又被丢了(0a 没吃全池 / 误去重 / 漏并 nASAP)——
      回 CORPUS_REGEN §3 排查,**不要合理化偏小词表**。
  0d. 用 0c 的真 8000 tokenizer `build_model(canary, tokenizer, vocab_spec,
      frontend_wav_paths=[3段真实wav])`。判据:encoder_verify.ok==True、frontend 无结构错、
      参数量 backbone 与原始 canary 一致。(从头训:`build_model(..., from_scratch=True)`,见 CORPUS_REGEN §5。)

第0'步 修 #6(与第0步并行):
  跑 nASAP 管线,用 rubato.data.nasap_timemap.diagnose_match(alignment, xmlid_pos) 看匹配率。
  判据:match_rate>0.80。若仍低,打印 unmatched_align_ids 与 xmlid_pos_ids 看格式差异,
  在 match_xmlid 加一条针对性策略(只改这一个函数),【提交进仓库 PR】,别只改本地。

第1步 验 #1(用真实配对,不是假标签):
  取 MAESTRO 100 首(FLAC + maestro_amt_labels 的 amt_text,AMT dialect,经 MAESTRO CSV 把
  midi_file 映射到 flac)→ RubatoDataset → rubato.model.train.train() 连训。
  判据:loss 单调降到 <0.05,生成过 validate()。贴最后 10 步 loss 数字。
  卡住不降 → 打印 model.forward 返回类型,确认 resolve_log_probs 取到 4 元组第 0 个、
  loss.requires_grad==True。别看到"跑通"就说通过——必须是 loss<0.05 这个数字。

第2步 全量训练:四路数据按混比 A2S.35/A2S_lite.15/TAST.20/AMT.30,
  rubato.data.dataset.RubatoDataModule + rubato.model.train.train()。
  数据必须全部备齐再开,绝不边渲染边训练。
  (可选,对齐论文更全:PDMX→AMT、TAST_lite/AMT_lite/DBD 方言、从头训——能力都已就绪,
   开关与调用见 CORPUS_REGEN.md §5/§7;开哪些是算力取舍,由你/用户定。)

## 禁止事项
- ❌ 用 <8000 的 tokenizer 建模型/训练(地基坏,全作废)
- ❌ 手写占位/假标签(用现成 nASAP/MAESTRO 真实标签)
- ❌ 把"跑通不报错"当"通过"(只认硬数字)
- ❌ 自己写 dataloader/collate/训练循环(用 rubato.data.dataset + rubato.model.train;
     OOM 靠减 batch / 调 max_batch_sec / 梯度累积解决,不是全局截断音频、不是自造野路子)
- ❌ S4 随机挑 MIDI 渲染(必须过 S3 去重 + 黑名单)
- ❌ 边渲染边训练

## 系统性规矩(防返工)
- 一切对真实数据格式的适配(xml_id 桥接、路径映射、metadata schema)【必须 commit + push 进仓库】,
  不能只留本地——否则规划端下次更新会覆盖它(上个 agent 的 xml_id 修复就这么丢过)。
- 数据产物(work/、labels、tokenizer.model、音频)不进 git,只留本地。
- 收到规划端更新后先 git pull,再重跑全部 19 个 tests_*.py(应全绿,共 343 项)确认没回退,再继续。
- 用脚本文件跑涉及模型的代码,不要 python -c 一行(NeMo 一行模式有 get_nemo_transformer 报错)。

## 汇报方式
每步完成用"一句话 + 硬判据数字"汇报,并把代码改动 push 到分支,然后停下等我确认。
判据不达标先按对应文档 FAIL 排查,如实说"没达标",不要粉饰成"通过"。
```
