"""S3 PDMX 逻辑测试(纯逻辑部分)。运行: python tests_pdmx.py"""
import sys
sys.path.insert(0, ".")
from rubato.data.pdmx import (
    normalize_work, work_key, ngram_set, minhash_signature, estimate_jaccard,
    cluster_duplicates, build_blacklist, check_split_leakage,
    license_ok, metadata_filter,
)

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] work_key 归一化")
# 同一曲不同写法应归一到相同 key
k1 = work_key("Frédéric Chopin", "Ballade No. 1 in G minor, Op. 23")
k2 = work_key("Frederic Chopin", "Ballade in G minor Op 23")
check("chopin_variants_same", k1 == k2, f"\n    {k1}\n    {k2}")
# 不同曲应不同
k3 = work_key("Chopin", "Nocturne in E-flat major")
check("different_works_differ", k1 != k3)
# 编号词/标点被去除
check("removes_opus", "op" not in normalize_work("Op. 23").split(), normalize_work("Op. 23"))

print("[2] MinHash 近重复检测")
# 两个几乎相同的序列
seq_a = [(60, 1), (62, 1), (64, 1), (65, 1), (67, 1), (69, 1), (71, 1), (72, 1), (74, 1), (76, 1)]
seq_b = seq_a[:]                              # 完全相同
seq_c = [(p + 12, d) for p, d in seq_a]       # 移高八度(完全不同 pitch)
sig_a = minhash_signature(ngram_set(seq_a))
sig_b = minhash_signature(ngram_set(seq_b))
sig_c = minhash_signature(ngram_set(seq_c))
check("identical_high_jaccard", estimate_jaccard(sig_a, sig_b) == 1.0)
check("different_low_jaccard", estimate_jaccard(sig_a, sig_c) < 0.3,
      estimate_jaccard(sig_a, sig_c))

print("[3] 近重复聚类")
# 3 个序列:a,b 相同,c 不同 → 应聚成 2 簇
sigs = {"a": sig_a, "b": sig_b, "c": sig_c}
clusters = cluster_duplicates(sigs, threshold=0.7)
check("ab_same_cluster", clusters["a"] == clusters["b"], clusters)
check("c_different_cluster", clusters["c"] != clusters["a"], clusters)
check("two_clusters_total", len(set(clusters.values())) == 2, clusters)

print("[4] 部分重复(75% 重叠)")
seq_d = seq_a[:8] + [(80, 2), (82, 2)]        # 前 8 个相同,后 2 个不同
sig_d = minhash_signature(ngram_set(seq_d))
j = estimate_jaccard(sig_a, sig_d)
check("partial_overlap_detected", 0.2 < j < 0.95, f"jaccard={j:.2f}")

print("[5] 跨数据集黑名单(A-S3.3)")
bl = build_blacklist(
    nasap_test_works=["chopin|ballade g minor", "liszt|sonata b minor"],
    asap_beyer_works=["bach|wtc prelude c major"])
check("blacklist_union", len(bl) == 3, bl)
# train 含黑名单曲目 → 违规
pieces_bad = [
    {"piece_id": "p1", "work_key": "chopin|ballade g minor", "dup_cluster": 0, "split": "train"},
    {"piece_id": "p2", "work_key": "mozart|sonata k545", "dup_cluster": 1, "split": "val"},
]
r = check_split_leakage(pieces_bad, bl)
check("blacklist_violation_caught", not r["ok"] and "chopin|ballade g minor" in r["blacklist_violations"], r)

