"""
S11 损失三件套(R-S11.1)。纯数学,沙盒可完整验证。

三件套:
  1. 序列级长度归一化:L_seq = (Σ_t CE_t) · |T|^(-1/2),batch 内平均。
     防长序列(AMT)淹没短序列梯度。
  2. 语义 token:label smoothing 0.1。
  3. 时间戳 token:序数平滑(ordinal),目标 bin 权重 0.9,邻域 ±5 二次衰减。
     因时间戳有序数结构(bin 50 比 bin 200 更接近 bin 51),普通 CE 忽略这个结构。
"""
from __future__ import annotations
import torch


def ordinal_smoothing_targets(y: int, n_bins: int = 4000, p_center: float = 0.9,
                              w: int = 5) -> torch.Tensor:
    """
    R-S11.1 时间戳序数平滑。返回长度 n_bins 的目标分布。
    q(y)=p_center;0<|i-y|≤w 时 q(i)=(1-p_center)·(w+1-|i-y|)²/Z_y;Z_y 归一化边界截断后的余量。
    """
    q = torch.zeros(n_bins)
    q[y] = p_center
    # 邻域权重(二次衰减),边界截断
    idxs, raw = [], []
    for d in range(1, w + 1):
        for i in (y - d, y + d):
            if 0 <= i < n_bins:
                idxs.append(i)
                raw.append((w + 1 - d) ** 2)
    if raw:
        Z = sum(raw)
        for i, r in zip(idxs, raw):
            q[i] = (1 - p_center) * r / Z
    return q


# ================================================================ 论文精确训练 loss(向量化)
#
# 论文 §3.3 的三个适配必须同时作用在 backward 路径上:
#   1. Token weighting: L_seq = (Σ_t CE_t) · |T|^(-1/2),batch 内对序列取平均
#   2. 语义 token: label smoothing 0.1(与 F.cross_entropy(label_smoothing=) 同口径)
#   3. 时间戳 token: 序数平滑 P_center=0.9, w=5, 二次衰减,边界截断重归一
#
# 输入是 log_probs(NeMo EncDecMultiTaskModel.forward 返回 log-softmax 后的
# transf_log_probs),不是裸 logits —— 所以这里直接在 log 概率上按目标分布 q 求
# -Σ q·logp,数学上与"logits 过 CE"完全一致。

def _per_token_semantic_nll(logp: torch.Tensor, targets: torch.Tensor,
                            label_smoothing: float = 0.1) -> torch.Tensor:
    """
    语义位置逐 token 的 label-smoothed NLL。
    logp: (N, V) log 概率;targets: (N,) 全词表 token id。返回 (N,)。
    与 F.cross_entropy(label_smoothing=ε) 同口径:q = (1-ε)·onehot + ε/V·uniform。
    """
    nll = -logp.gather(-1, targets.unsqueeze(-1)).squeeze(-1)          # (N,)
    smooth = -logp.sum(-1) / logp.shape[-1]                            # (N,)
    return (1.0 - label_smoothing) * nll + label_smoothing * smooth


def _per_token_ordinal_nll(logp: torch.Tensor, target_bins: torch.Tensor,
                           ts_token_ids: torch.Tensor,
                           p_center: float = 0.9, w: int = 5) -> torch.Tensor:
    """
    时间戳位置逐 token 的序数平滑 NLL(全词表 softmax 上计算,不截取子词表——
    模型放在非时间戳 token 上的概率质量同样计入惩罚)。
    logp: (N, V);target_bins: (N,) bin 编号 0..n_bins-1;
    ts_token_ids: (n_bins,) LongTensor,bin -> 全词表 token id 映射。
    返回 (N,)。
    """
    n_bins = ts_token_ids.shape[0]
    device = logp.device
    offsets = torch.arange(-w, w + 1, device=device)                   # (2w+1,)
    neigh_bins = target_bins.unsqueeze(-1) + offsets                   # (N, 2w+1)
    valid = (neigh_bins >= 0) & (neigh_bins < n_bins)
    neigh_bins_c = neigh_bins.clamp(0, n_bins - 1)
    # 权重:中心 = p_center;邻域 = (1-p)·(w+1-|d|)²/Z(Z=边界截断后的邻域权重和)
    raw = (w + 1 - offsets.abs()).float() ** 2                         # (2w+1,)
    wmat = raw.unsqueeze(0).expand_as(neigh_bins).clone()              # (N, 2w+1)
    center = offsets == 0
    wmat[:, center] = 0.0
    wmat = wmat * valid.float()
    Z = wmat.sum(-1, keepdim=True).clamp(min=1e-12)
    q = (1.0 - p_center) * wmat / Z                                    # (N, 2w+1)
    q[:, center] = p_center
    tok_ids = ts_token_ids.to(device)[neigh_bins_c]                    # (N, 2w+1)
    lp = logp.gather(-1, tok_ids)                                      # (N, 2w+1)
    return -(q * lp).sum(-1)


