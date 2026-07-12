"""外科手术重渲回归:S4/S5 哈希键分开圈定、只清受影响曲、验证残留 0、文本标签永不动。
运行: python tests_rerender.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import yaml

from rubato.render.core import assign_source_and_preset
import scripts.rerender_presets as rr

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
aud = tmp / "audio"; aud.mkdir()

SOURCES = {"sources": {"sA": {"ratio": 1.0, "path": "x.sfz"}}, "render": {}}
PRESETS = {"presets": {"pGOOD": {"wet": 0.1}, "pBAD": {"wet": 0.6}},
           "weights": {"pGOOD": 1.0, "pBAD": 1.0}, "seed": 0}
# sort_keys=False 保序;且期望值一律用【回读后的配置】算 —— _pick 按 dict 顺序累计权重,
# 序变则归属变(生产端安全:所有人读同一份 yaml;测试若用内存 dict 算就会错位)。
(tmp / "sources.yaml").write_text(yaml.safe_dump(SOURCES, sort_keys=False), encoding="utf-8")
(tmp / "presets.yaml").write_text(yaml.safe_dump(PRESETS, sort_keys=False), encoding="utf-8")
SOURCES = yaml.safe_load((tmp / "sources.yaml").read_text(encoding="utf-8"))
PRESETS = yaml.safe_load((tmp / "presets.yaml").read_text(encoding="utf-8"))

# 20 首曲:用真哈希预先算出每首的 S4/S5 归属(测试不猜哈希,直接对照真函数)
pids = [f"Qm{i:04d}" for i in range(20)]
mani = tmp / "m.jsonl"
with open(mani, "w", encoding="utf-8") as f:
    for pid in pids:
        f.write(json.dumps({"piece_id": pid}) + "\n")
s4_bad = {p for p in pids if assign_source_and_preset(f"pdmx_{p}", SOURCES, PRESETS)[1] == "pBAD"}
s5_bad = {p for p in pids if assign_source_and_preset(p, SOURCES, PRESETS)[1] == "pBAD"}
check("hash_keys_differ", s4_bad != s5_bad or len(pids) < 4,
      "20 曲下两键归属应有差异(哈希键不同)")

# 每首曲铺全套文件 + 标签行
vnl = tmp / "vn.jsonl"
txt = tmp / "txt.jsonl"
with open(vnl, "w", encoding="utf-8") as fv, open(txt, "w", encoding="utf-8") as ft:
    for pid in pids:
        (aud / f"pdmx_{pid}.opus").write_bytes(b"x")
        (aud / f"pdmx_{pid}_000.flac").write_bytes(b"x")
        (aud / f"pdmxperf_{pid}_000.wav").write_bytes(b"x")
        (aud / f"{pid}.done").touch()
        fv.write(json.dumps({"utt_id": f"pdmxperf_{pid}_000", "piece_id": pid, "TAST": "t"}) + "\n")
        ft.write(json.dumps({"utt_id": f"pdmx_{pid}_000", "piece_id": pid, "A2S": "a"}) + "\n")

base = ["--manifest", str(mani), "--audio-dir", str(aud), "--vn-labels", str(vnl),
        "--sources", str(tmp / "sources.yaml"), "--presets", str(tmp / "presets.yaml")]

print("[1] --list 成本表 + 干跑不改任何文件")
check("list_rc0", rr.main([*base, "--list"]) == 0)
check("dry_rc0", rr.main([*base, "--bad", "pBAD"]) == 0)
check("dry_untouched", all((aud / f"pdmx_{p}.opus").exists() for p in pids))

print("[2] --apply:恰好清掉 S4/S5 各自受影响集合,其余全保")
rc = rr.main([*base, "--bad", "pBAD", "--apply"])
check("apply_rc0", rc == 0, rc)
for p in pids:
    in4, in5 = p in s4_bad, p in s5_bad
    check(f"s4_{p}", (aud / f"pdmx_{p}.opus").exists() != in4, (p, in4))
    check(f"slice_{p}", (aud / f"pdmx_{p}_000.flac").exists() != in4, (p, in4))
    check(f"vn_{p}", (aud / f"pdmxperf_{p}_000.wav").exists() != in5, (p, in5))
    check(f"done_{p}", (aud / f"{p}.done").exists() != in5, (p, in5))

print("[3] VN 标签行:受影响曲剔除(留 .bak),文本标签一行不动")
vn_rows = [json.loads(l)["piece_id"] for l in open(vnl, encoding="utf-8") if l.strip()]
check("vn_rows_pruned", set(vn_rows) == set(pids) - s5_bad, len(vn_rows))
check("vn_bak", vnl.with_suffix(".bak").exists())
txt_rows = [l for l in open(txt, encoding="utf-8") if l.strip()]
check("text_labels_untouched", len(txt_rows) == len(pids))

print(f"\n全部通过: {PASS} 项(S4坏={len(s4_bad)} S5坏={len(s5_bad)}/20)")
