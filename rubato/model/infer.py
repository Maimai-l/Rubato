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


_TS_RE = re.compile(r"\s*<\|\d+\.\d{2}\|>")           # 时间戳:秒·两位小数


def strip_timestamps(tast_text: str) -> str:
    """R-S12.1.4:剥离所有时间戳 token(<|0.00|> 形式),得纯 A2S。"""
    return _TS_RE.sub("", tast_text).strip()


# 小节线单元在空格边界上以 "|" 开头(如 "|3/4k-4");时间戳/prompt token 的 "|" 都紧跟 "<"。
# 旧实现 rfind("|") 会切进 "<|tN|>" 内部产生 "...<" 垃圾 —— 必须按【单元】操作。
_BAR_UNIT_RE = re.compile(r"(?:^|(?<= ))\|\d+/\d+k(?:0|#[1-7]|-[1-7])")


def truncate_after_20s(tast_text: str, threshold_bin: int = 2000) -> str:
    """
    R-S12.1.2:首个时间戳 >2000 bin(20s)视作窗 EOS。截断规则(单元级,保 InterMo 合法):
      1. 找到首个 ts_bin > threshold 的单元,回退到其前最近的小节线单元 j;
      2. 保留 units[0..j];小节线 j 上的 onset(属被弃小节)剔除;
      3. 仍未闭合的音符(跨切点延音)在小节线 j 处补 offset —— Dyck 闭合、D-05 终止小节线均满足。
    解析失败时退化为正则粗截(后续 validate 会兜底)。
    """
    from rubato.intermo.core import units_to_text, ts_bin_from_glyph

    def _regex_fallback() -> str:
        for m in re.finditer(r"<\|(\d+\.\d{2})\|>", tast_text):
            if ts_bin_from_glyph(m.group(1)) > threshold_bin:
                head = tast_text[:m.start()]
                bars = list(_BAR_UNIT_RE.finditer(head))
                return head[:bars[-1].start()].strip() if bars else head.strip()
        return tast_text.strip()

    try:
        units = text_to_units(tast_text)
    except Exception:
        return _regex_fallback()

    cut = next((i for i, u in enumerate(units)
                if u.ts_bin is not None and u.ts_bin > threshold_bin), None)
    if cut is None:
        return tast_text.strip()
    bar_j = next((j for j in range(cut - 1, -1, -1) if units[j].bar is not None), None)
    if bar_j is None:
        return ""                                    # 20s 内无完整小节 → 本窗无产出

    kept = units[:bar_j + 1]
    term = kept[-1]
    # 运行 Dyck 状态:统计切点处仍 open 的 (staff, pitch)
    open_keys: set = set()
    for u in kept[:-1]:
        for staff, p in u.offs:
            open_keys.discard((staff, p))
        for staff, p, _v in u.ons:
            open_keys.add((staff, p))
    for staff, p in term.offs:                       # 终止小节线自带的 offset 先生效
        open_keys.discard((staff, p))
    term.ons = []                                    # 属被弃小节的 onset 剔除
    if open_keys:                                    # 跨切点延音 → 在边界补 offset
        from rubato.intermo.core import _pitch_key
        extra = sorted(open_keys, key=lambda e: (str(e[0]), _pitch_key(e[1])))
        seen = {(s, p) for s, p in term.offs}
        term.offs = sorted(term.offs + [e for e in extra if e not in seen],
                           key=lambda e: (str(e[0]), _pitch_key(e[1])))
    try:
        has_ts = all(u.ts_bin is not None for u in kept)
        return units_to_text(kept, with_ts=has_ts)
    except Exception:
        return _regex_fallback()


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
                        beam_size: int = 4, truncate: bool = True) -> str:
    """
    单窗 TAST 解码。R-S12.2:beam=4;不可解析→greedy 重试 1 次;再败返回空。
    需 NeMo 模型,本地跑。三种 API 形态兜底(不同 NeMo 版本签名不同)。
    truncate=False 用于【最后一窗】:其 20-40s 区间没有后续窗兜底,截断=直接丢内容。
    返回该窗的 A2S 文本(已按需截断、已剥戳)。
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
        tast = truncate_after_20s(raw) if truncate else raw   # >20s = EOS(末窗除外)
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
    if len(windows) == 1:                # R-S12.3:短音频单窗,不截断
        return single_window_infer(model, windows[0][1], sr, tokenizer, truncate=False)
    # 长音频:逐窗解码 → 收集各窗 A2S → 小节线合并。
    # 末窗 truncate=False:20-40s 区间无后续窗兜底,截断即丢失全曲结尾。
    window_a2s = []
    for wi, (start, seg) in enumerate(windows):
        is_last = wi == len(windows) - 1
        a2s = single_window_infer(model, seg, sr, tokenizer, truncate=not is_last)
        if a2s and a2s != _EMPTY_A2S:
            window_a2s.append(a2s)
    if not window_a2s:
        return _EMPTY_A2S
    merged = merge_windows(window_a2s)
    return merged if not validate_a2s(merged) else (window_a2s[0] or _EMPTY_A2S)


# ---------------------------------------------------------------- AMT 推理(eval hook 用)

def build_amt_prompt() -> list[str]:
    return list(DIALECT_PROMPT["AMT"])


def infer_amt(model, audio, tokenizer, sr: int = 16000, beam_size: int = 4) -> str:
    """
    AMT dialect 单窗推理(MAESTRO val 段 ≤25s,单窗覆盖)。
    返回 AMT 文本(含时间戳/力度/踏板);失败返回空串。
    """
    if model is None:
        return ""
    prompt = build_amt_prompt()
    try:
        if hasattr(model, "generate"):
            out = model.generate(audio, prompt=prompt, num_beams=beam_size)
            return out if isinstance(out, str) else tokenizer.decode(out)
        if hasattr(model, "transcribe"):
            return model.transcribe([audio], num_beams=beam_size)[0]
        return str(model(audio, prompt=prompt))
    except Exception:
        return ""


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
