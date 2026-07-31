# Encoder AMT Auxiliary / Cross-Architecture Distillation Experiment

Status: implementation validated on CPU; production A/B pending.

## Question

Can an explicit time×pitch objective make the Canary encoder learn piano
content sooner, instead of letting the teacher-forced InterMo decoder minimize
loss mainly from textual/music-language priors?

This is a two-stage experiment:

1. **Oracle auxiliary supervision (this A/B):** use exact timestamped AMT
   references where available, otherwise time-aligned TAST.  This establishes
   whether an encoder event objective helps at all without contaminating the
   result with teacher errors.
2. **TransKun distillation (only if stage 1 helps):** use offline TransKun
   events for unlabeled real piano recordings.  TransKun is never loaded in the
   Rubato training process.

Do not describe stage 1 as a TransKun result.  It is the clean upper-bound
test of the proposed distillation interface.

## Intervention

- Add a training-only linear head to Canary's existing post-projection encoder
  states: `1024 -> 3 × 88` (onset, occupancy, offset for MIDI 21–108).
- Reuse the encoder states returned by the normal Canary forward; there is no
  second teacher/student forward.
- Use class-balanced BCE so the all-off piano grid is not an easy optimum.
- Add a within-batch mismatched-reference margin.  Each audio must fit its own
  event grid better than another sample's grid.  This prevents a corpus-level
  piano prior from satisfying the auxiliary objective.
- Scale by the fraction of supervised examples before the existing
  per-sequence gradient accumulation.
- Default production behavior is exactly unchanged (`weight=0`).

The existing `--pitch-loss-weight 2.5` is not this intervention.  It only
reweights decoder pitch-token CE and can still be optimized from target-text
context.

## A/B discipline

- Fork both arms from the same atomic `last.pt`, including optimizer,
  scheduler, RNG, epoch, and batch cursor.
- A is the already-running production process.
- B uses an isolated checkpoint directory and:

  ```
  --amt-aux-weight 0.10
  --amt-align-weight 0.25
  --amt-align-margin 0.10
  ```

- First gate: 200 optimizer steps.  This is an engineering/convergence-direction
  gate, not a paper-quality result.
- Full decode is disabled during the short gate; cheap true/silence probes run
  at the end.
- The main checkpoint directory and `reports/eval_autolog.md` must not be
  touched by arm B.

## Readouts

Primary:

1. `af1` (encoder occupancy frame F1) must rise from its random-head baseline.
2. `aux` must fall and remain finite; `n_acoustic` must be non-zero.
3. MAESTRO true-audio vs silence `Δpitch` should improve relative to arm A.

Safety:

1. No NaN/OOM and no checkpoint/optimizer state loss.
2. `tc` overhead should be small enough that a convergence gain is plausible
   in wall-clock time.
3. A2S/A2S_lite/TAST semantic losses must not show an immediate regression
   outside normal 50-step noise.
4. Main AMT token `pv` and final note F1 remain authoritative; `af1` is only an
   auxiliary-head diagnostic.

## Decision

- **Continue to a longer run:** auxiliary loss decreases, `af1` rises, and
  either MAESTRO `Δpitch` or AMT `pv` improves without a clear non-AMT
  regression.
- **Tune weight once:** head learns (`af1` rises) but main decoder remains
  audio-insensitive.  The next intervention is a decoder/cross-attention
  dependence loss, not a larger teacher.
- **Reject:** no head learning, unacceptable throughput/memory cost, or clear
  damage to other dialects.

Only after stage 1 succeeds should TransKun pseudo-labeling be added for
otherwise unlabeled real recordings.
