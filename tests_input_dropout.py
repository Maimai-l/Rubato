"""
1c 遮上文(D86)判决性测试:p=0 位级恒等 / 只遮内容位(prompt+首位免疫)/
标签与 batch 张量零改动 / 缺 unk id 必炸 / resolve_unk_id 各路径 / 监控聚合口径。
"""
from __future__ import annotations

import sys
import time

import torch

from rubato.model.train import (accumulate_step_metrics, finalize_step_metrics,
                                new_step_metrics, resolve_unk_id,
                                training_step_logic)

V, NBINS = 64, 16
TS_IDS = torch.arange(40, 40 + NBINS)
UNK = 63


class MockPre(torch.nn.Module):
    def forward(self, input_signal, length):
        B, S = input_signal.shape
        T = max(S // 160, 1)
        return (input_signal[:, : T * 160].reshape(B, T, 160).transpose(1, 2),
                length // 160)

    def __call__(self, *, input_signal, length):
        return self.forward(input_signal, length)


class CaptureNemo(torch.nn.Module):
    """记录 forward 实际看到的 transcript —— 遮没遮、遮了哪些位,直接对账。"""

    def __init__(self):
        super().__init__()
        torch.manual_seed(0)
        self.preprocessor = MockPre()
        self.emb = torch.nn.Embedding(V, 16)
        self.out = torch.nn.Linear(16, V)
        self.seen = None

    def forward(self, processed_signal=None, processed_signal_length=None,
                transcript=None, transcript_length=None):
        self.seen = transcript.detach().clone()
        logp = torch.log_softmax(self.out(self.emb(transcript)), dim=-1)
        return logp, processed_signal_length, None, None


def _mk_batch(B=2, L=12, prompt=3, seed=3):
    g = torch.Generator().manual_seed(seed)
    full = torch.randint(0, 40, (B, L + 1), generator=g)
    mask = torch.ones(B, L, dtype=torch.bool)
    mask[:, :prompt] = False                      # labels 的前 prompt 位不计分
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


def test_p0_bitwise_identity():
    model = CaptureNemo()
    batch = _mk_batch()
    base = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                               loss_cfg={})
    assert torch.equal(model.seen, batch["input_ids"]), "p=0 不许碰输入"
    p0 = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                             loss_cfg={"input_dropout_p": 0.0,
                                       "input_dropout_token": UNK})
    assert torch.equal(base["loss"], p0["loss"]), "p=0 必须位级恒等"
    assert base["n_input_dropped"] == 0 and base["n_input_eligible"] == 0


def test_full_rate_hits_only_content_positions():
    model = CaptureNemo()
    batch = _mk_batch(B=2, L=12, prompt=3)
    orig = batch["input_ids"].clone()
    parts = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                                loss_cfg={"input_dropout_p": 1.0,
                                          "input_dropout_token": UNK})
    # 可遮位 = j≥1 且 loss_mask[j-1]:prompt=3 ⇒ j∈[4,L-1];j∈[0,3] 永不遮
    assert torch.equal(model.seen[:, :4], orig[:, :4]), "prompt/首位被遮 —— 越界"
    assert bool((model.seen[:, 4:] == UNK).all()), "p=1 时全部内容位必须被遮"
    n_eligible = 2 * (12 - 4)
    assert parts["n_input_eligible"] == n_eligible, parts["n_input_eligible"]
    assert parts["n_input_dropped"] == n_eligible
    # 监督面零改动:batch 张量(含 input_ids)不许被就地污染
    assert torch.equal(batch["input_ids"], orig), "batch['input_ids'] 被就地改写"


def test_partial_rate_masks_subset_with_unk_only():
    model = CaptureNemo()
    batch = _mk_batch(seed=11)
    orig = batch["input_ids"].clone()
    torch.manual_seed(1234)
    parts = training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                                loss_cfg={"input_dropout_p": 0.5,
                                          "input_dropout_token": UNK})
    changed = model.seen != orig
    assert 0 < parts["n_input_dropped"] < parts["n_input_eligible"]
    assert int(changed.sum()) == parts["n_input_dropped"]
    assert bool((model.seen[changed] == UNK).all()), "被遮位只能变成 unk"
    assert not bool(changed[:, :4].any()), "遮出可遮区之外"


def test_missing_unk_token_fails_closed():
    model = CaptureNemo()
    batch = _mk_batch()
    try:
        training_step_logic(model, batch, None, ts_token_ids=TS_IDS,
                            loss_cfg={"input_dropout_p": 0.5})
        raised = False
    except ValueError:
        raised = True
    assert raised, "p>0 缺 unk id 不能静默不遮"


def test_resolve_unk_id_paths():
    class AttrTok:
        unk_id = 7

    class MethTok:
        def unk_id(self):
            return 3

    class PieceTok:
        def piece_to_id(self, p):
            return 5 if p == "<unk>" else -1

    class NothingTok:
        pass

    assert resolve_unk_id(AttrTok()) == 7
    assert resolve_unk_id(MethTok()) == 3
    assert resolve_unk_id(PieceTok()) == 5
    for bad, vs in ((NothingTok(), None), (AttrTok(), 4)):
        try:
            resolve_unk_id(bad, vs)
            raised = False
        except RuntimeError:
            raised = True
        assert raised, f"{type(bad).__name__} vocab={vs} 应当抛错"


def test_metrics_aggregation_drop_rate():
    st = new_step_metrics()
    base = {"batch_size": 2, "loss": torch.tensor(1.0), "semantic_loss": 1.0,
            "n_sem": 4, "ts_loss": 0.0, "n_ts": 0, "batch_audio_sec": 10.0}
    accumulate_step_metrics(st, dict(base, n_input_dropped=8, n_input_eligible=16))
    accumulate_step_metrics(st, dict(base, n_input_dropped=0, n_input_eligible=16))
    m = finalize_step_metrics(st)
    assert abs(m["input_drop_rate"] - 8 / 32) < 1e-9, m["input_drop_rate"]
    st2 = new_step_metrics()
    accumulate_step_metrics(st2, dict(base))
    assert finalize_step_metrics(st2)["input_drop_rate"] is None


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
