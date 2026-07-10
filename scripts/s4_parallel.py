"""
S4 parallel batch render: MIDI → 16k Opus via sfizz.
Multi-worker pipeline test. Runs first N pieces then reports throughput.
"""
from __future__ import annotations
import json, sys, time, tempfile, os, multiprocessing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.render.core import render_midi_to_wav44, finalize, assign_source_and_preset
import yaml

ROOT = Path(r"D:\vscode_projects\ee_download")
MANIFEST = ROOT / "work" / "manifest_pieces.jsonl"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"
OUT_DIR = ROOT / "work" / "pdmx_audio"
N_WORKERS = 16
N_PIECES = 999999  # render all pieces


def load_configs():
    with open(CONFIG_DIR / "sources.yaml", 'r', encoding='utf-8') as f:
        sources = yaml.safe_load(f)
    with open(CONFIG_DIR / "recording_presets.yaml", 'r', encoding='utf-8') as f:
        presets = yaml.safe_load(f)
    return sources, presets


def render_one(args: tuple) -> dict:
    """Render one MIDI → Opus. Standalone for multiprocessing."""
    midi_path, utt_id, out_dir = args
    opus_path = str(Path(out_dir) / f"{utt_id}.opus")
    # Skip if already rendered (crash recovery)
    if os.path.isfile(opus_path) and os.path.getsize(opus_path) > 0:
        return {"utt_id": utt_id, "elapsed_s": 0, "source": "", "preset": "", "ok": True, "skipped": True}
    sources, presets = load_configs()
    t0 = time.time()

    src_id, preset_id = assign_source_and_preset(utt_id, sources, presets)
    source = sources["sources"][src_id]
    preset = presets["presets"][preset_id]

    wav_path = str(Path(out_dir) / f"{utt_id}.wav")
    try:
        render_midi_to_wav44(midi_path, source, sources, wav_path, utt_id=utt_id,
                             timeout_s=float(sources["render"].get("timeout_s", 600)))
        opus_path = str(Path(out_dir) / f"{utt_id}.opus")
        finalize(wav_path, preset, sources, presets, utt_id, opus_path)
        return {"utt_id": utt_id, "elapsed_s": round(time.time() - t0, 1),
                "source": src_id, "preset": preset_id, "ok": True}
    except Exception as e:
        return {"utt_id": utt_id, "error": f"{type(e).__name__}: {str(e)[:80]}",
                "elapsed_s": round(time.time() - t0, 1), "ok": False}
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    pieces = []
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        for line in f:
            p = json.loads(line.strip())
            if p.get("split") == "train" and p.get("midi_path"):
                pieces.append(p)

    print(f"S4 Parallel Render: {len(pieces)} train pieces, {N_WORKERS} workers, first {N_PIECES}")
    tasks = [(p["midi_path"], f"pdmx_{p['piece_id']}", str(OUT_DIR)) for p in pieces[:N_PIECES]]

    t0 = time.time()
    with multiprocessing.Pool(N_WORKERS) as pool:
        results = pool.map(render_one, tasks)
    elapsed = time.time() - t0

    ok = [r for r in results if r.get("ok")]
    fail = [r for r in results if not r.get("ok")]
    total_render = sum(r["elapsed_s"] for r in results)

    print(f"\n{'='*50}")
    print(f"Done: {len(ok)} ok, {len(fail)} fail in {elapsed/60:.1f}m")
    print(f"Wall clock: {elapsed/60:.1f}m for {N_PIECES} pieces")
    print(f"Throughput: {N_PIECES/(elapsed/3600):.0f} pieces/hour ({N_WORKERS} workers)")
    if ok:
        print(f"Avg single-piece render: {total_render/len(ok):.1f}s")
    if fail:
        print(f"Failures ({len(fail)}):")
        for f in fail[:5]:
            print(f"  {f['utt_id']}: {f.get('error')}")
    total_opus = sum(os.path.getsize(str(OUT_DIR / f)) for f in os.listdir(str(OUT_DIR)) if f.endswith(".opus"))
    print(f"Total Opus: {total_opus/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
