"""
S3 PDMX 池(R-S3.1~3.6)。work_key 归一化 + MinHash 近重复 + 跨集黑名单 + license。

修复问题#14:build_blacklist / check_split_leakage 是 S4/S5 选曲【必须】调用的过滤器,
不是只在事后核验。选 PDMX MIDI 渲染前先 check,命中黑名单/泄漏的整曲不进渲染队列。
"""
from __future__ import annotations
import hashlib
import re

# ---------------------------------------------------------------- work_key(R-S3.5)

# 编号词/装饰词:归一化时剔除,让"Op. 23"与"Op 23"、"No. 1"与"No 1"归一
_NOISE_WORDS = {"op", "opus", "no", "nr", "number", "k", "kv", "bwv", "d", "hob",
                "l", "s", "woo", "in", "the", "a", "an", "for", "and", "of"}
_ACCENT_MAP = str.maketrans("áàâäãéèêëíìîïóòôöõúùûüñçøåæ",
                            "aaaaaeeeeiiiiooooouuuuncoaa")


def normalize_work(s: str) -> str:
    """
    小写 + 去重音 + 去标点 + 去编号词,空格分隔。用于 work_key 组件归一。
    关键:剔除紧跟编号词的数字(No. 1 / Op. 23 / K. 545 中的 1/23/545),
    使 'Ballade No. 1 in G minor, Op. 23' 与 'Ballade in G minor Op 23' 归一一致。
    """
    s = (s or "").lower().translate(_ACCENT_MAP)
    s = re.sub(r"[^a-z0-9\s]", " ", s)          # 标点→空格
    toks = []
    drop_next_num = False
    for t in s.split():
        if not t:
            continue
        if t in _NOISE_WORDS:
            drop_next_num = True                # 下一个纯数字是该编号词的编号,一并剔除
            continue
        if drop_next_num and t.isdigit():
            drop_next_num = False               # 剔除编号数字
            continue
        drop_next_num = False
        toks.append(t)
    return " ".join(toks)


def work_key(composer: str, title: str) -> str:
    """R-S3.5:normalize(composer)+'|'+normalize(title)。查重与 split 隔离的键。"""
    return f"{normalize_work(composer)}|{normalize_work(title)}"


def work_key_or_fallback(composer: str, title: str, piece_id: str) -> str:
    """
    ⚠ 缺 composer/title 的曲【绝不丢弃】—— 它的 MIDI/乐谱是好的,只是元数据缺标签,
    对音频→乐谱训练毫无影响(作曲家名只是去重/split 的记账字段)。

    设计根因修正:旧 SPEC 把 work_key=composer|title 设成承重主键,导致缺 composer 的
    31k+ 首合格钢琴谱被硬删(占过滤损失的头号)。正解:缺元数据 → 用 piece_id 兜底成
    【独立作品键】(它就是自己的"作品",不与任何曲共 split-key)。去重与跨集泄漏改由
    MinHash 内容比对(near_dup_ids)兜底,命名无关,不需要 composer。

    有 composer+title → 正常 work_key(参与同作品去重/split 隔离);
    缺任一 → '__nometa__|<piece_id>'(唯一键,保证进 train 且不被误判重复)。
    """
    if _is_missing(composer) or _is_missing(title):
        return f"__nometa__|{piece_id}"
    c = normalize_work(composer)
    t = normalize_work(title)
    if not c or not t:                      # 归一化后为空(纯标点/编号词)也算缺
        return f"__nometa__|{piece_id}"
    return f"{c}|{t}"


# PDMX 元数据缺失的常见占位:"NA" 是最常见(31k+ 首),别当成真作曲家名
_MISSING_SENTINELS = {"", "na", "n/a", "none", "null", "nan", "unknown", "untitled", "?"}


def _is_missing(v) -> bool:
    return (v is None) or (str(v).strip().lower() in _MISSING_SENTINELS)


# ---------------------------------------------------------------- MinHash 近重复(R-S3.6)

