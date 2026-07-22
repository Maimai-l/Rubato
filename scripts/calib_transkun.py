"""
校准全量第 2 步:对每个配对的整曲录音跑 Transkun 转写(断点续跑)。

输入:$WORK/calib_pairs.jsonl(第 1 步产物)
输出:$WORK/calib_full/{perf_id}.mid(已存在且非空则跳过 → 可反复重跑)

用法(执行端,在带 transkun 的现有环境;勿重装):
  python scripts/calib_transkun.py             # 全量
  python scripts/calib_transkun.py --limit 3   # 冒烟
transkun 不在 PATH 时:--transkun 指到其可执行文件。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("RUBATO_WORK")
            or (ROOT.parent / "work" if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download\work"))


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="批量 Transkun 转写校准录音(断点续跑)")
    ap.add_argument("--pairs", default=str(WORK / "calib_pairs.jsonl"))
    ap.add_argument("--out-dir", default=str(WORK / "calib_full"))
    ap.add_argument("--transkun", default="transkun", help="transkun 命令/路径")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    pp = Path(args.pairs)
    if not pp.exists():
        print(f"✗ 配对清单不存在: {pp}(先跑 scripts/calib_pairs.py)")
        return 1
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs = list(read_jsonl(pp))
    if args.limit:
        pairs = pairs[:args.limit]
    done = skip = fail = 0
    fails: list[str] = []
    for i, p in enumerate(pairs):
        mid = out_dir / f"{p['perf_id']}.mid"
        if mid.exists() and mid.stat().st_size > 0:
            skip += 1
            continue
        t0 = time.time()
        try:
            r = subprocess.run([args.transkun, p["flac"], str(mid)],
                               capture_output=True, text=True, errors="backslashreplace")
        except FileNotFoundError:
            print(f"✗ 找不到 transkun 命令: {args.transkun!r} —— 用 --transkun 指路,整段贴回")
            return 1
        if r.returncode == 0 and mid.exists() and mid.stat().st_size > 0:
            done += 1
            print(f"  ✓ [{i+1}/{len(pairs)}] {p['perf_id']}.mid "
                  f"({mid.stat().st_size} bytes, {time.time()-t0:.0f}s)")
        else:
            fail += 1
            fails.append(p["perf_id"])
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-3:]
            print(f"  ✗ [{i+1}/{len(pairs)}] {p['perf_id']} rc={r.returncode}")
            for ln in tail:
                print(f"      {ln}")
    print(f"转写完成: 新 {done} / 跳过 {skip} / 失败 {fail} (共 {len(pairs)})")
    if fails:
        print("失败清单: " + ", ".join(fails))
    return 0 if (done + skip) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
