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

from scripts.pretrain_decoder import (classify_health, default_nemo_path,
                                      freeze_except_decoder, pretrain_step,
                                      load_resume_state, reset_decoder_parameters,
                                      rows_to_batch, save_decoder_init,
                                      save_resume_state)

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


def test_scratch_reset_and_exact_resume_roundtrip():
    model = StubModel()
    before = model.transf_decoder.emb.weight.detach().clone()
    torch.manual_seed(123)
    assert reset_decoder_parameters(model) > 0
    assert not torch.equal(before, model.transf_decoder.emb.weight.detach()), \
        "scratch 模式必须真的重置 decoder"
    freeze_except_decoder(model)
    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=1e-3)
    tok = StubTok()
    batch, _ = rows_to_batch(ROWS, tok)
    loss, _ = pretrain_step(model, batch, enc_dim=D, device="cpu")
    opt.zero_grad(set_to_none=True)
    loss.backward()
    opt.step()
    signature = {"corpus_sha256": "abc", "seed": 7}
    rng = __import__("random").Random(7)
    _ = [rng.randrange(100) for _ in range(3)]
    expected_rng = [rng.randrange(100) for _ in range(5)]
    # Recreate the state at save time for the actual snapshot.
    rng = __import__("random").Random(7)
    _ = [rng.randrange(100) for _ in range(3)]
    saved = {k: v.detach().clone() for k, v in model.transf_decoder.state_dict().items()}
    with tempfile.TemporaryDirectory() as td:
        path = str(Path(td) / "resume.pt")
        save_resume_state(model, opt, path, step=11, recent=[2.0, 1.5],
                          rng=rng, n_skipped=4, signature=signature)
        assert Path(path).is_file()
        assert not list(Path(td).glob("*.tmp.*")), "原子保存不应遗留临时文件"
        model2 = StubModel()
        freeze_except_decoder(model2)
        opt2 = torch.optim.AdamW(
            [p for p in model2.parameters() if p.requires_grad], lr=1e-3)
        state = load_resume_state(model2, opt2, path, signature, "cpu")
        assert state["step"] == 11 and state["recent"] == [2.0, 1.5]
        assert state["n_skipped_total"] == 4
        assert [state["rng"].randrange(100) for _ in range(5)] == expected_rng
        for k, v in saved.items():
            assert torch.equal(v, model2.transf_decoder.state_dict()[k])
        try:
            load_resume_state(model2, opt2, path, {"corpus_sha256": "wrong"}, "cpu")
            raised = False
        except RuntimeError:
            raised = True
        assert raised, "语料/配置指纹变化必须拒绝近似恢复"


def test_free_eval_rank_prefers_parseable_then_low_dyck():
    from scripts.pretrain_decoder import free_eval_rank
    from rubato.model.build import validate_decoder_init_meta
    a = {"n_parseable": 45, "n": 48, "violation_tally": {"DYCK": 2}}
    b = {"n_parseable": 36, "n": 48, "violation_tally": {"DYCK": 5}}
    c = {"n_parseable": 45, "n": 48, "violation_tally": {"DYCK": 0}}
    assert free_eval_rank(a) > free_eval_rank(b), "可解析数优先"
    assert free_eval_rank(c) > free_eval_rank(a), "同可解析数时 DYCK 少者胜"
    assert free_eval_rank(None) < free_eval_rank(b), "无评测垫底"
    # 最优旁存的 meta 必须能过生产装载检查(complete=True + 自身健康门)
    best_meta = {"complete": True, "best_of_run": True, "health_pass": True,
                 "artifact_role": "decoder_init", "free_eval": a}
    assert validate_decoder_init_meta(best_meta) is best_meta
    try:
        validate_decoder_init_meta(dict(best_meta, health_pass=False))
        raised = False
    except RuntimeError:
        raised = True
    assert raised, "健康门失败的 best 也必须被装载端拒收"


def test_default_nemo_path_matches_workspace_layout():
    with tempfile.TemporaryDirectory() as td:
        parent = Path(td)
        repo = parent / "Rubato"
        repo.mkdir()
        external = parent / "canary-180m-flash.nemo"
        external.write_bytes(b"external")
        assert default_nemo_path(repo) == external
        external.unlink()
        local = repo / "canary-180m-flash.nemo"
        local.write_bytes(b"local")
        assert default_nemo_path(repo) == local


def test_smoke_health_requires_finite_loss():
    # High-but-finite is diagnostic in a short smoke; NaN/Inf is always fatal.
    assert classify_health(4.3, is_smoke=True, free_ok=False) == ("FAIL", True)
    assert classify_health(float("nan"), is_smoke=True, free_ok=True)[1] is False
    assert classify_health(float("inf"), is_smoke=True, free_ok=True)[1] is False
    assert classify_health(2.0, is_smoke=False, free_ok=True) == ("GRAY", True)
    assert classify_health(2.0, is_smoke=False, free_ok=False) == ("GRAY", False)
    # D92: CE class is now diagnostic only; finite CE + both formal gates pass.
    assert classify_health(4.0, is_smoke=False, free_ok=True,
                           dyck_ok=True) == ("FAIL", True)
    assert classify_health(2.0, is_smoke=False, free_ok=True,
                           dyck_ok=False) == ("GRAY", False)


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
