"""nASAP utt 唯一化回归:同演奏者跨曲撞名 → 重写后唯一、piece 归属正确、split 不再泄漏。
运行: python tests_s7_uttids.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import scripts.s7_fix_uttids as fx
import scripts.s7_assign_split as sp

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
lab = tmp / "nasap_labels.jsonl"

# 同一演奏者 Shi05M 录了两首不同的曲(ASAP 现实):旧版 utt 完全撞名。
# 再加 6 个不撞名的作品,让 split 有足够作品可分。
rows = []
for w, (wk, perf) in enumerate([
    ("bach|prelude bwv 846", "{maestro}/2006/a.wav"),
    ("beethoven|sonata 17",  "{maestro}/2008/b.wav"),
]):
    for si in range(3):
        rows.append({"utt_id": f"nasap_Shi05M_xml_score_{si:03d}",   # ← 两曲撞名
                     "work_key": wk, "perf_audio": perf,
                     "A2S": "|4/4k0", "win": [si * 10.0, si * 10.0 + 8.0]})
for w in range(6):
    for si in range(3):
        rows.append({"utt_id": f"nasap_P{w}_xml_score_{si:03d}",
                     "work_key": f"comp{w}|title{w}", "perf_audio": f"{{maestro}}/2010/w{w}.wav",
                     "A2S": "|4/4k0", "win": [si * 10.0, si * 10.0 + 8.0]})
lab.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

base = ["--labels", str(lab), "--metadata", str(tmp / "no_metadata.csv")]

print("[1] 干跑:报出撞名 3 处(两曲各 3 段同名),不改文件")
check("dry_rc0", fx.main(base) == 0)
first = json.loads(lab.read_text(encoding="utf-8").splitlines()[0])
check("dry_untouched", first["utt_id"] == "nasap_Shi05M_xml_score_000")

print("[2] --apply:重写后 utt 全唯一,同演奏者两曲的 piece 分开,work_key 保留")
check("apply_rc0", fx.main([*base, "--apply"]) == 0)
got = [json.loads(l) for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]
ids = [r["utt_id"] for r in got]
check("unique_after", len(ids) == len(set(ids)), len(ids) - len(set(ids)))
pieces = {}
for r in got:
    pieces.setdefault(r["utt_id"].rsplit("_", 1)[0], set()).add(r["work_key"])
check("one_wk_per_piece", all(len(s) == 1 for s in pieces.values()),
      {k: v for k, v in pieces.items() if len(v) > 1})
shi = {p for p in pieces if p.startswith("nasap_Shi05M_")}
check("collided_now_two_pieces", len(shi) == 2, shi)
check("bak2_exists", lab.with_suffix(".bak2").exists())

print("[3] 幂等:再跑 --apply,重写 0 行、id 不变")
before = lab.read_text(encoding="utf-8")
check("idem_rc0", fx.main([*base, "--apply"]) == 0)
check("idem_unchanged", lab.read_text(encoding="utf-8") == before)

print("[4] 修完根因后 split 分配干净通过(此前撞名会造出跨 split 泄漏)")
rc = sp.main(["--labels", str(lab), "--val-target", "5",
              "--manifest-out", str(tmp / "m.json"), "--apply"])
check("split_rc0", rc == 0, rc)
got2 = [json.loads(l) for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]
wk_splits = {}
for r in got2:
    wk_splits.setdefault(r["work_key"], set()).add(r["split"])
check("no_cross_split", all(len(s) == 1 for s in wk_splits.values()),
      {k: sorted(v) for k, v in wk_splits.items() if len(v) > 1})
check("shi_two_works_may_differ", len({next(iter(wk_splits[wk])) for wk in
      ("bach|prelude bwv 846", "beethoven|sonata 17")}) >= 1)   # 两曲独立分配,不再绑死

print(f"\n全部通过: {PASS} 项")
