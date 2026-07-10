"""S4 retry worker: render one chunk of missing MIDI files."""
from __future__ import annotations
import json, sys, time, os, yaml
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(str(REPO))  # SFZ paths in sources.yaml are relative to repo root
from rubato.render.core import render_midi_to_wav44, finalize, assign_source_and_preset

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=int, default=0)
    ap.add_argument("--total-chunks", type=int, default=24)
    args = ap.parse_args()

    ROOT = Path(r"D:\vscode_projects\ee_download")
    OUT_DIR = ROOT / "work" / "pdmx_audio"

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

    # Take this worker's slice
    n = len(missing) // args.total_chunks
    start = args.chunk * n
    end = start + n if args.chunk < args.total_chunks - 1 else len(missing)
    my_pieces = missing[start:end]

    ok = fail = 0
    t0 = time.time()
    for i, p in enumerate(my_pieces):
        midi = p["midi_path"]; utt_id = f'pdmx_{p["piece_id"]}'
        opus_path = str(OUT_DIR / f"{utt_id}.opus")
        src_id, preset_id = assign_source_and_preset(utt_id, sources, presets)
        source = sources["sources"][src_id]; preset = presets["presets"][preset_id]
        wav_path = str(OUT_DIR / f"{utt_id}.wav")
        try:
            render_midi_to_wav44(midi, source, sources, wav_path, utt_id=utt_id, timeout_s=300)
            finalize(wav_path, preset, sources, presets, utt_id, opus_path)
            ok += 1
        except Exception as e:
            fail += 1
            if fail <= 3:
                print(f"  FAIL[{utt_id}]: {type(e).__name__}: {str(e)[:120]}")
        finally:
            if os.path.exists(wav_path): os.unlink(wav_path)
        if (i + 1) % 100 == 0:
            print(f"  [{i+1}/{len(my_pieces)}] ok={ok} fail={fail} ({i/(time.time()-t0):.1f}/s)")
    print(f"DONE chunk={args.chunk}: ok={ok} fail={fail} in {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
