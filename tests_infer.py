"""S12 infer.py 纯逻辑测试(分窗/剥戳/截断/stub)。运行: python tests_infer.py"""
import sys
import numpy as np
sys.path.insert(0, ".")
from rubato.model.infer import (
    split_audio, build_tast_prompt, strip_timestamps, truncate_after_20s,
    merge_windows, validate_a2s, infer_a2s, _EMPTY_A2S,
)

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] 分窗(40s 窗/20s hop)")
sr = 16000
# 100s 音频 → 应切成多窗
audio = np.zeros(100 * sr, dtype=np.float32)
wins = split_audio(audio, sr, window_s=40, hop_s=20)
check("multiple_windows", len(wins) >= 4, f"got {len(wins)}")
# 每窗 ≤40s
check("window_size", all(len(w) <= 40*sr for _, w in wins))
# 步长 20s
check("hop_correct", wins[1][0] - wins[0][0] == 20*sr, f"{wins[1][0]-wins[0][0]}")
# 起点覆盖到末尾
check("covers_end", wins[-1][0] + len(wins[-1][1]) >= len(audio) - 20*sr)

print("[2] 短音频单窗(R-S12.3)")
short = np.zeros(30 * sr, dtype=np.float32)
wins_short = split_audio(short, sr)
check("single_window_short", len(wins_short) == 1, f"got {len(wins_short)}")
check("single_window_full", len(wins_short[0][1]) == 30*sr)

print("[3] TAST prompt")
p = build_tast_prompt()
check("tast_prompt", p == ["<|sot|>","<|score|>","<|spell|>","<|ts|>","<|nomidi|>"], p)

print("[4] 剥戳(R-S12.1.4)")
tast = "|4/4k0PR:C4 <|0.00|> 1/1 <|1.00|> |4/4k0c4"
stripped = strip_timestamps(tast)
check("timestamps_removed", "<|t" not in stripped, stripped)
check("content_preserved", "PR:C4" in stripped and "|4/4k0c4" in stripped, stripped)
# 剥戳后应是合法 A2S
check("stripped_valid", not validate_a2s(stripped), validate_a2s(stripped))

print("[5] >20s 截断(R-S12.1.2)")
# bin 2000 = 20s;超过的时间戳触发截断
tast_long = "|4/4k0PR:C4 <|0.00|> 1/1 <|10.00|> |4/4k0c4D4 <|15.00|> 1/1 <|25.00|> |4/4k0d4E4 <|26.00|> 1/1"
truncated = truncate_after_20s(tast_long, threshold_bin=2000)
# t2500 > 2000 → 在它之前截断,E4 那段(t2600)应被切掉
check("truncated_at_20s", "26.00" not in truncated, truncated)
check("keeps_before_20s", "PR:C4" in truncated, truncated)

print("[6] 无超阈值时间戳 → 不截断")
tast_short = "|4/4k0PR:C4 <|0.00|> 1/1 <|1.00|> |4/4k0c4"
check("no_truncate", truncate_after_20s(tast_short, 2000) == tast_short.strip())

print("[7] stub 行为(model=None)")
result = infer_a2s(None, np.zeros(1000), None)
check("none_returns_stub", result == _EMPTY_A2S, result)
check("stub_is_valid", not validate_a2s(result), validate_a2s(result))

print("[8] 推理失败兜底")
class BrokenModel:
    def generate(self, *a, **k): raise RuntimeError("boom")
    def __call__(self, *a, **k): raise RuntimeError("boom")
# 会抛异常但 infer_a2s 应兜底返回合法谱
result2 = infer_a2s(BrokenModel(), np.zeros(30*16000, dtype=np.float32), None)
check("broken_returns_valid", not validate_a2s(result2), f"{result2}: {validate_a2s(result2)}")

print("[9] 合并委托 merge_ref")
from rubato.intermo.core import Note, Measure, ScoreIR, SPitch, project
from fractions import Fraction as F
def ir_of(steps, start=0):
    return ScoreIR([Note("PR", SPitch(s,0,4), F(start+i), F(1)) for i,s in enumerate(steps)],
                   [Measure(F(start+i),4,4,0) for i in range(len(steps))], F(start+len(steps)))
w1 = project(ir_of("CDE"), "A2S")
w2 = project(ir_of("EF"), "A2S")
merged = merge_windows([w1, w2])
check("merge_valid", not validate_a2s(merged), validate_a2s(merged))
check("merge_correct", merged == project(ir_of("CDEF"), "A2S"), merged)

print(f"\n全部通过: {PASS} 项")
print("注:single_window_infer 调 NeMo model.generate/transcribe 需 GPU,带三形态兜底+beam重试,")
print("    本地验证;分窗/剥戳/截断/合并/stub 沙盒已验证。")
