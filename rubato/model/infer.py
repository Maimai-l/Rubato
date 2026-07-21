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

# 吞错现场记录(2026-07-15 立):eval 连续多轮 样本0='|4/4k0' 被误读成"模型只会输出开头",
# 实为兜底常量 —— 三层静默吞错(解码异常/validate 拒绝/顶层异常)必须留案发现场,
# run_eval_hooks 在出现兜底时打印。只存最后一次,eval 开始时清零。
LAST_INFER_ERROR: str | None = None     # infer_a2s 顶层异常(traceback 头)
LAST_DECODE_DEBUG: dict | None = None   # 单窗解码:validate 拒绝的原始输出 / 解码异常
LAST_VIOLS: list = []                   # 本次 infer_a2s/infer_amt 全窗累计的真实违规(D44 拒因直方图)


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

def build_prompt(dialect: str, domain: str | None = None) -> list[str]:
    """
    训练/推理共用的 prompt 生成(D44,执行端发现的训推前缀不一致):训练侧 encode_target
    对每条样本都在方言 prompt 后追加 <|real|>/<|synth|>(dataset.py:74-77),而自由推理
    此前只用方言 prompt —— 模型从未在"无域提示"前缀下训练过,却一直被要求这样生成。
    修复 = 布局在此单点收口,推理显式传 domain。默认 None = 维持现状(G0):
    在 EXPERIMENT_PROMPT 的 G0/G1/G2 对照判决之前,任何调用方不得擅改缺省。
    """
    p = list(DIALECT_PROMPT[dialect])
    if domain in ("real", "synth"):
        p.append(f"<|{domain}|>")
    return p


def build_tast_prompt(domain: str | None = None) -> list[str]:
    """R-S12.1:推理走 TAST prompt(与 build.py 的 DIALECT_PROMPT 一致)。"""
    return build_prompt("TAST", domain)


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


# ---------------------------------------------------------------- 自研自回归解码(换表后唯一路径)

def _apply_rep_penalty(row, ids: list[int], n_prompt: int,
                       penalty: float, window: int):
    """重复惩罚(纯逻辑,可测):最近 window 个已生成 token 的 log-prob 减 log(penalty)。
    为什么:step30000 前缀acc=0.69(教师强制已过 0.60 线)而自由生成仍锁死在两和弦循环
    (c5E5↔e5C5)—— 贪心的循环捕获成了 parseable 的主瓶颈。LEGATO 终评同款(penalty 1.1),
    幅度温和(logit 平移 ~0.095),只翻近平局,强预测(如合法的 1/16 连续时值)不受影响。
    只罚已生成段,不罚 prompt。"""
    if not penalty or penalty == 1.0 or len(ids) <= n_prompt:
        return row
    import math
    import torch
    recent = sorted(set(ids[max(n_prompt, len(ids) - window):]))
    row = row.clone()
    row[torch.tensor(recent, device=row.device)] -= math.log(penalty)
    return row


