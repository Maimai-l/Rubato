"""训前体检 + 训练步前置守卫回归(CUDA 异步 assert 不可诊断 → 明文数字/精确断言)。
运行: python tests_preflight.py"""
import sys

sys.path.insert(0, ".")
import torch
import torch.nn as nn

from rubato.model.build import vocab_position_preflight
from rubato.model.train import training_step_logic

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


class M(nn.Module):
    def __init__(self, v_tok, v_out, pos, ffn=0):
        super().__init__()
        self.tok_emb = nn.Embedding(v_tok, 16)
        self.pos_emb = nn.Embedding(pos, 16)
        self.head = nn.Linear(16, v_out)
        if ffn:
            self.dense_in = nn.Linear(16, ffn)   # canary decoder FFN 隐层(1024→4096)


class Tok:
    def get_piece_size(self):
        return 8000


print("[1] 体检:一致模型 → 无问题,max_pos = 位置表行数;FFN 4096 隐层【不】误报")
pf = vocab_position_preflight(M(8000, 8000, 512, ffn=4096), Tok(), old_vocab=5248)
check("clean_no_problems", pf["problems"] == [], pf["problems"])   # 执行端第 4 次运行的误报回归
check("ffn_in_notes", any("dense_in" in w for w in pf["notes"]), pf["notes"])
check("max_pos_512", pf["max_pos"] == 512, pf["max_pos"])
check("vocab_8000", pf["vocab"] == 8000)

print("[2] 体检:输出头没换(旧词表 5248)→ 点名;词表 Embedding 没换 → 点名")
pf2 = vocab_position_preflight(M(8000, 5248, 512), Tok(), old_vocab=5248)
check("stale_head_flagged", any("head" in p and "5248" in p for p in pf2["problems"]), pf2["problems"])
pf3 = vocab_position_preflight(M(5248, 8000, 512), Tok(), old_vocab=5248)
check("stale_emb_flagged", any("tok_emb" in p for p in pf3["problems"]), pf3["problems"])

print("[3] 训练步前置守卫:越界 token / 超长序列在 forward 之前拦下,报错带肇事数字")
stub = M(8000, 8000, 512)          # 只用它的 parameters() 判设备;守卫在 forward 前就断言
B, L, S = 2, 8, 160
batch = {"audio": torch.zeros(B, S), "audio_lens": torch.tensor([S, S]),
         "input_ids": torch.full((B, L), 7999, dtype=torch.long),
         "input_lens": torch.tensor([L, L]),
         "labels": torch.full((B, L), 8500, dtype=torch.long),   # ← 越界
         "token_types": torch.zeros(B, L, dtype=torch.long),
         "loss_mask": torch.ones(B, L, dtype=torch.bool),
         "ts_bins": torch.zeros(B, L, dtype=torch.long)}
ts_ids = torch.zeros(4000, dtype=torch.long)
try:
    training_step_logic(stub, batch, None, ts_token_ids=ts_ids,
                        guards={"vocab": 8000, "max_pos": 512})
    check("oob_caught", False, "没拦住")
except ValueError as e:
    check("oob_caught", "8500" in str(e) and "7999" in str(e), str(e))

batch["labels"] = torch.full((B, L), 10, dtype=torch.long)
long_batch = dict(batch, input_ids=torch.full((B, 600), 10, dtype=torch.long),
                  labels=torch.full((B, 600), 10, dtype=torch.long),
                  token_types=torch.zeros(B, 600, dtype=torch.long),
                  loss_mask=torch.ones(B, 600, dtype=torch.bool),
                  ts_bins=torch.zeros(B, 600, dtype=torch.long),
                  input_lens=torch.tensor([600, 600]))
try:
    training_step_logic(stub, long_batch, None, ts_token_ids=ts_ids,
                        guards={"vocab": 8000, "max_pos": 512})
    check("overlen_caught", False, "没拦住")
except ValueError as e:
    check("overlen_caught", "600" in str(e) and "512" in str(e), str(e))

print(f"\n全部通过: {PASS} 项")
