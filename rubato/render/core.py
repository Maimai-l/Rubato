"""
渲染核心 —— MIDI → 16kHz Opus。统一封装 sfizz / fluidsynth 两种引擎,
串联"音源分配 + 录音预设 + 采样率链"。被 04(非表现性)与 05(表现性)共用。

链路:MIDI --[引擎+SF2/SFZ]--> 44.1k wav --[apply_preset 卷积混响/EQ/噪声]-->
     --[soxr 重采样 16k]--> --[可选 codec 重压缩]--> Opus 64k 落盘

音源与预设的分配由 hash(seed, utt_id) 决定,保证完全可复现且分布符合配置权重。
"""
from __future__ import annotations
import hashlib
import os
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


def events_to_midi(events: list[dict], pedal: list, out_path: str,
                    tempo_bpm: float = 120.0, ppq: int = 480) -> str:
    """
    演奏事件(秒)→ MIDI 文件。演奏事件渲成音频前的一步:
    调用方产出 [{pitch,on,off,vel}] + pedal[(sec,down)] → .mid,
    再交给 render_midi_to_wav44。用固定 tempo 把秒换算成 tick(秒本身已含表现性时序,
    tempo 只是 tick 标度,不改听感)。踏板写 CC64。
    """
    import mido
    tpb = ppq
    spb = 60.0 / tempo_bpm                              # 秒/拍
    def sec_to_tick(s): return int(round(s / spb * tpb))
    ev = []                                            # (tick, order, msg)
    for n in events:
        ev.append((sec_to_tick(n["on"]), 1, mido.Message(
            "note_on", note=int(n["pitch"]), velocity=int(n.get("vel", 64)))))
        ev.append((sec_to_tick(n["off"]), 0, mido.Message(
            "note_off", note=int(n["pitch"]), velocity=0)))
    for s, down in pedal:
        ev.append((sec_to_tick(s), 0, mido.Message(
            "control_change", control=64, value=127 if down else 0)))
    ev.sort(key=lambda x: (x[0], x[1]))                # 同 tick:off/CC 先于 on
    mid = mido.MidiFile(ticks_per_beat=tpb)
    track = mido.MidiTrack(); mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo_bpm)))
    prev = 0
    for tick, _o, msg in ev:
        msg.time = max(0, tick - prev)
        prev = tick
        track.append(msg)
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    mid.save(out_path)
    return out_path


# 压缩采样格式:sfizz 加载时解码成 PCM,内存 ≈ 文件大小 × 解码倍率(FLAC 压缩率 ~50-60% → 解码 ~2×)。
_COMPRESSED_SAMPLE_EXT = {".flac", ".ogg", ".oga", ".opus", ".wv", ".mp3"}


def soundfont_weights(sources_cfg: dict, repo_root, mem_factor: float = 1.0,
                      decode_factor: float | None = None) -> dict:
    """
    每个音源的【内存权重】(GB)= 其 .sfz 所在目录样本的【解码后】估计大小:
    未压缩(wav/aiff)按文件大小;压缩(flac/ogg/…)按 文件大小 × decode_factor
    (默认 2.0,env SF_DECODE_FACTOR 可调)。
    【为什么不能按文件大小】执行端实测:ExperienceNY 文件 6.9GB(FLAC)→ sfizz 实际 RSS ~12GB。
    按文件大小准入会在 22.8GB 预算里放行 2 个并发(6.9×2=13.8 "够"),实际 24GB → OOM。
    解码后大小才是 sfizz 常驻内存的真实上限。给内存预算调度用:大音源自动少并发、小音源多并发。
    目录缺失(如沙盒)→ 保守 2.0GB。mem_factor<1:承认流式加载、换更多并发(自担风险)。
    """
    if decode_factor is None:
        decode_factor = float(os.environ.get("SF_DECODE_FACTOR", "2.0"))
    out = {}
    for sid, s in sources_cfg.get("sources", {}).items():
        d = (pathlib.Path(repo_root) / s["path"]).parent
        gb = 2.0
        if d.exists():
            total = 0.0
            for f in d.rglob("*"):
                try:
                    if f.is_file():
                        mult = decode_factor if f.suffix.lower() in _COMPRESSED_SAMPLE_EXT else 1.0
                        total += f.stat().st_size * mult
                except OSError:
                    pass
            gb = total / 1e9
        out[sid] = max(0.1, gb * mem_factor)
    return out


def assign_source_and_preset(utt_id: str, sources_cfg: dict, presets_cfg: dict):
    """返回 (source_id, preset_id),可复现。"""
    seed = presets_cfg.get("seed", 0)
    src_weights = {sid: s["ratio"] for sid, s in sources_cfg["sources"].items()}
    src = _pick(src_weights, _unit(seed, utt_id, "src"))
    preset = _pick(presets_cfg["weights"], _unit(seed, utt_id, "preset"))
    return src, preset


