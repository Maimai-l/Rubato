"""
S9 tokenizer(R-S9.1~9.4)。词表唯一真源 = configs/vocab_spec.json(R-S9.3:
user_defined_symbols 从 spec 生成,禁止手写第二份清单)。

组成(A-S9.1 核账):
  8000 = 3571 可学习语义 piece + 4170 user_defined(4000 时间戳 + 129 MIDI + 1 beat
  + 40 prompt)+ 256 byte-fallback + 3 特殊符(unk/bos/eos)。
"""
from __future__ import annotations
import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC_PATH = _REPO_ROOT / "configs" / "vocab_spec.json"

N_BYTE_FALLBACK = 256
N_SPECIAL = 3           # <unk> <s> </s>
PAPER_SEMANTIC = 3571   # 论文 ~3570,SPEC A-S9.1 冻结 3571


def build_vocab_spec(spec_path: str | Path | None = None) -> dict:
    """
    读 configs/vocab_spec.json 并核算 counts。返回
    {timestamps, midi, beat, prompt, user_defined_symbols, counts}。
    spec 文件缺失时按规则重新生成(与已落盘版本 byte 级一致)。
    """
    p = Path(spec_path) if spec_path else _SPEC_PATH
    if p.exists():
        spec = json.loads(p.read_text(encoding="utf-8"))
    else:
        spec = _generate_spec()
    # counts 现算,不信任文件里的旧数(防手改失同步)
    counts = {
        "timestamps": len(spec["timestamps"]),
        "midi": len(spec["midi"]),
        "beat": len(spec["beat"]),
        "prompt": len(spec["prompt"]),
    }
    counts["total"] = sum(counts.values())
    spec["counts"] = counts
    assert spec["user_defined_symbols"] == (
        spec["timestamps"] + spec["midi"] + spec["beat"] + spec["prompt"]
    ), "user_defined_symbols 与四段清单失同步 —— vocab_spec.json 被手改?"
    return spec


def _generate_spec() -> dict:
    """按 R-S2.3 冻结字形重新生成(与 configs/vocab_spec.json 一致)。"""
    from rubato.intermo.core import ts_glyph, vel_glyph, pedal_glyph
    timestamps = [ts_glyph(i) for i in range(4000)]              # <|0.00|>..<|39.99|>
    midi = [vel_glyph(i) for i in range(1, 128)] + [pedal_glyph(1), pedal_glyph(0)]
    beat = ["*"]
    prompt = ["<|sot|>", "<|eot|>", "<|pad|>",
              "<|score|>", "<|noscore|>", "<|spell|>", "<|nospell|>",
              "<|ts|>", "<|nots|>", "<|midi|>", "<|nomidi|>",
              "<|beat|>", "<|nobeat|>", "<|real|>", "<|synth|>"]
    prompt += [f"<|rsv{i:02d}|>" for i in range(40 - len(prompt))]
    return {"timestamps": timestamps, "midi": midi, "beat": beat, "prompt": prompt,
            "user_defined_symbols": timestamps + midi + beat + prompt}


def reconcile(vocab_size: int, n_user_defined: int) -> dict:
    """
    A-S9.1 核账:可学习语义 piece = vocab − user_defined − 256 byte − 3 特殊符。
    与论文 3571 不合 = 切分或符号清单有 bug,阻塞。
    """
    learnable = vocab_size - n_user_defined - N_BYTE_FALLBACK - N_SPECIAL
    return {"vocab_size": vocab_size, "n_user_defined": n_user_defined,
            "learnable_semantic": learnable, "expected": PAPER_SEMANTIC,
            "ok": learnable == PAPER_SEMANTIC}


# ---------------------------------------------------------------- SPM 训练(R-S9.1,本地跑)

