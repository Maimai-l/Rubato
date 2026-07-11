"""
S4 离谱速度修复 —— MXL 编辑错误(如"四分音符=1")导致的荒谬渲染速度,钳制到 80bpm 后重渲。

一致性铁律:S4 音频由 MIDI 渲染,速度钳制【必须走"改写 MIDI → 删旧音频 → 重渲"】,
不能只改切割用的时间图(图和已渲音频会错位)。本脚本:
  干跑:扫描 manifest 里所有 MIDI 的 set_tempo,报告越界曲目(<--lo 或 >--hi bpm);
  --apply:越界 set_tempo 就地改写为 --fallback(原 MIDI 备份 *.tempo_orig.mid),
          删除对应整曲音频 pdmx_{pid}.opus → 之后重跑 s4_parallel.py 只重渲这些曲,
          再跑 s4_slice_segments.py(它读的是同一份钳制后 MIDI,图与音频天然一致)。

用法(执行端):
  python scripts/s4_fix_tempo.py                  # 干跑:报告
  python scripts/s4_fix_tempo.py --apply          # 实施
  python scripts/s4_parallel.py                   # 重渲被删音频的曲
  python scripts/s4_slice_segments.py             # 重新切段
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl
from rubato.data.midi_time import tempo_outliers, clamp_midi_tempo

ROOT = Path(r"D:\vscode_projects\ee_download")


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="检测/钳制 MIDI 离谱速度(MXL 编辑错误),钳后重渲")
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--lo", type=float, default=20.0, help="低于此 bpm 视为编辑错误")
    ap.add_argument("--hi", type=float, default=300.0, help="高于此 bpm 视为编辑错误")
    ap.add_argument("--fallback", type=float, default=80.0, help="钳制目标 bpm")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true", help="实施(默认只报告)")
    args = ap.parse_args(argv)

    audio_dir = Path(args.audio_dir)
    st = {"pieces": 0, "outlier_pieces": 0, "events_clamped": 0,
          "audio_deleted": 0, "midi_fail": 0}
    examples = []
    for p in read_jsonl(args.manifest):
        pid, midi_path = p.get("piece_id"), p.get("midi_path")
        if not (pid and midi_path):
            continue
        st["pieces"] += 1
        if args.limit and st["pieces"] > args.limit:
            st["pieces"] -= 1
            break
        try:
            bad = tempo_outliers(midi_path, args.lo, args.hi)
        except Exception:
            st["midi_fail"] += 1
            continue
        if not bad:
            continue
        st["outlier_pieces"] += 1
        if len(examples) < 10:
            examples.append((pid, bad[:4]))
        if args.apply:
            st["events_clamped"] += clamp_midi_tempo(midi_path, args.lo, args.hi, args.fallback)
            for ext in (".opus", ".flac", ".wav"):
                ap_ = audio_dir / f"pdmx_{pid}{ext}"
                if ap_.exists():
                    try:
                        ap_.unlink(); st["audio_deleted"] += 1
                    except OSError:
                        pass

    print(f"扫描 {st['pieces']} 曲:离谱速度(<{args.lo} 或 >{args.hi} bpm)的曲 = {st['outlier_pieces']},"
          f" MIDI 解析失败 = {st['midi_fail']}")
    for pid, bad in examples:
        print(f"  例: {pid}  bpm={bad}")
    if not args.apply:
        print("\n干跑结束(未改任何文件)。加 --apply 实施:钳到 "
              f"{args.fallback}bpm(原 MIDI 备份 *.tempo_orig.mid)+ 删旧整曲音频。")
        return 0
    print(f"\n已实施:改写 set_tempo {st['events_clamped']} 个,删整曲音频 {st['audio_deleted']} 个。")
    print("下一步:python scripts/s4_parallel.py(重渲这些曲)→ python scripts/s4_slice_segments.py(重切段)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
