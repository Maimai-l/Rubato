"""
D82 音高加权 loss 判决性测试:掩码构建与探针同一定义 / weight=1 位级恒等 /
监控口径永远未加权 / 加权方向正确(均值归一只移占比) / 梯度通。
"""
from __future__ import annotations

import sys
import time

import torch

from rubato.model.losses import batch_sequence_loss, build_pitch_token_mask

V = 32


class StubTok:
    """8 个可辨 piece:2 音高(id 3='C4', id 5='n60')+ 杂项;其余 id 返回占位。"""
    _pieces = {0: "<unk>", 1: "hello", 2: "<|0.00|>", 3: "C4", 4: "PL:",
               5: "n60", 6: "x9", 7: "F##5"}

    def id_to_piece(self, i):
        return self._pieces.get(i, f"tok{i}")


def _mk(B=2, L=6, seed=7):
    g = torch.Generator().manual_seed(seed)
    lp = torch.log_softmax(torch.randn(B, L, V, generator=g), dim=-1)
    labels = torch.randint(0, 8, (B, L), generator=g)
    types = torch.zeros(B, L, dtype=torch.long)
    mask = torch.ones(B, L, dtype=torch.bool)
    bins = torch.zeros(B, L, dtype=torch.long)
    ts_ids = torch.arange(16, dtype=torch.long)
    return lp, labels, types, mask, bins, ts_ids


def test_mask_matches_probe_regex():
    m = build_pitch_token_mask(StubTok(), 8)
    assert m.tolist() == [False, False, False, True, False, True, False, True], m.tolist()
    # C4 ✓ n60 ✓ F##5 ✓;x9(非音名字母)✗ 时间戳 ✗


def test_weight1_bitwise_identical_and_monitor_unweighted():
    lp, labels, types, mask, bins, ts_ids = _mk()
    m = build_pitch_token_mask(StubTok(), V)
    base = batch_sequence_loss(lp, labels, types, mask, bins, ts_ids)
    w1 = batch_sequence_loss(lp, labels, types, mask, bins, ts_ids,
                             pitch_weight=1.0, pitch_mask=m)
    assert torch.equal(base["loss"], w1["loss"]), "weight=1 必须位级恒等"
    assert torch.equal(base["seq_sem"], w1["seq_sem"])
    # weight=3:loss 变,但监控口径(sem/seq_sem)必须与未加权完全一致(基线可比性)
    w3 = batch_sequence_loss(lp, labels, types, mask, bins, ts_ids,
                             pitch_weight=3.0, pitch_mask=m)
    assert torch.equal(base["seq_sem"], w3["seq_sem"]), "监控口径被加权污染 —— 基线曲线失比"
    assert torch.allclose(base["sem"], w3["sem"])
    assert w3["n_pitch"] > 0


def test_weight_direction_with_normalization():
    lp, labels, types, mask, bins, ts_ids = _mk()
    labels[0, 0] = 3                                    # 保证至少一个音高位
    m = build_pitch_token_mask(StubTok(), V)
    # 构造:音高位 CE 高(概率压低),非音高位 CE 低 → 加权应抬升 loss
    lp_bad = lp.clone()
    pit = m[labels.clamp(max=V - 1)]
    lp_bad[pit] = torch.log_softmax(torch.full((V,), 0.0), dim=-1)      # 均匀=高 CE
    for b in range(labels.shape[0]):
        for t in range(labels.shape[1]):
            if not pit[b, t]:
                v = torch.full((V,), -10.0)
                v[labels[b, t]] = 0.0                                    # 尖峰=低 CE
                lp_bad[b, t] = torch.log_softmax(v, dim=-1)
    l1 = batch_sequence_loss(lp_bad, labels, types, mask, bins, ts_ids,
                             pitch_weight=1.0, pitch_mask=m)["loss"]
    l3 = batch_sequence_loss(lp_bad, labels, types, mask, bins, ts_ids,
                             pitch_weight=3.0, pitch_mask=m)["loss"]
    assert l3 > l1, f"音高位痛时加权应抬升 loss: {float(l1):.4f} → {float(l3):.4f}"
    # 反向:音高位好、其余差 → 加权应降低 loss(占比向好位移动)
    lp_good = lp.clone()
    for b in range(labels.shape[0]):
        for t in range(labels.shape[1]):
            v = torch.full((V,), -10.0 if pit[b, t] else 0.0)
            if pit[b, t]:
                v[labels[b, t]] = 0.0
            lp_good[b, t] = torch.log_softmax(v, dim=-1)
    g1 = batch_sequence_loss(lp_good, labels, types, mask, bins, ts_ids,
                             pitch_weight=1.0, pitch_mask=m)["loss"]
    g3 = batch_sequence_loss(lp_good, labels, types, mask, bins, ts_ids,
                             pitch_weight=3.0, pitch_mask=m)["loss"]
    assert g3 < g1, f"音高位好时加权应降低 loss: {float(g1):.4f} → {float(g3):.4f}"


def test_grad_flows_with_weighting():
    lp, labels, types, mask, bins, ts_ids = _mk()
    labels[0, 0] = 3
    raw = torch.randn(*lp.shape, requires_grad=True)
    lp2 = torch.log_softmax(raw, dim=-1)
    m = build_pitch_token_mask(StubTok(), V)
    out = batch_sequence_loss(lp2, labels, types, mask, bins, ts_ids,
                              pitch_weight=2.5, pitch_mask=m)
    out["loss"].backward()
    assert raw.grad is not None and torch.isfinite(raw.grad).all()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        t0 = time.time()
        try:
            fn()
            print(f"  ok {fn.__name__} ({time.time()-t0:.1f}s)")
        except Exception as e:
            bad += 1
            import traceback
            print(f"  FAIL {fn.__name__}: {e}")
            traceback.print_exc(limit=4)
    print(("PASS" if not bad else "FAIL") + f" {len(fns)-bad}/{len(fns)}")
    sys.exit(1 if bad else 0)
