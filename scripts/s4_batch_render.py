"""
S4 batch render: MIDI → 16k Opus via sfizz. Tests render pipeline throughput.
"""
from __future__ import annotations
import json, sys, time, tempfile, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.render.core import render_midi_to_wav44, finalize, assign_source_and_preset
import yaml

ROOT = Path(r"D:\vscode_projects\ee_download")
MANIFEST = ROOT / "work" / "manifest_pieces.jsonl"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"


def load_configs():
    with open(CONFIG_DIR / "sources.yaml", 'r', encoding='utf-8') as f:
        sources = yaml.safe_load(f)
    with open(CONFIG_DIR / "recording_presets.yaml", 'r', encoding='utf-8') as f:
        presets = yaml.safe_load(f)
    return sources, presets


def render_one(midi_path: str, utt_id: str, sources, presets, out_dir: Path) -> dict:
    """Render one MIDI to Opus. Returns timing info."""
    t0 = time.time()
    src_id, preset_id = assign_source_and_preset(utt_id, sources, presets)
    source = sources["sources"][src_id]
    preset = presets["presets"][preset_id]

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        render_midi_to_wav44(str(midi_path), source, sources, wav_path, utt_id=utt_id,
                             timeout_s=float(sources["render"].get("timeout_s", 600)))
        opus_path = str(out_dir / f"{utt_id}.opus")
        finalize(wav_path, preset, sources, presets, utt_id, opus_path)
        elapsed = time.time() - t0
        return {"utt_id": utt_id, "elapsed_s": round(elapsed, 1), "source": src_id,
                "preset": preset_id, "opus_size": os.path.getsize(opus_path)}
    except Exception as e:
        return {"utt_id": utt_id, "error": f"{type(e).__name__}: {str(e)[:80]}",
                "elapsed_s": round(time.time() - t0, 1)}
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)


def main():
    sources, presets = load_configs()
    pieces = []
    with open(MANIFEST, 'r') as f:
        for line in f:
            p = json.loads(line.strip())
            if p.get("split") == "train" and p.get("midi_path"):
                pieces.append(p)

    print(f"Train pieces with MIDI: {len(pieces)}")

    # Render first 10 for throughput test
    N = 10
    out_dir = ROOT / "work" / "s4_test"
    out_dir.mkdir(parents=True, exist_ok=True)

    ok, fail = 0, 0
    total_time = 0
    for i, p in enumerate(pieces[:N]):
        midi = p["midi_path"]
        utt_id = f"s4_test_{i:03d}"
        print(f"[{i+1}/{N}] {utt_id} ... ", end="", flush=True)
        result = render_one(midi, utt_id, sources, presets, out_dir)
        if "error" in result:
            print(f"FAIL: {result['error']}")
            fail += 1
        else:
            print(f"OK {result['elapsed_s']}s ({result['source']}/{result['preset']})")
            ok += 1
            total_time += result["elapsed_s"]

    print(f"\nResults: {ok} ok, {fail} fail")
    if ok:
        print(f"Avg render time: {total_time/ok:.1f}s/piece")
        print(f"Throughput: {3600/(total_time/ok):.0f} pieces/hour")
        total_opus = sum(os.path.getsize(str(out_dir / f)) for f in os.listdir(str(out_dir)) if f.endswith(".opus"))
        print(f"Total Opus: {total_opus/1024:.0f} KB")


if __name__ == "__main__":
    main()
