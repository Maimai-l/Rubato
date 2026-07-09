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
import torch.nn.functional as F


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


def timestamp_loss(logits: torch.Tensor, targets: torch.Tensor,
                   n_bins: int = 4000, p_center: float = 0.9, w: int = 5) -> torch.Tensor:
    """
    时间戳位置的序数平滑 CE。
    logits: (N, n_bins) 时间戳 token 的 logits;targets: (N,) 目标 bin。
    """
    logp = F.log_softmax(logits, dim=-1)
    loss = 0.0
    for i in range(logits.shape[0]):
        q = ordinal_smoothing_targets(int(targets[i].item()), n_bins, p_center, w).to(logits.device)
        loss = loss + (-(q * logp[i]).sum())
    return loss / max(logits.shape[0], 1)


def semantic_loss(logits: torch.Tensor, targets: torch.Tensor,
                  label_smoothing: float = 0.1) -> torch.Tensor:
    """语义 token 的 label-smoothed CE。logits: (N, V);targets: (N,)。"""
    return F.cross_entropy(logits, targets, label_smoothing=label_smoothing)


def sequence_loss(token_ce: torch.Tensor, seq_lengths: torch.Tensor) -> torch.Tensor:
    """
    R-S11.1 序列级长度归一化。
    token_ce: (B,) 每条序列的 Σ_t CE_t(已 mask,只含计 loss 的位置)。
    seq_lengths: (B,) 每条序列的有效 token 数 |T|。
    返回 batch 平均的 L_seq。
    """
    normalized = token_ce * seq_lengths.float().clamp(min=1).pow(-0.5)
    return normalized.mean()


def combined_loss(sem_logits, sem_targets, ts_logits, ts_targets,
                  seq_lengths, ts_seq_lengths=None,
                  label_smoothing: float = 0.1) -> dict:
    """
    组合三件套。返回 {loss, sem, ts}。
    实际训练中按 token 类型分流:语义位置走 semantic_loss,时间戳位置走 timestamp_loss,
    再各自序列级长度归一化后相加。此处给出结构,精确分流在 dataloader/collate 定 token 类型。

    注意:此函数是"结构演示/监控指标"版本(逐 token 平均,不含 1/√|T|)。
    真正进 backward 的训练 loss 用下面的 batch_sequence_loss —— 它精确实现论文公式
    (逐序列 ΣCE × |T|^{-1/2},batch 取平均)且完全向量化。
    """
    parts = {}
    total = torch.tensor(0.0)
    if sem_logits is not None and sem_logits.shape[0] > 0:
        parts["sem"] = semantic_loss(sem_logits, sem_targets, label_smoothing)
        total = total + parts["sem"]
    if ts_logits is not None and ts_logits.shape[0] > 0:
        parts["ts"] = timestamp_loss(ts_logits, ts_targets)
        total = total + parts["ts"]
    parts["loss"] = total
    return parts


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


def batch_sequence_loss(log_probs: torch.Tensor, labels: torch.Tensor,
                        token_types: torch.Tensor, loss_mask: torch.Tensor,
                        ts_bins: torch.Tensor, ts_token_ids: torch.Tensor,
                        label_smoothing: float = 0.1,
                        p_center: float = 0.9, w: int = 5) -> dict:
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

    per_token = per_token.reshape(B, L)
    seq_ce = per_token.sum(-1)                                         # (B,) Σ_t CE_t
    T = loss_mask.reshape(B, L).float().sum(-1).clamp(min=1.0)         # (B,) |T|
    loss = (seq_ce * T.pow(-0.5)).mean()                               # 论文 1/√|T|,batch 平均

    with torch.no_grad():
        sem_mean = per_token.reshape(-1)[sem_sel].mean() if sem_sel.any() else log_probs.new_tensor(0.0)
        ts_mean = per_token.reshape(-1)[ts_sel].mean() if ts_sel.any() else log_probs.new_tensor(0.0)
    return {"loss": loss, "sem": sem_mean, "ts": ts_mean,
            "n_sem": int(sem_sel.sum()), "n_ts": int(ts_sel.sum())}


def build_ts_token_ids(tokenizer, n_bins: int = 4000) -> torch.Tensor:
    """从 SentencePiece tokenizer 建 bin -> token id 映射(训练启动时建一次)。"""
    from rubato.intermo.core import ts_glyph
    ids = [tokenizer.piece_to_id(ts_glyph(i)) for i in range(n_bins)]
    unk = tokenizer.unk_id() if hasattr(tokenizer, "unk_id") else 0
    missing = sum(1 for i in ids if i == unk)
    if missing:
        raise ValueError(f"{missing}/{n_bins} 个时间戳 token 不在词表内 —— "
                         "tokenizer 训练时 user_defined_symbols 未含全部时间戳字形")
    return torch.tensor(ids, dtype=torch.long)
