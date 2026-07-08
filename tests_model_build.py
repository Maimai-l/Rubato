"""S10 模型构建测试(纯逻辑部分,GPU 部分本地验证)。运行: python tests_model_build.py"""
import sys
sys.path.insert(0, ".")
from rubato.model.build import (
    build_target_sequence, DIALECT_PROMPT, estimate_params, check_param_count,
)

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] 目标序列构造 + loss mask(R-S10.4)")
tokens, mask = build_target_sequence("A2S", ["|4/4k0PL:C4", "1/4c4"])
check("a2s_prompt_prefix", tokens[0] == "<|sot|>" and "<|score|>" in tokens[:5])
check("a2s_has_labels", "|4/4k0PL:C4" in tokens and "1/4c4" in tokens)
check("a2s_eot", tokens[-1] == "<|eot|>")
check("prompt_masked", mask[:5] == [False]*5, mask[:5])   # prompt 不计 loss
check("labels_and_eot_counted", mask[5:] == [True]*3, mask[5:])  # 2 label + eot
check("len_match", len(tokens) == len(mask))

print("[2] 各 dialect 的 prompt 开关正确")
t_tast, _ = build_target_sequence("TAST", ["x"])
check("tast_has_ts", "<|ts|>" in t_tast and "<|nots|>" not in t_tast)
t_amt, _ = build_target_sequence("AMT", ["x"])
check("amt_noscore_midi", "<|noscore|>" in t_amt and "<|midi|>" in t_amt)
t_lite, _ = build_target_sequence("A2S_lite", ["x"])
check("lite_nospell", "<|nospell|>" in t_lite)

print("[3] 域提示可选")
t_dom, m_dom = build_target_sequence("A2S", ["x"], domain="real")
check("domain_added", "<|real|>" in t_dom)
check("domain_masked", m_dom[t_dom.index("<|real|>")] == False)  # 域提示也是 prompt,不计 loss

print("[4] 参数量核算(A-S10.1,修正为 1024 维)")
# canary-180m-flash 实测配置:dec hidden=1024(非 512)
cfg = {"enc_layers": 17, "enc_d": 512, "enc_ffn": 2048,
       "dec_layers": 4, "dec_d": 1024, "dec_ffn": 4096, "n_heads": 8, "vocab": 5248}
est = estimate_params(cfg)
print(f"    估算: enc={est['encoder']/1e6:.1f}M dec={est['decoder']/1e6:.1f}M "
      f"proj={est['projection']/1e6:.2f}M emb={est['embedding']/1e6:.1f}M total={est['total_M']}M")
check("estimate_reasonable", 100e6 < est["total"] < 350e6, est["total"])
check("has_projection", est["projection"] > 0)   # 512→1024 投影存在

print("[5] 参数量相对基准验收(词表感知)")
# 原始 182.64M @ 5248 vocab。假设 backbone(非词表)= 182.64M - 2*5248*1024
backbone = int(182.64e6 - 2 * 5248 * 1024)
# 换 8000 词表后:backbone + 2*8000*1024
new_total = backbone + 2 * 8000 * 1024
r = check_param_count(new_total, backbone_ref=backbone, old_vocab=5248,
                      new_vocab=8000, emb_dim=1024, tied=False)
check("vocab_growth_ok", r["ok"], r)              # backbone 一致 → 通过
check("growth_computed", r["expected_vocab_growth_M"] > 0, r)
# backbone 变了(模型搭错)→ 应失败
r_bad = check_param_count(new_total + 20_000_000, backbone_ref=backbone,
                          old_vocab=5248, new_vocab=8000, emb_dim=1024, tied=False)
check("detects_wrong_backbone", not r_bad["ok"], r_bad)
# 无基准 → 只报告不判定
r_none = check_param_count(new_total)
check("no_ref_reports_only", r_none["ok"] is None, r_none)

print(f"\n全部通过: {PASS} 项")
print("注:实际 canary 加载、encoder hash 核对、前端一致性验证需 GPU+NeMo+canary.nemo,")
print("    已写成带断言的函数(build_model / verify_encoder_loaded / verify_frontend),本地跑即抓错。")
