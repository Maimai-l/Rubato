"""钳制 TAST 定点重渲回归:证据取自 .bak、整曲清场(混合曲全清)、无关曲全保、残留 0。
运行: python tests_rerender_tast.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import scripts.rerender_tast_clamped as rc

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
aud = tmp / "audio"
aud.mkdir()
lab = tmp / "pdmx_perf_labels.jsonl"
bak = lab.with_suffix(".bak")

CLAMPED = "<|39.99|>x <|39.99|>y"          # 全钳常数戳(bug 产物)
OK = "<|0.00|>x <|1.50|>y"

# 修复前原件(.bak):A 曲全钳;B 曲正常;C 曲混合(c0 正常 + c1 钳)
bak_rows = [
    {"utt_id": "pdmxperf_A_000", "piece_id": "A", "TAST": CLAMPED, "A2S": "a"},
    {"utt_id": "pdmxperf_B_000", "piece_id": "B", "TAST": OK, "A2S": "a"},
    {"utt_id": "pdmxperf_C_000", "piece_id": "C", "TAST": OK, "A2S": "a"},
    {"utt_id": "pdmxperf_C_001", "piece_id": "C", "TAST": CLAMPED, "A2S": "a"},
]
# 当前文件(P2e 修复后):钳制行 TAST 已置 null
cur_rows = [dict(r, TAST=None) if r["TAST"] == CLAMPED else dict(r) for r in bak_rows]
bak.write_text("\n".join(json.dumps(r) for r in bak_rows) + "\n", encoding="utf-8")
lab.write_text("\n".join(json.dumps(r) for r in cur_rows) + "\n", encoding="utf-8")
for pid in ("A", "B", "C"):
    (aud / f"pdmxperf_{pid}_000.wav").write_bytes(b"x")
    (aud / f"{pid}.done").touch()
(aud / "pdmxperf_C_001.wav").write_bytes(b"x")

base = ["--labels", str(lab), "--audio-dir", str(aud)]

print("[1] 干跑:圈定 A/C 两曲(证据来自 .bak),不改任何文件")
check("dry_rc0", rc.main(base) == 0)
check("dry_untouched", (aud / "pdmxperf_A_000.wav").exists() and len(
    [l for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]) == 4)
pids, st = rc.find_affected(lab)
check("affected_from_bak", pids == {"A", "C"} and st["bad_rows"] == 2, (pids, st))

print("[2] --apply:A/C 整曲清场(含 C 的正常段 c0),B 全保,残留 0")
check("apply_rc0", rc.main([*base, "--apply"]) == 0)
left = [json.loads(l) for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]
check("only_B_rows", [r["utt_id"] for r in left] == ["pdmxperf_B_000"], left)
check("A_files_gone", not (aud / "pdmxperf_A_000.wav").exists() and not (aud / "A.done").exists())
check("C_files_gone", not (aud / "pdmxperf_C_000.wav").exists()
      and not (aud / "pdmxperf_C_001.wav").exists() and not (aud / "C.done").exists())
check("B_files_kept", (aud / "pdmxperf_B_000.wav").exists() and (aud / "B.done").exists())
check("first_bak_preserved", json.loads(bak.read_text(encoding="utf-8").splitlines()[0])["TAST"] == CLAMPED)

print("[3] 幂等:重跑干跑 —— A/C 行已purge,.bak 证据仍在但当前无行可清 → 文件数 0")
check("rerun_rc0", rc.main(base) == 0)
pids2, _ = rc.find_affected(lab)
check("evidence_stable", pids2 == {"A", "C"})   # 证据源不变;清场后无残留行/文件,apply 无副作用
n_files = sum(len(rc._files_s5(aud, p)) for p in pids2)
check("no_residual_files", n_files == 0, n_files)

print(f"\n全部通过: {PASS} 项")
