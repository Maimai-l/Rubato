"""
S11 采样与 tiling(R-S11.2, R-S11.3)。纯逻辑,沙盒可验证。
"""
from __future__ import annotations
import hashlib

DIALECT_MIX = {"A2S": 0.35, "A2S_lite": 0.15, "TAST": 0.20, "AMT": 0.30}


def dialect_sampler(available_by_utt: dict, seed: int, epoch: int):
    """
    R-S11.2:按混比采样 (utt_id, dialect),不按数据集自然占比。
    available_by_utt: {utt_id: [可用 dialect]}。
    返回一个 epoch 的采样列表 [(utt_id, dialect)]。
    做法:对每个 utt,按其可用 dialect 在全局混比中的相对权重选一个 dialect。
    """
    import random
    rng = random.Random(f"{seed}:{epoch}")
    out = []
    for utt, avail in available_by_utt.items():
        if not avail:
            continue
        weights = [DIALECT_MIX.get(d, 0.0) for d in avail]
        tot = sum(weights)
        if tot == 0:
            d = rng.choice(avail)
        else:
            r = rng.random() * tot
            acc = 0.0
            d = avail[-1]
            for cand, wt in zip(avail, weights):
                acc += wt
                if r < acc:
                    d = cand
                    break
        out.append((utt, d))
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