def autoregressive_decode(model, audio, tokenizer, prompt_pieces: list[str],
                          max_new: int = 900, rep_penalty: float = 1.1,
                          rep_window: int = 128) -> str:
    """
    贪心解码,只依赖【训练验证过的同一个 forward】。为什么不用 NeMo transcribe/generate
    (执行端 step1000 eval 实测 parseable=0):词表已换成自有 8000 spm、forward 直喂 id,
    而 transcribe 走 NeMo 内部 aggregate tokenizer + canary prompt 表 —— 那套词表已不存在,
    签名也不兼容。
    路径:preprocessor+forward 跑一次(编码器只算一次,拿返回的 enc_states/enc_mask)→
    每步下一 token 用内部模块快路径(transf_decoder+log_softmax);快路径首次用 forward
    的 log_probs【自校验】,不一致自动退慢路径(每步全量 forward,正确但慢,打印警告)——
    对 NeMo 内部签名零盲猜。
    """
    import torch
    from rubato.model.train import resolve_log_probs
    device = next(model.parameters()).device
    ids = [tokenizer.piece_to_id(p) for p in prompt_pieces]
    n_prompt = len(ids)
    eot = tokenizer.piece_to_id("<|eot|>")
    audio_t = torch.as_tensor(audio, dtype=torch.float32, device=device).reshape(1, -1)
    len_t = torch.tensor([audio_t.shape[1]], device=device)
    processed, plen = model.preprocessor(input_signal=audio_t, length=len_t)

    def fwd(cur_ids):
        t = torch.tensor([cur_ids], dtype=torch.long, device=device)
        tl = torch.tensor([len(cur_ids)], device=device)
        return model.forward(processed_signal=processed, processed_signal_length=plen,
                             transcript=t, transcript_length=tl)

    with torch.no_grad():
        out0 = fwd(ids)
        lp = resolve_log_probs(out0)
        enc_states = out0[2] if isinstance(out0, (tuple, list)) and len(out0) >= 4 else None
        enc_mask = out0[3] if enc_states is not None else None

        fast = None
        if enc_states is not None and hasattr(model, "transf_decoder") \
                and hasattr(model, "log_softmax"):
            def fast_lp(cur_ids):
                t = torch.tensor([cur_ids], dtype=torch.long, device=device)
                dec = model.transf_decoder(input_ids=t, decoder_mask=torch.ones_like(t),
                                           encoder_embeddings=enc_states,
                                           encoder_mask=enc_mask)
                o = model.log_softmax(hidden_states=dec)
                return o[0] if isinstance(o, (tuple, list)) else o
            reason = ""
            try:
                cand = fast_lp(ids)
                if cand.shape == lp.shape and torch.allclose(cand, lp, atol=1e-3):
                    fast = fast_lp          # 与训练 forward 逐位一致 → 采用
                else:
                    reason = f"数值不一致 shape={tuple(cand.shape)} vs {tuple(lp.shape)}"
            except Exception as e:
                reason = f"{type(e).__name__}: {e}"
        else:
            reason = "缺 transf_decoder/log_softmax 成员"
        if fast is None and not getattr(autoregressive_decode, "_warned", False):
            autoregressive_decode._warned = True   # 每进程一次,别刷屏
            print(f"⚠ 解码快路径不可用({reason})→ 退全量 forward 慢路径(正确但慢十倍;"
                  "把本行原文+NeMo 版本贴回规划端)", flush=True)

        for _ in range(max_new):
            row = _apply_rep_penalty(lp[0, -1], ids, n_prompt, rep_penalty, rep_window)
            nxt = int(row.argmax())
            if nxt == eot or len(ids) >= 1023:
                break
            ids.append(nxt)
            lp = fast(ids) if fast is not None else resolve_log_probs(fwd(ids))

    return tokenizer.decode(ids[n_prompt:]).strip()


# ---------------------------------------------------------------- GPU 层:单窗解码(R-S12.2)

def single_window_infer(model, audio_window, sr: int, tokenizer,
                        beam_size: int = 4, truncate: bool = True) -> str:
    """
    单窗 TAST 解码。R-S12.2:beam=4;不可解析→greedy 重试 1 次;再败返回空。
    需 NeMo 模型,本地跑。三种 API 形态兜底(不同 NeMo 版本签名不同)。
    truncate=False 用于【最后一窗】:其 20-40s 区间没有后续窗兜底,截断=直接丢内容。
    返回该窗的 A2S 文本(已按需截断、已剥戳)。
    """
    tast = single_window_tast(model, audio_window, sr, tokenizer, beam_size, truncate)
    return strip_timestamps(tast) if tast else _EMPTY_A2S


def single_window_tast(model, audio_window, sr: int, tokenizer,
                       beam_size: int = 4, truncate: bool = True,
                       domain: str | None = None) -> str:
    """
    单窗 TAST 解码,返回截断后的【带时间戳】TAST 文本(剥戳后过 validate 才采用);失败返回 ''。
    保留时间戳是自适应 hop 的关键——下一窗起点 = 本窗最后小节线的时间戳。
    """
    prompt = build_tast_prompt(domain)

    def _decode(beam):
        # 真 NeMo 模型(有 preprocessor+forward)走自研解码 —— transcribe/generate 与换表后
        # 的模型不兼容(内部 tokenizer 已被绕开);beam 参数在 v1 忽略(贪心,监控够用,
        # 论文终评的 beam=4 等自研 beam 实现)。stub 分支保留给沙盒测试。
        if hasattr(model, "preprocessor") and hasattr(model, "forward"):
            return autoregressive_decode(model, audio_window, tokenizer, prompt)
        if hasattr(model, "generate"):
            out = model.generate(audio_window, prompt=prompt, num_beams=beam)
            return out if isinstance(out, str) else tokenizer.decode(out)
        if hasattr(model, "transcribe"):
            return model.transcribe([audio_window], num_beams=beam)[0]
        return str(model(audio_window, prompt=prompt))

    global LAST_DECODE_DEBUG
    for beam in (beam_size, 1):          # beam=4,失败退 greedy
        try:
            raw = _decode(beam)
        except Exception as e:
            import traceback
            LAST_DECODE_DEBUG = {"stage": "decode_exception",
                                 "err": f"{type(e).__name__}: {e}",
                                 "tb": traceback.format_exc(limit=4)}
            continue
        tast = truncate_after_20s(raw) if truncate else raw   # >20s = EOS(末窗除外)
        viol = validate_a2s(strip_timestamps(tast))           # 剥戳后合法即采用
        if not viol:
            return tast
        # 模型真实输出在此被丢弃 —— 这正是"样本0永远=兜底"时最需要看到的现场
        LAST_DECODE_DEBUG = {"stage": "validate_reject", "viol": viol[:4],
                             "raw": raw[:160], "truncated": tast[:100]}
        # 拒因直方图的证据源(D44):v1 只在 eval 层对兜底常量复验,真实违规从未传出 →
        # 直方图退化成 empty 率。此处全量累积,infer_a2s/infer_amt 入口清零。
        LAST_VIOLS.extend(viol)
    return ""                            # 两次都不合法 → 空(计入 n_fail)