def render_midi_to_wav44(midi_path: str, source: dict, sources_cfg: dict,
                         out_wav: str, utt_id: str = "",
                         timeout_s: float | None = None) -> None:
    """
    用指定音源把 MIDI 渲成 44.1k wav。引擎命令以各自 --help 为准,此处为核实过的通用形式。

    修复(问题#2/#8/#9 相关):
      1. 【必须有超时】旧版无 timeout —— sfizz_render 遇 Salamander(1.4GB FLAC、
         release/共鸣/踏板噪声三层附加采样、note_polyphony=1 抢音)会以 10-100× 实时
         的速度慢渲,表现为"卡死"。超时由 sources.yaml render.timeout_s 控制(默认 600s),
         超时抛 subprocess.TimeoutExpired,调用方按 R-S4.4 记 failures 重试/标废,不再挂整夜。
      2. sfizz 附加 flag 从 sources.yaml render.sfizz_flags 读(--polyphony 上限、
         --use-eot 以 MIDI 末尾为渲染终点、--quality)。flag 名以本机 --help 为准。
      3. 大型 SFZ 建议先跑 scripts/prepare_salamander.py 生成"渲染专用瘦身版"
         (剥 release/噪声层 + FLAC→WAV),源路径换成瘦身版后吞吐可提一个量级。
    """
    render_cfg = sources_cfg["render"]
    sr = render_cfg["sr_render"]
    engine = source["engine"]
    if timeout_s is None:
        timeout_s = float(render_cfg.get("timeout_s", 600))

    # 若 source 含 variants,确定性选一变体(同 utt_id 同 variant,bit 级可复现)
    variants = source.get("variants")
    if variants:
        seed = sources_cfg.get("seed", 0)
        idx = int(_unit(seed, utt_id, source.get("path", ""), "variant") * len(variants))
        sfpath = variants[idx]
    else:
        sfpath = source["path"]

    from rubato.platform import run
    # 【D36】sources.yaml 里的音源路径是相对路径(assets/soundfonts/...),按【工作目录】解析
    # —— 换个目录启动就是 3,480 曲 100% 全崩(SFZ not found),且此雷在"大家恰好都从
    # 同一目录启动"的几周里完全隐形。渲染进程的 cwd 一律钉在 repo 根,两个引擎同待遇。
    # (执行端 8b53bad 修 sfizz 分支,规划端审后追认并补齐 fluidsynth 分支。)
    repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
    if engine == "fluidsynth":
        gain = render_cfg["fluidsynth_gain"]
        run("fluidsynth", ["-ni", "-F", out_wav, "-r", str(sr),
                           "-g", str(gain), sfpath, midi_path],
            timeout=timeout_s, cwd=repo_root)
    elif engine == "sfizz":
        # sfizz_render flag 以 --help 为准(冒烟阶段核实);常见形式如下
        extra = list(source.get("sfizz_flags") or render_cfg.get("sfizz_flags") or [])
        run("sfizz_render", ["--sfz", sfpath, "--midi", midi_path,
                             "--wav", out_wav, "--samplerate", str(sr), *extra],
            timeout=timeout_s, cwd=repo_root)
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

    # 先重采样到 16k 再 apply_preset(混响细节 16k 足够,更快)。
    # 【内存/速度修复】改用 resample_poly(多相)而非 resample(整信号 FFT):
    #   实测同一 5 分钟缓冲,resample 峰值 91MB/1.35s → resample_poly 38MB/0.35s(2.4×省内存、3.9×提速)。
    #   16 个 worker 并行时,这一项从 ~1.5GB 降到 ~0.6GB。
    import scipy.signal as ss
    from math import gcd
    g = gcd(int(sr_target), int(sr))
    up, down = int(sr_target) // g, int(sr) // g
    audio16 = ss.resample_poly(audio, up, down).astype("float32")
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
            check=False, timeout=120)
    for line in r.stderr.splitlines():
        if "max_volume" in line:
            val = float(line.split("max_volume:")[1].replace("dB", "").strip())
            return val > gate_db
    return False


def duration_check(audio_path: str, expected_dur_s: float, tol_s: float = 1.5) -> dict:
    """
    R-S4.4 另一半 QC 门(旧版只有 silence_check):渲染时长 vs MIDI 末音 offset 差 <1.5s。
    返回 {ok, actual_s, expected_s, diff_s}。sfizz 慢渲被超时杀掉产出截断 wav 时在此被抓。
    """
    info = sf.info(audio_path)
    actual = info.frames / float(info.samplerate)
    diff = abs(actual - expected_dur_s)
    return {"ok": diff < tol_s, "actual_s": round(actual, 2),
            "expected_s": round(expected_dur_s, 2), "diff_s": round(diff, 2)}


def render_qc(midi_path: str, audio_path: str, tol_s: float = 1.5,
              gate_db: float = -60.0) -> dict:
    """R-S4.4 runtime gate for a newly rendered file.

    This is intentionally called by the render workers, not merely by an
    after-the-fact audit.  A parse/probe failure fails closed: a non-empty
    output file alone is not proof that sfizz completed successfully.
    """
    try:
        import mido
        expected = float(mido.MidiFile(str(midi_path)).length)
        duration = duration_check(audio_path, expected, tol_s=tol_s)
        audible = silence_check(audio_path, gate_db=gate_db)
    except Exception as exc:
        return {
            "ok": False,
            "audible": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        **duration,
        "audible": bool(audible),
        "ok": bool(duration["ok"] and audible),
    }
