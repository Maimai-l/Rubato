"""
S11 采样与 tiling(R-S11.2, R-S11.3)。纯逻辑,沙盒可验证。
"""
from __future__ import annotations
import hashlib

DIALECT_MIX = {"A2S": 0.35, "A2S_lite": 0.15, "TAST": 0.20, "AMT": 0.30}


def dialect_sampler(available_by_utt: dict, seed: int, epoch: int,
                    mix: dict | None = None, report: dict | None = None):
    """
    R-S11.2:按混比采样 (utt_id, dialect),不按数据集自然占比。
    available_by_utt: {utt_id: [可用 dialect]}。
    返回一个 epoch 的采样列表 [(utt_id, dialect)],总量 ≈ utt 数。
    mix:可从配置注入(DIALECT_MIX 只是缺省),便于按数据实况调混比。
    report:若传入 dict,填充每个 dialect 的 {pool_size, quota, oversample_ratio}——
      小池被有放回过采样多少倍是数据多样性风险(AMT 池小却配大额=同曲反复),必须可见不静默。

    修复说明:旧实现"逐 utt 按其可用 dialect 的相对权重选一个"——当可用性分布偏斜时
    (MAESTRO 只有 AMT、占语料大头),epoch 的 dialect 分布=数据自然占比,直接违反
    R-S11.2。现改为【全局配额】:每个 dialect 按混比分得 quota,从"支持该 dialect 的
    utt 池"中抽样填满(池小的 dialect 有放回过采样)——分布严格贴合混比。
    """
    import random
    rng = random.Random(f"{seed}:{epoch}")
    mix = mix or DIALECT_MIX
    pools = {d: [u for u, avail in available_by_utt.items() if avail and d in avail]
             for d in mix}
    pools = {d: p for d, p in pools.items() if p}
    if not pools:
        return []
    n_total = sum(1 for a in available_by_utt.values() if a)
    tot_w = sum(mix[d] for d in pools)
    out = []
    for d in sorted(pools):
        quota = int(round(n_total * mix[d] / tot_w))
        pool = pools[d]
        take = rng.sample(pool, min(quota, len(pool)))     # 优先无放回
        while len(take) < quota:                           # 小池按混比过采样(有放回)
            take.append(rng.choice(pool))
        out.extend((u, d) for u in take)
        if report is not None:
            report[d] = {"pool_size": len(pool), "quota": quota,
                         "oversample_ratio": round(quota / max(len(pool), 1), 2)}
    rng.shuffle(out)
    return out


def tiling_offset(dialect: str, dur_s: float, utt_id: str, epoch: int,
                  seed: int, window: float = 40.0) -> float:
    """
    R-S11.3:TAST/AMT 每 epoch 每样本 t0 ~ U[0, window-dur]。A2S/A2S_lite 不 tiling(返回 0)。
    """
    if dialect not in ("TAST", "AMT"):
        return 0.0
    room = max(0.0, window - dur_s)
    if room == 0:
        return 0.0
    h = hashlib.sha256(f"{seed}:{epoch}:{utt_id}:tile".encode()).hexdigest()
    u = int(h[:15], 16) / float(16 ** 15)
    return u * room
