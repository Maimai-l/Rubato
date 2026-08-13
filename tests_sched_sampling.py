"""
D102 真 scheduled sampling(两遍法)判决性测试:p=0 位级惰性 / p=1+argmax 时
第二遍输入 = 第一遍预测的右移混合(prompt 免疫)/ 训练损失取第二遍且梯度通 /
监控上报齐全 / 缺 decoder 成员必炸 / 聚合口径。
"""
from __future__ import annotations

import sys
import time
import weakref

import torch

sys.path.insert(0, ".")

from rubato.model.train import (accumulate_step_metrics, finalize_step_metrics,
                                new_step_metrics,
                                scheduled_sampling_probability,
                                training_step_logic)

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
    def __init__(self):
        super().__init__()
        self.emb = torch.nn.Embedding(V, D)
        self.mix = torch.nn.Linear(D, D)
        self.seen: list = []                     # 记录每次收到的 input_ids
        self._first_hidden_ref = None
        self.first_graph_alive_on_second = None

    def forward(self, input_ids=None, decoder_mask=None,
                encoder_embeddings=None, encoder_mask=None):
        self.seen.append(input_ids.detach().clone())
        m = encoder_mask.unsqueeze(-1).to(encoder_embeddings.dtype)
        ctx = (encoder_embeddings * m).sum(1) / m.sum(1).clamp(min=1e-6)
        hidden = self.emb(input_ids) + self.mix(ctx).unsqueeze(1)
        if self._first_hidden_ref is None:
            self._first_hidden_ref = weakref.ref(hidden)
        else:
            # 第二遍进场时，第一遍 decoder 图应已释放；encoder 图另有 enc 引用
            # 保留，不受此断言影响。
            self.first_graph_alive_on_second = self._first_hidden_ref() is not None
        return hidden


class MockLsm(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.out = torch.nn.Linear(D, V)

    def forward(self, hidden_states=None):
        return torch.log_softmax(self.out(hidden_states), dim=-1)


class SSNemo(torch.nn.Module):
    """主 forward 与 transf_decoder/log_softmax 同一路径(与生产契约一致)。"""

    def __init__(self):
        super().__init__()
        torch.manual_seed(0)
        self.preprocessor = MockPre()
        self.enc_proj = torch.nn.Linear(1, D)
        self.transf_decoder = MockDec()
        self.log_softmax = MockLsm()

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


def _mk_batch(B=2, L=12, prompt=3, seed=5):
    g = torch.Generator().manual_seed(seed)
    full = torch.randint(0, 40, (B, L + 1), generator=g)
    mask = torch.ones(B, L, dtype=torch.bool)
    mask[:, :prompt] = False
    return {
        "audio": torch.randn(B, 16000, generator=g),
        "audio_lens": torch.tensor([16000] * B),
        "input_ids": full[:, :-1],
        "input_lens": torch.tensor([L] * B),
        "labels": full[:, 1:],
        "token_types": torch.zeros(B, L, dtype=torch.long),
        "loss_mask": mask,
        "ts_bins": torch.zeros(B, L, dtype=torch.long),
    }


def test_p0_bitwise_inert():
    model = SSNemo()
    batch = _mk_batch()
    base = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                               loss_cfg={})
    off = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                              loss_cfg={"sched_sampling_p": 0.0})
    assert torch.equal(base["loss"], off["loss"])
    assert "ss_sem" not in base and "ss_sem" not in off
    assert len(model.transf_decoder.seen) == 2, "p=0 不许有第二遍 decoder 前向"


def test_full_rate_argmax_mixes_own_predictions():
    model = SSNemo()
    batch = _mk_batch(B=2, L=12, prompt=3)
    orig = batch["input_ids"].clone()
    parts = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"sched_sampling_p": 1.0, "sched_sampling_mode": "argmax"})
    # 每样本两次 decoder 调用:第一遍(主前向)+ 第二遍(混合输入)
    assert len(model.transf_decoder.seen) == 2
    first, second = model.transf_decoder.seen
    assert torch.equal(first, orig), "第一遍必须是原始教师强制输入"
    # 可替换位 = j≥1 且 loss_mask[j-1](prompt=3 ⇒ j∈[4,L-1]);j∈[0,3] 免疫
    assert torch.equal(second[:, :4], orig[:, :4]), "prompt/首位被替换 —— 越界"
    # p=1 时全部可替换位 = 第一遍 argmax 预测的右移
    with torch.no_grad():
        lp, _, enc, m = model(
            processed_signal=model.preprocessor(
                input_signal=batch["audio"], length=batch["audio_lens"])[0],
            processed_signal_length=model.preprocessor(
                input_signal=batch["audio"], length=batch["audio_lens"])[1],
            transcript=orig, transcript_length=batch["input_lens"])
    expect = lp.argmax(-1)[:, 3:-1]              # 位置 j 的替身 = 预测[j-1]
    assert torch.equal(second[:, 4:], expect), "替换值必须是第一遍 argmax 的右移"
    assert parts["n_ss_replaced"] == parts["n_ss_eligible"] == 2 * (12 - 4)
    assert torch.equal(batch["input_ids"], orig), "batch 张量不许就地污染"


def test_scheduled_sampling_never_replaces_timestamp_inputs():
    model = SSNemo()
    batch = _mk_batch(B=2, L=12, prompt=3)
    # token_types[k] 描述 labels[k]，也就是 input_ids[k+1] 的类型。
    # 把两个计分目标标成时间戳；即使 p=1，其对应 decoder 输入仍必须保持金标。
    for k, ts_bin in ((5, 2), (8, 7)):
        batch["token_types"][:, k] = 1
        batch["ts_bins"][:, k] = ts_bin
        batch["labels"][:, k] = TS_IDS[ts_bin]
        batch["input_ids"][:, k + 1] = TS_IDS[ts_bin]
    orig = batch["input_ids"].clone()
    training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"sched_sampling_p": 1.0,
                  "sched_sampling_mode": "argmax"})
    mixed = model.transf_decoder.seen[1]
    assert torch.equal(mixed[:, 6], orig[:, 6])
    assert torch.equal(mixed[:, 9], orig[:, 9])


