"""
交叉注意力音频依赖损失(D86)判决性测试:weight=0 位级惰性 / 同音频 ⇒ gap=0 罚=margin
(解析值)/ 异音频报告齐全且 loss=基线+权×罚 / 梯度通 / B=1 跳过计数 /
缺 transf_decoder 必炸 / 监控聚合口径。
"""
from __future__ import annotations

import sys
import time

import torch

from rubato.model.train import (accumulate_step_metrics, finalize_step_metrics,
                                new_step_metrics, training_step_logic)

V, NBINS, D = 64, 16, 16
TS_IDS = torch.arange(40, 40 + NBINS)


class MockPre(torch.nn.Module):
    def forward(self, input_signal, length):
        B, S = input_signal.shape
        T = max(S // 160, 1)
        return (input_signal[:, : T * 160].reshape(B, T, 160).transpose(1, 2),
                length // 160)

    def __call__(self, *, input_signal, length):
        return self.forward(input_signal, length)


class MockDec(torch.nn.Module):
    """镜像 NeMo TransformerDecoder 关键字签名;交叉注意力 = masked 均值上下文注入。"""

    def __init__(self, emb, mix):
        super().__init__()
        self.emb, self.mix = emb, mix

    def forward(self, input_ids=None, decoder_mask=None,
                encoder_embeddings=None, encoder_mask=None):
        m = encoder_mask.unsqueeze(-1).to(encoder_embeddings.dtype)
        ctx = (encoder_embeddings * m).sum(1) / m.sum(1).clamp(min=1e-6)
        return self.emb(input_ids) + self.mix(ctx).unsqueeze(1)


class MockLsm(torch.nn.Module):
    def __init__(self, out):
        super().__init__()
        self.out = out

    def forward(self, hidden_states=None):
        return torch.log_softmax(self.out(hidden_states), dim=-1)


class DepNemo(torch.nn.Module):
    """模仿 EncDecMultiTaskModel:主 forward 与 transf_decoder/log_softmax 同一路径,
    enc 状态真依赖音频内容(帧均值投影)—— 错配才会产生非零 gap。"""

    def __init__(self):
        super().__init__()
        torch.manual_seed(0)
        self.preprocessor = MockPre()
        self.enc_proj = torch.nn.Linear(1, D)
        self.transf_decoder = MockDec(torch.nn.Embedding(V, D),
                                      torch.nn.Linear(D, D))
        self.log_softmax = MockLsm(torch.nn.Linear(D, V))

    def forward(self, processed_signal=None, processed_signal_length=None,
                transcript=None, transcript_length=None):
        enc = self.enc_proj(processed_signal.mean(1).unsqueeze(-1))
        T = enc.shape[1]
        mask = (torch.arange(T).unsqueeze(0)
                < processed_signal_length.unsqueeze(1)).long()
        h = self.transf_decoder(input_ids=transcript,
                                decoder_mask=torch.ones_like(transcript),
                                encoder_embeddings=enc, encoder_mask=mask)
        return self.log_softmax(hidden_states=h), processed_signal_length, enc, mask


class NoDecNemo(torch.nn.Module):
    """有 4 元组返回但没有 transf_decoder/log_softmax 成员的模型。"""

    def __init__(self):
        super().__init__()
        torch.manual_seed(0)
        self.preprocessor = MockPre()
        self.emb = torch.nn.Embedding(V, D)
        self.out = torch.nn.Linear(D, V)

    def forward(self, processed_signal=None, processed_signal_length=None,
                transcript=None, transcript_length=None):
        logp = torch.log_softmax(self.out(self.emb(transcript)), dim=-1)
        B, T = transcript.shape[0], int(processed_signal.shape[-1])
        return (logp, processed_signal_length,
                torch.zeros(B, T, D), torch.ones(B, T, dtype=torch.long))


def _mk_batch(B=2, L=12, same_audio=False, seed=5):
    g = torch.Generator().manual_seed(seed)
    full = torch.randint(0, 40, (B, L + 1), generator=g)
    audio = torch.randn(B, 16000, generator=g)
    if same_audio:
        audio = audio[:1].expand(B, -1).clone()
    return {
        "audio": audio,
        "audio_lens": torch.tensor([16000] * B),
        "input_ids": full[:, :-1],
        "input_lens": torch.tensor([L] * B),
        "labels": full[:, 1:],
        "token_types": torch.zeros(B, L, dtype=torch.long),
        "loss_mask": torch.ones(B, L, dtype=torch.bool),
        "ts_bins": torch.zeros(B, L, dtype=torch.long),
    }


def test_weight0_inert():
    model = DepNemo()
    batch = _mk_batch()
    base = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                               loss_cfg={})
    off = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                              loss_cfg={"audio_dep": {"weight": 0.0}})
    assert torch.equal(base["loss"], off["loss"]), "weight=0 必须位级惰性"
    assert "audio_dep_loss" not in base and "audio_dep_loss" not in off


