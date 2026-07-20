"""
D43 新仪表的判决性测试:eval 拒因直方图(viol_tally)+ 探针音高分型(acc_pitch)。
"""
import time

import torch

from rubato.model.train import viol_tally
from rubato.model.infer import _probe_from_logprobs


def test_viol_tally_categories():
    entries = [
        (True, ["TERMINAL_BAR_MISSING"]),                      # 兜底样本:viol 是兜底常量的,只记兜底
        (False, []),                                           # 通过
        (False, ["DYCK_ORPHAN_OFFSET:x@1", "DYCK_UNCLOSED:y"]),  # 同类多条 → 记 1 个样本
        (False, ["MEASURE_SUM:2 got 7/8 want 1", "TERMINAL_BAR_MISSING"]),  # 跨类 → 各记 1
        (False, ["未知怪拒因:z"]),
    ]
    t = viol_tally(entries)
    assert t["兜底"] == 1
    assert t["通过"] == 1
    assert t["DYCK"] == 1
    assert t["MEASURE"] == 1
    assert t["TERMINAL"] == 1
    assert t["未知怪拒因"] == 1
    assert sum(t.values()) == 6                                # 5 样本,跨类样本记 2


def test_viol_tally_empty():
    assert viol_tally([]) == {}


class PitchTok:
    """id→piece:60=N60(音高) 61=n61(音高) 5=C4(音高) 7=vel 9=时间戳 11=普通语义。"""
    _m = {60: "N60", 61: "n61", 5: "C4", 7: "<|vel:9|>", 9: "<|0.50|>", 11: "PL:"}

    def id_to_piece(self, i):
        return self._m.get(int(i), "x")

    def decode(self, ids):
        return "".join(self._m.get(int(i), "?") for i in ids)


def test_probe_acc_pitch():
    # 5 个计分位,labels = [N60, n61, C4, vel, ts];logits 让 N60/C4 命中、n61 miss
    V = 100
    lp = torch.full((5, V), -10.0)
    labels = [60, 61, 5, 7, 9]
    hits = [60, 99, 5, 7, 9]        # 位置1 预测 99 ≠ 61
    for t, h in enumerate(hits):
        lp[t, h] = 0.0
    out = _probe_from_logprobs(lp, labels, [True] * 5, eot_id=2,
                               tokenizer=PitchTok(), token_types=[0, 0, 0, 0, 1])
    assert out["n_pitch"] == 3                                  # N60/n61/C4
    assert abs(out["acc_pitch"] - 2 / 3) < 1e-6                 # 命中 N60、C4
    assert abs(out["acc"] - 4 / 5) < 1e-6


def test_probe_acc_pitch_absent_without_id_to_piece():
    class NoPieceTok:
        def decode(self, ids):
            return ""
    lp = torch.full((2, 10), -1.0)
    out = _probe_from_logprobs(lp, [1, 2], [True, True], eot_id=0, tokenizer=NoPieceTok())
    assert "acc_pitch" not in out                               # 老分词器:仪表缺席而非报错


def test_probe_acc_pitch_none_when_no_pitch_tokens():
    lp = torch.full((2, 100), -1.0)
    out = _probe_from_logprobs(lp, [7, 9], [True, True], eot_id=2, tokenizer=PitchTok())
    assert out["acc_pitch"] is None and out["n_pitch"] == 0


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            t0 = time.time()
            try:
                fn()
                print(f"  ok {name} ({time.time() - t0:.1f}s)")
            except Exception as e:
                fails += 1
                print(f"  FAIL {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if fails else 0)
