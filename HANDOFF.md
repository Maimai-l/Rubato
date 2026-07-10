# HANDOFF —— 当前状态与下一步(接手先读这一页)

分支:`claude/training-issues-diagnosis-9ygud6`。规划端(改代码/给指令)与执行端(Windows+GPU+真数据,
`D:\vscode_projects\ee_download\Rubato`)靠 git 协作。执行端【只跑不改】,规矩见 `RUN.md` 的 5 条死规定。

## 现在卡在哪(两层,第一层刚修完)
1. **【第一 BLOCKER,已修】GBK 编码崩溃**:执行端 Windows 控制台是 GBK,打印 '−'(预算行)
   直接 `UnicodeEncodeError` 崩进程 —— **S5 五次全崩在这,VN 一次没跑成**(见 `reports/s5_vn_issues.md`)。
   之前那些"OOM 修复"其实【从没被执行到】。已在 `8590ebc` 修好(见下)。
2. **【第二层,待验证】OOM**:主进程常驻 VN 泄漏,内存 60%→99%。修复已 push,但因为第 1 层没跑成,
   **还没在真机验证过**。修 GBK 后【现在才第一次真能验】。

## 诊断
- GBK:`platform.py` 只把文件 IO 硬化成 UTF-8,漏了 **stdout**。print 非 GBK 字符('−'、作曲家名
  'Fauré'、'♭')即崩;且 VNEngine `import virtuoso` 带出 wandb,其 console_capture 重包 stdout 再按
  GBK 编码 → 更崩。
- OOM:S4/S5 共用同一套 worker+预算渲染路径,S4 不炸 → 问题不在 worker。S5 唯一多的常驻物是
  【主进程 VirtuosoNet】。预算只管 worker 准入、回收只回收 worker,**都管不到主进程**。平滑爬升=主进程泄漏。

## 已 push 的修复(按提交)
- `8590ebc` **GBK 止血(第一 BLOCKER)**:`platform.harden_stdout()`(放宽 stdout 编码错误策略,
  中文照常、坏字符转义不崩)+ `quiet_wandb()`(关 wandb 的 stdout 拦截);s5/s4/memtrace/procmon 入口调用。
  证据 `tests_console.py` 7 ok:模拟 GBK stdout,打印 '−' 修前崩、修后不崩。
- `7c5e1d3` **主进程 VN 止血(OOM)**:每 20 曲 `empty_cache+gc`;每 100 曲【整体重建 VN 引擎】
  (`S5_GC_EVERY` / `S5_VN_RECYCLE`);每 25 曲打印【主进程 RSS】自诊断。新增 `scripts/memtrace.py`。
- `0a650e6` worker 回收 + 读一次切片 + CSV/no_grad 清理(修 worker 侧,非主因)。

## 下一步(唯一动作:用数据验证,别再猜)
执行端【两个终端同时】跑,把表贴回来(GBK 已修,这次应真能跑起来):
```
git pull
python scripts/s5_vn_render.py --limit 400          # 终端1(先看它别再崩 GBK;再看 vn_ok>0 / TAST>0)
python scripts/memtrace.py --interval 5             # 终端2
```
读 `main_VN_RSS_GB | n_workers | workers_RSS_sum_GB | sys_avail_GB`:
- **主进程 RSS 涨** → 确认主进程 VN 泄漏。重建应压住;若仍涨 `set S5_VN_RECYCLE=50` 再贴。
- **主进程平、workers 涨** → 在 worker,`set S5_TASKS_PER_CHILD=8` 或加大 `S5_RESERVE_GB`。
- **worker 数量暴涨** → 预算没收住,贴回来改代码。

若重建仍压不住(泄漏在 virtuoso 的 C 扩展/模块级全局,重建实例清不掉),下一招:
把 VN 推理搬到【可回收的子进程】里跑(每 N 曲整个进程重开),彻底斩断主进程累积。

## 全绿基线
所有 `tests_*.py` 通过(`tests_ops` 23、`tests_s5_pipeline` 12、`tests_ops_recycle` 6 等)。
改任何东西后先跑对应 test 再 push。
