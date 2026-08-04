"""
D89 LEGATO 式优雅指标判决性测试:拒绝窗原文进旁路 / 入口清零不累积 /
eval 全样本 raw NED(拒绝样本不再一票归零)/ 通过样本两针一致。
"""
from __future__ import annotations

import sys
import time

import numpy as np

import rubato.model.infer as inf
from rubato.model.train import run_eval_hooks

VALID = "|4/4k0PR:C4 <|0.00|> 1/1 <|1.00|> |4/4k0c4"
GARBAGE = "PL:C4 PL:C4 PL:C4 garbage"


class GarbageStub:
    def generate(self, audio, prompt=None, num_beams=1):
        return GARBAGE


class ValidStub:
    def generate(self, audio, prompt=None, num_beams=1):
        return VALID


def test_rejected_window_raw_kept_and_reset_per_call():
    audio = np.zeros(10 * 16000, dtype="float32")     # 单窗
    pred = inf.infer_a2s(GarbageStub(), audio, tokenizer=None, beam_size=1)
    assert pred == inf._EMPTY_A2S
    assert inf.LAST_RAW_WINDOWS == [GARBAGE], inf.LAST_RAW_WINDOWS
    # 第二次调用必须清零重来,不许跨样本累积
    pred2 = inf.infer_a2s(ValidStub(), audio, tokenizer=None, beam_size=1)
    assert pred2 != inf._EMPTY_A2S
    assert inf.LAST_RAW_WINDOWS == [VALID], inf.LAST_RAW_WINDOWS


def test_eval_reports_raw_ned_despite_zero_parseable():
    audio = np.zeros(10 * 16000, dtype="float32")
    samples = [{"utt_id": f"u{i}", "audio": audio} for i in range(3)]
    labels = {f"u{i}": {"A2S": "|4/4k0PL:C4 1/1 |4/4k0c4"} for i in range(3)}
    m = run_eval_hooks(GarbageStub(), samples, [], None, labels=labels,
                       eval_max=3, autolog=None, step=0, decode_legs=True)
    assert m["parseable_rate"] == 0.0
    assert m["n_raw_scored"] == 3, m
    assert m["val_text_ned_raw"] is not None and 0.0 < m["val_text_ned_raw"] < 1.0, \
        f"拒绝样本的原文与参照共享 PL:C4 等片段,NED 必须落在 (0,1): {m['val_text_ned_raw']}"
    # 代理针(仅可解析样本)此时必须为空 —— 两针口径不同,不许互相污染
    assert m["n_text_proxy_scored"] == 0


def test_eval_raw_ned_matches_proxy_on_parseable():
    audio = np.zeros(10 * 16000, dtype="float32")
    samples = [{"utt_id": "ok0", "audio": audio}]
    labels = {"ok0": {"A2S": inf.strip_timestamps(VALID)}}
    m = run_eval_hooks(ValidStub(), samples, [], None, labels=labels,
                       eval_max=1, autolog=None, step=0, decode_legs=True)
    assert m["parseable_rate"] == 1.0, m
    assert m["n_raw_scored"] == 1
    assert abs(m["val_text_ned_raw"] - m["val_text_ned_proxy"]) < 1e-9, \
        "通过样本上 raw 针必须与 proxy 针同值(同一 pred 同一参照)"


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
