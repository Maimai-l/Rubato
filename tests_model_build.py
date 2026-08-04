"""S10 模型构建测试(纯逻辑部分,GPU 部分本地验证)。运行: python tests_model_build.py"""
import sys
sys.path.insert(0, ".")
from rubato.model.build import (
    build_target_sequence, DIALECT_PROMPT, estimate_params, check_param_count,
    validate_decoder_init_meta, verify_encoder_loaded, resize_decoder_vocab,
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
# 补齐方言:TAST_lite / AMT_lite / DBD 的 prompt 开关互异且齐全
t_tl, _ = build_target_sequence("TAST_lite", ["x"])
check("tast_lite_prompt", "<|score|>" in t_tl and "<|nospell|>" in t_tl and "<|ts|>" in t_tl and "<|nomidi|>" in t_tl)
t_al, _ = build_target_sequence("AMT_lite", ["x"])
check("amt_lite_prompt", "<|noscore|>" in t_al and "<|ts|>" in t_al and "<|nomidi|>" in t_al and "<|midi|>" not in t_al)
t_dbd, _ = build_target_sequence("DBD", ["x"])
check("dbd_prompt_beat", "<|beat|>" in t_dbd and "<|noscore|>" in t_dbd and "<|nomidi|>" in t_dbd)
# 各方言 prompt 多重集互异(模型可区分)
from rubato.model.build import DIALECT_PROMPT
sigs = {d: tuple(sorted(p)) for d, p in DIALECT_PROMPT.items()}
check("all_prompts_distinct", len(set(sigs.values())) == len(sigs), sigs)

print("[3] 域提示可选")
t_dom, m_dom = build_target_sequence("A2S", ["x"], domain="real")
check("domain_added", "<|real|>" in t_dom)
check("domain_masked", m_dom[t_dom.index("<|real|>")] == False)  # 域提示也是 prompt,不计 loss
try:
    build_target_sequence("A2S", ["x"], domain="unknown")
    bad_domain_rejected = False
except ValueError:
    bad_domain_rejected = True
check("bad_domain_rejected", bad_domain_rejected)

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

print("[6] encoder hash 校验支持嵌套键，零匹配必须失败")
import torch
_a = {"model.encoder.layer.weight": torch.tensor([1.0]),
      "decoder.weight": torch.tensor([2.0])}
_b = {"model.encoder.layer.weight": torch.tensor([1.0]),
      "decoder.weight": torch.tensor([9.0])}
_v = verify_encoder_loaded(_a, _b)
check("nested_encoder_matched", _v["ok"] and _v["n_checked"] == 1, _v)
_zero = verify_encoder_loaded({"decoder.weight": torch.tensor([1.0])},
                              {"decoder.weight": torch.tensor([1.0])})
check("zero_encoder_match_fails", not _zero["ok"] and _zero["n_checked"] == 0,
      _zero)

print("[7] 词表换形必须同时替换 embedding/输出头，参数增长精确可核")
class _VocabModel(torch.nn.Module):
    def __init__(self, with_head=True):
        super().__init__()
        self.emb = torch.nn.Embedding(10, 4)
        self.head = torch.nn.Linear(4, 10) if with_head else torch.nn.Linear(4, 4)
vm = _VocabModel()
before = sum(p.numel() for p in vm.parameters())
swap = resize_decoder_vocab(vm, 13, old_vocab=10)
after = sum(p.numel() for p in vm.parameters())
check("embedding_and_head_replaced",
      swap["replaced_embeddings"] == 1 and swap["replaced_linears"] == 1, swap)
check("param_growth_exact", after == before + swap["param_growth"], (before, after, swap))

# Canary 原始 token embedding 与 log-softmax tied；Rubato 的两层独立初始化，
# 并且既有 checkpoint 已训练成两份不同权重。解绑必须显式且精确计入参数增量。
tied_vm = _VocabModel()
tied_vm.head.weight = tied_vm.emb.weight
tied_before = sum(p.numel() for p in tied_vm.parameters())
tied_swap = resize_decoder_vocab(tied_vm, 13, old_vocab=10)
tied_after = sum(p.numel() for p in tied_vm.parameters())
check("tied_embedding_head_intentionally_untied",
      tied_vm.head.weight is not tied_vm.emb.weight
      and tied_swap["shared_weight_groups_untied"] == 1,
      tied_swap)
check("tied_param_growth_exact",
      tied_after == tied_before + tied_swap["param_growth"],
      (tied_before, tied_after, tied_swap))
try:
    resize_decoder_vocab(_VocabModel(with_head=False), 13, old_vocab=10)
    missing_head_rejected = False
except RuntimeError:
    missing_head_rejected = True
check("missing_output_head_rejected", missing_head_rejected)

print("[8] decoder-init 元数据安全门")
check("healthy_decoder_init_allowed", validate_decoder_init_meta({
    "complete": True, "health_pass": True, "artifact_role": "decoder_init"
})["complete"] is True)
for name, meta in (
        ("incomplete_decoder_init_rejected", {"complete": False}),
        ("failed_decoder_init_rejected", {"health_pass": False}),
        ("smoke_decoder_init_rejected", {"artifact_role": "smoke"})):
    try:
        validate_decoder_init_meta(meta)
        raised = False
    except RuntimeError:
        raised = True
    check(name, raised)

print(f"\n全部通过: {PASS} 项")
print("注:实际 canary 加载、encoder hash 核对、前端一致性验证需 GPU+NeMo+canary.nemo,")
print("    已写成带断言的函数(build_model / verify_encoder_loaded / verify_frontend),本地跑即抓错。")
