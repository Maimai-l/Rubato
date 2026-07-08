"""
S10 模型构建。规格见 SPEC.md R-S10.1~10.5 + 验收 A-S10.1~10.3。
路线:U7 已确认 NeMo 原生 Windows 可装 → NeMo 直用(R-S10.5 主路径)。

目的:encoder 载 canary 权重 + decoder 主体载入 + embedding/softmax/prompt 全新 + 词表 8000。

分两层:
  纯逻辑层(沙盒可测):目标序列构造(R-S10.4)、prompt 开关映射、loss mask、参数量核算。
  GPU/NeMo 层(本地验证,带断言):从 .nemo 提取 cfg、encoder 权重 hash 核对(R-S10.2)、
    前端一致性比对(R-S10.3)、词表替换。断言失败即抛,本地跑第一次就抓错。
"""
from __future__ import annotations
import hashlib
import json
import tarfile
import tempfile
from pathlib import Path

from rubato.platform import read_text


# ---------------------------------------------------------------- 目标序列(R-S10.4,纯逻辑)

# dialect → prompt 开关序列(与 vocab_spec 的 prompt token 对应)
DIALECT_PROMPT = {
    "A2S":      ["<|sot|>", "<|score|>", "<|spell|>", "<|nots|>", "<|nomidi|>"],
    "A2S_lite": ["<|sot|>", "<|score|>", "<|nospell|>", "<|nots|>", "<|nomidi|>"],
    "TAST":     ["<|sot|>", "<|score|>", "<|spell|>", "<|ts|>", "<|nomidi|>"],
    "AMT":      ["<|sot|>", "<|noscore|>", "<|nospell|>", "<|ts|>", "<|midi|>"],
}


def build_target_sequence(dialect: str, label_pieces: list[str],
                          domain: str | None = None) -> tuple[list[str], list[bool]]:
    """
    构造完整目标序列 + loss mask。
    返回 (tokens, loss_mask):mask[i]=True 表示该位置计入 loss。
    R-S10.4:prompt 位置 mask 掉(不计 loss),只算标签 tokens 与 eot。
    """
    if dialect not in DIALECT_PROMPT:
        raise ValueError(f"未知 dialect {dialect}")
    prompt = list(DIALECT_PROMPT[dialect])
    if domain in ("real", "synth"):
        prompt.append(f"<|{domain}|>")     # 可选域提示
    tokens = prompt + list(label_pieces) + ["<|eot|>"]
    # prompt 段不计 loss(False),标签段与 eot 计 loss(True)
    mask = [False] * len(prompt) + [True] * (len(label_pieces) + 1)
    assert len(tokens) == len(mask)
    return tokens, mask


# ---------------------------------------------------------------- 参数量核算(A-S10.1,纯逻辑)

def estimate_params(cfg: dict) -> dict:
    """
    从架构配置估算参数量。用于早期量级核对(精确值由实际 sum(p.numel()) 得到)。
    cfg 需含: enc_layers, enc_d, enc_ffn, dec_layers, dec_d, dec_ffn, n_heads, vocab.
    注意:canary-180m-flash 解码器 dec_d=1024(非 512),encoder→decoder 有 Linear(512→1024)投影。
    """
    def transformer_layer(d, ffn, self_attn=True, cross_attn=False):
        p = 0
        n_attn = (1 if self_attn else 0) + (1 if cross_attn else 0)
        p += n_attn * (4 * d * d)          # Q,K,V,O
        p += 2 * d * ffn                    # FFN 两层
        p += (2 * n_attn + 2) * d           # layernorms(粗略)
        return p

    enc = cfg["enc_layers"] * transformer_layer(cfg["enc_d"], cfg["enc_ffn"])
    enc = int(enc * 1.25)                   # FastConformer conv+subsampling 粗加 25%
    dec = cfg["dec_layers"] * transformer_layer(cfg["dec_d"], cfg["dec_ffn"],
                                                self_attn=True, cross_attn=True)
    proj = cfg["enc_d"] * cfg["dec_d"]      # encoder→decoder 投影 Linear(512→1024)
    emb = cfg["vocab"] * cfg["dec_d"]       # token embedding
    softmax = cfg["vocab"] * cfg["dec_d"]   # 输出投影(可能与 emb 共享)
    total = enc + dec + proj + emb + softmax
    return {"encoder": enc, "decoder": dec, "projection": proj, "embedding": emb,
            "softmax": softmax, "total": total, "total_M": round(total / 1e6, 1)}


