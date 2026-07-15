"""教师强制探针纯计算部分回归(_probe_from_logprobs)。运行: python tests_probe.py"""
import sys
sys.path.insert(0, ".")
import math
import torch

from rubato.model.infer import _probe_from_logprobs

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


V, EOT = 20, 7


def logprobs_for(preferred: list[int], spike: float = 5.0):
    """构造 [T,V] log-prob:每个位置把概率压在 preferred[t] 上。"""
    x = torch.full((len(preferred), V), -spike)
    for t, p in enumerate(preferred):
        x[t, p] = spike
    return torch.log_softmax(x, dim=-1)


print("[1] 全对:acc=1,前缀=1,计分位数=非 prompt 位数")
labels = [3, 4, 5, 6, 8]
mask = [False, False, True, True, True]        # 前两位是 prompt
lp = logprobs_for(labels)
r = _probe_from_logprobs(lp, labels, mask, EOT)
check("acc_perfect", abs(r["acc"] - 1.0) < 1e-6, r)
check("prefix_perfect", abs(r["acc_prefix"] - 1.0) < 1e-6, r)
check("n_scored", r["n_scored"] == 3, r)

print("[2] prompt 位不计分:prompt 位全错不拉低 acc")
wrong_at_prompt = [9, 9] + labels[2:]
r = _probe_from_logprobs(logprobs_for(wrong_at_prompt), labels, mask, EOT)
check("prompt_excluded", abs(r["acc"] - 1.0) < 1e-6, r)

print("[3] 计分位半对半错")
half = [3, 4, 5, 9, 9]                          # 计分位 2,3,4 → 对 1 错 2
r = _probe_from_logprobs(logprobs_for(half), labels, mask, EOT)
check("acc_third", abs(r["acc"] - 1 / 3) < 1e-6, r)

print("[4] eot_p_first:第一个计分位上 eot 的概率")
lp2 = logprobs_for(labels)
lp2[2] = torch.log(torch.full((V,), 0.02))      # 手工铺一行:eot 给 0.4,其余均分
lp2[2, EOT] = math.log(0.4)
r = _probe_from_logprobs(lp2, labels, mask, EOT)
check("eot_p_first", abs(r["eot_p_first"] - 0.4) < 1e-3, r["eot_p_first"])

print("[5] prefix_n 截断:只取前 N 个计分位")
labels5 = [3] * 10
mask5 = [False] + [True] * 9
pref = [3, 3, 3, 9, 9, 9, 9, 9, 9, 9]           # 前 2 个计分位对,后面全错
r = _probe_from_logprobs(logprobs_for(pref), labels5, mask5, EOT, prefix_n=2)
check("prefix_slices", abs(r["acc_prefix"] - 1.0) < 1e-6, r)
check("acc_overall", abs(r["acc"] - 2 / 9) < 1e-6, r)

print("[6] 空计分/长度不齐不炸")
r = _probe_from_logprobs(logprobs_for([3, 4]), [3, 4], [False, False], EOT)
check("empty_mask_zero", r["acc"] == 0.0 and r["n_scored"] == 0 and r["eot_p_first"] is None, r)
r = _probe_from_logprobs(logprobs_for([3, 4, 5]), [3, 4], [True, True], EOT)  # lp 比 labels 长
check("length_mismatch_ok", r["n_scored"] == 2, r)

print(f"\n全部通过: {PASS} 项")
