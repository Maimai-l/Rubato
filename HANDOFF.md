# HANDOFF —— 当前状态与下一步(接手先读这一页)

分支:`claude/training-issues-diagnosis-9ygud6`。规划端(改代码/给指令)与执行端(Windows+GPU+真数据,
`D:\vscode_projects\ee_download\Rubato`)靠 git 协作。执行端【只跑不改】,规矩见 `RUN.md` 的 5 条死规定。

## 现在卡在哪(两层,均已定位并修复,待真机复验)
1. **【第一 BLOCKER,已修】GBK 编码崩溃**:GBK 控制台打印 '−' 直接崩,**S5 五次全崩在这、VN 一次没跑成**。
   `8590ebc` 修好(`harden_stdout`+`quiet_wandb`,`tests_console` 证)。修了才第一次真能跑起来。
2. **【OOM,已用 memtrace 实锤 + 修】**:memtrace 数据(`reports/s5_vn_memleak_v2.md`)证明:VN 模型驻
   【主进程】时主机 RSS ~1GB/5s 稳涨(**GPU 显存却静态**→是 CUDA 驱动/WDDM 占的主机内存,RTX50 上),
   而 CLI(模型在子进程)主进程恒平。Python 侧 empty_cache/gc/重建对象都收不回(驱动侧、且是时间型不是每曲)。
   **修法 `e61bc4f`**:VN 跑在【可回收子进程】,RSS 超 `S5_VN_RSS_CAP_GB`(默4)即 kill 重开,OS 全额回收,
   主进程恒平;模型跨曲复用(比 CLI 每曲重载快);监控线程在渲染长等待期也盯着回收。

## 诊断
- GBK:`platform.py` 只把文件 IO 硬化成 UTF-8,漏了 **stdout**。print 非 GBK 字符('−'、作曲家名
  'Fauré'、'♭')即崩;且 VNEngine `import virtuoso` 带出 wandb,其 console_capture 重包 stdout 再按
  GBK 编码 → 更崩。
- OOM:S4/S5 共用同一套 worker+预算渲染路径,S4 不炸 → 问题不在 worker。S5 唯一多的常驻物是
  【主进程 VirtuosoNet】。预算只管 worker 准入、回收只回收 worker,**都管不到主进程**。平滑爬升=主进程泄漏。

## 已 push 的修复(按提交)
- `最新` **三修**(依据 s5_vn_worker_oom.md + memtrace.csv):
  ① `_slice_audio` NameError(拆函数漏 import soundfile,段级音频全写不出)——规划端引入的 bug,已修+回归;
  ② **VNSubprocess 监控被锁死**:memtrace 实锤 25GB 独占进程 = VN 子进程在某曲推理卡住期间泄漏,旧版
    infer() 全程握锁 → 监控 180s 进不来。重构:等待期不握锁 + gen 代号,监控【推理进行中也能砍】,
    卡死曲秒级判失败(续跑重试);psutil 缺失从静默 0.0 改为响亮警告。`tests_vn_subprocess` [5] 复现该场景;
  ③ **音源权重按解码后大小**(执行端发现,属实):FLAC→PCM 约 ×2(ExperienceNY 6.9GB→实测 12GB),
    `soundfont_weights` 压缩格式 ×`SF_DECODE_FACTOR`(默2.0)→ ExperienceNY 只放行 1 并发。s4 同源统一。
  另:S4/S5 任务按音源亲和排序(同音源连续渲,页缓存热、并发同质)。
- `e61bc4f` VNSubprocess(VN 驻可回收子进程);`8590ebc` GBK 止血;`e7d074b` 续跑按真标签;`0a650e6` worker 回收。

## 120bpm 假设的全部清算(用户拍板:S5 全量重跑)—— 当前最优先
旧版三处沿用"恒速 2s/全音符(120bpm)"假设,后果:①段长失控(快曲 0.2s 碎片/慢曲 93s 超窗);
②段长与真实速度负相关的分布偏置;③【S4 段音频配对根本没实现,且按假速换算切整曲音频必然错位】
(整曲音频是 MuseScore 真速度)。另:部分 MXL 有编辑错误(如"四分音符=1"),渲出荒谬速度。

已修(全部有测试):
- S5 VN:`segment_score(..., tmap=真tmap)` + 最短段守卫 + 行补 `measure_range`。
- S4:新 `rubato/data/midi_time.py` 从渲染所用 MIDI 提取【真实 set_tempo 速度图 + 拍号小节网格】;
  新 `scripts/s4_slice_segments.py` 据此把整曲音频切成与文本标签 measure_range 精确对齐的段 flac
  (结构不一致/越界段跳过并计数,不静默)。
- 离谱速度:`scripts/s4_fix_tempo.py` 把 <20 或 >300bpm 的 set_tempo 钳到 80bpm(原 MIDI 备份
  *.tempo_orig.mid)+ 删旧整曲音频待重渲。【铁律】钳制必须走"改 MIDI→重渲",不能只改切割图。

### 执行顺序(依次跑,每步结果贴回)
```
git pull
# — S5 VN 全量重跑(分段算法级修复,用户已拍板)—
python scripts/s5_repair_segments.py --all --apply   # 清全部 VN 行/段音频/.done(labels 留 .bak)
python scripts/s5_vn_render.py                       # 全量重渲(真 tmap 分段);另终端 memtrace 照旧
# — S4 速度钳制 + 段切割 —
python scripts/s4_fix_tempo.py                       # 干跑:看多少曲离谱速度(先贴报告)
python scripts/s4_fix_tempo.py --apply               # 钳到 80bpm + 删这些曲的整曲音频
python scripts/s4_parallel.py                        # 只重渲被删的曲(续跑机制)
python scripts/s4_slice_segments.py --limit 20       # 冒烟:看 sliced/skip 计数
python scripts/s4_slice_segments.py                  # 全量切段 → pdmx_audio/<utt_id>.flac
```
判据:S5 DONE 行 `过短段弃/无音频段弃` 小、不 OOM;S4 切割报告里 structure_mismatch 占比贴回来
(高 = MIDI 展开了反复,需另处理);抽听几段确认速度/边界自然。

## 全绿基线
所有 `tests_*.py` 通过(`tests_ops` 23、`tests_s5_pipeline` 12、`tests_ops_recycle` 6 等)。
改任何东西后先跑对应 test 再 push。
