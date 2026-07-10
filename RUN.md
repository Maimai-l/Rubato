# RUN —— 执行端【只按这一张跑】

> 这是唯一的执行清单。其它 md(CORPUS_REGEN / OPS / SPEC …)是背景资料,跑的时候不用翻。

## 三条铁律(违反=返工 + 拖慢进度)

1. **代码是最终版、已测。你的活是【跑】+【报数字】,不是改代码。**
   `scripts/` 和 `rubato/` 里的脚本都通过了 400+ 项测试。**不要编辑、不要重写任何脚本。**
2. **脚本报错 → 贴完整 traceback 给我,停下等修。** 不要自己改脚本"绕过"——
   你上次把内存安全的 `s4_parallel.py` 改回 `Pool(16)` + 每 task 重读配置,又把内存搞爆了。
   自己改脚本 = 引入回归 + 和规划端冲突 + 拖慢整体。有问题我来改,你只管报。
3. **每步:`git pull` → 跑 → 贴数字 → 等确认 → 下一步。** 不要跳步、不要边渲染边训练。

需要更快/更省内存,用脚本【自带的 `--workers`/`--limit`】,不要动源码。

---

## 命令(按序,每条基本就一行)

```
# 第0步 拉最新(每次开工先做)
git fetch origin && git checkout claude/training-issues-diagnosis-9ygud6 && git pull

# 第1步 PDMX 过滤 → manifest(注意:产 manifest 的是 s3_filter_pdmx,不是 s3_full_filter)
python scripts/s3_filter_pdmx.py            # 判据:manifest ~5 万曲;若 1 万几→停,报我
# 第2步 去跨数据集泄漏(必须在 s5 前,否则测试集污染)
python scripts/s3_minhash_leakage.py

# 第3步 PDMX A2S/A2S_lite 文本(tokenizer 语料大头)
python scripts/s5_parallel.py               # 判据:processed ~几万;合并阶段流式不 OOM

# 第4步 PDMX 直排音频(S4)
python scripts/s4_parallel.py               # worker 数按内存自动定;跳过已渲;--workers N 可手动封顶
# 第5步 PDMX 表现性音频 + TAST(S5,VN 模型只加载一次)
python scripts/s5_vn_render.py --vn-checkpoint <你的 checkpoint_best.pt 路径> --limit 20
python scripts/s5_vn_render.py --vn-checkpoint <同上>   # 判据:vn_ok>0、TAST>0;先 --limit 20 验证再全量

# 第6步 nASAP(必须带输出参数,否则不落 labels)
python scripts/s7_full_nasap.py --out-labels work/nasap_labels.jsonl --out-corpus work/a2s_corpus.txt
# 判据:match_rate 0.9+;末行 successful/segments > 0
# 第7步 MAESTRO AMT
python scripts/gen_amt_labels.py            # 判据:处理曲数 ~1276

# 第8步 装配 tokenizer 语料(只 A2S+A2S_lite,不去重)→ 训 tokenizer
#   语料 = s5/s7 产出的 A2S+A2S_lite(a2s_corpus.txt);装配脚本见 CORPUS_REGEN §2
python -c "from rubato.data.tokenizer import train_unigram; \
print(train_unigram(['work/a2s_corpus.txt'],'work/rubato_spm',vocab_size=8000,spec_path='configs/vocab_spec.json'))"
# 判据:vocab_size=8000, fell_back=False, warning=None(代码已修 split_by_number,别自己调参)
python -c "from rubato.data.tokenizer import check_glyph_coverage as c; print(c('work/rubato_spm.model'))"
# 判据:split_rate<0.30

# 第9步 装配数据集自检(无 GPU 也能跑)
python scripts/build_dataset.py --dry-run   # 判据:每源 kept>0;pdmx 的 no_audio 不占大头

# 第10步 训练(热启动,四方言)
python scripts/build_dataset.py --tokenizer work/rubato_spm.model --nemo <canary.nemo>
```

## 监控 / 救火(另开一个终端)
```
python scripts/procmon.py watch --pattern sfizz    # 渲染时看 worker 数 + 内存
python scripts/procmon.py kill  --pattern sfizz --yes   # 内存爆了先杀
python scripts/s4_parallel.py --workers 6          # 再用更小并发重开(跳过已完成)
```

## 汇报格式(每步)
一句话 + 硬判据数字(如 "s5_parallel: processed=48213, corpus 39.9M chars")。
达不到判据就如实说"没达标 + 数字",别粉饰;报错就贴 traceback。**不要改脚本。**
