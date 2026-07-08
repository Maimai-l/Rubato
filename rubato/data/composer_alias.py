"""
S5 作曲家策略(R-S5.3,实现问题#10 的正解)。三级策略,选择由 hash(seed, piece_id)
派生(§2.2:同 piece_id 同结果,byte 级可复现),【不硬编码单一作曲家】。

问题#10 根因:S5 批量脚本写死 --composer Chopin,166 首表现性渲染风格同质化。
正解:按 PDMX 实际 composer 元数据走三级 —— 命中 / shuffle_p 洗牌 / 加权 fallback。
配置真源 = configs/virtuosonet.yaml(supported / high_data / shuffle_p / fallback_weights)。
"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VN_CFG = _REPO_ROOT / "configs" / "virtuosonet.yaml"

# PDMX composer 字段 → VirtuosoNet supported 名的别名表(常见写法/母语名/拼写变体)
_ALIAS = {
    "js bach": "Bach", "johann sebastian bach": "Bach", "j s bach": "Bach", "bach": "Bach",
    "ludwig van beethoven": "Beethoven", "l v beethoven": "Beethoven", "beethoven": "Beethoven",
    "frederic chopin": "Chopin", "fryderyk chopin": "Chopin", "chopin": "Chopin",
    "claude debussy": "Debussy", "debussy": "Debussy",
    "franz liszt": "Liszt", "liszt": "Liszt",
    "wolfgang amadeus mozart": "Mozart", "w a mozart": "Mozart", "mozart": "Mozart",
    "sergei rachmaninoff": "Rachmaninoff", "rachmaninov": "Rachmaninoff", "rachmaninoff": "Rachmaninoff",
    "maurice ravel": "Ravel", "ravel": "Ravel",
    "franz schubert": "Schubert", "schubert": "Schubert",
    "robert schumann": "Schumann", "schumann": "Schumann",
    "alexander scriabin": "Scriabin", "scriabin": "Scriabin", "skryabin": "Scriabin",
    "johannes brahms": "Brahms", "brahms": "Brahms",
    "joseph haydn": "Haydn", "haydn": "Haydn",
    "mily balakirev": "Balakirev", "balakirev": "Balakirev",
    "mikhail glinka": "Glinka", "glinka": "Glinka",
    "sergei prokofiev": "Prokofiev", "prokofiev": "Prokofiev",
}


def _norm(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    return " ".join(s.split())


def _u(*parts) -> float:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:15], 16) / float(16 ** 15)


def load_vn_config(path=None) -> dict:
    import yaml
    p = Path(path) if path else _VN_CFG
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def match_composer(pdmx_composer: str, supported: list[str]) -> str | None:
    """级1:PDMX composer 元数据归一化匹配 supported。命中返回规范名,否则 None。"""
    n = _norm(pdmx_composer)
    if not n:
        return None
    if n in _ALIAS and _ALIAS[n] in supported:
        return _ALIAS[n]
    # 姓氏兜底:取最后一词查别名
    last = n.split()[-1]
    if last in _ALIAS and _ALIAS[last] in supported:
        return _ALIAS[last]
    # 直接名字匹配 supported(大小写无关)
    for s in supported:
        if _norm(s) == n or _norm(s) == last:
            return s
    return None


def _weighted_pick(weights: dict, u: float) -> str:
    tot = sum(weights.values())
    acc = 0.0
    for k, w in weights.items():
        acc += w / tot
        if u < acc:
            return k
    return next(iter(weights))


def assign_composer(pdmx_composer: str, piece_id: str, cfg: dict | None = None,
                    seed: int = 20260706) -> dict:
    """
    R-S5.3 三级策略,返回 {composer_used, level}。选择全由 hash(seed, piece_id) 派生。
      级1 命中 → 用命中名;但以 shuffle_p 概率(级2)洗牌为 high_data 之一;
      级1 未命中 → 级3 按 fallback_weights 加权采样(偏浪漫派)。
    """
    cfg = cfg or load_vn_config()
    supported = cfg["supported"]
    high_data = cfg["high_data"]
    shuffle_p = cfg.get("shuffle_p", 0.15)
    fb = cfg["fallback_weights"]

    matched = match_composer(pdmx_composer, supported)
    if matched is not None:
        # 级2:shuffle_p 概率替换为 high_data 之一(演奏风格可跨作曲家)
        if _u(seed, piece_id, "shuffle") < shuffle_p:
            idx = int(_u(seed, piece_id, "shuffle_pick") * len(high_data))
            return {"composer_used": high_data[min(idx, len(high_data) - 1)],
                    "level": "2_shuffled", "matched": matched}
        return {"composer_used": matched, "level": "1_matched", "matched": matched}
    # 级3:加权 fallback(偏浪漫派)
    picked = _weighted_pick(fb, _u(seed, piece_id, "fallback"))
    return {"composer_used": picked, "level": "3_fallback", "matched": None}


if __name__ == "__main__":
    # 自检:分布贴合策略,可复现,不退化成单一作曲家
    cfg = load_vn_config()
    from collections import Counter
    dist = Counter()
    levels = Counter()
    # 一半有元数据(各作曲家),一半无
    for i in range(4000):
        comp = ["Chopin", "Beethoven", "Unknown Composer", "J.S. Bach",
                "", "Xyz Nobody", "Franz Liszt", "Mozart"][i % 8]
        r = assign_composer(comp, f"p{i}", cfg)
        dist[r["composer_used"]] += 1
        levels[r["level"]] += 1
    r1 = assign_composer("Chopin", "p1", cfg)
    r2 = assign_composer("Chopin", "p1", cfg)
    assert r1 == r2, "不可复现!"
    assert len(dist) >= 6, f"作曲家多样性不足(问题#10 会复发): {dist}"
    print("composer distribution:", dict(dist.most_common()))
    print("levels:", dict(levels))
    print("reproducible:", r1 == r2, "| distinct composers:", len(dist))
    print("OK: 不再单一 Chopin,分布多样且可复现")
