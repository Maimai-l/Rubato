"""nASAP utt 唯一化 v2 回归:跨曲撞名、【乐章共音频撞名】(执行端实测 dup_after=584)、
以 .bak2 原件重生成(撤销 v1 的 work_key 污染)、幂等、split 通过。
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

rows = []
# 情形 A(跨曲撞名):同演奏者 Shi05M 录了两首不同曲(不同音频)
for wk, perf in [("bach|prelude bwv 846", "{maestro}/2006/a.wav"),
                 ("liszt|sonata b minor", "{maestro}/2008/b.wav")]:
    for si in range(3):
        rows.append({"utt_id": f"nasap_Shi05M_xml_score_{si:03d}",
                     "work_key": wk, "perf_audio": perf,
                     "A2S": "|4/4k0", "win": [si * 10.0, si * 10.0 + 8.0]})
# 情形 B(乐章共音频撞名,v1 修不掉的那 584):同录音 c.wav 三个乐章,
# 演奏者 stem 同、音频同、各自段号从 000 起 —— 只有 work_key(带乐章号)能区分
for mv in (1, 2, 3):
    for si in range(2):
        rows.append({"utt_id": f"nasap_LuoJ01_xml_score_{si:03d}",
                     "work_key": f"beethoven|piano sonatas 17 {mv}",
                     "perf_audio": "{maestro}/2011/c.wav",
                     "A2S": "|4/4k0", "win": [mv * 100.0 + si * 10.0, mv * 100.0 + si * 10.0 + 8.0]})
# 情形 C(重复对齐变体):同(录音, 乐章, 段号)出现两次 → 保首份丢后份,大声记账
rows.append({"utt_id": "nasap_Shi05M_xml_score_000",
             "work_key": "bach|prelude bwv 846", "perf_audio": "{maestro}/2006/a.wav",
             "A2S": "|4/4k0 VARIANT", "win": [0.0, 8.0]})
# 填充作品,让 split 有得分
for w in range(6):
    for si in range(3):
        rows.append({"utt_id": f"nasap_P{w}_xml_score_{si:03d}",
                     "work_key": f"comp{w}|title{w}", "perf_audio": f"{{maestro}}/2010/w{w}.wav",
                     "A2S": "|4/4k0", "win": [si * 10.0, si * 10.0 + 8.0]})
lab.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

base = ["--labels", str(lab)]

print("[1] 干跑不动文件;--apply 后全唯一(跨曲 + 乐章两类撞名都解),piece↔work_key 一一对应")
check("dry_rc0", fx.main(base) == 0)
check("dry_untouched", "xml_score" in lab.read_text(encoding="utf-8").splitlines()[0])
check("apply_rc0", fx.main([*base, "--apply"]) == 0)
got = [json.loads(l) for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]
ids = [r["utt_id"] for r in got]
check("unique_after", len(ids) == len(set(ids)), len(ids) - len(set(ids)))
pieces = {}
for r in got:
    pieces.setdefault(r["utt_id"].rsplit("_", 1)[0], set()).add(r["work_key"])
check("one_wk_per_piece", all(len(s) == 1 for s in pieces.values()))
check("movements_three_pieces",
      len({p for p in pieces if p.startswith("nasap_LuoJ01_")}) == 3,
      {p for p in pieces if p.startswith("nasap_LuoJ01_")})
check("crosswork_two_pieces", len({p for p in pieces if p.startswith("nasap_Shi05M_")}) == 2)
check("bak2_exists", lab.with_suffix(".bak2").exists())
kept_variant = [r for r in got if r["utt_id"].endswith("_000")
                and r["work_key"] == "bach|prelude bwv 846"]
check("variant_dropped_keep_first",
      len(kept_variant) == 1 and kept_variant[0]["A2S"] == "|4/4k0", kept_variant)

print("[2] 以原件重生成:模拟 v1 污染(错 work_key + 旧 tag)→ 重跑自动撤销,恢复正确值")
polluted = [dict(r) for r in got]
for r in polluted:
    if r["utt_id"].startswith("nasap_LuoJ01_"):
        r["work_key"] = "beethoven|piano sonatas 17 3"     # v1 的"最后行赢"污染
lab.write_text("\n".join(json.dumps(r) for r in polluted) + "\n", encoding="utf-8")
check("repair_rc0", fx.main([*base, "--apply"]) == 0)
got2 = [json.loads(l) for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]
wks = sorted({r["work_key"] for r in got2 if r["utt_id"].startswith("nasap_LuoJ01_")})
check("pollution_reverted", wks == [f"beethoven|piano sonatas 17 {m}" for m in (1, 2, 3)], wks)

print("[3] 幂等:再跑 --apply 输出不变")
before = lab.read_text(encoding="utf-8")
check("idem_rc0", fx.main([*base, "--apply"]) == 0)
check("idem_unchanged", lab.read_text(encoding="utf-8") == before)

print("[4] split 分配干净通过(撞名修根后不再跨 split)")
rc = sp.main(["--labels", str(lab), "--val-target", "5",
              "--manifest-out", str(tmp / "m.json"), "--apply"])
check("split_rc0", rc == 0, rc)
got3 = [json.loads(l) for l in lab.read_text(encoding="utf-8").splitlines() if l.strip()]
wk_splits = {}
for r in got3:
    wk_splits.setdefault(r["work_key"], set()).add(r["split"])
check("no_cross_split", all(len(s) == 1 for s in wk_splits.values()),
      {k: sorted(v) for k, v in wk_splits.items() if len(v) > 1})

print(f"\n全部通过: {PASS} 项")
