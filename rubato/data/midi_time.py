"""
从 MIDI 文件本身提取【真实时间图 + 小节网格】—— S4 段切割的正确时间源。

为什么必须有这个模块:S4 整曲音频由 MuseScore 导出的 MIDI 渲染,速度来自谱面记号
(set_tempo 事件,可能多次变速);而旧管线用"恒速 2s/全音符(120bpm)"假设去换算段边界秒数 ——
除了恰好 120bpm 的曲,【每一段都切在错误位置】(A2S 文本对应 [a,b] 小节,音频却是别的小节)。
唯一与音频严格一致的时间源就是渲染所用的那个 MIDI 自己:
  - set_tempo 事件 → 分段线性 TimeMap(乐谱位置(全音符) → 秒),与 VN 路径同一抽象;
  - time_signature 事件 → 小节网格(每小节起点的乐谱位置),对齐 IR 的小节索引。

对齐保障(不静默):调用方应校验 IR 小节数 vs 网格小节数 —— 若 MIDI 展开了反复(repeat)或
结构不一致,两者对不上,该曲【跳过并计数】,绝不产出错位音频。
"""
from __future__ import annotations
from fractions import Fraction
from pathlib import Path

from rubato.intermo.core import TimeMap


def midi_time(midi_path: str | Path):
    """
    解析 MIDI → (tmap, measure_starts, total_whole)。
      tmap:           TimeMap,乐谱位置(全音符 Fraction,从 0 起)→ 秒。由 set_tempo 分段构成。
      measure_starts: [Fraction],每小节起点的乐谱位置(由 time_signature 推小节长,变拍号生效
                      于其出现处;MuseScore 导出的变拍号总在小节线上)。
      total_whole:    Fraction,末事件的乐谱位置(曲长)。
    失败抛异常(调用方计 failures,不静默)。
    """
    import mido
    mid = mido.MidiFile(str(midi_path))
    ppq = mid.ticks_per_beat or 480
    whole_per_tick = Fraction(1, ppq * 4)          # 1 tick = 1/(ppq*4) 全音符

    # 合并所有轨到绝对 tick(mido 的 merge_tracks 保相对时序)
    tempo_events: list[tuple[int, int]] = []       # (abs_tick, us_per_beat)
    tsig_events: list[tuple[int, Fraction]] = []   # (abs_tick, 每小节长(全音符))
    t = 0
    last_tick = 0
    for msg in mido.merge_tracks(mid.tracks):
        t += msg.time
        if msg.type == "set_tempo":
            tempo_events.append((t, msg.tempo))
        elif msg.type == "time_signature":
            tsig_events.append((t, Fraction(msg.numerator, msg.denominator)))
        if not msg.is_meta:
            last_tick = t                          # 曲长按真实事件(音符等)算,忽略曲尾 meta
    if last_tick == 0:
        last_tick = t                              # 纯 meta 文件兜底
    total_whole = last_tick * whole_per_tick

    # --- 速度图:分段线性锚点。无 set_tempo 时 MIDI 规范默认 500000(=120bpm)。
    if not tempo_events or tempo_events[0][0] > 0:
        tempo_events.insert(0, (0, 500000))
    anchors: list[tuple[Fraction, float]] = []
    sec = 0.0
    for i, (tick, us) in enumerate(tempo_events):
        if i > 0:
            prev_tick, prev_us = tempo_events[i - 1]
            sec += (tick - prev_tick) / ppq * prev_us / 1e6
        anchors.append((tick * whole_per_tick, sec))
    end_tick = max(last_tick, tempo_events[-1][0] + 1)      # 末锚点:延到曲尾(含末段斜率)
    sec_end = anchors[-1][1] + (end_tick - tempo_events[-1][0]) / ppq * tempo_events[-1][1] / 1e6
    anchors.append((end_tick * whole_per_tick, sec_end))
    tmap = TimeMap(anchors)

    # --- 小节网格:按拍号推进。无 time_signature 默认 4/4。
    if not tsig_events or tsig_events[0][0] > 0:
        tsig_events.insert(0, (0, Fraction(1)))             # 4/4 = 1 全音符/小节
    measure_starts: list[Fraction] = []
    pos = Fraction(0)
    seg = 0
    bar = tsig_events[0][1]
    next_change = tsig_events[1][0] * whole_per_tick if len(tsig_events) > 1 else None
    while pos < total_whole:
        measure_starts.append(pos)
        if next_change is not None and pos + bar >= next_change:
            pos = next_change                               # 变拍号在小节线:直接跳到变化点
            seg += 1
            bar = tsig_events[seg][1]
            next_change = (tsig_events[seg + 1][0] * whole_per_tick
                           if len(tsig_events) > seg + 1 else None)
        else:
            pos += bar
    return tmap, measure_starts, total_whole


# ---------------------------------------------------------------- 离谱速度检测与钳制(MXL 编辑错误)

def tempo_outliers(midi_path: str | Path, lo_bpm: float = 20.0, hi_bpm: float = 300.0) -> list[float]:
    """返回该 MIDI 中越界的速度们(bpm)。空列表 = 正常。谱面编辑错误如"四分音符=1"在此现形。"""
    import mido
    out = []
    for msg in mido.merge_tracks(mido.MidiFile(str(midi_path)).tracks):
        if msg.type == "set_tempo":
            bpm = mido.tempo2bpm(msg.tempo)
            if bpm < lo_bpm or bpm > hi_bpm:
                out.append(round(bpm, 2))
    return out


def clamp_midi_tempo(midi_path: str | Path, lo_bpm: float = 20.0, hi_bpm: float = 300.0,
                     fallback_bpm: float = 80.0, backup_suffix: str = ".tempo_orig.mid") -> int:
    """
    把越界 set_tempo【就地】改写为 fallback_bpm(默认 80,用户定的合理中速);原文件备份到
    <midi>.tempo_orig.mid。返回改写的事件数(0 = 未动文件,也不产生备份)。
    【一致性铁律】音频必须由钳制后的 MIDI 重渲 —— 只改时间图不改音频会切错位。调用方
    (scripts/s4_fix_tempo.py)负责:改写后删掉旧整曲音频,让 s4_parallel 续跑机制重渲。
    """
    import mido
    p = Path(midi_path)
    mid = mido.MidiFile(str(p))
    n = 0
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo":
                bpm = mido.tempo2bpm(msg.tempo)
                if bpm < lo_bpm or bpm > hi_bpm:
                    msg.tempo = mido.bpm2tempo(fallback_bpm)
                    n += 1
    if n:
        bak = p.with_suffix("")
        bak = Path(str(bak) + backup_suffix)
        if not bak.exists():
            p.replace(bak)             # 原件 → 备份
            mid.save(str(p))           # 钳制版落回原路径(manifest 不用改)
        else:
            mid.save(str(p))           # 已有备份(重复运行):只更新钳制版
    return n
