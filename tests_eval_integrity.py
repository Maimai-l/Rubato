"""评测完整性回归：真实 beam 与局部丢窗状态不得再被 fallback 掩盖。"""
import math
import sys

import numpy as np
import torch

sys.path.insert(0, ".")

import rubato.model.infer as inf


class TinyTokenizer:
    pieces = {"<p>": 0, "<|eot|>": 4}
    names = {0: "P", 1: "A", 2: "B", 3: "C", 4: "E"}

    def piece_to_id(self, piece):
        return self.pieces[piece]

    def decode(self, ids):
        return "".join(self.names[int(i)] for i in ids)


class TinyDecoder(torch.nn.Module):
    """首步 greedy 选 A；全局 beam 应发现 B→EOT 的累计概率更高。"""
    def __init__(self):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(()))

    def preprocessor(self, input_signal, length):
        return input_signal[:, None, :1], length

    @staticmethod
    def _lp(ids):
        b, t = ids.shape
        out = torch.full((b, t, 5), math.log(1e-6), device=ids.device)
        for i in range(b):
            last = int(ids[i, -1])
            if last == 0:       # prompt: greedy A=.6, alternate B=.4
                probs = [1e-6, .60, .399997, 1e-6, 1e-6]
            elif last == 1:     # A 后续很差，最好也只有 .2
                probs = [.199, .199, .199, .204, .199]
            elif last == 2:     # B 立刻可靠结束
                probs = [.0025, .0025, .0025, .0025, .99]
            else:
                probs = [.20, .20, .20, .20, .20]
            out[i, -1] = torch.log(torch.tensor(probs, device=ids.device))
        return out

    def forward(self, processed_signal, processed_signal_length,
                transcript, transcript_length):
        b = transcript.shape[0]
        enc = torch.zeros((b, 1, 2), device=transcript.device)
        mask = torch.ones((b, 1), device=transcript.device)
        return self._lp(transcript), transcript_length, enc, mask

    def transf_decoder(self, input_ids, decoder_mask,
                       encoder_embeddings, encoder_mask):
        return input_ids

    def log_softmax(self, hidden_states):
        return self._lp(hidden_states)


def test_real_beam_differs_from_greedy():
    model = TinyDecoder()
    tok = TinyTokenizer()
    audio = np.zeros(32, dtype="float32")
    greedy = inf.autoregressive_decode(
        model, audio, tok, ["<p>"], max_new=2,
        rep_penalty=1.0, beam_size=1)
    beam = inf.autoregressive_decode(
        model, audio, tok, ["<p>"], max_new=2,
        rep_penalty=1.0, beam_size=2)
    assert greedy == "AC", greedy
    assert beam == "B", beam
    assert inf.LAST_GEN_STATS["beam_size"] == 2


class PartialStub:
    def __init__(self):
        self.calls = 0

    def generate(self, audio, prompt=None, num_beams=1):
        self.calls += 1
        if self.calls == 1:
            return "garbage"
        return "|4/4k0PR:C4 <|0.00|> 1/1 <|1.00|> |4/4k0c4"


def test_partial_window_is_structured_failure_not_silent_success():
    audio = np.zeros(60 * 16000, dtype="float32")
    pred = inf.infer_a2s(PartialStub(), audio, tokenizer=None, beam_size=1)
    assert pred != inf._EMPTY_A2S
    assert inf.LAST_INFER_STATS["status"] == "partial", inf.LAST_INFER_STATS
    assert inf.LAST_INFER_STATS["n_failed_windows"] == 1
    assert not inf.LAST_INFER_STATS["fallback"]

def test_tast_timestamp_guard_rejects_nonmonotone_and_missing():
    good = "|4/4k0PR:C4 <|0.00|> 1/1 <|1.00|> |4/4k0c4"
    assert inf.validate_tast_timestamps(good) == []
    bad = "|4/4k0PR:C4 <|2.00|> 1/1 <|1.00|> |4/4k0c4"
    assert any(v.startswith("TS_NONMONOTONE") for v in
               inf.validate_tast_timestamps(bad))
    missing = "|4/4k0PR:C4 1/1 <|1.00|> |4/4k0c4"
    assert any(v.startswith("TS_MISSING") for v in
               inf.validate_tast_timestamps(missing))


def test_window_guard_exhaustion_is_partial_not_success():
    original = inf.single_window_tast
    # 必须是非空合法谱；空谱的投影与 _EMPTY_A2S 相同，无法区分
    # “部分成功”与 fallback，反而会让测试误报。
    inf.single_window_tast = (
        lambda *a, **k:
        "|4/4k0PR:C4 <|0.10|> 1/1 <|0.10|> |4/4k0c4"
    )
    try:
        pred = inf.infer_a2s(object(), np.zeros(100 * 16000, dtype="float32"),
                             tokenizer=None)
    finally:
        inf.single_window_tast = original
    assert pred != inf._EMPTY_A2S
    assert inf.LAST_INFER_STATS["status"] == "partial", inf.LAST_INFER_STATS
    assert any(x["stage"] == "window_guard_exhausted"
               for x in inf.LAST_INFER_STATS["window_failures"])


def test_amt_failure_has_structured_status():
    class Broken:
        def generate(self, *args, **kwargs):
            raise RuntimeError("boom")
    assert inf.infer_amt(Broken(), np.zeros(16, dtype="float32"), None) == ""
    assert inf.LAST_INFER_STATS["status"] == "exception"
    assert inf.LAST_INFER_STATS["fallback"] is True


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print("  ok", fn.__name__)
    print(f"全部通过: {len(tests)} 项")
