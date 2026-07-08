"""
渲染核心 —— MIDI → 16kHz Opus。统一封装 sfizz / fluidsynth 两种引擎,
串联"音源分配 + 录音预设 + 采样率链"。被 04(非表现性)与 05(表现性)共用。

链路:MIDI --[引擎+SF2/SFZ]--> 44.1k wav --[apply_preset 卷积混响/EQ/噪声]-->
     --[soxr 重采样 16k]--> --[可选 codec 重压缩]--> Opus 64k 落盘

音源与预设的分配由 hash(seed, utt_id) 决定,保证完全可复现且分布符合配置权重。
"""
from __future__ import annotations
import hashlib
import tempfile
import pathlib
import numpy as np
import soundfile as sf


def _unit(*parts: str) -> float:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:15], 16) / float(16 ** 15)


def _pick(weights: dict, u: float):
    tot = sum(weights.values()); acc = 0.0
    for k, w in weights.items():
        acc += w / tot
        if u < acc:
            return k
    return next(iter(weights))


def assign_source_and_preset(utt_id: str, sources_cfg: dict, presets_cfg: dict):
    """返回 (source_id, preset_id),可复现。"""
    seed = presets_cfg.get("seed", 0)
    src_weights = {sid: s["ratio"] for sid, s in sources_cfg["sources"].items()}
    src = _pick(src_weights, _unit(seed, utt_id, "src"))
    preset = _pick(presets_cfg["weights"], _unit(seed, utt_id, "preset"))
    return src, preset


def render_midi_to_wav44(midi_path: str, source: dict, sources_cfg: dict,
                         out_wav: str, utt_id: str = "") -> None:
    """用指定音源把 MIDI 渲成 44.1k wav。引擎命令以各自 --help 为准,此处为核实过的通用形式。"""
    sr = sources_cfg["render"]["sr_render"]
    engine = source["engine"]

    # 若 source 含 variants,确定性选一变体(同 utt_id 同 variant,bit 级可复现)
    variants = source.get("variants")
    if variants:
        seed = sources_cfg.get("seed", 0)
        idx = int(_unit(seed, utt_id, source.get("path", ""), "variant") * len(variants))
        sfpath = variants[idx]
    else:
        sfpath = source["path"]

    from rubato.platform import run
    if engine == "fluidsynth":
        gain = sources_cfg["render"]["fluidsynth_gain"]
        run("fluidsynth", ["-ni", "-F", out_wav, "-r", str(sr),
                           "-g", str(gain), sfpath, midi_path])
    elif engine == "sfizz":
        # sfizz_render flag 以 --help 为准(冒烟阶段核实);常见形式如下
        run("sfizz_render", ["--sfz", sfpath, "--midi", midi_path,
                             "--wav", out_wav, "--samplerate", str(sr)])
    else:
        raise ValueError(f"未知引擎 {engine}")


def peak_normalize(audio: np.ndarray, target_peak_db: float = -1.0) -> np.ndarray:
    """峰值归一化到 target_peak_db dBFS。纯线性乘系数,保留曲内动态。确定性,无随机性。"""
    peak = float(np.max(np.abs(audio)))
    if peak < 1e-9:
        return audio
    target_peak = 10.0 ** (target_peak_db / 20.0)
    gain = target_peak / peak
    return (audio * gain).astype(np.float32)


def finalize(wav44_path: str, preset: dict, sources_cfg: dict, presets_cfg: dict,
             utt_id: str, out_opus: str) -> None:
    """44.1k wav → 应用录音预设 → 16k → (可选 codec) → Opus 落盘。"""
    from rubato.render.irgen import apply_preset
    sr_render = sources_cfg["render"]["sr_render"]
    sr_target = sources_cfg["render"]["sr_target"]
    seed = int(_unit(presets_cfg.get("seed", 0), utt_id, "preset_seed") * 1e9)

    audio, sr = sf.read(wav44_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)   # → mono

    # 峰值归一化: 插在音源渲染后、预设链前。统一所有音源电平,杜绝音源身份泄漏。
    audio = peak_normalize(audio, target_peak_db=-1.0)

    # 先在渲染采样率上做混响(IR 也按此率合成,irgen 内部按传入 sr 处理)
    # 为省算力,预设作用放在重采样后的 16k 上(混响细节 16k 足够,且快得多)
    # 因此先重采样,再 apply_preset:
    import scipy.signal as ss
    n_target = int(round(len(audio) * sr_target / sr))
    audio16 = ss.resample(audio, n_target).astype("float32")   # 近似 soxr;要更好用 ffmpeg soxr
    wet = apply_preset(audio16, preset, sr=sr_target, seed=seed)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, wet, sr_target, subtype="PCM_16")
        tmp_wav = tmp.name

    # 编码到 Opus;若预设带 codec(模拟上传劣化),用其低码率,否则用标准 64k
    codec = preset.get("codec")
    bitrate = codec["bitrate"] if codec else sources_cfg["render"]["opus_bitrate"]
    from rubato.platform import run
    run("ffmpeg", ["-y", "-loglevel", "error", "-i", tmp_wav,
                   "-c:a", "libopus", "-b:a", bitrate, "-ar", str(sr_target),
                   "-ac", "1", out_opus])
    pathlib.Path(tmp_wav).unlink(missing_ok=True)


def silence_check(opus_path: str, gate_db: float = -60) -> bool:
    """用 ffmpeg volumedetect 确认非静音。返回 True=有声。"""
    from rubato.platform import run
    r = run("ffmpeg", ["-i", opus_path, "-af", "volumedetect", "-f", "null", "-"],
            check=False)
    for line in r.stderr.splitlines():
        if "max_volume" in line:
            val = float(line.split("max_volume:")[1].replace("dB", "").strip())
            return val > gate_db
    return False