def test_input_dropout_never_replaces_timestamp_inputs():
    model = SSNemo()
    batch = _mk_batch(B=2, L=12, prompt=3)
    for k, ts_bin in ((5, 2), (8, 7)):
        batch["token_types"][:, k] = 1
        batch["ts_bins"][:, k] = ts_bin
        batch["labels"][:, k] = TS_IDS[ts_bin]
        batch["input_ids"][:, k + 1] = TS_IDS[ts_bin]
    orig = batch["input_ids"].clone()
    training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"input_dropout_p": 1.0, "input_dropout_token": 47})
    seen = model.transf_decoder.seen[0]
    assert torch.equal(seen[:, 6], orig[:, 6])
    assert torch.equal(seen[:, 9], orig[:, 9])
    # 至少一个普通内容输入确实被遮，防止测试因整个功能没生效而假通过。
    assert bool((seen[:, 4:] == 47).any())


def test_loss_from_second_pass_and_grads_flow():
    model = SSNemo()
    batch = _mk_batch(seed=9)
    base = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                               loss_cfg={})
    torch.manual_seed(77)
    parts = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"sched_sampling_p": 0.7, "sched_sampling_mode": "sample"})
    assert "ss_sem" in parts and parts["n_ss_sem"] > 0
    assert not torch.equal(base["loss"], parts["loss"]), \
        "训练损失必须来自第二遍(混合输入),不应与教师强制损失位级相同"
    # 监控口径不被污染:第一遍 sem 与基线一致(同输入同权重,前向确定性)
    assert torch.allclose(base["semantic_loss"], parts["semantic_loss"])
    parts["loss"].backward()
    gn = sum(float(p.grad.abs().sum()) for p in model.parameters()
             if p.grad is not None)
    assert gn > 0 and all(
        torch.isfinite(p.grad).all() for p in model.parameters()
        if p.grad is not None)


def test_first_decoder_graph_released_before_second_pass():
    model = SSNemo()
    batch = _mk_batch(seed=13)
    parts = training_step_logic(
        model, batch, None, ts_token_ids=TS_IDS,
        loss_cfg={"sched_sampling_p": 0.25, "sched_sampling_mode": "sample"})
    assert model.transf_decoder.first_graph_alive_on_second is False, \
        "第一遍 decoder 图被挂到第二遍，长 batch 会同时驻留两套图"
    parts["loss"].backward()
    assert any(p.grad is not None for p in model.parameters()), \
        "释放第一遍图不得切断第二遍梯度"


def test_sampling_probabilities_are_chunked():
    model = SSNemo()
    batch = _mk_batch(B=5, L=1024, prompt=3, seed=17)  # 5120 rows > 4096 chunk
    original = torch.multinomial
    seen_rows = []

    def wrapped(probs, *args, **kwargs):
        seen_rows.append(int(probs.shape[0]))
        return original(probs, *args, **kwargs)

    torch.multinomial = wrapped
    try:
        parts = training_step_logic(
            model, batch, None, ts_token_ids=TS_IDS,
            loss_cfg={"sched_sampling_p": 0.25, "sched_sampling_mode": "sample"})
    finally:
        torch.multinomial = original
    assert len(seen_rows) == 2 and max(seen_rows) <= 4096, seen_rows
    assert parts["n_ss_replaced"] > 0


def test_missing_decoder_fails_loud():
    model = NoDecNemo()
    batch = _mk_batch()
    try:
        training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                            loss_cfg={"sched_sampling_p": 0.5})
        raised = False
    except RuntimeError:
        raised = True
    assert raised, "缺 transf_decoder/log_softmax 不能静默跳过"


def test_metrics_aggregation():
    st = new_step_metrics()
    base = {"batch_size": 2, "loss": torch.tensor(1.0), "semantic_loss": 1.0,
            "n_sem": 4, "ts_loss": 0.0, "n_ts": 0, "batch_audio_sec": 10.0}
    accumulate_step_metrics(st, dict(base, ss_sem=3.0, n_ss_sem=4,
                                     n_ss_replaced=6, n_ss_eligible=8))
    accumulate_step_metrics(st, dict(base, ss_sem=1.0, n_ss_sem=4,
                                     n_ss_replaced=2, n_ss_eligible=8))
    m = finalize_step_metrics(st)
    assert abs(m["ss_sem"] - 2.0) < 1e-9
    assert abs(m["ss_replace_rate"] - 0.5) < 1e-9
    st2 = new_step_metrics()
    accumulate_step_metrics(st2, dict(base))
    m2 = finalize_step_metrics(st2)
    assert m2["ss_sem"] is None and m2["ss_replace_rate"] is None


def test_ramp_is_relative_to_immutable_entry_step():
    target, ramp, start = 0.10, 5000, 51300
    assert scheduled_sampling_probability(target, ramp, start, 51300) == 0.0
    assert abs(scheduled_sampling_probability(
        target, ramp, start, 53800) - 0.05) < 1e-12
    assert abs(scheduled_sampling_probability(
        target, ramp, start, 56300) - 0.10) < 1e-12
    # A restart at 54k must retain the original dose, not restart from zero.
    before = scheduled_sampling_probability(target, ramp, start, 54000)
    after = scheduled_sampling_probability(target, ramp, start, 54001)
    assert 0.05 < before < after < 0.10


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
