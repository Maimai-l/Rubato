"""
抽听采样器 —— 把"用户用耳朵抓 bug"制度化:每个渲染/切割阶段完成后,随机抽 N 段音频
连同标签文本拷到一个文件夹,用户直接听 + 对照文本,5 分钟完成最高效的真值校验。
(历史上两个最严重的数据 bug —— 假 120bpm 分段、鼓谱混入 —— 都是用户听出来的,不是测试抓的。)

用法:
  python scripts/spot_check.py --labels work/pdmx_perf_labels.jsonl --n 5 --tag vn
  python scripts/spot_check.py --labels work/pdmx_a2s_labels.jsonl --n 5 --tag s4
输出:reports/spot_check_<tag>/ 下 N 组 <utt>.flac/.wav + <utt>.txt(标签文本+元信息)。
每次换 --seed 抽不同样本。SOP 驱动器在 P2d/P6d 自动跑,执行端把文件夹路径贴回,用户抽听。
"""
from __future__ import annotations
import argparse
import json
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout

ROOT = Path(r"D:\vscode_projects\ee_download")


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="随机抽 N 段音频+标签到 spot_check 文件夹供人工抽听")
    ap.add_argument("--labels", required=True)
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"),
                    help="行内无 audio_path 时按 <utt_id>.flac 在此目录找(S4 段)")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0, help="换个数字抽不同样本")
    ap.add_argument("--tag", default="check")
    ap.add_argument("--out", default="", help="默认 <ROOT>/reports/spot_check_<tag>")
    args = ap.parse_args(argv)

    out = Path(args.out) if args.out else ROOT / "reports" / f"spot_check_{args.tag}"
    out.mkdir(parents=True, exist_ok=True)
    audio_dir = Path(args.audio_dir)

    # 蓄水池采样:流式过标签,只保留 n 个候选(不载全文件)
    rng = random.Random(args.seed)
    picked: list[dict] = []
    seen = 0
    with open(args.labels, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            ap_ = row.get("audio_path")
            cand = Path(ap_) if ap_ else audio_dir / f"{row.get('utt_id', '')}.flac"
            if not cand.exists():
                continue
            seen += 1
            if len(picked) < args.n:
                picked.append({"row": row, "audio": cand})
            else:
                j = rng.randrange(seen)
                if j < args.n:
                    picked[j] = {"row": row, "audio": cand}

    for it in picked:
        row, src = it["row"], it["audio"]
        uid = row.get("utt_id", src.stem)
        shutil.copy2(src, out / (uid + src.suffix))
        meta = [f"utt_id: {uid}", f"audio: {src}",
                f"measure_range: {row.get('measure_range')}",
                f"score_range: {row.get('score_range')}", ""]
        for d in ("A2S", "TAST", "AMT"):
            if row.get(d):
                meta.append(f"--- {d}(前 500 字)---")
                meta.append(str(row[d])[:500])
                meta.append("")
        (out / f"{uid}.txt").write_text("\n".join(meta), encoding="utf-8")

    print(f"spot_check: 从 {seen} 个有音频的段中抽了 {len(picked)} 个 → {out}")
    for it in picked:
        print(f"  {it['row'].get('utt_id')}")
    print("【给执行端】把上面的文件夹路径贴回给用户;【给用户】逐段听 + 对照同名 .txt:"
          "速度自然?边界在小节线?内容对得上文本?任何异样直接指认 utt_id。")
    return 0 if picked else 1


if __name__ == "__main__":
    raise SystemExit(main())
