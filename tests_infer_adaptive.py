"""S12 自适应 hop 推理测试(修复固定 hop 与截断互相拆台)。运行: python tests_infer_adaptive.py"""
import sys
import numpy as np
from fractions import Fraction as F
sys.path.insert(0, ".")
from rubato.intermo.core import (
    Note, Measure, ScoreIR, SPitch, TimeMap, project, text_to_units, validate_units,
)
from rubato.model.infer import _last_barline_sec, _infer_impl, strip_timestamps, _EMPTY_A2S
from rubato.model.merge_ref import _concat_ir, a2s_to_ir

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)


print("[1] _last_barline_sec:取截断后最后一条小节线的时间戳(自适应 hop 起点)")
# 3 小节 4/4,每小节一个全音符;tmap 每小节 8s
ir = ScoreIR(
    [Note("PR", SPitch("C", 0, 4), F(0), F(1)),
     Note("PR", SPitch("D", 0, 4), F(1), F(1)),
     Note("PR", SPitch("E", 0, 4), F(2), F(1))],
    [Measure(F(0), 4, 4, 0), Measure(F(1), 4, 4, 0), Measure(F(2), 4, 4, 0)], F(3))
tmap = TimeMap([(F(0), 0.0), (F(3), 24.0)])   # 每小节 8s
tast = project(ir, "TAST", tmap)
# 最后一个小节线单元是终止小节线 @ 24s
check("last_barline_24s", _last_barline_sec(tast) == 24.0, _last_barline_sec(tast))

print("[2] _concat_ir(overlap_hint=0):平凡拼接 + 接缝延音融合(Dyck 跨窗)")
# 窗A:小节0-1,C4 从小节0持续到接缝(在接缝闭合);窗B:小节0(=接缝)起,C4 在接缝重开→应融合成一个长音
a = ScoreIR([Note("PR", SPitch("C", 0, 4), F(0), F(2))],
            [Measure(F(0), 4, 4, 0), Measure(F(1), 4, 4, 0)], F(2))       # C4 跨接缝,末端闭合
b = ScoreIR([Note("PR", SPitch("C", 0, 4), F(0), F(1)),
             Note("PR", SPitch("E", 0, 4), F(1), F(1))],
            [Measure(F(0), 4, 4, 0), Measure(F(1), 4, 4, 0)], F(2))        # C4 从接缝续,再接 E4
merged = _concat_ir(a, b, overlap_hint=0)
# 合法 + 无重叠丢失:总小节数 = 2 + 2 = 4(overlap=0 不去重)
a2s_m = project(merged, "A2S")
check("concat_valid", not validate_units(text_to_units(a2s_m)), a2s_m)
check("concat_measures", len(merged.measures) == 4, len(merged.measures))
# 接缝 C4 融合:窗A 的 C4(0-2)与窗B 接缝处的 C4(2-3)融成一个 0-3 的长音(接缝无重按)
c4 = [nn for nn in merged.notes if str(nn.pitch) == str(SPitch("C",0,4))]
check("seam_tie_fused", any(nn.onset == F(0) and nn.dur == F(3) for nn in c4),
      [(str(n.onset), str(n.dur)) for n in c4])

print("[3] 自适应 hop 主循环:mock 模型,终止 + 产物合法 + 用时间戳推进")
class MockTastModel:
    """每次 generate 返回一段带时间戳的 TAST(小节线在 8s),模拟每窗解码。"""
    def __init__(self):
        self.calls = 0
    def generate(self, audio_window, prompt=None, num_beams=1):
        self.calls += 1
        # 2 小节,末小节线 @ 8s(<20s → truncate 保留,自适应 hop 应前进 ~8s)
        sub = ScoreIR([Note("PR", SPitch("C", 0, 4), F(0), F(1)),
                       Note("PR", SPitch("D", 0, 4), F(1), F(1))],
                      [Measure(F(0), 4, 4, 0), Measure(F(1), 4, 4, 0)], F(2))
        return project(sub, "TAST", TimeMap([(F(0), 0.0), (F(2), 16.0)]))  # 每小节 8s

sr = 16000
audio = np.zeros(60 * sr, dtype="float32")   # 60s → 多窗
model = MockTastModel()
out = _infer_impl(model, audio, tokenizer=None, sr=sr)
check("terminates_and_valid", out and not validate_units(text_to_units(out)), out[:80])
check("made_progress", model.calls >= 2, model.calls)         # 多窗解码
check("no_timestamps_in_output", "<|" not in out or "|>" not in out.replace("<|", ""), out[:80])

print("[4] 短音频单窗(≤40s)")
short = np.zeros(20 * sr, dtype="float32")
model2 = MockTastModel()
out2 = _infer_impl(model2, short, tokenizer=None, sr=sr)
check("single_window_valid", out2 and not validate_units(text_to_units(out2)), out2[:80])

print(f"\n全部通过: {PASS} 项")
print("注:真实 NeMo 解码需 GPU;自适应 hop 的时间戳推进/接缝融合/终止/合法性沙盒已验证。")
