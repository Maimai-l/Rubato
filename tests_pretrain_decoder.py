"""
D91 decoder 预训练判决性测试:encode_target 同构批 / 零上下文前向 + 掩码 CE /
只有 decoder 侧参数得到梯度且真的在学 / 存-载往返 + build_model 注入契约(stub 层)。
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import torch

sys.path.insert(0, ".")

from scripts.pretrain_decoder import (freeze_except_decoder, pretrain_step,
                                      rows_to_batch, save_decoder_init)

V, D = 96, 16


class StubTok:
    """自动编号词表:encode 切空格,piece_to_id 首见即注册(含 prompt/eot piece)。"""

    def __init__(self):
        self.map: dict = {}

    def _id(self, p):
        if p not in self.map:
            if len(self.map) >= V:
                raise RuntimeError("stub 词表溢出")
            self.map[p] = len(self.map)
        return self.map[p]

    def encode(self, text, out_type=str, **kw):
        assert out_type is str
        return text.split()

    def piece_to_id(self, p):
        return self._id(p)


class MockDec(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.emb = torch.nn.Embedding(V, D)
        self.mix = torch.nn.Linear(D, D)

    def forward(self, input_ids=None, decoder_mask=None,
                encoder_embeddings=None, encoder_mask=None):
        m = encoder_mask.unsqueeze(-1).to(encoder_embeddings.dtype)
        ctx = (encoder_embeddings * m).sum(1) / m.sum(1).clamp(min=1e-6)
        # 零上下文时 ctx=0,mix 仅贡献 bias —— decoder-only LM 语义成立
        return self.emb(input_ids) + self.mix(ctx).unsqueeze(1)


class MockLsm(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.out = torch.nn.Linear(D, V)

    def forward(self, hidden_states=None):
        return torch.log_softmax(self.out(hidden_states), dim=-1)


class StubModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        torch.manual_seed(0)
        self.transf_decoder = MockDec()
        self.log_softmax = MockLsm()
        self.encoder_frozen = torch.nn.Linear(4, 4)   # 代表"其余必须冻结"的参数


ROWS = [{"dialect": "A2S", "text": "|4/4k0 PL:C4 1/4 c4D4 1/4 d4 1/2"},
        {"dialect": "A2S", "text": "|3/4k-1 PR:E5 1/4 e5F5 1/4 f5G5 1/4 g5"}]


def test_batch_via_production_encode_target():
    tok = StubTok()
    batch, skipped = rows_to_batch(ROWS, tok)
    assert skipped == 0 and batch is not None
    assert batch["input_ids"].shape == batch["labels"].shape
    assert bool(batch["loss_mask"].any()), "标签位必须计分"
    # prompt 位不计分:每行 loss_mask 的 False 前缀非空(encode_target 契约)
    for i in range(batch["input_ids"].shape[0]):
        n = int(batch["input_lens"][i])
        assert not bool(batch["loss_mask"][i, 0]), "首位(prompt)不该计分"
        assert bool(batch["loss_mask"][i, :n][-1]), "eot 位该计分"
    # 超长过滤
    long_row = {"dialect": "A2S", "text": " ".join(["1/4 PL:C4 c4"] * 800)}
    b2, sk2 = rows_to_batch([long_row], tok, max_len=100)
    assert b2 is None and sk2 == 1


def test_only_decoder_learns_and_loss_drops():
    model = StubModel()
    n_train, n_frozen = freeze_except_decoder(model)
    assert n_train > 0 and n_frozen > 0
    frozen_before = model.encoder_frozen.weight.detach().clone()
    tok = StubTok()
    batch, _ = rows_to_batch(ROWS, tok)
    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=5e-2)
    losses = []
    for _ in range(30):
        loss, n_tok = pretrain_step(model, batch, enc_dim=D, device="cpu")
        assert n_tok > 0 and torch.isfinite(loss)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        assert model.encoder_frozen.weight.grad is None, "冻结参数不许有梯度"
        opt.step()
        losses.append(float(loss.detach()))
    assert losses[-1] < losses[0] * 0.7, f"30 步应显著下降: {losses[0]:.3f}→{losses[-1]:.3f}"
    assert torch.equal(frozen_before, model.encoder_frozen.weight.detach()), \
        "冻结参数被更新 —— 只训 decoder 的契约破了"


def test_save_load_roundtrip_and_strict_mismatch():
    model = StubModel()
    with tempfile.TemporaryDirectory() as td:
        p = str(Path(td) / "dec.pt")
        save_decoder_init(model, p, {"steps": 7})
        snap = torch.load(p)
        assert set(snap) == {"transf_decoder", "log_softmax", "meta"}
        m2 = StubModel()
        m2.transf_decoder.load_state_dict(snap["transf_decoder"], strict=True)
        m2.log_softmax.load_state_dict(snap["log_softmax"], strict=True)
        assert torch.equal(m2.transf_decoder.emb.weight,
                           model.transf_decoder.emb.weight)
        # 形状不符必须 strict 崩(build_model 注入走同一契约)
        class OtherDec(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.emb = torch.nn.Embedding(V + 1, D)
                self.mix = torch.nn.Linear(D, D)
        try:
            OtherDec().load_state_dict(snap["transf_decoder"], strict=True)
            raised = False
        except RuntimeError:
            raised = True
        assert raised, "词表不符的 decoder_init 不许静默载入"


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
