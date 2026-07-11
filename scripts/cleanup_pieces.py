"""
通用按曲清理 CLI —— 以后任何"把某些曲清掉"的需求都走这一个入口,禁止手删。

为什么:上次清理清了 .done 和段音频,但 _vn/ 的 mid+csv、_perf.mid/_whole.opus、标签行全漏了;
而且"清了"没有凭证。本工具按 rubato.data.cleanup.ARTIFACTS 穷举所有产物类别,清完自动输出
【验证表】(每类残留计数,全 0 = 干净)—— 把表贴回给用户,数字说话。

用法:
  python scripts/cleanup_pieces.py --ids-file reports/nonpiano_ids.txt          # 干跑:只报要清什么
  python scripts/cleanup_pieces.py --ids-file ... --apply                       # 清 + 验证
  python scripts/cleanup_pieces.py --pids id1 id2 --apply                       # 少量曲直接给 id
  python scripts/cleanup_pieces.py --ids-file ... --verify-only                 # 只验证(清没清干净)
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout
from rubato.data.cleanup import piece_files, purge_pieces, verify_pieces, format_verify

ROOT = Path(r"D:\vscode_projects\ee_download")


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="按曲清理全部产物 + 输出验证表(默认干跑)")
    ap.add_argument("--ids-file", default="", help="每行一个 piece_id(可带 \\t注释)")
    ap.add_argument("--pids", nargs="*", default=[])
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--text-labels", default=str(ROOT / "work" / "pdmx_a2s_labels.jsonl"))
    ap.add_argument("--vn-labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args(argv)

    pids = set(args.pids)
    if args.ids_file:
        for line in Path(args.ids_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                pids.add(line.split("\t")[0])
    if not pids:
        print("没有给任何 piece_id(--ids-file / --pids)。")
        return 2
    label_files = [(args.text_labels, ("pdmx_",)), (args.vn_labels, ("pdmxperf_",))]

    if args.verify_only:
        clean, counts = verify_pieces(pids, args.audio_dir, label_files)
        print(format_verify(clean, counts))
        return 0 if clean else 1

    if not args.apply:
        total = 0
        for pid in sorted(pids)[:5]:
            files = piece_files(Path(args.audio_dir), pid)
            n = sum(len(v) for v in files.values())
            total += n
            print(f"  {pid}: " + " ".join(f"{k}={len(v)}" for k, v in files.items() if v) or "无文件")
        print(f"干跑:{len(pids)} 曲待清(前 5 曲明细如上)。--apply 执行,清完自动验证。")
        return 0

    st = purge_pieces(pids, args.audio_dir, label_files)
    print("清理统计: " + " ".join(f"{k}={v}" for k, v in sorted(st.items())))
    clean, counts = verify_pieces(pids, args.audio_dir, label_files)
    print(format_verify(clean, counts))
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
