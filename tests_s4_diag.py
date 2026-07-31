"""s4_diag.collect 纯逻辑回归(合成 manifest/音频/MIDI)。运行: python tests_s4_diag.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from scripts.s4_diag import collect

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


tmp = Path(tempfile.mkdtemp())
audio = tmp / "pdmx_audio"
audio.mkdir()
midi = tmp / "midi"
midi.mkdir()
# p1 已渲(control);p2 待渲+MIDI 实存;p3 待渲+MIDI 缺失;p4 待渲+MIDI 零字节
(audio / "pdmx_p1.opus").write_bytes(b"x")
(midi / "p1.mid").write_bytes(b"m")
(midi / "p2.mid").write_bytes(b"m")
(midi / "p4.mid").write_bytes(b"")
mani = tmp / "manifest.jsonl"
with open(mani, "w", encoding="utf-8") as f:
    for pid, mp in [("p1", midi / "p1.mid"), ("p2", midi / "p2.mid"),
                    ("p3", midi / "p3.mid"), ("p4", midi / "p4.mid")]:
        f.write(json.dumps({"piece_id": pid, "midi_path": str(mp)}) + "\n")

r = collect(mani, audio)
print("[1] worklist 与 MIDI 存在性分类")
check("n_todo", r["n_todo"] == 3, r["n_todo"])
check("n_control", r["n_control"] == 1, r["n_control"])
check("missing", len(r["midi_missing"]) == 1 and r["midi_missing"][0].endswith("p3.mid"), r["midi_missing"])
check("zero", len(r["midi_zero"]) == 1 and r["midi_zero"][0].endswith("p4.mid"), r["midi_zero"])
check("ok", len(r["midi_ok"]) == 1 and r["midi_ok"][0]["piece_id"] == "p2", r["midi_ok"])

print(f"\n全部通过: {PASS} 项")
