"""recall_explain 对账逻辑回归(合成 labels/manifest/音频目录)。运行: python tests_recall_explain.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
from scripts.recall_explain import explain

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
# 曲况:
#  p1 有整曲(不进对账);p2 清场遗留(无整曲,不在 manifest,段缺)→ A
#  p3 无整曲、不在 manifest、但段全在 → B;p4 在 manifest、无整曲、段缺 → C(矛盾)
#  p5 在 manifest、无整曲、段全在 → D
(audio / "pdmx_p1.opus").write_bytes(b"x")
(audio / "pdmx_p3_000.flac").write_bytes(b"x")
(audio / "pdmx_p5_000.flac").write_bytes(b"x")
labels = tmp / "labels.jsonl"
with open(labels, "w", encoding="utf-8") as f:
    for pid, uid in [("p1", "pdmx_p1_000"), ("p2", "pdmx_p2_000"), ("p2", "pdmx_p2_001"),
                     ("p3", "pdmx_p3_000"), ("p4", "pdmx_p4_000"), ("p5", "pdmx_p5_000")]:
        f.write(json.dumps({"piece_id": pid, "utt_id": uid}) + "\n")
manifest = tmp / "manifest.jsonl"
with open(manifest, "w", encoding="utf-8") as f:
    for pid in ("p1", "p4", "p5"):
        f.write(json.dumps({"piece_id": pid}) + "\n")

r = explain(labels, manifest, audio, audio)
print("[1] 缺整曲曲数与分类")
check("n_no_whole", r["n_no_whole"] == 4, r["n_no_whole"])
check("A_purged", [c[0] for c in r["cats"]["A_purged_stale"]] == ["p2"], r["cats"])
check("A_rows", r["rows"]["A"] == 2, r["rows"])
check("B_benign", [c[0] for c in r["cats"]["B_benign_no_manifest"]] == ["p3"], r["cats"])
check("C_conflict", [c[0] for c in r["cats"]["C_CONFLICT_in_manifest_missing"]] == ["p4"], r["cats"])
check("D_benign", [c[0] for c in r["cats"]["D_benign_in_manifest"]] == ["p5"], r["cats"])

print(f"\n全部通过: {PASS} 项")