print("[6] val/test 与 train 的 work_key 隔离")
pieces_cross = [
    {"piece_id": "p1", "work_key": "shared|piece", "dup_cluster": 0, "split": "train"},
    {"piece_id": "p2", "work_key": "shared|piece", "dup_cluster": 1, "split": "test"},  # 泄漏!
]
r = check_split_leakage(pieces_cross, set())
check("cross_split_caught", not r["ok"] and "shared|piece" in r["cross_split_work_key"], r)
# dup_cluster 泄漏
pieces_dup = [
    {"piece_id": "p1", "work_key": "a|1", "dup_cluster": 5, "split": "train"},
    {"piece_id": "p2", "work_key": "b|2", "dup_cluster": 5, "split": "val"},  # 同簇泄漏
]
r = check_split_leakage(pieces_dup, set())
check("dup_cross_caught", not r["ok"] and 5 in r["cross_split_dup_cluster"], r)
# 干净的应通过
pieces_clean = [
    {"piece_id": "p1", "work_key": "a|1", "dup_cluster": 0, "split": "train"},
    {"piece_id": "p2", "work_key": "b|2", "dup_cluster": 1, "split": "val"},
]
check("clean_passes", check_split_leakage(pieces_clean, set())["ok"])

print("[7] license 白名单 + metadata 过滤")
check("public_domain_ok", license_ok("Public Domain"))
check("cc0_ok", license_ok("CC0 1.0"))
check("ccby_ok", license_ok("CC-BY-4.0"))
check("all_rights_rejected", not license_ok("All Rights Reserved"))
# metadata 过滤
ok, reason = metadata_filter({"is_duplicate": "true", "license": "CC0"})
check("duplicate_filtered", not ok and reason == "pdmx_is_duplicate", reason)
ok, reason = metadata_filter({"is_duplicate": "false", "is_transcription": "false", "license": "Public Domain"})
check("clean_metadata_passes", ok, reason)

print("[7b] 缺 composer/title 不丢弃,兜底独立 work_key(修头号数据杀手)")
from rubato.data.pdmx import work_key_or_fallback
# 有元数据 → 正常 work_key
check("meta_present_normal", work_key_or_fallback("Chopin", "Ballade", "pA") == work_key("Chopin", "Ballade"))
# 缺 composer → 兜底 piece_id 独立键(不丢)
wk_nc = work_key_or_fallback("NA", "Some Piece", "pB")
check("missing_composer_fallback", wk_nc == "__nometa__|pB", wk_nc)
# 缺 title → 兜底
wk_nt = work_key_or_fallback("Bach", "", "pC")
check("missing_title_fallback", wk_nt == "__nometa__|pC", wk_nt)
# 两首都缺元数据 → 各自独立键(不会被误当同一"作品"塌缩)
wk1 = work_key_or_fallback("", "", "p1")
wk2 = work_key_or_fallback("", "", "p2")
check("nometa_pieces_distinct", wk1 != wk2, (wk1, wk2))

print("[8] MinHash 近重复防线(命名无关,R-S3.6)—— 修 0a 黑名单删 0 的正解")
import sys
sys.path.insert(0, ".")
from fractions import Fraction as F
from rubato.intermo.core import Note, Measure, ScoreIR, SPitch
from rubato.data.pdmx import ir_to_pitch_dur_seq, piece_signature, near_dup_ids

def _ir(steps):
    return ScoreIR([Note("PR", SPitch(s, 0, 4), F(i), F(1)) for i, s in enumerate(steps)],
                   [Measure(F(i), 4, 4, 0) for i in range(len(steps))], F(len(steps)))

# 参考曲(ASAP test)与一首"改了标题作曲家但音符相同"的 PDMX 曲 → 应被 MinHash 抓到
ref = _ir("CDEFGABCDEF")
pdmx_same = _ir("CDEFGABCDEF")          # 同音符,元数据可能完全不同的作曲家/标题
pdmx_diff = _ir("CGCGCGCGCGC")          # 不同音符
ref_sig = piece_signature(ref)
targets = {"same": piece_signature(pdmx_same), "diff": piece_signature(pdmx_diff)}
flagged = near_dup_ids(targets, [ref_sig], threshold=0.7)
check("near_dup_catches_same", "same" in flagged, flagged)
check("near_dup_spares_diff", "diff" not in flagged, flagged)
check("pitch_dur_seq_order", ir_to_pitch_dur_seq(ref)[0][0] == 60)   # C4 = MIDI 60

print(f"\n全部通过: {PASS} 项")
print("注:PDMX metadata 读取、MuseScore4 归一化、partitura 结构检查需真实数据,本地验证;")
print("    work_key/MinHash/近重复/黑名单/license 逻辑沙盒已验证。")