def ngram_set(seq: list, n: int = 8) -> frozenset:
    """
    展开后 (pitch, dur) 序列的 n-gram 集合。R-S3.6 默认 8-gram(针对真实曲目的
    数百音符序列)。短序列上 8-gram 只有零星几个,Jaccard 分辨率极粗——对短序列
    收缩 shingle 到 len//2(下限 2),使近重复信号在长短序列上都可用。
    """
    if not seq:
        return frozenset()
    eff_n = min(n, max(2, len(seq) // 2))
    if len(seq) < eff_n:
        return frozenset([tuple(seq)])
    return frozenset(tuple(seq[i:i + eff_n]) for i in range(len(seq) - eff_n + 1))


_MINHASH_K = 128
# 固定派生的哈希族(可复现,不依赖运行时随机)
_SEEDS = [hashlib.sha256(f"minhash:{i}".encode()).digest()[:8] for i in range(_MINHASH_K)]


def _h(item, seed: bytes) -> int:
    return int.from_bytes(hashlib.sha256(seed + repr(item).encode()).digest()[:8], "big")


class _Sig(tuple):
    """
    签名 = (minhash 元组) 但额外携带原始 n-gram 集合。
    对聚类扩展性:大池用 minhash 分量做 LSH banding;对精度:相似度用【精确 Jaccard】,
    不吃 MinHash 在短序列(n-gram 少)上的采样噪声——否则真值恰在 0.2 边界的样本会随机
    落到界内/界外。tuple 子类,现有按 tuple 用法不受影响。
    """

    def __new__(cls, minhash: tuple, grams: frozenset):
        self = super().__new__(cls, minhash)
        self._grams = grams
        return self


def minhash_signature(grams: frozenset, k: int = _MINHASH_K) -> _Sig:
    """k 个最小哈希组成的签名(并携带原 gram 集合供精确 Jaccard)。空集 → 全 inf。"""
    if not grams:
        return _Sig(tuple([float("inf")] * k), frozenset())
    mh = tuple(min(_h(g, _SEEDS[i]) for g in grams) for i in range(k))
    return _Sig(mh, grams)


def estimate_jaccard(sig_a, sig_b) -> float:
    """
    Jaccard 相似度。携带 gram 集合(_Sig)时走精确 |A∩B|/|A∪B|;否则退化到
    MinHash 分量相等占比(纯 tuple 输入的向后兼容路径)。
    """
    ga = getattr(sig_a, "_grams", None)
    gb = getattr(sig_b, "_grams", None)
    if ga is not None and gb is not None:
        if not ga and not gb:
            return 1.0
        union = len(ga | gb)
        return len(ga & gb) / union if union else 1.0
    if not sig_a or not sig_b:
        return 0.0
    same = sum(1 for a, b in zip(sig_a, sig_b) if a == b and a != float("inf"))
    return same / len(sig_a)


def cluster_duplicates(sigs: dict, threshold: float = 0.7) -> dict:
    """
    R-S3.6:Jaccard>threshold 判同簇。返回 {id: cluster_id}。
    简单并查集:两两比较(O(n²),PDMX 池 <2 万可接受;更大规模用 LSH banding)。
    """
    ids = list(sigs)
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if estimate_jaccard(sigs[ids[i]], sigs[ids[j]]) > threshold:
                union(ids[i], ids[j])
    # 归一化簇号为稳定整数
    roots = {}
    out = {}
    for i in ids:
        r = find(i)
        if r not in roots:
            roots[r] = len(roots)
        out[i] = roots[r]
    return out


# ---------------------------------------------------------------- 跨集黑名单与泄漏(R-S3.6, A-S3.3)

def build_blacklist(nasap_test_works: list[str], asap_beyer_works: list[str]) -> set:
    """
    R-S3.6:nASAP test 与 ASAP-Beyer 曲目的 work_key 全量列入 train 黑名单
    (跨数据集泄漏防线,work_key 字符串匹配路径)。返回 work_key 集合。

    ⚠ 已知局限(实测):PDMX 元数据与 ASAP 文件夹名的命名体系不同——
    ASAP 'bach|fugue' vs PDMX 'johann sebastian bach|fugue c major',字符串 work_key
    匹配常删 0 首。**真正的泄漏防线是下面的 MinHash 近重复(命名无关)**,work_key
    仅作辅助。用 build_blacklist 后务必核对删除数非 0,为 0 就改用 near_dup_ids。
    """
    return set(nasap_test_works) | set(asap_beyer_works)


# ---------------------------------------------------------------- MinHash 近重复防线(R-S3.6,命名无关)

def ir_to_pitch_dur_seq(ir) -> list:
    """
    ScoreIR → 按 (onset, pitch) 排序的 (midi_pitch, dur_str) 序列。
    这是 MinHash 近重复比对的输入:比的是【实际音符内容】,不吃标题/作曲家命名差异。
    """
    def _midi(p):
        return p.midi if hasattr(p, "midi") else int(p)
    notes = sorted(ir.notes, key=lambda n: (n.onset, _midi(n.pitch)))
    return [(_midi(n.pitch), str(n.dur)) for n in notes]


def piece_signature(ir, n: int = 8):
    """ScoreIR → MinHash 签名(经 (pitch,dur) 序列)。近重复用。"""
    return minhash_signature(ngram_set(ir_to_pitch_dur_seq(ir), n))


def near_dup_ids(target_sigs: dict, ref_sigs: list, threshold: float = 0.7) -> set:
    """
    R-S3.6 真正的泄漏防线(命名无关)。
    target_sigs: {piece_id: signature}(PDMX 候选曲);ref_sigs: [signature](ASAP test/Beyer 参考曲)。
    返回近重复于【任一】参考曲的 piece_id 集合(判为泄漏,剔除出 train)。
    Jaccard>threshold 判近重复。ref 数通常小(ASAP ~百首),O(n_pdmx × n_ref) 可接受。
    """
    flagged = set()
    for pid, sig in target_sigs.items():
        for ref in ref_sigs:
            if estimate_jaccard(sig, ref) > threshold:
                flagged.add(pid)
                break
    return flagged


def check_split_leakage(pieces: list[dict], blacklist: set) -> dict:
    """
    A-S3.3 + A-S8.3 泄漏终检。pieces: [{piece_id, work_key, dup_cluster, split}]。
    三维检查:
      - blacklist_violations:train 曲目命中跨集黑名单
      - cross_split_work_key:同 work_key 跨 train/val/test
      - cross_split_dup_cluster:同 dup_cluster 跨 split
    返回 {ok, blacklist_violations, cross_split_work_key, cross_split_dup_cluster}。
    """
    by_wk, by_dup = {}, {}
    bl_viol = []
    for p in pieces:
        by_wk.setdefault(p["work_key"], set()).add(p["split"])
        by_dup.setdefault(p["dup_cluster"], set()).add(p["split"])
        if p["split"] == "train" and p["work_key"] in blacklist:
            bl_viol.append(p["work_key"])
    cross_wk = [wk for wk, sp in by_wk.items() if len(sp) > 1]
    cross_dup = [dc for dc, sp in by_dup.items() if len(sp) > 1]
    ok = not bl_viol and not cross_wk and not cross_dup
    return {"ok": ok, "blacklist_violations": bl_viol,
            "cross_split_work_key": cross_wk, "cross_split_dup_cluster": cross_dup}


# ---------------------------------------------------------------- license + metadata(R-S3.1/3.2)

# cc-zero / cc zero 是 CC0 的另一种写法(PDMX 元数据里大量用),不识别会误杀 30k+ 有效曲。
_LICENSE_OK = ("public domain", "publicdomain", "cc0", "cc-zero", "cc zero",
               "cc-by", "cc by", "ccby")


def license_ok(license_str: str) -> bool:
    """R-S3.2:license ∈ {public domain, CC0(含 cc-zero), CC-BY 系}。"""
    s = (license_str or "").lower()
    return any(tok in s for tok in _LICENSE_OK)


def metadata_filter(meta: dict) -> tuple[bool, str]:
    """
    R-S3.1/3.2 元数据级过滤(在读 XML 前先筛)。
    返回 (ok, reason)。PDMX 自曝 is_duplicate/is_transcription 等标记要过滤。
    """
    if str(meta.get("is_duplicate", "")).lower() == "true":
        return False, "pdmx_is_duplicate"
    if str(meta.get("is_transcription", "")).lower() == "true":
        return False, "pdmx_is_transcription"
    if not license_ok(meta.get("license", "")):
        return False, "license_not_whitelisted"
    return True, "ok"
