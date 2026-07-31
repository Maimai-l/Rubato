"""
录音/空间预设实现 —— 回答"16 个空间/录音参数怎么调"。

论文用 8 VST × 2 房间/麦克风 = 16 个音色变体。VST 型号未公开(U5),我们用
"5 个具名音源 × 16 个程序化录音预设"覆盖同等的音色多样性。这个文件负责**录音预设**
那一维:把 configs/recording_presets.yaml 里的物理参数合成成卷积混响的脉冲响应(IR),
再串上 EQ/降采样/房噪/编解码,模拟不同房间与录音链。

每个参数调什么、为什么这么调:
  rt60      混响衰减时间。0.15s=消音室,3.2s=教堂。这是"空间大小"的主轴。
  predelay  直达声与混响之间的延迟,拉大=听感更远/更大的空间。
  wet       干湿比。湿声占比越高=离麦越远/空间感越强。
  shelf4k   4kHz 高架 EQ。正=近距离拾音的明亮感,负=远场/旧设备的暗淡。这是"麦克风特性"主轴。
  lp/hp     低通/高通。旧录音、电话拾音的带限。
  noise     房间噪声底。安静录音棚 -63dB,嘈杂现场 -42dB。教模型抗噪。
  gain_jitter 每段随机增益,模拟录音电平不一致。
  codec     落盘前用低码率 Opus 重压缩一次,模拟 YouTube/上传劣化(真实录音域的关键差异源)。

为什么程序化合成而不是下载真实 IR:①可复现(参数即 IR,无需分发大文件);②不怕
下载链接腐烂;③想用真实 IR 时,放 assets/irs/real/<id>.wav 即自动覆盖同名合成 IR。

合成方法:指数衰减白噪声是房间混响 IR 的标准一阶近似(image-source / Moorer 模型的
简化)。对训练数据增强足够真实——我们要的是"多样且合理的空间染色",不是声学仿真级精度。
"""
from __future__ import annotations
import os
import numpy as np


def load_real_ir(preset_id: str, sr: int = 16000,
                 irs_dir: str = "assets/irs/real") -> "np.ndarray | None":
    """
    真实 IR(R-S4.3 + U12):assets/irs/real/<preset_id>.wav 存在则加载、转单声道、
    重采样到 sr、能量归一化,返回;不存在返回 None(调用方回退 synth_ir)。

    为什么要真实 IR:程序化 synth_ir 是【指数衰减白噪声】,只近似 RT60 与粗略频谱,
    缺真实空间的早期反射图样、模态密度、房间染色。对【真实录音鲁棒性】(论文头号卖点)
    这是域差:模型学会抗"假混响",真录音的真房间声学不一样。真实 IR 消除这个域差。

    免费真实 IR 来源(下载后放 assets/irs/real/<preset_id>.wav):
      OpenAIR(openairlib.net,教堂/厅堂/房间)、EchoThief(echothief.com,100+ 真实空间)、
      MIT Acoustical Reverberation Survey(270 个日常空间)、Aachen AIR。
    """
    import os
    from pathlib import Path
    import soundfile as sf
    p = Path(irs_dir) / f"{preset_id}.wav"
    if not p.exists():
        return None
    ir, ir_sr = sf.read(str(p), dtype="float32")
    if ir.ndim > 1:
        ir = ir.mean(axis=1)                     # → mono
    if ir_sr != sr:
        try:
            import soxr
            ir = soxr.resample(ir, ir_sr, sr)
        except Exception:
            import scipy.signal as ss
            ir = ss.resample(ir, int(round(len(ir) * sr / ir_sr))).astype("float32")
    ir = ir.astype("float32")
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9        # 能量归一,防卷积后音量漂移
    return ir


def audit_real_irs(preset_ids, irs_dir: str = "assets/irs/real", sr: int = 16000) -> dict:
    """
    报告每个 preset 用的是真实 IR 还是程序化(防【静默回退】陷阱):
    load_real_ir 找不到文件会静默返回 None → 回退 synth,不报错。若 EchoThief wav 的
    文件名没【精确】改成 <preset_id>.wav,该预设会悄悄用回合成混响,你还以为在用真实 IR。
    返回 {preset_id: 'real'|'synth'};渲染/训练前跑一次,核对 real 的数目符合预期。
    """
    return {pid: ("real" if load_real_ir(pid, sr, irs_dir) is not None else "synth")
            for pid in preset_ids}


