"""PDMX content-leakage certificate binding tests."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from scripts.build_dataset import (
    _file_fingerprint, verify_pdmx_leakage_certificate)
from scripts.certify_pdmx_leakage import (
    _build_ref_index, _cert_worker_init, _is_leaked_grams,
    _read_active_training_scope, _signature_only_ir,
)


def write_cert(path: Path, manifests: list[Path], status="pass",
               label_sources=None):
    rows = []
    for manifest in manifests:
        sha, n = _file_fingerprint(manifest)
        rows.append({"path": str(manifest), "sha256": sha, "rows": n})
    payload = {
        "status": status,
        "reason": "test",
        "leaked_count": 0,
        "target_parse_failed": 0,
        "reference_parse_failed": 0,
        "manifests": rows,
    }
    if label_sources is not None:
        payload["label_sources"] = []
        for src in label_sources:
            label = Path(src["path"]).resolve()
            sha, n = _file_fingerprint(label)
            payload["label_sources"].append({
                "path": str(label), "sha256": sha, "rows": n,
                "manifests": [
                    str(Path(p).resolve())
                    for p in (src.get("manifests") or [src["manifest"]])],
                "quarantine_unmapped": bool(
                    src.get("quarantine_unmapped", False)),
            })
    path.write_text(json.dumps(payload), encoding="utf-8")


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


def test_label_bytes_and_source_mapping_are_bound():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        manifest = root / "m.jsonl"
        labels = root / "labels.jsonl"
        manifest.write_text(
            '{"piece_id":"p","split":"train","work_key":"wk",'
            f'"xml_raw":"{str(root / "p.musicxml").replace(chr(92), chr(92) * 2)}"}}\n',
            encoding="utf-8")
        labels.write_text(
            '{"piece_id":"p","utt_id":"u","A2S":"x"}\n',
            encoding="utf-8")
        src = {
            "path": str(labels), "kind": "pdmx",
            "manifest": str(manifest),
        }
        cert = root / "cert.json"
        write_cert(cert, [manifest], label_sources=[src])
        verify_pdmx_leakage_certificate(
            [manifest], cert, label_sources=[src])
        labels.write_text(
            '{"piece_id":"p","utt_id":"u","A2S":"changed"}\n',
            encoding="utf-8")
        try:
            verify_pdmx_leakage_certificate(
                [manifest], cert, label_sources=[src])
            raise AssertionError("mutated labels were accepted")
        except ValueError as e:
            assert "labels/source 过期" in str(e)


def test_scope_uses_only_referenced_train_rows_after_blacklist():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        manifest = root / "m.jsonl"
        labels = root / "labels.jsonl"
        score = root / "score.musicxml"
        score.write_text("<score-partwise/>", encoding="utf-8")
        rows = [
            {"piece_id": "used", "split": "train", "work_key": "ok",
             "xml_raw": str(score)},
            {"piece_id": "unused", "split": "train", "work_key": "ok",
             "xml_raw": str(score)},
            {"piece_id": "validation", "split": "val", "work_key": "ok",
             "xml_raw": str(score)},
            {"piece_id": "blocked", "split": "train",
             "work_key": "external-eval", "xml_raw": str(score)},
        ]
        manifest.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8")
        label_rows = [
            {"piece_id": "used", "utt_id": "u", "A2S": "x"},
            {"piece_id": "validation", "utt_id": "v", "A2S": "x"},
            {"piece_id": "blocked", "utt_id": "b", "A2S": "x"},
        ]
        labels.write_text(
            "".join(json.dumps(row) + "\n" for row in label_rows),
            encoding="utf-8")
        source = {
            "path": str(labels), "kind": "pdmx",
            "manifest": str(manifest),
        }
        _manifests, label_records, targets = _read_active_training_scope(
            [source], [manifest], blacklist={"external-eval"})
        assert [row["piece_id"] for row in targets] == ["used"]
        assert label_records[0]["train_label_rows"] == 1
        assert label_records[0]["train_piece_ids"] == 1


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

    ir = _signature_only_ir(FakePart())
    assert len(ir.notes) == 2, "touching re-articulations must not merge"
    assert [str(note.dur) for note in ir.notes] == ["1/4", "1/4"]


def test_inverted_index_keeps_exact_jaccard_semantics():
    ref = frozenset({("a",), ("b",), ("c",), ("d",)})
    _cert_worker_init([ref], threshold=0.7)
    assert _is_leaked_grams(
        frozenset({("a",), ("b",), ("c",), ("d",), ("e",)}))
    assert not _is_leaked_grams(
        frozenset({("a",), ("x",), ("y",), ("z",)}))
    assert not _is_leaked_grams(frozenset({("x",), ("y",)}))
    index = _build_ref_index([ref])
    assert index[("a",)] == (0,)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print(f"全部通过: {len(tests)} 项")
