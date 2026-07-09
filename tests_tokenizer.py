"""S9 tokenizer 核账测试(纯逻辑,不依赖大语料训练)。运行: python tests_tokenizer.py"""
import sys
sys.path.insert(0, ".")
from rubato.data.tokenizer import build_vocab_spec, reconcile

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] vocab_spec 计数")
spec = build_vocab_spec()
c = spec["counts"]
check("timestamps_4000", c["timestamps"] == 4000, c)
check("midi_129", c["midi"] == 129, c)           # 127 vel + 2 pedal
check("beat_1", c["beat"] == 1)
check("prompt_40", c["prompt"] == 40, c)
check("total_4170", c["total"] == 4170, c)

print("[2] A-S9.1 核账闭合 3571")
rec = reconcile(8000, 4170)
check("learnable_3571", rec["learnable_semantic"] == 3571, rec)
check("closes_with_paper", rec["ok"])

print("[3] user_defined 无重复、格式正确")
ud = spec["user_defined_symbols"]
check("no_duplicates", len(ud) == len(set(ud)), f"{len(ud)} vs {len(set(ud))}")
check("ts_format", spec["timestamps"][0] == "<|0.00|>" and spec["timestamps"][-1] == "<|39.99|>")
check("midi_vel_range", "<|vel:1|>" in spec["midi"] and "<|vel:127|>" in spec["midi"])
check("midi_pedal", "<|CC64:on|>" in spec["midi"] and "<|CC64:off|>" in spec["midi"])
check("prompt_switches", all(x in spec["prompt"] for x in
      ["<|sot|>","<|eot|>","<|score|>","<|spell|>","<|ts|>"]))

print("[4] 核账对错误配置敏感(防退化)")
bad = reconcile(8000, 4000)      # 少算 170 special
check("detects_wrong_count", not bad["ok"] and bad["learnable_semantic"] == 3741, bad)

print(f"\n全部通过: {PASS} 项")
print("注:vocab=8000 的真实训练需 PDMX 大语料(几百万 token);沙盒合成数据不足以支撑")
print("    3571 语义 piece,故训练本身在执行者环境用真实 labels.jsonl 完成。")