def resolve_ir(preset: dict, preset_id: str | None, sr: int, seed: int,
               irs_dir: str = "assets/irs/real") -> np.ndarray:
    """真实 IR 优先(assets/irs/real/<preset_id>.wav),缺失回退程序化 synth_ir。"""
    if preset_id is not None:
        real = load_real_ir(preset_id, sr, irs_dir)
        if real is not None:
            return real
    return synth_ir(preset["rt60"], preset["predelay"], sr, seed)


def synth_ir(rt60_s: float, predelay_ms: float, sr: int = 16000,
             seed: int = 0) -> np.ndarray:
    """合成一个房间混响 IR:predelay 静音 + 指数衰减白噪声尾巴。"""
    rng = np.random.default_rng(seed)
    pre = int(sr * predelay_ms / 1000.0)
    # 尾巴长度取到 rt60 对应衰减基本结束(-60dB 即定义点,取 1.0×rt60 足够,留一点余量)
    tail_len = max(int(sr * rt60_s * 1.05), sr // 100)
    t = np.arange(tail_len) / sr
    # -60dB over rt60 → 衰减系数
    decay = 10.0 ** (-3.0 * t / max(rt60_s, 1e-3))   # 幅度 -60dB=1e-3
    tail = rng.standard_normal(tail_len).astype(np.float32) * decay.astype(np.float32)
    ir = np.concatenate([np.zeros(pre, np.float32),
                         np.array([1.0], np.float32),   # 直达声脉冲
                         tail])
    # 能量归一,避免卷积后整体音量漂移
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    return ir


def _highshelf(x: np.ndarray, sr: int, gain_db: float, f0: float = 4000.0) -> np.ndarray:
    """一阶高架 EQ(shelf4k)。gain_db 正=提亮,负=压暗。"""
    if abs(gain_db) < 1e-3:
        return x
    import math
    A = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / sr
    alpha = math.sin(w0) / 2 * math.sqrt(2)
    cw = math.cos(w0)
    # RBJ high-shelf 系数
    b0 = A * ((A + 1) + (A - 1) * cw + 2 * math.sqrt(A) * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cw)
    b2 = A * ((A + 1) + (A - 1) * cw - 2 * math.sqrt(A) * alpha)
    a0 = (A + 1) - (A - 1) * cw + 2 * math.sqrt(A) * alpha
    a1 = 2 * ((A - 1) - (A + 1) * cw)
    a2 = (A + 1) - (A - 1) * cw - 2 * math.sqrt(A) * alpha
    from scipy.signal import lfilter
    return lfilter([b0/a0, b1/a0, b2/a0], [1.0, a1/a0, a2/a0], x).astype(np.float32)


def apply_preset(audio: np.ndarray, preset: dict, sr: int = 16000,
                 seed: int = 0, ir_override: np.ndarray | None = None,
                 preset_id: str | None = None,
                 irs_dir: str = "assets/irs/real",
                 wet_mode: str = "energy") -> np.ndarray:
    """
    把一个录音预设完整作用到干声上。audio: mono float32 @ sr。返回同格式。
    IR 优先级:ir_override > 真实 IR(assets/irs/real/<preset_id>.wav)> 程序化 synth_ir。
    传 preset_id 即自动启用真实 IR(存在时);不传则维持旧行为(程序化)。
    wet_mode="energy"(默认,听感修复)|"legacy"(旧峰值对齐,仅供 A/B 对照)。
    全局旋钮(用户实听调音,不改配置):RUBATO_WET_SCALE(默认 1.0,湿度整体缩放)、
    RUBATO_NOISE_DB_OFFSET(默认 0,噪底整体加减 dB,负数=更安静)。
    """
    from scipy.signal import fftconvolve, butter, lfilter
    rng = np.random.default_rng(seed)
    x = audio.astype(np.float32)

    # 1) 卷积混响(真实 IR 优先)
    if ir_override is not None:
        ir = ir_override
    else:
        ir = resolve_ir(preset, preset_id, sr, seed, irs_dir)
    mix = float(preset["wet"]) * float(os.environ.get("RUBATO_WET_SCALE", "1.0"))
    mix = min(max(mix, 0.0), 1.0)
    if wet_mode == "legacy":
        # 旧算法【听感 bug,仅留作 A/B】:湿声按"峰值"对齐干声峰值再混 —— 混响把能量摊平后
        # 峰值低而 RMS 高,峰值对齐等于把湿声响度抬高数 dB,同一 wet 数值下听感远比标称湿
        # (用户实听"糊/混响过大"的主放大器)。
        wet = fftconvolve(x, ir, mode="full")[:len(x)]
        y = (1 - mix) * x + mix * (wet / (np.max(np.abs(wet)) + 1e-9) * np.max(np.abs(x)))
    else:
        # 【听感修复】IR 归一到单位能量:卷积保持响度,mix 才是真实的湿/干能量比。
        ir_e = ir / (np.sqrt(np.sum(ir.astype(np.float64) ** 2)) + 1e-12)
        wet = fftconvolve(x, ir_e.astype(np.float32), mode="full")[:len(x)]
        y = (1 - mix) * x + mix * wet

    # 2) 高架 EQ(麦克风特性)
    y = _highshelf(y, sr, preset["shelf4k"])

    # 3) 带限(旧设备/电话)
    if preset.get("hp", 0):
        b, a = butter(2, preset["hp"] / (sr / 2), btype="high")
        y = lfilter(b, a, y).astype(np.float32)
    if preset.get("lp", 0):
        b, a = butter(4, min(preset["lp"], sr/2 - 1) / (sr / 2), btype="low")
        y = lfilter(b, a, y).astype(np.float32)

    # 4) 房噪底(RUBATO_NOISE_DB_OFFSET 全局加减,负数=更安静;用户实听"吵"的调音旋钮)
    noise_db = preset.get("noise", -60) + float(os.environ.get("RUBATO_NOISE_DB_OFFSET", "0"))
    noise_amp = 10 ** (noise_db / 20.0)
    y = y + rng.standard_normal(len(y)).astype(np.float32) * noise_amp

    # 5) 增益抖动
    gj = preset.get("gain_jitter", 0.0)
    if gj:
        y *= 10 ** (rng.uniform(-gj, gj) / 20.0)

    # 6) 防削波
    peak = np.max(np.abs(y))
    if peak > 0.99:
        y *= 0.99 / peak
    return y.astype(np.float32)
    # 注:codec 重压缩(preset["codec"])在落盘阶段用 ffmpeg 做,不在此纯 numpy 函数内


if __name__ == "__main__":
    # 自检:每个预设都能作用、输出有限、RT60 单调影响尾部能量
    import yaml, pathlib
    cfg = yaml.safe_load((pathlib.Path(__file__).parents[2] / "configs/recording_presets.yaml").read_text())
    sr = 16000
    # 造一个 2s 的衰减钢琴样冲击串
    imp = np.zeros(sr * 2, np.float32)
    imp[::sr // 4] = 1.0
    imp *= np.exp(-np.arange(len(imp)) / sr * 0.5)
    energies = {}
    for pid, p in cfg["presets"].items():
        out = apply_preset(imp, p, sr=sr, seed=1)
        assert np.all(np.isfinite(out)), f"{pid} produced non-finite!"
        assert np.max(np.abs(out)) <= 1.0, f"{pid} clipped!"
        # 尾部 200ms 能量作为"混响量"代理
        energies[pid] = float(np.mean(out[-sr // 5:] ** 2))
    dry = energies["p16_bone_dry"]
    church = energies["p09_church"]
    print(f"bone_dry tail energy: {dry:.2e}")
    print(f"church   tail energy: {church:.2e}")
    assert church > dry, "RT60 ordering broken: church should have more tail energy than bone_dry"
    print(f"all {len(cfg['presets'])} presets valid; RT60 ordering OK")