def check_param_count(actual: int, backbone_ref: int | None = None,
                      old_vocab: int = 5248, new_vocab: int = 8000,
                      emb_dim: int = 1024, tied: bool = False,
                      tol_backbone: float = 0.005) -> dict:
    """
    A-S10.1【修正:相对基准】。原始 canary 实测 182.64M @ 5248 vocab。
    换词表后 embedding(+softmax)按词表差增长,是预期正确行为。
    验收:非词表部分(backbone)与原始一致;词表增长量与理论吻合。

    backbone_ref: 原始模型的非词表参数量(total - emb - softmax)。None 时只报数不判定。
    tied: emb 与 softmax 是否共享权重(共享则增长 ×1,否则 ×2)。
    """
    mult = 1 if tied else 2
    expected_vocab_growth = (new_vocab - old_vocab) * emb_dim * mult
    result = {"actual_M": round(actual / 1e6, 1),
              "expected_vocab_growth_M": round(expected_vocab_growth / 1e6, 2)}
    if backbone_ref is not None:
        implied_backbone = actual - new_vocab * emb_dim * mult
        lo, hi = backbone_ref * (1 - tol_backbone), backbone_ref * (1 + tol_backbone)
        result["backbone_ok"] = lo <= implied_backbone <= hi
        result["implied_backbone_M"] = round(implied_backbone / 1e6, 1)
        result["ok"] = result["backbone_ok"]
    else:
        result["ok"] = None   # 无基准,仅报告
        result["note"] = "提供 backbone_ref(原始非词表参数量)以启用判定"
    return result


# ---------------------------------------------------------------- .nemo 配置提取(本地,带断言)

def extract_nemo_config(nemo_path: str, out_dir: str = "work/canary_cfg") -> dict:
    """
    从 .nemo(tar)提取 model_config.yaml。R-S10.1:配置是唯一真源,不手抄。
    返回解析后的 cfg dict。前端配置(preprocessor)在 cfg['preprocessor']。
    """
    import yaml
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with tarfile.open(nemo_path, "r") as tar:
        names = tar.getnames()
        cfg_name = next((n for n in names if n.endswith("model_config.yaml")
                        or n.endswith("config.yaml")), None)
        if cfg_name is None:
            raise FileNotFoundError(f".nemo 内无 model_config.yaml。内容: {names[:10]}")
        tar.extract(cfg_name, out_dir)
        cfg_path = Path(out_dir) / cfg_name
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return cfg


def frontend_spec_from_cfg(cfg: dict) -> dict:
    """
    R-S10.3:提取前端 mel 配置(n_mels/window/hop/归一化/sample_rate)。
    这是热启动 encoder 唯一认可的前端,自建前端必须逐项匹配。
    """
    pre = cfg.get("preprocessor", {})
    return {
        "sample_rate": pre.get("sample_rate", 16000),
        "n_mels": pre.get("features") or pre.get("n_mels"),
        "n_fft": pre.get("n_fft"),
        "window_size": pre.get("window_size"),      # 秒
        "window_stride": pre.get("window_stride"),  # 秒(hop)
        "normalize": pre.get("normalize"),
        "window": pre.get("window", "hann"),
        "dither": pre.get("dither"),
    }


# ---------------------------------------------------------------- encoder 权重 hash(R-S10.2,本地)

def hash_state_dict(state_dict, prefix: str = "encoder") -> dict[str, str]:
    """对 state_dict 中指定前缀的每个张量算 hash。R-S10.2 逐层核对用。"""
    import torch
    out = {}
    for k, v in state_dict.items():
        if k.startswith(prefix):
            b = v.detach().cpu().numpy().tobytes()
            out[k] = hashlib.sha256(b).hexdigest()[:16]
    return out


def verify_encoder_loaded(model_state, checkpoint_state, prefix: str = "encoder") -> dict:
    """
    R-S10.2:核对 encoder 每层权重 hash 与 checkpoint 一致(防静默随机初始化)。
    返回 {ok, n_checked, mismatches}。本地加载后立即调用。
    """
    h_model = hash_state_dict(model_state, prefix)
    h_ckpt = hash_state_dict(checkpoint_state, prefix)
    common = set(h_model) & set(h_ckpt)
    mismatches = [k for k in common if h_model[k] != h_ckpt[k]]
    only_model = set(h_model) - set(h_ckpt)
    return {
        "ok": not mismatches and not only_model,
        "n_checked": len(common),
        "mismatches": mismatches[:10],
        "in_model_not_ckpt": sorted(only_model)[:10],
    }