def _last_barline_sec(tast_text: str, ts_ms: int = 10) -> float | None:
    """截断后 TAST 里最后一个小节线单元的时间戳(秒)—— 自适应 hop 的下一窗起点。"""
    try:
        units = text_to_units(tast_text)
    except Exception:
        return None
    for u in reversed(units):
        if u.bar is not None and u.ts_bin is not None:
            return u.ts_bin * ts_ms / 1000.0
    return None


# ---------------------------------------------------------------- 主入口

def infer_a2s(model, audio, tokenizer, sr: int = 16000,
              domain: str | None = None) -> str:
    """
    S12 主入口。train.py eval hook 调用:infer_a2s(model, audio, tokenizer) -> str。
    model=None 或推理失败 → 返回合法空谱,保证 hook 不崩(parseable=1.0 起步)。
    domain:None=不加域提示(现状 G0);"real"/"synth" 与训练前缀一致(EXPERIMENT_PROMPT
    判决前,eval/产品调用方不得擅改缺省)。
    """
    global LAST_VIOLS
    LAST_VIOLS = []
    if model is None:
        return _EMPTY_A2S
    try:
        return _infer_impl(model, audio, tokenizer, sr, domain=domain)
    except Exception as e:
        import traceback
        global LAST_INFER_ERROR
        LAST_INFER_ERROR = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}"
        return _EMPTY_A2S


