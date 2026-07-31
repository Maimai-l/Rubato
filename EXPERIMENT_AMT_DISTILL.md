# Encoder AMT Auxiliary / Cross-Architecture Distillation Experiment

Status: 100-step direction gate completed; encoder-head learning passed,
decoder-transfer gate did not.

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
  --stop-after-step 35500
  ```

  `max_steps` remains the production value (100000) in both arms.  Reusing
  `max_steps` as a short-run stop would also compress the cosine schedule and
  silently lower the resumed learning rates, invalidating the comparison.

- First gate: 100 optimizer steps (35400→35500).  The original 200-step plan
  was shortened after the production arm's first optimizer step after 35500
  remained in active GPU compute for more than 34 minutes versus a 7.6-second
  recent average.  Both arms therefore stop before that pathological batch.
  This is an engineering/convergence-direction
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

## 2026-07-31 result

Both arms resumed the same atomic step-35400 snapshot (`epoch=4`,
`batch_cursor=39613`) and used the production cosine horizon
`max_steps=100000`, learning rates, dialect mix, acoustic augmentation, and
pitch weighting.  Both stopped and atomically saved at step 35500.

| readout (last 50 steps) | A: control | B: AMT aux | B - A |
|---|---:|---:|---:|
| total loss | 46.8815 | 46.8828 | +0.0013 |
| semantic loss | 2.4540 | 2.4531 | -0.0009 |
| timestamp loss | 2.2123 | 2.2104 | -0.0019 |
| pitch CE (`pv`) | 2.809 | 2.806 | -0.003 |
| compute time / optimizer step | 8.0 s | 8.4 s | +5.0% |
| auxiliary BCE | — | 0.473 → 0.319 | -32.6% |
| mismatch margin | — | 0.028 → 0.016 | -42.9% |
| auxiliary frame F1 | — | 0.080 → 0.116 | +45.0% |

The auxiliary objective clearly learned without an immediate main-task
regression.  This passes the head-learning and overhead safety gates.

The fixed three-source true-audio-vs-silence teacher-forced probe did **not**
show decoder transfer:

| aligned-sample mean Δsemantic accuracy | A | B |
|---|---:|---:|
| all sources | +0.07 | +0.06 |
| nASAP | +0.10 | +0.09 |
| MAESTRO | +0.02 | +0.01 |
| PDMX | +0.15 | +0.14 |

These rounded differences are small but consistently non-positive.  At this
100-step horizon the intervention makes encoder states more event-decodable,
but does not yet make the InterMo decoder depend more on audio.  Therefore:

- do not claim that TransKun accelerates the current run;
- do not merge pseudo-label generation into production training yet;
- retain this implementation as the clean distillation interface;
- the next bounded experiment should test a longer horizon or a direct
  decoder/cross-attention audio-dependence objective, then repeat the identical
  fixed probe.

Artifacts (outside Git):

- `work/amt_aux_A_control_s35400_35500_v2.out.log`
- `work/amt_aux_B_w010_s35400_35500.out.log`
- `work/amt_aux_probe_A_s35500.out.log`
- `work/amt_aux_probe_B_s35500.out.log`
- `outputs/experiments/amt_aux_control_s35400/last.pt`
- `outputs/experiments/amt_aux_s35400_w010/last.pt`

## Operational findings fixed during the gate

1. `max_steps` was previously the only short-run stop knob, but it also sets
   the cosine scheduler horizon.  Setting it to 35500 silently changed resumed
   learning rates from `7.62e-5 / 2.28e-4` to `1e-5 / 3e-5`.  The new
   `--stop-after-step` terminates a process without changing the LR schedule.
2. A short run ending between regular 200-step save boundaries returned
   without saving its final state.  It now atomically saves before the
   `stop_after_step_reached` return.
3. The pre-existing long-lived process spent more than 34 minutes without a
   new log after step 35500, while CPU and GPU remained active.  An isolated
   exact resume from the control step-35500 snapshot disproved the initial
   "deterministic pathological batch" hypothesis: step 35501 completed
   normally with 45 micro-batches, 8.731 seconds summed compute time, and
   per-micro times of 0.133–0.919 seconds.  No utterance should be quarantined
   from this evidence.  The event was a transient process/runtime slowdown,
   not a reproducible data defect.  Optional tracing is now available with
   `RUBATO_TRACE_MICROBATCH=1`; it logs each micro-batch identity and tensor
   lengths before forward, then its elapsed time after backward.
