"""钳制 TAST 定点重渲回归(证据修正版):证据=活文件 TAST=null 行(不信 .bak),
待渲侧车防清完就崩、渲回自动消账;整曲清场;无关曲全保;残留 0。
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
OK = "<|0.00|>x <|1.50|>y"

# 活文件(P2e 修复后):A 曲 TAST 全 null;B 曲正常;C 曲混合(c0 正常 + c1 null)。
# 陈旧 .bak 故意放一份【全正常】的老世代文件 —— 证据链绝不能再读它(读了就是 affected=0 翻车)。
cur_rows = [
    {"utt_id": "pdmxperf_A_000", "piece_id": "A", "TAST": None, "A2S": "a"},
    {"utt_id": "pdmxperf_B_000", "piece_id": "B", "TAST": OK, "A2S": "a"},
    {"utt_id": "pdmxperf_C_000", "piece_id": "C", "TAST": OK, "A2S": "a"},
    {"utt_id": "pdmxperf_C_001", "piece_id": "C", "TAST": None, "A2S": "a"},
]
lab.write_text("\n".join(json.dumps(r) for r in cur_rows) + "\n", encoding="utf-8")
lab.with_suffix(".bak").write_text(
    json.dumps({"utt_id": "old_gen", "piece_id": "OLD", "TAST": OK, "A2S": "a"}) + "\n",
    encoding="utf-8")
for pid in ("A", "B", "C"):
    (aud / f"pdmxperf_{pid}_000.wav").write_bytes(b"x")
    (aud / f"{pid}.done").touch()
(aud / "pdmxperf_C_001.wav").write_bytes(b"x")

base = ["--labels", str(lab), "--audio-dir", str(aud)]
sc = rc._sidecar(lab)

print("[1] 证据=活文件 null 行:圈定 A/C;陈旧 .bak 被无视;干跑不动文件")
pids, st = rc.find_affected(lab)
check("affected_live", pids == {"A", "C"} and st["live_null_rows"] == 2, (pids, st))
check("bak_ignored", "OLD" not in pids)
check("dry_rc0", rc.main(base) == 0)
check("dry_untouched", (aud / "pdmxperf_A_000.wav").exists() and not sc.exists())

print("[2] --apply:先写意向侧车,再整曲清场(含 C 的正常段),B 全保,残留 0")
check("apply_rc0", rc.main([*base, "--apply"]) == 0)
left = [json.loads(l) for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]
check("only_B_rows", [r["utt_id"] for r in left] == ["pdmxperf_B_000"], left)
check("A_files_gone", not (aud / "pdmxperf_A_000.wav").exists() and not (aud / "A.done").exists())
check("C_files_gone", not (aud / "pdmxperf_C_000.wav").exists()
      and not (aud / "pdmxperf_C_001.wav").exists() and not (aud / "C.done").exists())
check("B_files_kept", (aud / "pdmxperf_B_000.wav").exists() and (aud / "B.done").exists())
check("sidecar_written", sc.exists()
      and set(json.loads(sc.read_text(encoding="utf-8"))["pieces"]) == {"A", "C"})

print("[3] 崩溃窗口:行已清、曲还没渲回 → 侧车兜底,A/C 仍在账上(活文件已无 null 行)")
pids3, st3 = rc.find_affected(lab)
check("pending_via_sidecar", pids3 == {"A", "C"} and st3["pending"] == 2, (pids3, st3))
check("apply_idempotent_rc0", rc.main([*base, "--apply"]) == 0)   # 再清一遍=无副作用
check("sidecar_survives", set(json.loads(sc.read_text(encoding="utf-8"))["pieces"]) == {"A", "C"})

print("[4] 渲回消账:A 渲回(TAST 非空)→ 只剩 C 在账;C 也渲回 → 侧车删除,affected=0")
with open(lab, "a", encoding="utf-8") as f:
    f.write(json.dumps({"utt_id": "pdmxperf_A_000", "piece_id": "A", "TAST": OK, "A2S": "a"}) + "\n")
pids4, st4 = rc.find_affected(lab)
check("A_consumed", pids4 == {"C"}, pids4)
check("sidecar_shrunk", set(json.loads(sc.read_text(encoding="utf-8"))["pieces"]) == {"C"})
with open(lab, "a", encoding="utf-8") as f:
    f.write(json.dumps({"utt_id": "pdmxperf_C_000", "piece_id": "C", "TAST": OK, "A2S": "a"}) + "\n")
pids5, _ = rc.find_affected(lab)
check("all_consumed", pids5 == set(), pids5)
check("sidecar_removed", not sc.exists())
check("noop_rc0", rc.main([*base, "--apply"]) == 0)   # 收敛后恒 0 曲,不再折腾

print("[5] 标签文件不存在(全新管线):无事可做 rc=0(P2c1 是常驻步骤,不许挡道)")
check("missing_rc0", rc.main(["--labels", str(tmp / "nope.jsonl"), "--audio-dir", str(aud)]) == 0)

print(f"\n全部通过: {PASS} 项")