def test_identical_audio_gap_zero_penalty_margin():
    model = DepNemo()
    batch = _mk_batch(same_audio=True)
    parts = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"audio_dep": {"weight": 0.3, "margin": 0.2}})
    # 两条序列音频相同 ⇒ roll 后 enc 不变 ⇒ ce_mis≡ce_mat ⇒ gap=0,罚=margin(解析值)
    assert abs(float(parts["audio_dep_gap"])) < 1e-5, float(parts["audio_dep_gap"])
    assert abs(float(parts["audio_dep_loss"]) - 0.2) < 1e-5, \
        float(parts["audio_dep_loss"])
    assert parts["n_audio_dep"] == 2


def test_distinct_audio_reports_and_loss_composition():
    model = DepNemo()
    batch = _mk_batch()
    base = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                               loss_cfg={})
    parts = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"audio_dep": {"weight": 0.3, "margin": 0.2}})
    assert parts["n_audio_dep"] == 2
    assert torch.isfinite(parts["audio_dep_gap"])
    expect = float(base["loss"].detach()) + 0.3 * float(parts["audio_dep_loss"])
    assert abs(float(parts["loss"].detach()) - expect) < 1e-5, \
        f"{float(parts['loss'].detach())} vs {expect}"
    parts["loss"].backward()
    for name, p in model.named_parameters():
        assert p.grad is None or bool(torch.isfinite(p.grad).all()), name
    gn = sum(float(p.grad.abs().sum()) for p in model.parameters()
             if p.grad is not None)
    assert gn > 0


def test_b1_skipped_with_counter():
    model = DepNemo()
    batch = _mk_batch(B=1)
    base = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                               loss_cfg={})
    parts = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"audio_dep": {"weight": 0.3, "margin": 0.2}})
    assert parts["n_audio_dep"] == 0 and parts["audio_dep_loss"] is None
    assert torch.equal(base["loss"], parts["loss"]), "跳过时不许改 loss"


def test_missing_decoder_fails_loud():
    model = NoDecNemo()
    batch = _mk_batch()
    try:
        training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                            loss_cfg={"audio_dep": {"weight": 0.3}})
        raised = False
    except RuntimeError:
        raised = True
    assert raised, "缺 transf_decoder/log_softmax 不能静默跳过"


def test_monitor_mode_gauges_without_touching_loss():
    model = DepNemo()
    batch = _mk_batch()
    base = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                               loss_cfg={})
    mon = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"audio_dep": {"weight": 0.0, "margin": 0.2,
                                "monitor_now": True}})
    assert torch.equal(base["loss"], mon["loss"]), "仪表模式不许碰 loss"
    assert mon["n_audio_dep"] == 2
    assert torch.isfinite(mon["audio_dep_gap"])
    assert not mon["audio_dep_gap"].requires_grad, "仪表读数不得挂梯度图"
    off = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"audio_dep": {"weight": 0.0, "monitor_now": False}})
    assert "audio_dep_gap" not in off, "monitor_now=False 不该做第二次 forward"


def test_monitor_yields_to_live_weight():
    model = DepNemo()
    batch = _mk_batch()
    base = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                               loss_cfg={})
    live = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"audio_dep": {"weight": 0.3, "margin": 0.2,
                                "monitor_now": True}})
    expect = float(base["loss"].detach()) + 0.3 * float(live["audio_dep_loss"])
    assert abs(float(live["loss"].detach()) - expect) < 1e-5, \
        "weight>0 时 monitor_now 必须让位于训练版(罚项照加)"


def test_metrics_aggregation_weighted_mean():
    st = new_step_metrics()
    base = {"batch_size": 2, "loss": torch.tensor(1.0), "semantic_loss": 1.0,
            "n_sem": 4, "ts_loss": 0.0, "n_ts": 0, "batch_audio_sec": 10.0}
    accumulate_step_metrics(st, dict(base, n_audio_dep=2,
                                     audio_dep_loss=torch.tensor(0.4),
                                     audio_dep_gap=torch.tensor(0.1)))
    accumulate_step_metrics(st, dict(base, n_audio_dep=1,
                                     audio_dep_loss=torch.tensor(0.1),
                                     audio_dep_gap=torch.tensor(0.4)))
    m = finalize_step_metrics(st)
    assert abs(m["audio_dep_loss"] - (0.4 * 2 + 0.1) / 3) < 1e-6
    assert abs(m["audio_dep_gap"] - (0.1 * 2 + 0.4) / 3) < 1e-6
    assert m["n_audio_dep"] == 3
    st2 = new_step_metrics()
    accumulate_step_metrics(st2, dict(base, n_audio_dep=0,
                                      audio_dep_loss=None, audio_dep_gap=None))
    m2 = finalize_step_metrics(st2)
    assert m2["audio_dep_loss"] is None and m2["n_audio_dep"] == 0


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