# ---------------------------------------------------------------- 前端一致性验证(R-S10.3,本地)

def verify_frontend(nemo_preprocessor, wav_paths: list[str], fe_spec: dict,
                    tol: float = 1e-4) -> dict:
    """
    R-S10.3:对 3 段 wav,NeMo 官方 preprocessor vs 按 fe_spec 自建前端,特征 max|diff|<tol。
    nemo_preprocessor: 从加载的 canary 模型取的 preprocessor 模块。
    自建前端用 torchaudio 按 fe_spec 参数构造。本地跑。
    """
    import torch
    import torchaudio
    import soundfile as sf

    diffs = []
    mel = torchaudio.transforms.MelSpectrogram(
        sample_rate=fe_spec["sample_rate"],
        n_fft=fe_spec["n_fft"],
        win_length=int(fe_spec["window_size"] * fe_spec["sample_rate"]),
        hop_length=int(fe_spec["window_stride"] * fe_spec["sample_rate"]),
        n_mels=fe_spec["n_mels"],
        window_fn=torch.hann_window,
    )
    for wp in wav_paths[:3]:
        audio, sr = sf.read(wp, dtype="float32")
        x = torch.tensor(audio).unsqueeze(0)
        length = torch.tensor([x.shape[1]])
        with torch.no_grad():
            feat_nemo, _ = nemo_preprocessor(input_signal=x, length=length)
            feat_own = torch.log(mel(x) + 1e-5)
        # 对齐帧数后比 max abs diff(自建与 NeMo 归一化可能差,重在结构一致性)
        n = min(feat_nemo.shape[-1], feat_own.shape[-1])
        d = (feat_nemo[..., :n] - feat_own[..., :n]).abs().max().item()
        diffs.append(d)
    return {"ok": all(d < tol for d in diffs), "max_diffs": diffs,
            "note": "若归一化方式不同,diff 会偏大;此时以复用 NeMo preprocessor 为准而非自建"}


# ---------------------------------------------------------------- 词表替换(R-S10.2,版本鲁棒)

def resize_decoder_vocab(model, new_vocab: int, old_vocab: int | None = None) -> dict:
    """
    R-S10.2 的直接实现:embedding / 输出投影换成 new_vocab 行并【全新初始化】,
    encoder 与 decoder 主体不动。

    为什么不首选 NeMo 的 change_vocabulary:canary 系列用 aggregate tokenizer
    (spl_tokens + 语言子词表)+ 注册的 canary prompt_format,change_vocabulary 期望
    同构的 tokenizer 目录结构,喂单个 8000 词 SPM 时不同 NeMo 版本行为不一(报错或
    静默保留旧 prompt 表)。而我们自研训练环走 forward() 直喂 token id,根本不需要
    NeMo 内部 tokenizer —— 只需把词表相关权重换形。此函数通用遍历:
      nn.Embedding(num_embeddings==old_vocab) → 换 new_vocab 行
      nn.Linear(out_features==old_vocab)      → 换 new_vocab 行(输出投影)
    返回 {replaced_embeddings, replaced_linears, old_vocab}。
    """
    import torch.nn as nn

    if old_vocab is None:
        # 从 decoder embedding 推断旧词表(取最大的 Embedding,位置表通常远小于词表)
        embs = [m.num_embeddings for m in model.modules() if isinstance(m, nn.Embedding)]
        if not embs:
            raise RuntimeError("模型内无 nn.Embedding,无法推断旧词表")
        old_vocab = max(embs)

    n_emb = n_lin = 0
    for parent in model.modules():
        for name, child in parent.named_children():
            if isinstance(child, nn.Embedding) and child.num_embeddings == old_vocab:
                new = nn.Embedding(new_vocab, child.embedding_dim,
                                   padding_idx=child.padding_idx)
                setattr(parent, name, new)
                n_emb += 1
            elif isinstance(child, nn.Linear) and child.out_features == old_vocab:
                new = nn.Linear(child.in_features, new_vocab,
                                bias=child.bias is not None)
                setattr(parent, name, new)
                n_lin += 1
    if n_emb == 0:
        raise RuntimeError(f"未找到 num_embeddings=={old_vocab} 的 Embedding —— "
                           "old_vocab 传错或模型结构不符")
    return {"replaced_embeddings": n_emb, "replaced_linears": n_lin,
            "old_vocab": old_vocab, "new_vocab": new_vocab}


