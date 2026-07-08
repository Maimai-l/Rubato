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
