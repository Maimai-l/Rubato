"""
S6b MAESTRO AMT 切窗标签 —— 补上"整曲 AMT 标签没法训练"的缺口。

审计发现(与 S4 段切割同类的"配对没实现"):gen_amt_labels 产的是【整曲】AMT 文本
(几分钟长),而训练窗 ≤40s、AMT 目标窗 12–25s(R-S6.3)—— segment_amt/make_amt_label
库函数一直在,但【没有任何脚本调用】,占混比 0.30 的 AMT 数据实际配不成训练对。

本脚本:MAESTRO zip → 每场演奏 midi_to_events(真演奏秒,tempo 正确)→ segment_amt
(12–25s 智能切点:无发声音符且踏板抬起处)→ 每窗 make_amt_label(校验后)→ 行:
  {utt_id: maestro_<slug>_<wi>, midi_file, win: [t0,t1], AMT, split, n_notes}
音频【不切文件】:行带 win=[t0,t1](整曲坐标),assemble 直通、dataset.load_audio 按窗
帧级读取整曲 FLAC(resolve_audio 的 maestro 分支照旧用 midi_file→FLAC 映射)。

用法(执行端):
  python scripts/s6_amt_windows.py --limit 5      # 冒烟:5 场演奏,看 windows/labels 计数
  python scripts/s6_amt_windows.py                # 全量 → work/maestro_amt_windows.jsonl
build_dataset 的 maestro source 应指向本产物(整曲版 maestro_amt_labels.jsonl 弃用于训练,
仅留统计)。
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout
from rubato.data.maestro import midi_to_events
from rubato.data.segment import segment_amt, make_amt_label
from rubato.ops import auto_map
from scripts.gen_amt_labels import load_csv_rows, resolve_zip_member

_ZF: dict = {}      # 每个 worker 进程各持一个 zip 句柄(懒开,进程生命周期内复用)


def _win_task(t):
    """并行 worker:一场演奏 → MIDI 解析 → 12–25s 切窗 → AMT 校验标签行列表。
    每场 ~0.5-2s 纯 CPU × 1276 场 —— 并行后分钟级。返回 (rows, n_windows, n_fail) 。"""
    zpath, member, midi_filename, split, lo, hi, max_notes = t
    import zipfile as _zip
    zf = _ZF.get(zpath)
    if zf is None:
        zf = _ZF[zpath] = _zip.ZipFile(zpath)
    notes, pedal = midi_to_events(zf.read(member))
    base = _slug(midi_filename)
    rows, n_win, n_fail = [], 0, 0
    for wi, (win_notes, win_pedal, (w0, w1)) in enumerate(
            segment_amt(notes, pedal, target_lo=lo, target_hi=hi, max_notes=max_notes)):
        n_win += 1
        labels, _fails = make_amt_label(win_notes, win_pedal)
        if not labels.get("AMT"):
            n_fail += 1
            continue
        rows.append({"utt_id": f"maestro_{base}_{wi:03d}", "midi_file": midi_filename,
                     "win": [round(w0, 3), round(w1, 3)], "AMT": labels["AMT"],
                     "split": split, "n_notes": len(win_notes)})
    return rows, n_win, n_fail

ROOT = Path(r"D:\vscode_projects\ee_download")


def _slug(midi_file: str) -> str:
    return Path(midi_file).stem.replace(" ", "_")


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="MAESTRO 整曲 → 12–25s AMT 窗标签(win 坐标,不切音频文件)")
    ap.add_argument("--zip", default=str(ROOT / "maestro-v3.0.0-midi.zip"))
    ap.add_argument("--csv", default=str(ROOT / "maestro-v3.0.0.csv"))
    ap.add_argument("--out", default=str(ROOT / "work" / "maestro_amt_windows.jsonl"))
    ap.add_argument("--target-lo", type=float, default=12.0)
    ap.add_argument("--target-hi", type=float, default=25.0)
    ap.add_argument("--max-notes", type=int, default=160,
                    help="每窗音符预算(AMT ≈4-5 tok/音符,160 → 目标序列稳进 decoder 1024 位置表;"
                         "全量实测不预算时 78%% 的窗超限被丢)")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 场演奏(冒烟)")
    ap.add_argument("--workers", type=int, default=0, help="0=自动(核数,≤16)")
    args = ap.parse_args(argv)

    rows = load_csv_rows(args.csv)
    if args.limit:
        rows = rows[:args.limit]
    zf = zipfile.ZipFile(args.zip)       # 主进程只做 member 解析(namelist 查表,快)
    st = {"performances": 0, "windows": 0, "labels": 0, "win_fail": 0,
          "not_found": 0, "parse_fail": 0}
    tasks = []
    for row in rows:
        member = resolve_zip_member(zf, row["midi_filename"])
        if member is None:
            st["not_found"] += 1
            continue
        tasks.append((args.zip, member, row["midi_filename"], row.get("split"),
                      args.target_lo, args.target_hi, args.max_notes))
    zf.close()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    fo = open(out_path, "w", encoding="utf-8")

    def _write(_t, res):                 # 主进程单写者:并行结果即时落盘,不在内存累积
        out_rows, n_win, n_fail = res
        st["performances"] += 1
        st["windows"] += n_win
        st["win_fail"] += n_fail
        for r in out_rows:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
            st["labels"] += 1

    stats = auto_map(tasks, _win_task, workers=args.workers, on_result=_write, log_every=100)
    st["parse_fail"] += stats.get("failed", 0)
    fo.close()
    print(f"\nDONE in {time.time() - t0:.0f}s: " + " ".join(f"{k}={v}" for k, v in st.items()))
    print(f"  → {out_path}(行带 win=[t0,t1],加载时按窗读整曲 FLAC,不切文件)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
