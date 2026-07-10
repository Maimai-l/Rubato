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
- `e61bc4f` **VN OOM 真修**:`VNSubprocess` —— VN 模型驻【可回收子进程】,RSS 超 cap 即 kill 重开
  (`S5_VN_RSS_CAP_GB` 默4;`S5_VN_INFER_TIMEOUT` 卡死超时;监控线程盯空闲期)。默认开;
  `S5_VN_INPROCESS=1` 退回旧内联(仅调试)。`tests_vn_subprocess.py` 7 ok(假子进程+注入 RSS,无需 GPU)。
- `8590ebc` **GBK 止血**:`harden_stdout`+`quiet_wandb`;`tests_console` 7 ok。
- `e7d074b` 续跑按【真有标签】判定,不靠 .done(旧 CLI 的 7514 个 .done 不再静默丢曲)。
- `0a650e6` 渲染 worker 回收 + 读一次切片 + CSV/no_grad 清理。

## 下一步(唯一动作:真机复验两层都平)
```
git pull
python scripts/s5_vn_render.py --limit 400          # 终端1:看"子进程模式"行;每25曲[mem]主进程RSS应【平】
python scripts/memtrace.py --interval 5             # 终端2:main_VN_RSS_GB 应不再爬
```
判据:`vn_ok>0`、`TAST>0`、跑完不 OOM、结尾 `vn_子进程回收=N次`(N>0 说明回收在起作用)。
- 若 `main_VN_RSS_GB` 仍缓慢爬(cap 之下的残留)→ `set S5_VN_RSS_CAP_GB=3` 更勤回收,再贴 memtrace。
- 若渲染 worker 侧涨 → `set S5_TASKS_PER_CHILD=8` 或加大 `S5_RESERVE_GB`。

## 全绿基线
所有 `tests_*.py` 通过(`tests_ops` 23、`tests_s5_pipeline` 12、`tests_ops_recycle` 6 等)。
改任何东西后先跑对应 test 再 push。