import re as _re

# 与 infer.py 探针 acc_pitch 同一正则(D43/D82:加权的"音高"定义必须与被测指标一字不差,
# 否则打点和读表不在同一块肉上)。音高字形为原子 piece:AMT/TAST 的 N60/n60、A2S 的 C4/F##5/A-3。
_PITCH_PIECE = _re.compile(r"^(?:[Nn]\d{1,3}|[a-gA-G](?:#{1,2}|-{1,2})?\d)$")


def build_pitch_token_mask(tokenizer, vocab_size: int | None = None) -> torch.Tensor:
    """全词表扫一遍 → BoolTensor[vocab],True=音高 piece。启动时建一次(8000 次查表,毫秒级)。"""
    if vocab_size is None:
        if not hasattr(tokenizer, "get_piece_size"):
            raise ValueError("vocab_size 未提供且 tokenizer 无 get_piece_size()")
        vocab_size = int(tokenizer.get_piece_size())
    if vocab_size <= 0:
        raise ValueError(f"vocab_size 必须 >0，得到 {vocab_size}")
    m = torch.zeros(vocab_size, dtype=torch.bool)
    for i in range(vocab_size):
        try:
            if _PITCH_PIECE.match(tokenizer.id_to_piece(i) or ""):
                m[i] = True
        except Exception:
            continue
    return m


