"""Acoustically grounded AMT auxiliary objective for Canary/Rubato.

The main decoder loss is teacher-forced text prediction.  It can therefore
improve by exploiting target-language regularities without learning a useful
audio representation.  This module adds a deliberately small training-only
head on the encoder states returned by Canary's normal forward pass:

    encoder state -> piano onset / occupancy / offset grid

Targets live in a common event space, so they may come from exact MIDI/TAST
references or, later, from a heterogeneous teacher such as TransKun.  No
teacher model is run in the training process.
"""
from __future__ import annotations

from dataclasses import dataclass


PIANO_MIN = 21
PIANO_MAX = 108
N_PITCHES = PIANO_MAX - PIANO_MIN + 1
EVENT_NAMES = ("onset", "frame", "offset")


class AcousticAMTHead:
    """Factory-compatible wrapper; returns a real ``torch.nn.Module`` instance.

    Keeping torch out of module import makes dataset-only tooling cheap.  The
    returned module is registered on the NeMo model by ``attach_amt_aux_head``.
    """

    def __new__(cls, input_dim: int, hidden_dim: int = 0,
                dropout: float = 0.0):
        import torch.nn as nn

        input_dim = int(input_dim)
        hidden_dim = int(hidden_dim)
        if input_dim <= 0 or hidden_dim < 0:
            raise ValueError(
                f"AMT auxiliary dimensions must be valid: "
                f"input={input_dim} hidden={hidden_dim}")
        layers: list[nn.Module] = [nn.LayerNorm(input_dim)]
        if hidden_dim:
            layers.extend([
                nn.Linear(input_dim, hidden_dim),
                nn.GELU(),
                nn.Dropout(float(dropout)),
                nn.Linear(hidden_dim, len(EVENT_NAMES) * N_PITCHES),
            ])
        else:
            layers.append(nn.Linear(input_dim, len(EVENT_NAMES) * N_PITCHES))

        class _Head(nn.Sequential):
            def forward(self, x):
                y = super().forward(x)
                return y.unflatten(-1, (len(EVENT_NAMES), N_PITCHES))

        return _Head(*layers)


def infer_encoder_state_dim(model) -> int:
    """Infer the post-projection encoder dimension returned by Canary forward."""
    import torch.nn as nn

    proj = getattr(model, "encoder_decoder_proj", None)
    if proj is not None:
        linears = [m for m in proj.modules() if isinstance(m, nn.Linear)]
        if linears:
            return int(linears[-1].out_features)
        out_features = getattr(proj, "out_features", None)
        if out_features:
            return int(out_features)
    cfg = getattr(model, "cfg", None)
    defaults = getattr(cfg, "model_defaults", None)
    for name in ("lm_enc_hidden", "lm_dec_hidden"):
        value = getattr(defaults, name, None)
        if value:
            return int(value)
        if isinstance(defaults, dict) and defaults.get(name):
            return int(defaults[name])
    raise ValueError(
        "Cannot infer Canary encoder-state dimension; "
        "encoder_decoder_proj/cfg.model_defaults is unavailable")


def attach_amt_aux_head(model, hidden_dim: int = 0, dropout: float = 0.0) -> dict:
    """Register the training-only AMT head and return an auditable summary."""
    import torch.nn as nn

    name = "rubato_amt_aux_head"
    input_dim = infer_encoder_state_dim(model)
    existing = getattr(model, name, None)
    if existing is None:
        model.add_module(
            name, AcousticAMTHead(input_dim, hidden_dim=hidden_dim,
                                  dropout=dropout))
        existing = getattr(model, name)
    elif not isinstance(existing, nn.Module):
        raise TypeError(f"{name} exists but is not an nn.Module")
    n_params = sum(p.numel() for p in existing.parameters())
    return {
        "name": name,
        "input_dim": input_dim,
        "hidden_dim": int(hidden_dim),
        "n_params": int(n_params),
    }


@dataclass
class AcousticTargets:
    events: object
    valid: object
    supervised: object
    note_counts: tuple[int, ...]


