"""Pure-CPU regression tests for the AMT auxiliary/distillation experiment."""
from __future__ import annotations

import tempfile
from pathlib import Path

import torch

from rubato.data.dataset import collate_batch
from rubato.model.acoustic_aux import (
    AcousticAMTHead,
    acoustic_auxiliary_loss,
    attach_amt_aux_head,
    build_acoustic_targets,
)
from rubato.model.train import (
    build_optimizer,
    load_snapshot,
    save_snapshot,
    training_step_logic,
)


PASS = 0


def check(name, cond, detail=""):
    global PASS
    if not cond:
        raise AssertionError(f"{name}: {detail}")
    PASS += 1
    print(f"  ✓ {name}")


REF_C = "N60 <|0.00|> n60 <|0.40|>"
REF_G = "N67 <|0.00|> n67 <|0.65|>"


print("[1] sparse InterMo references -> aligned onset/frame/offset grid")
lengths = torch.tensor([10, 8])
audio_lengths = torch.tensor([16000, 16000])
targets = build_acoustic_targets(
    [REF_C, REF_G], lengths, max_frames=10, audio_lengths=audio_lengths)
check("target_shape", targets.events.shape == (2, 10, 3, 88),
      targets.events.shape)
check("valid_lengths",
      int(targets.valid[0].sum()) == 10 and int(targets.valid[1].sum()) == 8)
check("notes_parsed", targets.note_counts == (1, 1), targets.note_counts)
check("pitch_tracks",
      targets.events[0, :, :, 60 - 21].sum() > 0
      and targets.events[1, :, :, 67 - 21].sum() > 0)


print("[2] perfect event logits have low loss, unit frame F1, and gradients")
perfect = (targets.events * 16.0 - 8.0).requires_grad_()
losses = acoustic_auxiliary_loss(
    perfect, targets, alignment_weight=0.25, alignment_margin=0.1)
check("perfect_event_loss", float(losses["event_loss"].detach()) < 0.01,
      float(losses["event_loss"].detach()))
check("perfect_frame_f1", abs(losses["frame_f1"] - 1.0) < 1e-7,
      losses["frame_f1"])
check("alignment_satisfied",
      float(losses["alignment_loss"].detach()) < 1e-6,
      float(losses["alignment_loss"].detach()))
losses["loss"].backward()
check("aux_gradient", perfect.grad is not None
      and bool(torch.isfinite(perfect.grad).all()))


print("[3] training-only head is small and preserves B,T geometry")
head = AcousticAMTHead(8)
h = torch.randn(2, 10, 8, requires_grad=True)
logits = head(h)
check("head_shape", logits.shape == targets.events.shape, logits.shape)
check("head_small", sum(p.numel() for p in head.parameters()) < 5000)


print("[4] collate carries sparse references without tensorizing strings")
base_item = {
    "audio": [0.0] * 160,
    "input_ids": [1, 2],
    "labels": [2, 3],
    "token_types": [0, 0],
    "loss_mask": [True, True],
    "ts_bins": [0, 0],
    "dialect": "AMT",
}
batch_refs = collate_batch([
    {**base_item, "acoustic_ref": REF_C},
    {**base_item, "acoustic_ref": None},
])
check("refs_preserved",
      batch_refs["acoustic_refs"] == [REF_C, None],
      batch_refs.get("acoustic_refs"))


print("[5] legacy checkpoint resumes with exact old Adam state + new head")


class TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = torch.nn.Linear(4, 4)
        self.encoder_decoder_proj = torch.nn.Linear(4, 8)
        self.decoder = torch.nn.Linear(8, 3)


cfg = {
    "lr_encoder": 1e-4, "lr_decoder": 3e-4,
    "warmup_steps": 2, "max_steps": 20,
}
old_model = TinyModel()
old_opt, old_sched = build_optimizer(old_model, cfg)
old_model.decoder(old_model.encoder_decoder_proj(
    old_model.encoder(torch.randn(2, 4)))).sum().backward()
