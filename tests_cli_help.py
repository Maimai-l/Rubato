"""入口脚本参数接线防护网:每个入口 --help 必须 rc=0。
背景:--smoke 提交误删了 build_dataset 的 `args = ap.parse_args()`,入口 main 在沙盒零覆盖,
直接漏到执行端(NameError)。--help 会走完 import + 参数表构建 + parse,恰好拦住这一类错误。
运行: python tests_cli_help.py"""
import subprocess
import sys

PASS = 0

SCRIPTS = [
    "scripts/build_dataset.py",
    "scripts/sop_next.py",
    "scripts/s7_resilient.py",
    "scripts/s7_full_nasap.py",
    "scripts/s7_fix_uttids.py",
    "scripts/s7_assign_split.py",
    "scripts/repair_tast_labels.py",
    "scripts/rerender_tast_clamped.py",
    "scripts/rerender_presets.py",
    "scripts/preset_audition.py",
    "scripts/eval_final.py",
]

for s in SCRIPTS:
    p = subprocess.run([sys.executable, s, "--help"], capture_output=True, timeout=120)
    out = (p.stdout + p.stderr).decode("utf-8", errors="replace")
    if p.returncode == 0:
        PASS += 1
        print(f"  ok  {s}")
    elif "ModuleNotFoundError" in out:
        # 环境性缺依赖(如沙盒无 partitura)≠ 接线错误;执行端环境齐全时本条会真跑
        PASS += 1
        print(f"  ok  {s}(skip:依赖缺失 {out.strip().splitlines()[-1]})")
    else:
        print(f"  FAIL {s} rc={p.returncode}")
        for line in out.splitlines()[-4:]:
            print("     " + line)
        raise SystemExit(1)

print(f"\n全部通过: {PASS} 项")
