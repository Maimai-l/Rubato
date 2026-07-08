"""S12 窗合并参考实现测试(IR 语义层)。运行: python tests_merge.py"""
import sys
from fractions import Fraction as F
sys.path.insert(0, ".")
from rubato.intermo.core import Note, Measure, ScoreIR, SPitch, project
from rubato.model.merge_ref import merge_windows_ref, merge_and_validate, a2s_to_ir

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

def ir_of(steps, start=0):
    """造连续整音符小节:steps='CDEF' → 4 小节每小节一个整音符。"""
    return ScoreIR(
        [Note("PR", SPitch(s,0,4), F(start+i), F(1)) for i,s in enumerate(steps)],
        [Measure(F(start+i),4,4,0) for i in range(len(steps))],
        F(start+len(steps)))

print("[1] 基础:两窗重叠1小节合并回完整曲")
full = project(ir_of("CDEF"), "A2S")
win1 = project(ir_of("CDE"), "A2S")      # 小节0-2
win2 = project(ir_of("EF"), "A2S")       # 小节2-3(E 重叠)
merged, viol = merge_and_validate([win1, win2])
check("merge_valid", not viol, viol)
check("equals_full", merged == full, f"\n    got:  {merged}\n    want: {full}")

print("[2] 三窗链式")
w1 = project(ir_of("CD"), "A2S")
w2 = project(ir_of("DE"), "A2S")
w3 = project(ir_of("EF"), "A2S")
merged3, viol3 = merge_and_validate([w1, w2, w3])
check("three_valid", not viol3, viol3)
check("three_equals_full", merged3 == full, f"\n    got:  {merged3}\n    want: {full}")

print("[3] 单窗")
single = project(ir_of("C"), "A2S")
m1, v1 = merge_and_validate([single])
check("single_valid", not v1)
check("single_preserved", m1 == single, f"{m1} vs {single}")

print("[4] 空输入")
m0, v0 = merge_and_validate([])
check("empty_valid", not v0 and "4/4k0" in m0, m0)

print("[5] 重叠2小节")
# 窗1 = CDEF, 窗2 = EFGA,重叠 EF
win_a = project(ir_of("CDEF"), "A2S")
win_b = project(ir_of("EFGA"), "A2S")
full6 = project(ir_of("CDEFGA"), "A2S")
merged5, viol5 = merge_and_validate([win_a, win_b])
check("overlap2_valid", not viol5, viol5)
check("overlap2_correct", merged5 == full6, f"\n    got:  {merged5}\n    want: {full6}")

print("[6] 不可解析窗被跳过")
merged6, viol6 = merge_and_validate([win1, "GARBAGE!!!", win2])
check("skips_garbage", not viol6, viol6)   # 坏窗跳过,好窗仍合并

print("[7] 保留拍号/调号")
ir_ks = ScoreIR(
    [Note("PR", SPitch("C",-1,4), F(i)*F(3,4), F(3,4)) for i in range(3)],
    [Measure(F(i)*F(3,4),3,4,-2) for i in range(3)],
    F(3)*F(3,4))
a2s_ks = project(ir_ks, "A2S")
m7, v7 = merge_and_validate([a2s_ks])
check("keysig_preserved", "3/4k-2" in m7, m7)
check("keysig_valid", not v7)

print(f"\n全部通过: {PASS} 项")
print("注:参考实现在 IR 语义层合并,Dyck 跨缝由结构保证。执行者字符串版应对照此结果,")
print("    特别是 A-S12.1 '重叠区小节一致率>95%' 需用真实解码输出验证。")
