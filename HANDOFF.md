# HANDOFF —— 当前状态与下一步(接手先读这一页)

分支:`claude/training-issues-diagnosis-9ygud6`。规划端(改代码/给指令)与执行端(Windows+GPU+真数据,
`D:\vscode_projects\ee_download\Rubato`)靠 git 协作。执行端【只跑不改】,规矩见 `RUN.md` 的 5 条死规定。

## 现在卡在哪
**S5(VN 表现性渲染)内存一路涨到 OOM**,要手动停/重启。S4(直排)早跑完、从不 OOM。

## 诊断(已定位,未被数据最终确认)
S4 和 S5 用【同一套】worker+sfizz+内存预算渲染路径,S4 不炸 → 问题不在 worker 渲染。
S5 唯一多出来的常驻物是【主进程里的 VirtuosoNet 模型】。内存预算只管 worker 准入、
`max_tasks_per_child` 只回收 worker —— **都管不到主进程**。60%→99% 的平滑爬升 = 单个常驻进程泄漏
= 主进程 VN。这是本轮的核心修正(上一轮误以为是 worker,已纠正)。

## 已 push 的修复(按提交)
- `7c5e1d3` **主进程 VN 止血**:每 20 曲 `empty_cache+gc`;每 100 曲【整体重建 VN 引擎】清累积
  (`S5_GC_EVERY` / `S5_VN_RECYCLE`);每 25 曲打印【主进程 RSS】自诊断。新增 `scripts/memtrace.py`。
- `5e7fcc7` `RUN.md` 记录 worker 回收(Windows 默认 16 曲/进程回收)。
- `0a650e6` worker 回收 + 读一次切片 + CSV/no_grad 清理(修 worker 侧,非主因)。

## 下一步(唯一动作:用数据定位,别再猜)
执行端【两个终端同时】跑,把表贴回来:
```
git pull
python scripts/s5_vn_render.py --limit 400          # 终端1
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
