# Training code review — 2026-07-27

Scope: `rubato/model/train.py`, `rubato/data/dataset.py`, and the training assembly
path in `scripts/build_dataset.py`.

## Confirmed defects and fixes

1. **Gradient accumulation used audio-duration weighting.** Each micro-batch loss
   was already a sequence mean, but it was multiplied by its audio seconds. This
   made long sequences heavier and made the result depend on micro-batch
   partitioning. It now accumulates `micro_mean × sequence_count` and divides all
   gradients by the effective step's total sequence count before clipping.

2. **Training logs described only the final micro-batch.** `loss`, `sem`, `ts`,
   dialect metrics, and `audio` came from the last micro-batch although an
   optimizer step accumulated about 2000 audio seconds. Timing was also credited
   on the next generator advance. Logs now aggregate the complete optimizer step
   and print total `audio`, `micro`, `seq`, and current/50-step-average `td`/`tc`.

3. **A single sample could exceed `max_batch_sec`.** The greedy bucketer admitted
   an oversized sample when the current bucket was empty. The data module now
   quarantines such pairs with count/max/examples, and the bucketer raises if a
   caller bypasses that quarantine.

4. **Resume restarted the saved epoch from its first batch.** Snapshots now store
   the next epoch-local batch cursor; data generation and process prefetch resume
   from it without rereading skipped audio. Prefetch failure also continues from
   the first unconsumed batch instead of replaying the epoch.

5. **A corrupt snapshot silently restarted at step 0.** Missing snapshots still
   mean a fresh run; existing but unreadable/incompatible snapshots now abort.
   Legacy snapshots without a cursor require the explicit
   `--allow-legacy-resume-from-epoch-start` acknowledgement.

6. **Conditional OMR scores could select `best.pt` or drive convergence using a
   few easy parseable samples.** OMR control now requires an untruncated eval,
   at least 12 scored samples, and at least 80% score coverage.

7. **Automatic rollback mixed old model weights with current Adam/scheduler
   state.** Because the eval ring is model-only, unsafe live rollback is now
   refused with an explicit stop reason instead of continuing with inconsistent
   optimizer state.

8. **PDMX leakage-filter construction could fail open.** Missing/empty manifests
   and blacklist-construction exceptions now stop assembly instead of training
   with all PDMX rows implicitly in `train`.

## Verification

- Syntax compilation: passed.
- `tests_train.py`: 21 passed.
- `tests_resume.py`: 16 passed.
- `tests_prefetch.py`: all passed, including injected child crash/death.
- `tests_train_step.py`: 17 passed.
- `tests_dataset.py`: 33 passed.
- `tests_len_filter.py`: 15 passed.
- `tests_early_stop.py`: 9 passed.
- `tests_evaluate.py`: 22 passed.
- `tests_losses.py`: 24 passed.
- `tests_metrics_v2.py`: all passed, including OMR coverage gates.
- `tests_cli_help.py`: 11 passed.

The Python process that was already running when these files changed retains the
old imported code. The fixes take effect only on the next process start.
