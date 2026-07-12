# [C] 失败 — 步骤C(可失败:flag 存在就 exit 1)
- time: 2026-07-12 09:06:19

## 日志尾部
```
  $ /usr/local/bin/python -c import sys,os; sys.exit(1 if os.path.exists(r'/tmp/tmpswnyk1mg/fail_flag') else 0)
```
