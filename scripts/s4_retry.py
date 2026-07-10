"""S4 retry: render only missing opus files with 4 workers."""
from __future__ import annotations
import json, multiprocessing, sys, time, os, yaml
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.render.core import render_midi_to_wav44, finalize, assign_source_and_preset

ROOT = Path(r"D:\vscode_projects\ee_download")
OUT_DIR = ROOT / "work" / "pdmx_audio"
N_WORKERS = 24

with open("configs/sources.yaml", "r", encoding="utf-8") as f: sources = yaml.safe_load(f)
with open("configs/recording_presets.yaml", "r", encoding="utf-8") as f: presets = yaml.safe_load(f)

missing = []
with open(ROOT / "work" / "manifest_pieces.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        p = json.loads(line.strip())
        if p.get("split") == "train" and p.get("midi_path") and not p.get("render_skip"):
            opus_path = OUT_DIR / f'pdmx_{p["piece_id"]}.opus'
            if not opus_path.exists() or opus_path.stat().st_size == 0:
                missing.append(p)

print(f"Missing: {len(missing)} pieces, {N_WORKERS} workers")

def render_one(args):
    p, idx = args
    midi = p["midi_path"]; utt_id = f'pdmx_{p["piece_id"]}'
    opus_path = str(OUT_DIR / f"{utt_id}.opus")
    src_id, preset_id = assign_source_and_preset(utt_id, sources, presets)
    source = sources["sources"][src_id]; preset = presets["presets"][preset_id]
    wav_path = str(OUT_DIR / f"{utt_id}.wav")
    try:
        render_midi_to_wav44(midi, source, sources, wav_path, utt_id=utt_id, timeout_s=300)
        finalize(wav_path, preset, sources, presets, utt_id, opus_path)
        return (idx, True)
    except Exception:
        return (idx, False)
    finally:
        if os.path.exists(wav_path): os.unlink(wav_path)

if __name__ == "__main__":
    t0 = time.time()
    with multiprocessing.Pool(N_WORKERS) as pool:
        results = pool.map(render_one, [(p, i) for i, p in enumerate(missing)])
    elapsed = time.time() - t0
    ok = sum(1 for r in results if r[1])
    fail = len(results) - ok
    print(f"Done: {ok} ok, {fail} fail in {elapsed/60:.1f}m")
    print(f"Final opus: {len(list(OUT_DIR.glob('*.opus')))}")
