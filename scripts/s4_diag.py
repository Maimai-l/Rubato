"""S4 全崩分诊(D36):3,480 曲 100% CalledProcessError。

"全崩"指向系统性前置条件,不是内存争抢(那是间歇杀手,不会 100% 齐崩)。
按嫌疑排序取证,不修不猜:

1.【头号嫌疑】这批曲历史上从未渲过 —— 若产 MIDI 的上游步骤(如 D7 tempo 钳制重写)
  当年也按 split=="train" 过滤,则它们的 midi_path 是"记了账没造货":文件缺失/零字节
  → sfizz 必崩,且恰好 100% 崩。→ 先 stat 全部 MIDI,零成本定案。
2.【环境对照】重渲 1 首"当年渲成功过"的曲到临时目录:它也崩 → 环境坏
  (sfizz/PATH/音源移动);它成功 → 环境无罪,问题在这批曲自身。
3. 取 2 首 MIDI 实存的失败曲,原样渲染并打印【完整 stderr】(报告 80 字符截断丢证据)。

用法(执行端,分钟级):python scripts/s4_diag.py
输出追加 reports/s4_diag.md(代码写,commit+push 即上报,勿编辑)。
"""
from __future__ import annotations
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout

harden_stdout()

ROOT = Path(r"D:\vscode_projects\ee_download")
MANIFEST = ROOT / "work" / "manifest_pieces.jsonl"
AUDIO_DIR = ROOT / "work" / "pdmx_audio"


def collect(manifest_path, audio_dir) -> dict:
    """纯逻辑(沙盒可测):worklist(缺 opus)与 control(有 opus)+ MIDI 存在性统计。"""
    audio_dir = Path(audio_dir)
    todo, control = [], []
    midi_missing, midi_zero, midi_ok = [], [], []
    with open(manifest_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            mp = p.get("midi_path")
            if not mp or not p.get("piece_id"):
                continue
            has_opus = (audio_dir / f"pdmx_{p['piece_id']}.opus").exists()
            (control if has_opus else todo).append(p)
            if not has_opus:
                mp_path = Path(mp)
                if not mp_path.exists():
                    midi_missing.append(mp)
                elif mp_path.stat().st_size == 0:
                    midi_zero.append(mp)
                else:
                    midi_ok.append(p)
    return {"n_todo": len(todo), "n_control": len(control),
            "midi_missing": midi_missing, "midi_zero": midi_zero, "midi_ok": midi_ok}


def _try_render(p: dict, out_dir: Path, lines: list, tag: str):
    from scripts.s4_parallel import load_configs
    from rubato.render.core import assign_source_and_preset, render_midi_to_wav44
    sources, presets = load_configs()
    uid = f"pdmx_{p['piece_id']}"
    src_id, _ = assign_source_and_preset(uid, sources, presets)
    wav = out_dir / f"{uid}.wav"

    def _p(s):
        print(s, flush=True)
        lines.append(s)

    _p(f"  [{tag}] {uid} midi={p['midi_path']} source={src_id}")
    try:
        render_midi_to_wav44(p["midi_path"], sources["sources"][src_id], sources,
                             str(wav), utt_id=uid, timeout_s=180)
        ok = wav.exists() and wav.stat().st_size > 0
        _p(f"  [{tag}] 渲染成功 wav={wav.stat().st_size if ok else 0}B")
    except Exception as e:
        _p(f"  [{tag}] 崩:{type(e).__name__}: {e}")
        for attr in ("stdout", "stderr"):
            v = getattr(e, attr, None)
            if v:
                if isinstance(v, bytes):
                    v = v.decode("utf-8", errors="replace")
                _p(f"  [{tag}] {attr} 尾部: {v[-800:]}")
        if not hasattr(e, "stderr"):
            _p(f"  [{tag}] traceback: {traceback.format_exc(limit=4)}")
    finally:
        if wav.exists():
            wav.unlink()


def main():
    lines = [f"\n## S4 全崩分诊 @ {time.strftime('%Y-%m-%d %H:%M:%S')}"]

    def _p(s):
        print(s, flush=True)
        lines.append(s)

    r = collect(MANIFEST, AUDIO_DIR)
    n_bad = len(r["midi_missing"]) + len(r["midi_zero"])
    _p(f"  待渲 {r['n_todo']} 曲 | MIDI 缺失={len(r['midi_missing'])} "
       f"零字节={len(r['midi_zero'])} 实存={len(r['midi_ok'])} | 已渲对照池={r['n_control']}")
    for mp in r["midi_missing"][:10]:
        _p(f"    缺失样例: {mp}")
    if n_bad and n_bad >= r["n_todo"] * 0.9:
        _p("  判定: ≥90% MIDI 缺失/零字节 → 全崩根因=上游 MIDI 从未生成(记账没造货),"
           "修法在产 MIDI 的步骤,不在渲染。")
    tmp = Path(tempfile.mkdtemp())
    import random
    rng = random.Random(0)
    if r["midi_ok"]:
        for p in rng.sample(r["midi_ok"], min(2, len(r["midi_ok"]))):
            _try_render(p, tmp, lines, "失败组样本")
    # 环境对照:挑一首已渲曲(MIDI 实存者)重渲到临时目录
    ctrl = None
    with open(MANIFEST, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p = json.loads(line)
            if (p.get("midi_path") and p.get("piece_id")
                    and (AUDIO_DIR / f"pdmx_{p['piece_id']}.opus").exists()
                    and Path(p["midi_path"]).exists()):
                ctrl = p
                break
    if ctrl:
        _try_render(ctrl, tmp, lines, "环境对照(当年渲成功过)")
    else:
        _p("  环境对照: 找不到 MIDI 实存的已渲曲,跳过")

    out = Path(__file__).resolve().parent.parent / "reports" / "s4_diag.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"报告已落盘 {out}(git add + commit + push 即上报,勿编辑)", flush=True)


if __name__ == "__main__":
    main()
