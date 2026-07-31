"""【已废弃 — 禁止运行】此脚本是早期版本:写死并发、无内存预算、无音源解码权重,
运行会重现"24 worker × 大音源"的 OOM 事故。渲染一律用 scripts/s4_parallel.py(内存预算调度)。
原实现在 git 历史中(此文件被截断为守卫,防止误跑)。"""
import sys
print(__doc__)
sys.exit(2)