def train_unigram(corpus_files: list[str], model_prefix: str,
                  vocab_size: int = 8000, spec_path: str | Path | None = None,
                  extra_args: dict | None = None, allow_fallback: bool = True) -> dict:
    """
    SentencePiece UnigramLM 训练封装。R-S9.1 全部不变量在此固化:
      normalization_rule_name=identity(默认 NFKC 会改写 |/#/: —— 已知致命陷阱)
      byte_fallback / character_coverage=1.0 / split_by_whitespace
    user_defined_symbols 从 vocab_spec 注入(R-S9.3)。

    ⚠ 缩水规模的真实约束(问题#3 复盘):A2S 文本的【可学习 piece 上限由语料的
    distinct 子串数决定】。缩水池(SPEC D4:12-20k 曲 → ~6万段 → ~56-90k 行)只能支撑
    远少于 3571 的可学习 piece,vocab==8000 不可达,SentencePiece 会直接报
    "vocab_size too high, set <= N"。这不是 bug,是缩水规模的固有结果。
    → 真正该看的验收是 check_glyph_coverage 的 split_rate<0.30(常见字形是否原子),
      不是 vocab==8000。词表小(~5k)但字形原子 = 模型可用,只是序列略长。
    → allow_fallback=True:目标词表过高时自动回退到 SentencePiece 报的上限重训,
      返回实际词表 + 显式 warning,不让流程卡死。
    → 扩语料的安全杠杆(想逼近 8000):①并入 nASAP A2S/A2S_lite 文本(论文语料含它,
      白拿 ~18M chars);②重叠切段(segment_score_overlap);③tokenizer 语料用【未按
      work_key 去重】的训练侧全部曲(去重是给 train/val/test 隔离用的,不是给 tokenizer
      语料用的)。仍不够则是缩水规模上限,需用户决策(见 EXECUTOR_CORRECTIONS §6b)。
    """
    import sentencepiece as spm
    spec = build_vocab_spec(spec_path)

    def _train(vs: int):
        args = {
            "input": ",".join(str(f) for f in corpus_files),
            "model_prefix": str(model_prefix),
            "vocab_size": vs,
            "model_type": "unigram",
            "normalization_rule_name": "identity",
            "byte_fallback": True,
            "character_coverage": 1.0,
            "split_by_whitespace": True,
            "user_defined_symbols": spec["user_defined_symbols"],
            "train_extremely_large_corpus": True,
            "unk_id": 0, "bos_id": 1, "eos_id": 2,
        }
        args.update(extra_args or {})
        spm.SentencePieceTrainer.train(**args)

    fell_back = False
    try:
        _train(vocab_size)
    except Exception as e:
        m = re.search(r"<=\s*(\d+)", str(e))
        if allow_fallback and m:
            cap = int(m.group(1))
            _train(cap)                      # 回退到语料支持的上限
            fell_back = True
        else:
            raise

    sp = spm.SentencePieceProcessor(model_file=f"{model_prefix}.model")
    got = sp.get_piece_size()
    rec = reconcile(got, len(spec["user_defined_symbols"]))
    warning = None
    if got != vocab_size:
        warning = (f"实际词表 {got} < 目标 {vocab_size}(语料 distinct 子串不足)。"
                   f"这是缩水规模固有结果,不是 bug。请以 check_glyph_coverage 的 "
                   f"split_rate<0.30 为准;若字形原子则模型可用。要逼近 8000 需扩语料"
                   f"(并入 nASAP A2S、重叠切段、不按 work_key 去重语料)或用户决策扩池。")
    return {"vocab_size": got, "requested": vocab_size, "fell_back": fell_back,
            "reconcile": rec, "warning": warning}


# ---------------------------------------------------------------- 训后验收(问题#20)

# 需要"不被切碎"的原子字形:音高(C4/A-3/F##5)、MIDI 音高(N60/n60)、
# 常见 interval 分数、小节线。它们是 InterMo 的最小语义原子,若 100% 分裂
# 说明语料覆盖不足(问题#3 的症状)。
_PROBE_GLYPHS = (
    [f"{s}{o}" for s in "CDEFGAB" for o in range(1, 8)] +
    [f"{s}-{o}" for s in "ABDEG" for o in range(2, 7)] +
    [f"{s}#{o}" for s in "CDFGA" for o in range(2, 7)] +
    [f"{s.lower()}{o}" for s in "CDEFGAB" for o in range(2, 7)] +
    [f"N{m}" for m in range(36, 97, 6)] + [f"n{m}" for m in range(36, 97, 6)] +
    ["1/4", "1/8", "1/2", "1/16", "3/8", "1/1", "3/4", "1/32", "1/12", "1/6"] +
    ["|4/4k0", "|3/4k0", "|2/4k0", "|6/8k0", "|4/4k-3", "|3/4k#2"]
)


def check_glyph_coverage(spm_model_path: str, probes: list[str] | None = None) -> dict:
    """
    A-S9.2 训后验收:探针字形应存在为【单 piece】(或至少不被切成字符/byte 级碎片)。
    返回 {n_probes, single_piece, split, split_rate, examples_split}。
    split_rate 接近 1.0 = 问题#3 的"字形 100% 分裂",需扩语料重训。
    """
    import sentencepiece as spm
    sp = spm.SentencePieceProcessor(model_file=str(spm_model_path))
    probes = probes or _PROBE_GLYPHS
    single, split, examples = 0, 0, []
    for g in probes:
        pieces = sp.encode(g, out_type=str)
        if len(pieces) == 1:
            single += 1
        else:
            split += 1
            if len(examples) < 10:
                examples.append({g: pieces})
    return {"n_probes": len(probes), "single_piece": single, "split": split,
            "split_rate": round(split / max(len(probes), 1), 3),
            "examples_split": examples}


# ---------------------------------------------------------------- 训练期子词正则(R-S9.4)

def encode_with_regularization(sp, text: str, alpha: float = 0.25,
                               sample: bool = True) -> list[int]:
    """
    论文 α=0.25 采样式切分(R-S9.4)。user_defined_symbols(时间戳/prompt/MIDI)
    在 SPM 内永远原子,不受采样影响 —— 只有语义 piece 参与正则。
    eval 时 sample=False 走确定性最优切分。
    """
    if sample:
        return sp.encode(text, out_type=int, enable_sampling=True,
                         alpha=alpha, nbest_size=-1)
    return sp.encode(text, out_type=int)
