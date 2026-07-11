"""
S5 humanize 兜底(R-S5.7)。把直排乐谱变成"有表现力的演奏":给出演奏 TimeMap(供 TAST 时间戳)
和抖动后的演奏事件(供渲染音频 / AMT 目标)。

【为什么需要它】此前 S5(表现性渲染)只在 SPEC 里设计,从未实现 —— 只有 S4 直排。
后果:PDMX 只能产 A2S/A2S_lite,TAST 恒 null,且音频全是恒速节拍器味,模型学不到"从
表现性演奏里恢复乐谱"。humanize 是 SPEC 钦定的 VN 兜底(VN 失败/超预算的曲走它),纯 CPU、
确定性(按 piece 种子),白拿 PDMX 的 TAST + 时序多样性。VN 主路径见 scripts/s5_vn_render.py。

R-S5.7 参数(冻结):
  ① 逐拍速度因子 OU:φ_{k+1}=φ_k+0.2(1−φ_k)Δt+0.05√Δt·ε,截断[0.90,1.10];Δt=1 拍。
  ② onset 抖动 N(0,12ms) 截 ±35ms;offset 同步平移(保时值)。
  ③ 力度 +U[−10,10] 截 [20,120]。
  ④ 踏板照谱(此处无谱面踏板则不产)。
时间自生成 ⇒ tmap 是【真值】(我们精确知道每个乐谱位置被"演奏"在何秒),TAST 时间戳无对齐误差。
"""
from __future__ import annotations
from fractions import Fraction

from rubato.intermo.core import ScoreIR, SPitch, TimeMap, _derive_beats


def _seeded_rng(seed, piece_id):
    import numpy as np
    # 按 (seed, piece_id) 确定性播种:同曲每次一致,不同曲不同(与 R-S4.2 同风格)。
    h = abs(hash((seed, str(piece_id)))) % (2**32)
    return np.random.default_rng(h)


def _ou_tempo(n_beats: int, rng, phi0: float = 1.0):
    """OU 逐拍速度因子 φ(截断 [0.90,1.10])。返回长度 n_beats 的列表。"""
    phi = phi0
    out = []
    for _ in range(n_beats):
        eps = rng.standard_normal()
        phi = phi + 0.2 * (1.0 - phi) * 1.0 + 0.05 * (1.0 ** 0.5) * eps
        phi = min(1.10, max(0.90, phi))
        out.append(phi)
    return out


def humanize_timemap(ir: ScoreIR, base_sec_per_whole: float = 2.0,
                     seed: int = 20260706, piece_id: str = "") -> TimeMap:
    """
    直排乐谱 + OU 速度 → 演奏 TimeMap(乐谱位置 Fraction → 演奏秒)。
    拍点网格用 _derive_beats;每拍的名义时长 = (1/den)*base_sec_per_whole,乘 OU 因子 φ_k
    得实际时长,累加成演奏时刻。锚点覆盖每个拍点(含各小节下拍),TAST 投影用它加时间戳。

    ⚠ base_sec_per_whole=2.0 是【基准恒速 120bpm】:标签与音频由同一 tmap 产出、自洽不错位
    (与 120bpm 事故不同类),但音乐上所有曲都在 ~120bpm 附近,忽略谱面速度记号。
    此路仅是 VN 失败的兜底(默认关);若要启用,调用方应从该曲渲染 MIDI 的
    rubato.data.midi_time 取真实平均速度换算 base_sec_per_whole,别用默认 2.0。
    """
    beats = _derive_beats(ir)                       # [(score_pos, is_downbeat)] 升序
    positions = [p for p, _ in beats]
    if positions and positions[0] != Fraction(0):
        positions = [Fraction(0)] + positions
    # 确保覆盖曲末,便于末段插值
    if not positions or positions[-1] != ir.score_end:
        positions = positions + [ir.score_end]
    rng = _seeded_rng(seed, piece_id)
    phis = _ou_tempo(max(len(positions) - 1, 1), rng)
    anchors = [(positions[0], 0.0)]
    t = 0.0
    for k in range(1, len(positions)):
        span_whole = float(positions[k] - positions[k - 1])   # 该拍名义占多少全音符
        t += span_whole * base_sec_per_whole * phis[k - 1]
        anchors.append((positions[k], t))
    return TimeMap(anchors)


def humanize_events(ir: ScoreIR, base_sec_per_whole: float = 2.0,
                    seed: int = 20260706, piece_id: str = "",
                    default_vel: int = 64) -> tuple[list[dict], list, TimeMap]:
    """
    直排乐谱 → (演奏事件, 踏板, tmap)。事件用于渲染音频 + 作 AMT 目标(与音频同源,天然对齐);
    tmap 用于 TAST。onset 抖动 N(0,12ms)截±35ms,offset 同步平移保时值;力度 +U[-10,10] 截[20,120]。
    """
    import numpy as np
    ir = ir.normalized()
    tmap = humanize_timemap(ir, base_sec_per_whole, seed, piece_id)
    rng = _seeded_rng(seed, str(piece_id) + ":ev")
    events = []
    for n in ir.notes:
        on_s = float(tmap(n.onset))
        off_s = float(tmap(n.offset))
        jit = float(np.clip(rng.normal(0.0, 0.012), -0.035, 0.035))   # ②
        on_j = max(0.0, on_s + jit)
        off_j = max(on_j + 0.005, off_s + jit)                        # 同步平移保时值
        vel = int(np.clip(default_vel + rng.integers(-10, 11), 20, 120))  # ③
        pitch = n.pitch.midi if isinstance(n.pitch, SPitch) else int(n.pitch)
        events.append({"pitch": pitch, "on": on_j, "off": off_j, "vel": vel})
    events.sort(key=lambda e: (e["on"], e["pitch"]))
    return events, [], tmap                          # ④ 无谱面踏板则空