def batch_sequence_loss(log_probs: torch.Tensor, labels: torch.Tensor,
                        token_types: torch.Tensor, loss_mask: torch.Tensor,
                        ts_bins: torch.Tensor, ts_token_ids: torch.Tensor,
                        label_smoothing: float = 0.1,
                        p_center: float = 0.9, w: int = 5,
                        pitch_weight: float = 1.0,
                        pitch_mask: torch.Tensor | None = None) -> dict:
    """
    论文精确训练 loss(R-S11.1 全三件套,进 backward)。
    log_probs: (B, L, V) —— 模型 forward 的 log 概率(teacher forcing,已右移对齐 labels)
    labels: (B, L) 目标 token id
    token_types: (B, L) 0=语义 1=时间戳(与 labels 对齐)
    loss_mask: (B, L) bool,True=计入 loss(prompt 位置 False)
    ts_bins: (B, L) 时间戳位置的 bin 编号(非时间戳位置任意值,被 mask 忽略)
    ts_token_ids: (n_bins,) bin -> token id
    返回 {loss, sem, ts, n_sem, n_ts}(loss 带梯度)。
    """
    B, L, V = log_probs.shape
    if not (0.0 <= label_smoothing < 1.0):
        raise ValueError(f"label_smoothing 越界:{label_smoothing}")
    if not (0.0 < p_center <= 1.0) or w < 1:
        raise ValueError(f"时间戳平滑参数非法:p_center={p_center} w={w}")
    flat_lp = log_probs.reshape(B * L, V)
    flat_labels = labels.reshape(B * L)
    flat_types = token_types.reshape(B * L)
    flat_mask = loss_mask.reshape(B * L).bool()
    flat_bins = ts_bins.reshape(B * L)

    per_token = log_probs.new_zeros(B * L)
    sem_sel = flat_mask & (flat_types == 0)
    ts_sel = flat_mask & (flat_types == 1)
    if sem_sel.any():
        per_token[sem_sel] = _per_token_semantic_nll(
            flat_lp[sem_sel], flat_labels[sem_sel], label_smoothing)
    if ts_sel.any():
        per_token[ts_sel] = _per_token_ordinal_nll(
            flat_lp[ts_sel], flat_bins[ts_sel], ts_token_ids, p_center, w)

    # 【D82 音高加权】病灶算术:音高 token 只占 loss 小头,梯度走文本先验近路。
    # 权重只移【内部占比】不改总量级(按掩码内均值归一)—— 一轮基线曲线保持可比,
    # D81 护栏(合成侧轨迹对表)依赖这一点。pitch_weight=1.0 时本段数值恒等于原实现。
    is_pitch_flat = None
    per_token_mon = per_token                       # 监控口径 = 未加权(基线曲线可比性)
    if pitch_mask is not None:
        pm = pitch_mask.to(flat_labels.device)
        if pm.numel() != V:
            raise ValueError(
                f"pitch_mask 长度 {pm.numel()} != 模型词表 {V}；拒绝静默 clamp token id")
        is_pitch_flat = pm[flat_labels] & sem_sel
        if pitch_weight != 1.0 and is_pitch_flat.any():
            per_token_mon = per_token.detach().clone()
            w_vec = torch.ones_like(per_token)
            w_vec[is_pitch_flat] = float(pitch_weight)
            per_token = per_token * (w_vec / w_vec[flat_mask].mean().clamp(min=1e-6))

    per_token = per_token.reshape(B, L)
    seq_ce = per_token.sum(-1)                                         # (B,) Σ_t CE_t
    T = loss_mask.reshape(B, L).float().sum(-1).clamp(min=1.0)         # (B,) |T|
    loss = (seq_ce * T.pow(-0.5)).mean()                               # 论文 1/√|T|,batch 平均

    with torch.no_grad():
        mon = per_token_mon.reshape(B, L)
        mon_flat = per_token_mon.reshape(-1)
        sem_mean = mon_flat[sem_sel].mean() if sem_sel.any() else log_probs.new_tensor(0.0)
        ts_mean = mon_flat[ts_sel].mean() if ts_sel.any() else log_probs.new_tensor(0.0)
        # 音高单列监控(未加权口径):二轮盯"听没听"的训练侧直读仪表
        pitch_mean = (mon_flat[is_pitch_flat].mean()
                      if is_pitch_flat is not None and is_pitch_flat.any()
                      else log_probs.new_tensor(0.0))
        n_pitch = int(is_pitch_flat.sum()) if is_pitch_flat is not None else 0
        # 逐序列均值(监控用,供上层按 dialect 聚合出各自学习曲线)
        sem_m = (loss_mask & (token_types == 0)).float()
        ts_m = (loss_mask & (token_types == 1)).float()
        seq_sem = (mon * sem_m).sum(-1) / sem_m.sum(-1).clamp(min=1.0)
        seq_ts = (mon * ts_m).sum(-1) / ts_m.sum(-1).clamp(min=1.0)
        has_ts = ts_m.sum(-1) > 0
    return {"loss": loss, "sem": sem_mean, "ts": ts_mean,
            "pitch": pitch_mean, "n_pitch": n_pitch,
            "n_sem": int(sem_sel.sum()), "n_ts": int(ts_sel.sum()),
            "seq_sem": seq_sem, "seq_ts": seq_ts, "seq_has_ts": has_ts}


def build_ts_token_ids(tokenizer, n_bins: int = 4000) -> torch.Tensor:
    """从 SentencePiece tokenizer 建 bin -> token id 映射(训练启动时建一次)。"""
    from rubato.intermo.core import ts_glyph
    ids = [tokenizer.piece_to_id(ts_glyph(i)) for i in range(n_bins)]
    unk = tokenizer.unk_id() if hasattr(tokenizer, "unk_id") else 0
    missing = sum(1 for i in ids if i == unk)
    if missing:
        raise ValueError(f"{missing}/{n_bins} 个时间戳 token 不在词表内 —— "
                         "tokenizer 训练时 user_defined_symbols 未含全部时间戳字形")
    if len(set(ids)) != n_bins:
        raise ValueError(
            f"时间戳 token id 非一一映射:只有 {len(set(ids))}/{n_bins} 个唯一 id")
    if hasattr(tokenizer, "get_piece_size"):
        vocab = int(tokenizer.get_piece_size())
        if min(ids) < 0 or max(ids) >= vocab:
            raise ValueError(
                f"时间戳 token id 越界:[{min(ids)},{max(ids)}] vs vocab={vocab}")
    return torch.tensor(ids, dtype=torch.long)