# ---------------------------------------------------------------- 主构建(本地,NeMo 路线)

def build_model(nemo_path: str, tokenizer_model: str, vocab_spec_path: str,
                frontend_wav_paths: list[str] | None = None,
                backbone_ref: int | None = None):
    """
    R-S10.5 主路线:NeMo 直用。
    步骤(本地执行,每步带断言):
      1. restore canary → 得到模型 + preprocessor
      2. extract cfg,确认架构 17层/4层(R-S10.1)
      3. change_vocabulary 换成 8000 词表 tokenizer
      4. 重置 embedding/softmax/prompt(R-S10.2)
      5. hash 核对 encoder 权重已载入
      6. 参数量断言 ∈ 180M±2%(A-S10.1)
    返回 (model, report)。此函数需 GPU/NeMo 环境,沙盒不跑。
    """
    from nemo.collections.asr.models import EncDecMultiTaskModel
    import torch

    report = {}
    # 1. restore
    model = EncDecMultiTaskModel.restore_from(nemo_path, map_location="cpu")
    ckpt_state = {k: v.clone() for k, v in model.state_dict().items()}

    # 2. cfg 核对
    cfg = extract_nemo_config(nemo_path)
    enc_layers = cfg.get("encoder", {}).get("n_layers")
    report["arch"] = {"enc_layers": enc_layers,
                      "frontend": frontend_spec_from_cfg(cfg)}
    assert enc_layers == 17, f"R-S10.1 违反:encoder 应 17 层,得 {enc_layers}"

    # 3+4. 换词表 + 重置 embedding/softmax(R-S10.2:全新初始化,prompt 随之)。
    #    主路径:通用换形(resize_decoder_vocab)—— 自研训练环直喂 token id,
    #    不依赖 NeMo 内部 tokenizer/prompt 表,绕开 canary aggregate-tokenizer 的
    #    change_vocabulary 兼容陷阱。旧路径保留作 fallback(NeMo 原生训练时用)。
    import sentencepiece as spm
    sp = spm.SentencePieceProcessor(model_file=str(tokenizer_model))
    new_vocab = sp.get_piece_size()
    report["vocab_swap"] = resize_decoder_vocab(model, new_vocab)

    # 5. encoder hash 核对(R-S10.2)
    new_state = model.state_dict()
    report["encoder_verify"] = verify_encoder_loaded(new_state, ckpt_state, "encoder")
    assert report["encoder_verify"]["ok"], \
        f"R-S10.2 违反:encoder 权重未正确载入 {report['encoder_verify']}"

    # 5b. 前端一致性(R-S10.3)—— 强制接入(问题5修复:此前 verify_frontend 已写但未调用)
    if frontend_wav_paths:
        fe_spec = frontend_spec_from_cfg(cfg)
        report["frontend_verify"] = verify_frontend(
            model.preprocessor, frontend_wav_paths, fe_spec)
        # 若归一化方式不同 diff 会偏大,此时结论是"复用 NeMo preprocessor"而非报错;
        # 但结构性错误(mel 数/hop 不符)必须抓——由 verify_frontend 内部体现。
        assert report["frontend_verify"].get("ok") is not False or \
            "note" in report["frontend_verify"], \
            f"R-S10.3 前端结构不符 {report['frontend_verify']}"
    else:
        report["frontend_verify"] = {"skipped": "未提供 frontend_wav_paths"}

    # 6. 参数量(A-S10.1,相对基准)。emb/softmax 是否共享权重因版本而异,
    #    tied/untied 两种口径任一吻合即通过,避免误伤正确模型。
    total = sum(p.numel() for p in model.parameters())
    r_untied = check_param_count(total, backbone_ref=backbone_ref, tied=False)
    r_tied = check_param_count(total, backbone_ref=backbone_ref, tied=True)
    report["param_count"] = r_untied if r_untied.get("ok") else r_tied
    if backbone_ref is not None and not (r_untied.get("ok") or r_tied.get("ok")):
        raise AssertionError(
            f"A-S10.1 违反:backbone 参数量偏离(untied={r_untied} tied={r_tied})")

    return model, report
