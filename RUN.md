# RUN —— 执行端【只按这一张跑】

> ⚠【2026-07-11 起,当前任务 = 数据重跑】:先按 **SOP_RERUN.md** 的 P0→P7 顺序执行完毕,
> 那是现在唯一的作战顺序(带进度表、判据、贴回项)。本文件的分步命令是背景与判据参考。
> 其它 md(CORPUS_REGEN / OPS / SPEC …)是背景资料,跑的时候不用翻。

## 死规定(违反任何一条 = 你在拖慢进度,停)

1. **禁止改代码。** `scripts/` 和 `rubato/` 是最终版、已过 400+ 测试。你【不许】编辑、重写、
   "优化"、"简化"任何脚本或 rubato 模块 —— 一个字都不许改。你的唯一职责:**跑命令 + 贴数字**。
2. **禁止自己造脚本 / 造并发。** 不许写你自己的渲染循环、不许 `multiprocessing.Pool(N)`、
   不许改 worker 数写法。并发/内存已由脚本内部管好(内存预算调度)。
3. **报错就停 + 贴完整 traceback,等我修。** 不许"绕过"、不许猜着改。
   (前科:你把内存安全的 s4 改回 Pool(16) 又炸内存;这种事不许再发生。)
4. **调内存/速度只准用环境变量**(下面每条命令给了),【不许】改源码里的常量。
5. **一步一停:** `git pull` → 跑一条 → 贴硬判据数字 → 等我确认 → 下一条。不跳步、不并行开多阶段。

> 你不改代码,就不会再有内存回退、不会和规划端冲突、不会返工。有任何"我觉得应该改"的念头 → 先贴给我,我来改。

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
# 第5步 PDMX 表现性音频 + TAST(S5,VN 模型只加载一次,权重自动定位,【内存预算调度不 OOM】)
python scripts/s5_vn_render.py --limit 20    # 先 20 曲:判据 vn_ok>0、TAST>0;看打印的"渲染内存预算"行
python scripts/s5_vn_render.py               # 全量;.done 标记的曲自动跳过(可续跑)
# 【不用传 --vn-checkpoint】——脚本按 GUIDE §1 自动定位 virtuoso 标准权重。
# 【VN 泄漏的真正止血点】VN 模型现在跑在【可回收子进程】里:memtrace 实测 VN 模型驻主进程会以
#   ~1GB/5s 泄漏主机内存(RTX50/WDDM 驱动侧,Python 收不回),放子进程里、RSS 超 4GB 就 kill 重开,
#   OS 全额回收,主进程恒平。Windows 默认已开,你什么都不用做。看打印的"子进程模式"行 + 每 25 曲的
#   [mem] 主进程 RSS(应【平】,不再爬)。
# 【音源权重已按解码后大小算】FLAC 音源解码成 PCM 后 sfizz 实际 RSS ≈ 文件大小×2(你实测
#   ExperienceNY 6.9GB→12GB),权重已 ×2 修正 → ExperienceNY 同时只跑 1 个,不再放行 2 个炸掉。
# 【音源亲和】任务已按音源分组连续渲染:大 FLAC 页缓存保持热、加载快,同时段并发同质。
# 还炸内存?只调环境变量,别改代码:
#   set SF_DECODE_FACTOR=2.5       # 压缩音源解码倍率估计(默认2.0;实测 RSS 更高就调大)
#   set S5_VN_RSS_CAP_GB=3         # VN 子进程超 3GB 就回收(默认4;越小越稳、重载略勤)
#   set S5_RESERVE_GB=8            # 多留系统内存
#   set S5_TASKS_PER_CHILD=8       # 渲染 worker 回收更勤(默认16)
#   set S5_VN_INFER_TIMEOUT=300    # 单曲 VN 卡死超时(秒),超时杀重开、该曲续跑重试
# 三层都封了:VN 子进程(RSS cap,推理卡死时监控也能砍)+ 渲染 sfizz(解码后权重准入)
#   + 渲染 worker(max_tasks_per_child 回收)。若还炸,把 memtrace 表贴回来。

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
