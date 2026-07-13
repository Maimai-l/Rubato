"""自研自回归解码回归:只用 forward、快路径自校验、不符退慢路径、eot 停、长度上限。
运行: python tests_infer_decode.py"""
import sys

sys.path.insert(0, ".")
import torch
import torch.nn as nn

from rubato.model.infer import autoregressive_decode

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


V, EOT = 10, 9


class Tok:
    """id 即语义:piece '<|p{i}|>'→i,eot→9,decode → 连字符串。"""
    def piece_to_id(self, p):
        return EOT if p == "<|eot|>" else int(p.strip("<|p>"))

    def decode(self, ids):
        return "".join(str(i) for i in ids)


def rule_lp(ids_row):
    """确定性规则:下一 token = (最后一个 id + 1) % 10 → 从 2 起会数到 9(eot)停。"""
    L = len(ids_row)
    lp = torch.full((1, L, V), -10.0)
    for j, tid in enumerate(ids_row):
        lp[0, j, (int(tid) + 1) % V] = 0.0
    return lp


class StubModel(nn.Module):
    """forward 契约与训练一致:(lp, enc_len, enc_states, enc_mask)。fast_consistent 控制
    内部模块快路径与 forward 是否一致(不一致必须被自校验拒收 → 退慢路径)。"""
    def __init__(self, fast_consistent=True):
        super().__init__()
        self.p = nn.Parameter(torch.zeros(1))
        self.fast_consistent = fast_consistent
        self.n_forward = 0
        self.n_fast = 0

    def preprocessor(self, input_signal, length):
        return input_signal, length

    def forward(self, processed_signal, processed_signal_length, transcript, transcript_length):
        self.n_forward += 1
        return (rule_lp(transcript[0].tolist()), processed_signal_length,
                torch.zeros(1, 4, 8), torch.ones(1, 4))

    def transf_decoder(self, input_ids, decoder_mask, encoder_embeddings, encoder_mask):
        return input_ids                       # 占位,真正出 lp 在 log_softmax

    def log_softmax(self, hidden_states):
        self.n_fast += 1
        lp = rule_lp(hidden_states[0].tolist())
        return lp if self.fast_consistent else lp + 3.14   # 不一致:自校验必须拒收


audio = torch.zeros(64)

print("[1] 快路径自校验通过:贪心从 prompt=2 数到 8,eot(9)停;解码只走快路径")
m = StubModel(fast_consistent=True)
out = autoregressive_decode(m, audio, Tok(), ["<|p2|>"])
check("sequence", out == "345678", out)         # prompt 2 之后:3..8,预测 9=eot 停
check("fast_used", m.n_fast > 3, m.n_fast)
check("encoder_once", m.n_forward == 1, m.n_forward)   # forward 只为编码器+自校验跑一次

print("[2] 快路径与 forward 不一致 → 自校验拒收,退慢路径(全量 forward),结果仍正确")
m2 = StubModel(fast_consistent=False)
out2 = autoregressive_decode(m2, audio, Tok(), ["<|p2|>"])
check("slow_sequence", out2 == "345678", out2)
check("slow_via_forward", m2.n_forward > 3, m2.n_forward)

print("[3] max_new 上限:规则改成永不出 eot 时按上限截断")
class NoEotStub(StubModel):
    def forward(self, processed_signal, processed_signal_length, transcript, transcript_length):
        self.n_forward += 1
        L = len(transcript[0])
        lp = torch.full((1, L, V), -10.0)
        lp[0, -1, 5] = 0.0                     # 永远预测 5,不出 eot
        return lp, processed_signal_length, torch.zeros(1, 4, 8), torch.ones(1, 4)
    def log_softmax(self, hidden_states):
        self.n_fast += 1
        L = len(hidden_states[0])
        lp = torch.full((1, L, V), -10.0)
        lp[0, -1, 5] = 0.0
        return lp
out3 = autoregressive_decode(NoEotStub(), audio, Tok(), ["<|p2|>"], max_new=7)
check("max_new_capped", out3 == "5" * 7, out3)

print(f"\n全部通过: {PASS} 项")
