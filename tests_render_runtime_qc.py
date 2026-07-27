"""Runtime render QC wiring: new S4 outputs cannot pass on file existence alone."""
from __future__ import annotations

import tempfile
import time
from pathlib import Path

import rubato.render.core as core
import scripts.s4_parallel as s4
import scripts.c3_timbre_copies as c3


def test_render_qc_combines_duration_and_audibility():
    old_duration, old_silence = core.duration_check, core.silence_check
    try:
        core.duration_check = lambda path, expected, tol_s=1.5: {
            "ok": True, "actual_s": 10.0, "expected_s": expected, "diff_s": 0.0}
        core.silence_check = lambda path, gate_db=-60: False
        result = core.render_qc("x.mid", "x.opus")
        assert not result["ok"]
        assert result["audible"] is False
    finally:
        core.duration_check, core.silence_check = old_duration, old_silence


def test_s4_qc_failure_retries_once_then_succeeds():
    tmp = Path(tempfile.mkdtemp(prefix="s4_qc_retry_"))
    midi = tmp / "x.mid"
    midi.touch()
    attempts = {"render": 0, "qc": 0}
    originals = {
        name: getattr(s4, name)
        for name in ("load_configs", "assign_source_and_preset",
                     "render_midi_to_wav44", "finalize", "render_qc")
    }
    try:
        s4.load_configs = lambda: (
            {"sources": {"src": {"engine": "fake"}},
             "render": {"timeout_s": 1, "silence_gate_db": -60}},
            {"presets": {"pre": {}}, "weights": {"pre": 1.0}})
        s4.assign_source_and_preset = lambda *args: ("src", "pre")

        def fake_render(_midi, _source, _sources, wav, **kwargs):
            attempts["render"] += 1
            Path(wav).touch()

        def fake_finalize(_wav, _preset, _sources, _presets, _utt, opus):
            Path(opus).write_bytes(b"audio")

        def fake_qc(*args, **kwargs):
            attempts["qc"] += 1
            ok = attempts["qc"] == 2
            return {"ok": ok, "audible": ok, "diff_s": 0.0 if ok else 99.0}

        s4.render_midi_to_wav44 = fake_render
        s4.finalize = fake_finalize
        s4.render_qc = fake_qc
        result = s4.render_one((str(midi), "pdmx_x", str(tmp)))
        assert result["ok"] and result["attempts"] == 2, result
        assert attempts == {"render": 2, "qc": 2}
        assert (tmp / "pdmx_x.opus").is_file()
    finally:
        for name, value in originals.items():
            setattr(s4, name, value)


def test_s4_double_qc_failure_removes_bad_output():
    tmp = Path(tempfile.mkdtemp(prefix="s4_qc_fail_"))
    midi = tmp / "x.mid"
    midi.touch()
    originals = {
        name: getattr(s4, name)
        for name in ("load_configs", "assign_source_and_preset",
                     "render_midi_to_wav44", "finalize", "render_qc")
    }
    try:
        s4.load_configs = lambda: (
            {"sources": {"src": {"engine": "fake"}},
             "render": {"timeout_s": 1, "silence_gate_db": -60}},
            {"presets": {"pre": {}}, "weights": {"pre": 1.0}})
        s4.assign_source_and_preset = lambda *args: ("src", "pre")
        s4.render_midi_to_wav44 = (
            lambda _m, _so, _sc, wav, **kw: Path(wav).touch())
        s4.finalize = (
            lambda _w, _p, _sc, _pc, _u, opus: Path(opus).write_bytes(b"bad"))
        s4.render_qc = lambda *args, **kwargs: {
            "ok": False, "audible": False, "diff_s": 20.0}
        result = s4.render_one((str(midi), "pdmx_x", str(tmp)))
        assert not result["ok"] and result["attempts"] == 2, result
        assert not (tmp / "pdmx_x.opus").exists()
        assert "render_qc" in result["error"]
    finally:
        for name, value in originals.items():
            setattr(s4, name, value)


def test_second_timbre_render_also_runs_qc():
    import yaml

    tmp = Path(tempfile.mkdtemp(prefix="c3_qc_retry_"))
    midi = tmp / "x.mid"
    midi.touch()
    repo = Path(__file__).resolve().parent
    sources = yaml.safe_load(
        (repo / "configs" / "sources.yaml").read_text(encoding="utf-8"))
    presets = yaml.safe_load(
        (repo / "configs" / "recording_presets.yaml").read_text(encoding="utf-8"))
    src_id = next(iter(sources["sources"]))
    preset_id = next(iter(presets["presets"]))
    attempts = {"qc": 0}
    originals = {
        name: getattr(core, name)
        for name in ("render_midi_to_wav44", "finalize", "render_qc")
    }
    try:
        core.render_midi_to_wav44 = (
            lambda _m, _so, _sc, wav, **kw: Path(wav).touch())
        core.finalize = (
            lambda _w, _p, _sc, _pc, _u, opus: Path(opus).write_bytes(b"audio"))

        def fake_qc(*args, **kwargs):
            attempts["qc"] += 1
            ok = attempts["qc"] == 2
            return {"ok": ok, "audible": ok, "diff_s": 0.0 if ok else 20.0}

        core.render_qc = fake_qc
        result = c3._render_s2_task(
            (str(midi), "x", str(tmp), src_id, preset_id))
        assert result["ok"] and result["attempts"] == 2, result
        assert attempts["qc"] == 2
        assert (tmp / "pdmx_x_s2.opus").is_file()
    finally:
        for name, value in originals.items():
            setattr(core, name, value)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            started = time.time()
            try:
                fn()
                print(f"  ok {name} ({time.time() - started:.2f}s)")
            except Exception as exc:
                failures += 1
                print(f"  FAIL {name}: {type(exc).__name__}: {exc}")
    raise SystemExit(1 if failures else 0)