def build_acoustic_targets(reference_texts, encoded_lengths, max_frames: int,
                           audio_lengths, sample_rate: int = 16000,
                           onset_radius: int = 1):
    """Convert exact/teacher InterMo references to a padded event grid.

    ``events`` has shape ``[B,T,3,88]``.  Onset and offset are widened by one
    encoder frame by default because Canary-Flash emits one state per roughly
    80 ms while the source timestamps are 10 ms.
    """
    import torch
    from rubato.model.evaluate import amt_text_to_notes

    if max_frames <= 0 or sample_rate <= 0 or onset_radius < 0:
        raise ValueError(
            f"Invalid target geometry: T={max_frames} sr={sample_rate} "
            f"radius={onset_radius}")
    if len(reference_texts) != int(encoded_lengths.numel()):
        raise ValueError(
            f"reference batch {len(reference_texts)} != "
            f"encoded lengths {int(encoded_lengths.numel())}")
    device = encoded_lengths.device
    batch = len(reference_texts)
    targets = torch.zeros(
        batch, max_frames, len(EVENT_NAMES), N_PITCHES,
        dtype=torch.float32, device=device)
    valid = torch.zeros(batch, max_frames, 1, 1,
                        dtype=torch.bool, device=device)
    supervised = torch.zeros(batch, dtype=torch.bool, device=device)
    note_counts: list[int] = []

    for i, text in enumerate(reference_texts):
        n_frames = min(int(encoded_lengths[i]), max_frames)
        if n_frames <= 0:
            raise ValueError(f"encoded length must be positive, got {n_frames}")
        valid[i, :n_frames] = True
        if text is None:
            note_counts.append(0)
            continue
        supervised[i] = True
        notes = amt_text_to_notes(str(text))
        note_counts.append(len(notes))
        audio_sec = float(audio_lengths[i]) / float(sample_rate)
        if audio_sec <= 0:
            raise ValueError(f"audio length must be positive, got {audio_sec}")

        def _frame_index(second: float) -> int:
            # Map timestamps to encoder frames by the sample's actual encoded
            # length.  This stays correct at frontend boundary/padding effects.
            return max(0, min(n_frames - 1,
                              int(round(float(second) / audio_sec * n_frames))))

        for note in notes:
            pitch = int(note["pitch"])
            if not PIANO_MIN <= pitch <= PIANO_MAX:
                continue
            p = pitch - PIANO_MIN
            on = _frame_index(note["on"])
            off = _frame_index(note["off"])
            if off < on:
                off = on
            # Occupancy uses a half-open range, but every note gets at least one
            # positive frame even when shorter than the encoder stride.
            targets[i, on:min(off + 1, n_frames), 1, p] = 1.0
            for center, event in ((on, 0), (off, 2)):
                lo = max(0, center - onset_radius)
                hi = min(n_frames, center + onset_radius + 1)
                targets[i, lo:hi, event, p] = 1.0

    return AcousticTargets(
        events=targets,
        valid=valid,
        supervised=supervised,
        note_counts=tuple(note_counts),
    )


def _balanced_bce_per_sample(logits, targets, valid, supervised):
    """Class-balanced BCE per sample; silence remains a valid negative target."""
    import torch
    import torch.nn.functional as F

    raw = F.binary_cross_entropy_with_logits(
        logits.float(), targets.float(), reduction="none")
    mask = valid.expand_as(targets) & supervised[:, None, None, None]
    positive = mask & (targets > 0.5)
    negative = mask & ~positive
    reduce_dims = (1, 2, 3)
    pos_n = positive.sum(reduce_dims)
    neg_n = negative.sum(reduce_dims)
    pos = (raw * positive).sum(reduce_dims) / pos_n.clamp(min=1)
    neg = (raw * negative).sum(reduce_dims) / neg_n.clamp(min=1)
    both = 0.5 * (pos + neg)
    per_sample = torch.where(pos_n > 0, both, neg)
    return per_sample


def acoustic_auxiliary_loss(logits, targets: AcousticTargets,
                            alignment_weight: float = 0.25,
                            alignment_margin: float = 0.10) -> dict:
    """AMT event loss plus a no-extra-forward mismatched-target margin.

    For supervised batches with at least two examples, each audio's logits must
    fit its own event grid better than another example's grid.  This prevents a
    corpus-level piano prior from satisfying the auxiliary objective.
    """
    import torch

    if logits.shape != targets.events.shape:
        raise ValueError(
            f"AMT logits {tuple(logits.shape)} != targets "
            f"{tuple(targets.events.shape)}")
    if alignment_weight < 0 or alignment_margin < 0:
        raise ValueError(
            f"alignment settings must be non-negative: "
            f"weight={alignment_weight} margin={alignment_margin}")
    supervised = targets.supervised
    n_supervised = int(supervised.sum())
    zero = logits.float().sum() * 0.0
    if n_supervised == 0:
        return {
            "loss": zero, "event_loss": zero, "alignment_loss": zero,
            "n_supervised": 0, "frame_f1": None,
        }

    per_sample = _balanced_bce_per_sample(
        logits, targets.events, targets.valid, supervised)
    event_loss = per_sample[supervised].mean()
    alignment_loss = zero
    indices = supervised.nonzero(as_tuple=False).flatten()
    if indices.numel() >= 2 and alignment_weight:
        wrong_indices = indices.roll(1)
        own_logits = logits[indices]
        wrong_targets = targets.events[wrong_indices]
        common_valid = targets.valid[indices] & targets.valid[wrong_indices]
        wrong_supervised = torch.ones(
            len(indices), dtype=torch.bool, device=logits.device)
        wrong = _balanced_bce_per_sample(
            own_logits, wrong_targets, common_valid, wrong_supervised)
        own = _balanced_bce_per_sample(
            own_logits, targets.events[indices], common_valid,
            wrong_supervised)
        alignment_loss = torch.relu(
            float(alignment_margin) + own - wrong).mean()

    with torch.no_grad():
        # Occupancy F1 is a compact optimization diagnostic, not the final
        # mir_eval note F1.  It is intentionally named frame_f1.
        mask = (targets.valid.expand_as(targets.events)
                & supervised[:, None, None, None])
        frame_mask = mask[:, :, 1]
        pred = logits[:, :, 1] >= 0
        truth = targets.events[:, :, 1] > 0.5
        tp = (pred & truth & frame_mask).sum().float()
        fp = (pred & ~truth & frame_mask).sum().float()
        fn = (~pred & truth & frame_mask).sum().float()
        denom = 2 * tp + fp + fn
        frame_f1 = float((2 * tp / denom).item()) if denom > 0 else 1.0

    return {
        "loss": event_loss + float(alignment_weight) * alignment_loss,
        "event_loss": event_loss,
        "alignment_loss": alignment_loss,
        "n_supervised": n_supervised,
        "frame_f1": frame_f1,
    }
