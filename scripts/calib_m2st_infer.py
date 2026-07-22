"""
M2ST 推理包装(校准线,D56)。为什么存在:
  1. M2ST 的 requirements 里 `muster @ git+.../amtevaluation.github.io` 对所有人都是坏的
     (该仓库是 MUSTER 评测工具的发布页,无 setup.py,master 分支不存在 —— 沙盒核实);
  2. utils.py 顶部 `from muster import muster` 却只在算它自家评测指标时用到(utils.py:23),
     我们要的推理链 quantize_path(tokenize→infer→detokenize→postprocess)不碰它。
处置:进程内注入一个【显式报错】的 muster 垫片 —— 不伪造行为:谁真调用该指标,当场
RuntimeError 说明原因。这是规划端批准的绕行,记录于 D56。

用法(执行端,用 venv_m2st 的 python):
  python scripts/calib_m2st_infer.py --m2st-dir D:\\vscode_projects\\ee_download\\m2st ^
      --ckpt D:\\vscode_projects\\ee_download\\m2st\\MIDI2ScoreTF.ckpt ^
      --midi rec1.mid rec2.mid rec3.mid ^
      --in-dir D:\\vscode_projects\\ee_download\\work\\calib_smoke ^
      --out-dir D:\\vscode_projects\\ee_download\\work\\calib_smoke
"""
from __future__ import annotations

import argparse
import sys
import types
from pathlib import Path


def install_muster_stub():
    """垫片:muster 指标不可得(上游包已断),推理不需要;误用时显式报错而非静默错值。"""
    m = types.ModuleType("muster")

    def _unavailable(*_a, **_k):
        raise RuntimeError("muster 指标未安装(上游 git 依赖对外已断,见 D56);"
                           "本包装只做 MIDI→MusicXML 推理,不计算该指标")

    m.muster = _unavailable
    sys.modules["muster"] = m
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m2st-dir", required=True, help="MIDI2ScoreTransformer 仓库根目录")
    ap.add_argument("--ckpt", required=True, help="MIDI2ScoreTF.ckpt 路径")
    ap.add_argument("--midi", nargs="*", default=None, help="输入 MIDI 文件名(相对 --in-dir)")
    ap.add_argument("--all-mids", action="store_true",
                    help="取 --in-dir 下全部 *.mid(全量校准用;已存在的输出 xml 跳过=断点续跑)")
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    if args.all_mids:
        args.midi = sorted(p.name for p in Path(args.in_dir).glob("*.mid"))
        if not args.midi:
            print(f"✗ {args.in_dir} 下没有 *.mid")
            return 2
    elif not args.midi:
        print("✗ 需要 --midi 名单或 --all-mids 二选一")
        return 2

    pkg = Path(args.m2st_dir) / "midi2scoretransformer"
    if not pkg.exists():
        print(f"✗ 找不到 {pkg} —— --m2st-dir 应指向仓库根(其下有 midi2scoretransformer/)")
        return 2
    sys.path.insert(0, str(pkg))
    install_muster_stub()

    import torch                                    # noqa: E402(venv 内)
    from utils import quantize_path                 # noqa: E402(m2st 包,垫片已就位)
    from models.roformer import Roformer            # noqa: E402

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"加载 ckpt({dev}): {args.ckpt}")
    model = Roformer.load_from_checkpoint(args.ckpt, map_location=dev)
    model.to(dev).eval()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n_ok = n_skip = 0
    for name in args.midi:
        src = Path(args.in_dir) / name
        dst = out_dir / (Path(name).stem + ".xml")
        if args.all_mids and dst.exists() and dst.stat().st_size > 0:
            n_skip += 1
            n_ok += 1
            continue
        try:
            score = quantize_path(str(src), model)
            score.write("musicxml", fp=str(dst), makeNotation=False)
            print(f"  ✓ {name} → {dst.name}({dst.stat().st_size} bytes)")
            n_ok += 1
        except Exception as e:
            import traceback
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
            traceback.print_exc(limit=6)
    print(f"完成: {n_ok}/{len(args.midi)} 个 MusicXML(其中续跑跳过 {n_skip})")
    return 0 if n_ok == len(args.midi) else 1


if __name__ == "__main__":
    raise SystemExit(main())