def _infer_impl(model, audio, tokenizer, sr: int, domain: str | None = None) -> str:
    """
    R-S12.1/12.3 自适应 hop 推理(修复固定 20s hop 与"截断到最后小节线"互相拆台的架构问题):
    每窗 40s 编码(右侧看未来),解码 TAST 截断到 20s 前最后一条小节线;
    【下一窗从该小节线的时间戳起】—— 窗间无缝、无内容 gap、无重叠,且窗起点恒在小节线(与训练
    数据的小节对齐分布一致)。合并退化为 IR 层平凡拼接(overlap=0)+ 接缝延音融合(Dyck 跨窗延续);
    merge_ref 的重叠检测(精确/Jaccard 模糊)整个退役,顺带消除自相似音乐里模糊去重误删真实重复小节。
    """
    import numpy as np
    from rubato.model.merge_ref import a2s_to_ir, _concat_ir
    from rubato.intermo.core import project

    n = len(audio)
    win = int(40 * sr)
    default_hop = int(20 * sr)           # 解码失败/无小节线时的兜底 hop
    t_start = 0
    acc_ir = None
    n_fail = 0
    guard = 0
    max_windows = max(4, n // max(default_hop, 1) + 8)

    while t_start < n and guard < max_windows:
        guard += 1
        seg = audio[t_start:t_start + win]
        is_last = (t_start + win >= n)
        tast = single_window_tast(model, seg, sr, tokenizer, truncate=not is_last,
                                  domain=domain)
        if not tast:                     # 解码失败:按默认 hop 前进(计 n_fail),不静默错位/死循环
            n_fail += 1
            t_start += default_hop
            continue
        a2s_w = strip_timestamps(tast)
        try:
            ir_w = a2s_to_ir(a2s_w)
        except Exception:
            n_fail += 1
            t_start += default_hop
            continue
        # IR 层平凡拼接(无重叠)+ 接缝延音融合;不做脆弱的重叠/模糊匹配
        acc_ir = ir_w if acc_ir is None else _concat_ir(acc_ir, ir_w, overlap_hint=0)
        if is_last:
            break
        last_sec = _last_barline_sec(tast)
        t_start += int(round(last_sec * sr)) if (last_sec and last_sec > 0) else default_hop

    if acc_ir is None:
        return _EMPTY_A2S
    try:
        return project(acc_ir, "A2S")    # IR 层拼接产物恒合法,不再有"退回第一窗"的丢内容兜底
    except Exception:
        return _EMPTY_A2S


# ---------------------------------------------------------------- AMT 推理(eval hook 用)

def build_amt_prompt(domain: str | None = None) -> list[str]:
    return build_prompt("AMT", domain)


def infer_amt(model, audio, tokenizer, sr: int = 16000, beam_size: int = 4,
              domain: str | None = None) -> str:
    """
    AMT dialect 单窗推理(MAESTRO val 段 ≤25s,单窗覆盖)。
    返回 AMT 文本(含时间戳/力度/踏板);失败返回空串。
    domain 语义同 infer_a2s(缺省 None=现状,判决前不得擅改)。
    """
    global LAST_VIOLS
    LAST_VIOLS = []
    if model is None:
        return ""
    prompt = build_amt_prompt(domain)
    try:
        if hasattr(model, "preprocessor") and hasattr(model, "forward"):
            return autoregressive_decode(model, audio, tokenizer, prompt)
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


# ---------------------------------------------------------------- 教师强制探针(诊断,2026-07-15)

def _probe_from_logprobs(lp, labels, loss_mask, eot_id, tokenizer=None, prefix_n: int = 32,
                         token_types=None) -> dict:
    """探针的纯计算部分(沙盒可测)。lp: [T,V] log-prob 张量;labels/loss_mask: list(与
    encode_target 输出同构,右移后逐位对齐)。返回:
      acc          全序列计分位的 argmax 命中率
      acc_prefix   前 prefix_n 个计分位的命中率(自由生成塌缩发生在开头,前缀命中率才是主证)
      eot_p_first  第一个计分位上 <|eot|> 的概率 ——"一开口就想收工"的直接证据
      n_scored     计分位数量;argmax_prefix/ref_prefix:前缀的 argmax 解码 vs 参照解码(可读对照)
    """
    import torch
    # 全部落 CPU 再比较:lp 来自 GPU forward,labels/mask 是 python list ——
    # 混设备比较是 RuntimeError(执行端 step15000 eval 实测),数据量 T×V≈4M float 无压力。
    lp = torch.as_tensor(lp).detach().float().cpu()
    lab = torch.as_tensor(labels)
    mask = torch.as_tensor(loss_mask, dtype=torch.bool)
    T = min(int(lp.shape[0]), int(lab.shape[0]), int(mask.shape[0]))
    lp, lab, mask = lp[:T], lab[:T], mask[:T]
    pred = lp.argmax(-1)
    idx = mask.nonzero(as_tuple=True)[0]
    n = int(idx.numel())
    out = {"acc": 0.0, "acc_prefix": 0.0, "eot_p_first": None, "n_scored": n}
    if not n:
        return out
    out["acc"] = float((pred[idx] == lab[idx]).float().mean())
    head = idx[:prefix_n]
    out["acc_prefix"] = float((pred[head] == lab[head]).float().mean())
    out["eot_p_first"] = float(lp[idx[0], eot_id].exp())
    if token_types is not None:
        # 分型命中率:0=语义(音高/时值/结构) 1=时间戳。"模型在不在读音频"要看语义:
        # 时间戳靠谱、音高全错的模型,总 acc 会被时间戳撑得虚高。
        tt = torch.as_tensor(token_types)[:T]
        for name, want in (("acc_sem", 0), ("acc_ts", 1)):
            sel = idx[tt[idx] == want]
            out[name] = float((pred[sel] == lab[sel]).float().mean()) if sel.numel() else None
    if tokenizer is not None and hasattr(tokenizer, "id_to_piece"):
        # 音高分型(D43,执行端提议采纳):音高字形是原子 piece(AMT/TAST 的 N60/n60,
        # A2S 的 C4/F##5/A-3)。O4 的核心问题"AMT 音高从音频读没读"要看 Δacc_pitch ——
        # 总 acc_sem 被 velocity/结构 token 稀释,音高单列才锋利。
        import re as _re
        _pit = _re.compile(r"^(?:[Nn]\d{1,3}|[a-gA-G](?:#{1,2}|-{1,2})?\d)$")
        try:
            sel = idx[torch.tensor([bool(_pit.match(tokenizer.id_to_piece(int(t))))
                                    for t in lab[idx]], dtype=torch.bool)]
            out["n_pitch"] = int(sel.numel())
            out["acc_pitch"] = float((pred[sel] == lab[sel]).float().mean()) \
                if sel.numel() else None
        except Exception:
            out["acc_pitch"] = None                 # 分词器不支持/解码失败:缺仪表不毒化探针
            out["n_pitch"] = 0
    if tokenizer is not None:
        out["argmax_prefix"] = tokenizer.decode([int(i) for i in pred[head]])[:80]
        out["ref_prefix"] = tokenizer.decode([int(i) for i in lab[head]])[:80]
    return out


def _truncate_enc(enc: dict, max_len: int) -> dict:
    """探针输入长度护栏(纯逻辑,沙盒可测):参照序列超 decoder 位置表上限时截断。
    为什么必须有:val 参照没过训练侧的超长过滤,22000 步 eval 实测第二个样本超 1024
    → CUDA device-side assert → 上下文中毒,本轮 eval 后续全部解码报废。
    截断后仍是合法的 teacher-forcing 前缀测量(命中率语义不变)。"""
    if len(enc.get("input_ids", [])) <= max_len:
        return enc
    out = dict(enc)
    for k in ("input_ids", "labels", "loss_mask", "token_types", "ts_bins"):
        if k in out and isinstance(out[k], list):
            out[k] = out[k][:max_len]
    out["truncated_to"] = max_len
    return out


def teacher_forced_probe(model, audio, ref_text: str, dialect: str, tokenizer,
                         domain: str | None = None, prefix_n: int = 32,
                         max_len: int = 1000) -> dict:
    """教师强制探针:给足参照上文,量模型逐位预测下一 token 的命中率。
    为什么需要它:自由生成塌缩在开头(eval 恒吐 '|4/4k0' 即停)有两种病因,损失曲线分不开——
      前缀命中率高 + 自由生成塌 → 暴露偏置/解码侧问题(往 scheduled sampling / 解码约束修);
      前缀命中率也低            → 模型确实没学会,继续训,命中率成为比 parseable 灵敏得多的进度表。
    与训练严格同构:encode_target(sample=False,同 prompt/domain 布局)+ 同一个 forward
    (走 autoregressive_decode 已验证的 preprocessor→forward→resolve_log_probs 路径)。
    """
    import torch
    from rubato.data.dataset import encode_target
    from rubato.model.train import resolve_log_probs
    enc = _truncate_enc(encode_target(tokenizer, dialect, ref_text, sample=False,
                                      domain=domain), max_len)
    device = next(model.parameters()).device
    audio_t = torch.as_tensor(audio, dtype=torch.float32, device=device).reshape(1, -1)
    len_t = torch.tensor([audio_t.shape[1]], device=device)
    with torch.no_grad():
        processed, plen = model.preprocessor(input_signal=audio_t, length=len_t)
        t = torch.tensor([enc["input_ids"]], dtype=torch.long, device=device)
        tl = torch.tensor([len(enc["input_ids"])], device=device)
        out = model.forward(processed_signal=processed, processed_signal_length=plen,
                            transcript=t, transcript_length=tl)
        lp = resolve_log_probs(out)[0]
        # encoder 侧体征:enc_frames=0 → 编码器 mask 全空(decoder 从结构上就看不到音频);
        # enc_std ≈ 0 → 特征坍缩。静音 vs 真音频的 enc_std 应明显不同 —— 不同证明
        # 声学前端在工作,相同则病灶在 encoder/preprocessor,一行定位。
        enc_diag = {}
        if isinstance(out, (tuple, list)) and len(out) >= 4:
            try:
                es, em = out[2], out[3]
                enc_diag = {"enc_frames": float(em.float().sum()),
                            "enc_std": float(es.float().std())}
            except Exception:
                pass
    res = _probe_from_logprobs(lp, enc["labels"], enc["loss_mask"],
                               tokenizer.piece_to_id("<|eot|>"), tokenizer, prefix_n,
                               token_types=enc.get("token_types"))
    res.update(enc_diag)
    if enc.get("truncated_to"):
        res["truncated_to"] = enc["truncated_to"]
    return res
