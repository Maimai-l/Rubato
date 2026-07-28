"""PDMX content-leakage certificate binding tests."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from scripts.build_dataset import (
    _file_fingerprint, verify_pdmx_leakage_certificate)
from scripts.certify_pdmx_leakage import _variable_division_signature_ir


def write_cert(path: Path, manifests: list[Path], status="pass"):
    rows = []
    for manifest in manifests:
        sha, n = _file_fingerprint(manifest)
        rows.append({"path": str(manifest), "sha256": sha, "rows": n})
    path.write_text(json.dumps({
        "status": status,
        "reason": "test",
        "leaked_count": 0,
        "target_parse_failed": 0,
        "reference_parse_failed": 0,
        "manifests": rows,
    }), encoding="utf-8")


def test_exact_bytes_pass_and_mutation_fails():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        manifest = root / "m.jsonl"
        manifest.write_text('{"piece_id":"p","split":"train"}\n',
                            encoding="utf-8")
        cert = root / "cert.json"
        write_cert(cert, [manifest])
        verify_pdmx_leakage_certificate([manifest], cert)
        manifest.write_text(
            '{"piece_id":"p","split":"train"}\n'
            '{"piece_id":"q","split":"train"}\n', encoding="utf-8")
        try:
            verify_pdmx_leakage_certificate([manifest], cert)
            raise AssertionError("mutated manifest was accepted")
        except ValueError as e:
            assert "过期" in str(e)


def test_manifest_set_and_failed_status_fail_closed():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a, b = root / "a.jsonl", root / "b.jsonl"
        a.write_text("{}\n", encoding="utf-8")
        b.write_text("{}\n", encoding="utf-8")
        cert = root / "cert.json"
        write_cert(cert, [a])
        try:
            verify_pdmx_leakage_certificate([a, b], cert)
            raise AssertionError("uncertified manifest was accepted")
        except ValueError as e:
            assert "集合不匹配" in str(e)
        write_cert(cert, [a], status="fail")
        try:
            verify_pdmx_leakage_certificate([a], cert)
            raise AssertionError("failed certificate was accepted")
        except ValueError as e:
            assert "未通过" in str(e)


def test_variable_divisions_use_normalized_quarter_map_only_for_signature():
    class FakePart:
        def __init__(self):
            self.notes_tied = [
                SimpleNamespace(
                    staff=1, midi_pitch=60,
                    start=SimpleNamespace(t=0),
                    end_tied=SimpleNamespace(t=1)),
                SimpleNamespace(
                    staff=1, midi_pitch=60,
                    start=SimpleNamespace(t=1),
                    end_tied=SimpleNamespace(t=4)),
            ]

        @staticmethod
        def quarter_map(t):
            # Simulates a divisions change: raw durations 1 then 3 both mean
            # one quarter note in normalized musical time.
            return {0: 0.0, 1: 1.0, 4: 2.0}[t]

    ir = _variable_division_signature_ir(FakePart())
    assert len(ir.notes) == 2, "touching re-articulations must not merge"
    assert [str(note.dur) for note in ir.notes] == ["1/4", "1/4"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print(f"全部通过: {len(tests)} 项")