old_opt.step()
old_sched.step()
old_opt.zero_grad(set_to_none=True)
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "legacy.pt"
    save_snapshot(path, old_model, old_opt, old_sched, 7, 1, batch_cursor=3)
    new_model = TinyModel()
    report = attach_amt_aux_head(new_model)
    new_opt, new_sched = build_optimizer(new_model, cfg)
    got = load_snapshot(
        path, new_model, new_opt, new_sched,
        allow_new_model_prefixes=("rubato_amt_aux_head.",),
        allow_optimizer_param_append=True)
    check("resume_cursor", got == (7, 1, 3), got)
    check("head_attached", report["n_params"] > 0)
    check("old_weights_exact",
          torch.equal(old_model.encoder.weight, new_model.encoder.weight))
    old_state_n = len(old_opt.state)
    check("old_adam_state_preserved",
          len(new_opt.state) == old_state_n,
          (len(new_opt.state), old_state_n))


print("[6] full training step uses one Canary forward and backpropagates head")
V = 64
NBINS = 8


class MockPreprocessor(torch.nn.Module):
    def forward(self, input_signal, length):
        return input_signal.unsqueeze(1), torch.full_like(length, 10)

    def __call__(self, *, input_signal, length):
        return self.forward(input_signal, length)


class MockCanary(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.preprocessor = MockPreprocessor()
        self.encoder = torch.nn.Linear(1, 8)
        self.encoder_decoder_proj = torch.nn.Linear(8, 8)
        self.emb = torch.nn.Embedding(V, 8)
        self.decoder = torch.nn.Linear(8, V)
        self.forward_calls = 0

    def forward(self, processed_signal, processed_signal_length,
                transcript, transcript_length):
        self.forward_calls += 1
        # Ten audio-dependent encoder frames from the waveform.
        x = processed_signal[:, :, :10].transpose(1, 2)
        enc = self.encoder_decoder_proj(self.encoder(x))
        lp = torch.log_softmax(self.decoder(self.emb(transcript)), dim=-1)
        mask = torch.ones(enc.shape[:2], device=enc.device)
        return lp, torch.full_like(processed_signal_length, 10), enc, mask


class Tok:
    def piece_to_id(self, piece):
        if piece.startswith("<|t") and piece.endswith("|>"):
            return 40 + int(piece[3:-2])
        return 0

    def unk_id(self):
        return -1


model = MockCanary()
attach_amt_aux_head(model)
B, L = 2, 6
full = torch.randint(0, 35, (B, L + 1))
full[:, 3] = 42
batch = {
    "audio": torch.randn(B, 16000),
    "audio_lens": torch.tensor([16000, 16000]),
    "input_ids": full[:, :-1],
    "input_lens": torch.tensor([L, L]),
    "labels": full[:, 1:],
    "token_types": (full[:, 1:] >= 40).long(),
    "loss_mask": torch.ones(B, L, dtype=torch.bool),
    "ts_bins": (full[:, 1:] - 40).clamp(min=0),
    "acoustic_refs": [REF_C, REF_G],
}
parts = training_step_logic(
    model, batch, Tok(), ts_token_ids=torch.arange(40, 40 + NBINS),
    loss_cfg={"acoustic_aux": {
        "weight": 0.2, "alignment_weight": 0.25,
        "alignment_margin": 0.1}})
check("one_forward", model.forward_calls == 1, model.forward_calls)
check("aux_count", parts["n_acoustic"] == 2, parts["n_acoustic"])
check("aux_finite", torch.isfinite(parts["acoustic_aux_loss"]))
parts["loss"].backward()
head_grad = sum(
    p.grad.abs().sum().item()
    for p in model.rubato_amt_aux_head.parameters()
    if p.grad is not None)
check("head_grad", head_grad > 0, head_grad)
encoder_grad = sum(
    p.grad.abs().sum().item()
    for p in model.encoder.parameters()
    if p.grad is not None)
check("encoder_grad", encoder_grad > 0, encoder_grad)

print(f"\n全部通过: {PASS} 项")
