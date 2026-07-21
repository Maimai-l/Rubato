"""
渲染质检 + 声学多样性审计(D47 阶段 C 第一枪,只读,CPU,可与训练并行)。

三件事,一次跑完,报告由代码写(reports/render_qc.md 追加):
  1) 时长对账 —— 把从未接线的 QC 门(rubato.render.core.duration_check,D45)补上:
     每首有 MIDI 且有整曲音频的曲,比较 实际时长 vs MIDI 末音时长,|差|>1.5s = 疑似截断。
  2) 音色分布 —— 用渲染期同一个确定性哈希(assign_source_and_preset)重算每曲的
     源/预设组合:量化"每曲恰一音色"的现状 + 五个音源的池间均衡。
  3) 整曲库存 —— maestro_audio 整曲 flac 数/小时数(C2 密集切窗的原料盘点)。

用法(执行端):
  python scripts/audit_render_qc.py            # 全量(时长对账 ~20 分钟)
  python scripts/audit_render_qc.py --limit 200  # 冒烟
"""
from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rubato.platform import harden_stdout, read_jsonl          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT.parent / "work" if (ROOT.parent / "work").exists() else ROOT / "work"


def _find_whole(piece_id: str, whole_dir: Path):
    """与 recall_explain 同一约定:pdmx_{pid}.opus/.flac/.wav。"""
    for ext in (".opus", ".flac", ".wav"):
        p = whole_dir / f"pdmx_{piece_id}{ext}"
        if p.exists():
            return p
    return None


def _audio_dur(path: Path):
    try:
        import soundfile as sf
        info = sf.info(str(path))
        return info.frames / float(info.samplerate)
    except Exception:
        return None


def _midi_dur(path: Path):
    try:
        import mido
        return float(mido.MidiFile(str(path)).length)
    except Exception:
        return None


def main() -> int:
    harden_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(WORK / "manifest_pieces.jsonl"))
    ap.add_argument("--whole-dir", default=str(WORK / "pdmx_whole"))
    ap.add_argument("--maestro-dir", default=str(WORK / "maestro_audio"))
    ap.add_argument("--sources", default=str(ROOT / "configs" / "sources.yaml"))
    ap.add_argument("--presets", default=str(ROOT / "configs" / "recording_presets.yaml"))
    ap.add_argument("--limit", type=int, default=0, help="只查前 N 曲(冒烟);0=全量")
    ap.add_argument("--tol", type=float, default=1.5, help="时长差阈值秒(duration_check 同款)")
    args = ap.parse_args()

    lines: list[str] = [f"\n## render QC 审计 @ {time.strftime('%Y-%m-%d %H:%M:%S')}"]

    # ---- 1) 时长对账(pdmx 整曲 vs MIDI)----
    pieces = []
    try:
        for row in read_jsonl(args.manifest):
            if row.get("midi_path"):
                pieces.append(row)
    except Exception as e:
        lines.append(f"  ✗ manifest 读取失败: {type(e).__name__}: {e}(路径 {args.manifest})")
        pieces = []
    if args.limit:
        pieces = pieces[: args.limit]
    n_checked = n_no_audio = n_no_mididur = 0
    truncs: list[tuple[str, float, float, float]] = []
    diffs: Counter = Counter()          # 差值分桶
    whole_dir = Path(args.whole_dir)
    for i, row in enumerate(pieces):
        pid = str(row.get("piece_id") or row.get("id") or "?")
        wav = _find_whole(pid, whole_dir)
        if wav is None:
            n_no_audio += 1
            continue
        exp = _midi_dur(Path(str(row["midi_path"])) if Path(str(row["midi_path"])).is_absolute()
                        else WORK / str(row["midi_path"]))
        if exp is None:
            n_no_mididur += 1
            continue
        act = _audio_dur(wav)
        if act is None:
            n_no_mididur += 1
            continue
        n_checked += 1
        d = act - exp
        bucket = "<-1.5s" if d < -args.tol else (">+1.5s" if d > args.tol else "±1.5s内")
        diffs[bucket] += 1
        if d < -args.tol:               # 音频比 MIDI 短 = 截断嫌疑(sfizz 超时被杀的指纹)
            truncs.append((pid, exp, act, d))
        if i % 2000 == 0:
            print(f"  时长对账 {i}/{len(pieces)}", flush=True)
    lines.append(f"  时长对账: 查={n_checked} 无整曲={n_no_audio} 读不出={n_no_mididur} "
                 f"分布: " + " ".join(f"{k}={v}" for k, v in sorted(diffs.items())))
    truncs.sort(key=lambda t: t[3])
    lines.append(f"  疑似截断(音频短于 MIDI >{args.tol}s): {len(truncs)} 曲"
                 + ("" if not truncs else " —— 最重 5 例:"))
    for pid, exp, act, d in truncs[:5]:
        lines.append(f"    - {pid}: MIDI={exp:.1f}s 音频={act:.1f}s 差={d:+.1f}s")

    # ---- 2) 音色分布(确定性哈希重算,与渲染期同函数)----
    try:
        import yaml
        from rubato.render.core import assign_source_and_preset
        scfg = yaml.safe_load(open(args.sources, encoding="utf-8"))
        pcfg = yaml.safe_load(open(args.presets, encoding="utf-8"))
        combos: Counter = Counter()
        for row in pieces:
            pid = str(row.get("piece_id") or row.get("id") or "?")
            try:
                # s4 整曲渲染的分配键 = f"pdmx_{pid}"(tests_rerender 同款口径)
                src, preset = assign_source_and_preset(f"pdmx_{pid}", scfg, pcfg)
                combos[f"{src}/{preset}"] += 1
            except Exception:
                combos["assign失败"] += 1
        lines.append(f"  音色分布(每曲恰 1 个确定性 源/预设 组合;组合种数={len(combos)}): "
                     + " ".join(f"{k}={v}" for k, v in combos.most_common(10)))
        lines.append("  · 与论文差距即在此:论文每曲 16 变体,我们每曲 1 个(C1/C3 的靶)")
    except Exception as e:
        lines.append(f"  音色分布: 跳过({type(e).__name__}: {e})—— 贴回本行,规划端修参数")

    # ---- 3) 整曲库存(C2 原料)----
    mdir = Path(args.maestro_dir)
    if mdir.exists():
        flacs = list(mdir.glob("*.flac"))
        hours = 0.0
        for i, f in enumerate(flacs):
            d = _audio_dur(f)
            hours += (d or 0.0) / 3600.0
            if args.limit and i >= args.limit:
                hours = hours * len(flacs) / max(i + 1, 1)   # 冒烟:外推估计
                break
        lines.append(f"  maestro_audio 整曲库存: {len(flacs)} 个 flac ≈ {hours:.0f} 小时"
                     f"(C2 密集切窗原料;论文用同池切出 804k AMT + 214k TAST)")
    else:
        lines.append(f"  maestro_audio 目录不存在: {mdir}")

    out = ROOT / "reports" / "render_qc.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n已追加 {out} —— git add + commit + push 即完成上报。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
