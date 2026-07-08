"""
S12 推理(A2S 主线产出形态)。规格见 SPEC.md R-S12.1~12.3 + 验收 A-S12.1。

主线设计(R-S12.1):长音频走 TAST prompt,时间戳仅内部用作分窗信号,输出前剥离。
  1. 40s 编码窗、20s hop;
  2. 解码中首个时间戳 >20s 视作该窗 EOS;
  3. 窗间在小节线合并(用 merge_ref 的 IR 层合并,Dyck 跨缝由结构保证);
  4. 合并后剥戳 → A2S → MusicXML。

分层:
  纯逻辑(沙盒可测):split_audio 分窗、strip_timestamps 剥戳、truncate_after_20s 截断、
    build_tast_prompt、窗合并(委托 merge_ref)。
  GPU 层(本地,带断言):single_window_infer 调 NeMo model.generate/transcribe,beam=4 重试。

infer_a2s 是 train.py 的 eval hook 依赖项:model=None 或失败时返回合法空谱,保证 hook 不崩。
"""
from __future__ import annotations
import re

from rubato.intermo.core import text_to_units, validate_units
from rubato.model.build import DIALECT_PROMPT
from rubato.model.merge_ref import merge_windows_ref

_EMPTY_A2S = "|4/4k0"           # 合法空谱(过 validate),stub 与兜底用


# ---------------------------------------------------------------- 纯逻辑:分窗(R-S12.1.1)

def split_audio(audio, sr: int = 16000, window_s: float = 40.0, hop_s: float = 20.0):
    """
    长音频切成 40s 窗、20s hop(50% 重叠)。返回 [(start_sample, window_array), ...]。
    audio: 1D numpy 数组。短于一窗 → 单窗返回。
    """
    import numpy as np
    n = len(audio)
    win = int(window_s * sr)
    hop = int(hop_s * sr)
    if n <= win:
        return [(0, audio)]
    out = []
    start = 0
    while start < n:
        seg = audio[start:start + win]
        out.append((start, seg))
        if start + win >= n:
            break
        start += hop
    return out


# ---------------------------------------------------------------- 纯逻辑:prompt / 剥戳 / 截断

def build_tast_prompt() -> list[str]:
    """R-S12.1:推理走 TAST prompt(与 build.py 的 DIALECT_PROMPT 一致)。"""
    return list(DIALECT_PROMPT["TAST"])


_TS_RE = re.compile(r"\s*<\|t\d+\|>")


def strip_timestamps(tast_text: str) -> str:
    """R-S12.1.4:剥离所有 <|tN|> 时间戳 token,得纯 A2S。"""
    return _TS_RE.sub("", tast_text).strip()


def truncate_after_20s(tast_text: str, threshold_bin: int = 2000) -> str:
    """
    R-S12.1.2:首个时间戳 >20s(bin>threshold)视作窗 EOS,截断其后内容。
    4000-bin/10ms 编码下 20s = bin 2000。保留触发点之前(含该小节线)的内容。
    """
    # 找第一个超阈值的时间戳位置
    for m in re.finditer(r"<\|t(\d+)\|>", tast_text):
        if int(m.group(1)) > threshold_bin:
            # 截断到该时间戳之前;回退到最近的小节线以保小节完整
            cut = m.start()
            head = tast_text[:cut]
            last_bar = head.rfind("|")
            return head[:last_bar].strip() if last_bar > 0 else head.strip()
    return tast_text.strip()


# ---------------------------------------------------------------- 纯逻辑:窗合并(R-S12.1.3)

def merge_windows(window_a2s: list[str]) -> str:
    """
    委托 merge_ref 的 IR 层合并(在小节线合并,Dyck 跨缝由结构保证)。
    window_a2s: 各窗【已剥戳】的 A2S 文本。
    """
    return merge_windows_ref(window_a2s)


def validate_a2s(a2s_text: str) -> list[str]:
    """校验 A2S 合法性。返回违规列表(空=合法)。"""
    try:
        return validate_units(text_to_units(a2s_text))
    except Exception as e:
        return [f"parse_error:{type(e).__name__}"]


# ---------------------------------------------------------------- GPU 层:单窗解码(R-S12.2)

def single_window_infer(model, audio_window, sr: int, tokenizer,
                        beam_size: int = 4) -> str:
    """
    单窗 TAST 解码。R-S12.2:beam=4;不可解析→greedy 重试 1 次;再败返回空。
    需 NeMo 模型,本地跑。三种 API 形态兜底(不同 NeMo 版本签名不同)。
    返回该窗的 A2S 文本(已截断 >20s、已剥戳)。
    """
    prompt = build_tast_prompt()

    def _decode(beam):
        # 形态1: model.generate(audio, prompt, num_beams)
        if hasattr(model, "generate"):
            out = model.generate(audio_window, prompt=prompt, num_beams=beam)
            return out if isinstance(out, str) else tokenizer.decode(out)
        # 形态2: model.transcribe([audio])
        if hasattr(model, "transcribe"):
            return model.transcribe([audio_window], num_beams=beam)[0]
        # 形态3: 直接调用
        return str(model(audio_window, prompt=prompt))

    for beam in (beam_size, 1):          # beam=4,失败退 greedy
        try:
            raw = _decode(beam)
        except Exception:
            continue
        tast = truncate_after_20s(raw)   # >20s = EOS
        a2s = strip_timestamps(tast)     # 剥戳
        if not validate_a2s(a2s):        # 合法即采用
            return a2s
    return _EMPTY_A2S                    # 两次都不合法 → 占位空谱(计入 n_fail)


# ---------------------------------------------------------------- 主入口

def infer_a2s(model, audio, tokenizer, sr: int = 16000) -> str:
    """
    S12 主入口。train.py eval hook 调用:infer_a2s(model, audio, tokenizer) -> str。
    model=None 或推理失败 → 返回合法空谱,保证 hook 不崩(parseable=1.0 起步)。
    """
    if model is None:
        return _EMPTY_A2S
    try:
        return _infer_impl(model, audio, tokenizer, sr)
    except Exception:
        return _EMPTY_A2S


def _infer_impl(model, audio, tokenizer, sr: int) -> str:
    """真实推理流程(R-S12.1/12.3)。"""
    windows = split_audio(audio, sr)
    if len(windows) == 1:                # R-S12.3:短音频单窗
        return single_window_infer(model, windows[0][1], sr, tokenizer)
    # 长音频:逐窗解码 → 收集各窗 A2S → 小节线合并
    window_a2s = []
    for start, seg in windows:
        a2s = single_window_infer(model, seg, sr, tokenizer)
        if a2s and a2s != _EMPTY_A2S:
            window_a2s.append(a2s)
    if not window_a2s:
        return _EMPTY_A2S
    merged = merge_windows(window_a2s)
    return merged if not validate_a2s(merged) else (window_a2s[0] or _EMPTY_A2S)


# ---------------------------------------------------------------- 便利封装

def infer_file(audio_path: str, model, tokenizer):
    """从音频文件推理。本地用(需 soundfile)。"""
    import soundfile as sf
    import numpy as np
    audio, sr = sf.read(audio_path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)       # 转单声道
    if sr != 16000:
        import soxr
        audio = soxr.resample(audio, sr, 16000)
        sr = 16000
    return infer_a2s(model, audio, tokenizer, sr)
