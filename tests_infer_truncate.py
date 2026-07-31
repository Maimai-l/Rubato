"""S12 截断修复回归测试(问题#7 相关:单元级截断,替代脆弱的字符级 rfind("|"))。
运行: python tests_infer_truncate.py"""
import sys
sys.path.insert(0, ".")
from rubato.model.infer import truncate_after_20s, strip_timestamps, validate_a2s

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] 旧 bug 场景:截断点前最后一个 '|' 在时间戳 token 内部")
# 触发戳 t2500 前的最后一个 '|' 字符属于 <|19.99|> —— 旧 rfind('|') 会切出 '...<' 垃圾
t = "|4/4k0PR:C4 <|0.00|> 1/1 <|19.99|> |4/4k0c4D4 <|21.00|> 1/1 <|25.00|> |4/4k0d4"
out = truncate_after_20s(t, threshold_bin=2000)
check("no_token_corruption", "<" not in out.replace("<|t", "") or "|>" in out, out)
a2s = strip_timestamps(out)
check("truncated_parses", not validate_a2s(a2s), f"{a2s}: {validate_a2s(a2s)}")
check("cut_before_2100", "21.00" not in out and "25.00" not in out, out)

print("[2] 跨切点延音:开着的音在边界补 offset(Dyck 闭合)")
# C4 从第1小节持续到第3小节;截断发生在第2小节末 → C4 必须在切点闭合
t2 = ("|4/4k0PR:C4E4 <|0.00|> 1/1e4 <|1.90|> |4/4k0F4 <|2.00|> 1/1f4 <|3.90|> "
      "|4/4k0G4 <|24.00|> 1/1c4g4 <|27.90|> |4/4k0")
out2 = truncate_after_20s(t2, threshold_bin=2000)
a2s2 = strip_timestamps(out2)
viol = validate_a2s(a2s2)
check("tie_closed_at_cut", not viol, f"{a2s2}: {viol}")
check("c4_offset_present", "c4" in a2s2, a2s2)      # 长音 C4 被补了 offset
check("g4_dropped", "G4" not in a2s2, a2s2)          # 被弃小节的 onset 剔除

print("[3] 截断产物以小节线单元终止(D-05)")
last_unit = a2s2.split(" ")[-1]
check("terminal_bar", last_unit.startswith("|"), a2s2)

print("[4] 20s 内无完整小节 → 空串(该窗无产出,而非垃圾)")
t3 = "1/1PR:C4 <|25.00|> |4/4k0c4"
check("no_bar_empty", truncate_after_20s(t3, 2000) == "", repr(truncate_after_20s(t3, 2000)))

print(f"\n全部通过: {PASS} 项")
