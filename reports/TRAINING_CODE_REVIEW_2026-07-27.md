# Training code review — 2026-07-27

Scope: the production path from manifests/labels through assembly, dataset
sampling, model construction, loss/backward, checkpoint/resume, inference and
formal evaluation.  Rendering entrypoints that create training audio were also
reviewed because their output is trusted by assembly.

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

9. **`configs/train.yaml` was mostly documentation, not runtime configuration.**
   The production CLI now loads it, applies it only where the CLI did not
   explicitly override a value, and rejects unknown/unsupported keys.  Optimizer,
   scheduler, precision, batch/eval cadence, LR, accumulation, epoch/step limits
   and checkpoint controls are all wired.  Unsupported `specaugment: true`
   fails explicitly instead of pretending to work.

10. **Fresh training could use the hot-start encoder LR by accident.** Fresh
    runs now use the decoder/base LR unless an explicit
    `lr_encoder_from_scratch` is configured.

11. **Target-length filtering duplicated target construction and was off by one.**
    It now calls the same `build_target_sequence()` used by production encoding
    and measures the actual decoder input (`seq[:-1]`).  Exact-boundary samples
    are no longer over-filtered.  A missing `DIALECT_PROMPT` import that the full
    suite exposed was also fixed.

12. **Evaluation split identity was fabricated from counts/names.** nASAP now
    uses the actual 12-work `nasap_split.json`; ASAP-Beyer is the real public
    14-work/25-recording split.  Blacklists affect training only and no longer
    delete validation/test examples.

13. **A local 34-performance calibration set was labelled paper-comparable.**
    Paper comparison now requires an explicit benchmark identity plus the exact
    expected 102 ASAP rows.  Local runs still produce useful metrics but cannot
    emit a paper-gap verdict.  MAESTRO/TAST window-macro metrics are likewise
    labelled non-paper-certified.

14. **The old MinHash script could skip parse failures and overwrite one legacy
    manifest while restored manifests remained unchecked.** The new strict
    certificate scans every active PDMX train manifest, fails closed on any
    reference/target parse failure, and binds the result to each file's SHA-256
    and row count.  Formal training refuses a missing/stale/failing certificate.
    The old filename is now a compatibility redirect and no longer mutates data.

15. **R-S4.4 render QC existed but was not called.** Newly rendered S4 and C3
    second-timbre files now must pass both ffmpeg non-silence detection and
    MIDI/audio duration agreement (<1.5 s).  S4 receives exactly one re-render
    after QC failure; C3 retains its bounded retry loop.  Repeated failures are
    deleted so resume cannot accept a bad non-empty file.  S5 already checked
    truncation and now also rejects below-gate decoded audio before labels are
    written.

16. **The S5 wiring test skipped all assertions on Windows.** It now uses a
    same-process scheduler harness for the production callbacks and executes 15
    real wiring assertions on Windows: VN, MIDI/CSV, render, slice, labels,
    cleanup, resume and single model load.  Process scheduling/recycling remains
    covered independently by `tests_ops.py`.

17. **Several “implemented” features were only dead APIs.** The unsafe dry-audio
    `online_room_augment` prototype (current pool is already wet), the duplicate
    tokenizer regularization wrapper, the retired overlap-window merger and four
    unused convenience wrappers were removed.  Production subword
    regularization remains active inside `encode_target`; safe wet-audio
    gain/EQ/noise augmentation remains wired behind `--augment-acoustic`.

18. **Default config/vocab/render paths depended on the caller's CWD.** Defaults
    are now anchored to the repository, matching the user's normal invocation
    from `C:\Users\Administrator`.

19. **Loss helpers implied multiple training losses although only one path was
    used.** Dead `timestamp_loss`, `semantic_loss`, `sequence_loss` and
    `combined_loss` APIs were removed.  Tests now exercise the actual
    `batch_sequence_loss` backward path, including exact `1/sqrt(T)` weighting.

20. **Formal OMR-NED and training proxies were conflated.** Training logs expose
    only their proxy/coverage status; final scoring uses official LEGATO only.
    Fallback/partial/failed inference states cannot count as parseable successes.
    The LEGATO 0–1 CSV is correctly converted to 0–100; no scale patch was
    needed.

## Verification

- Syntax compilation of all `rubato/` and `scripts/`: passed.
- All 71 `tests_*.py` scripts: full-suite pass on Windows.
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
- `tests_s5_pipeline.py`: 15 passed on Windows (previously skipped).
- `tests_render_runtime_qc.py`: S4 retry/delete and C3 QC wiring passed.
- `tests_eval_final_integrity.py`, `tests_eval_integrity.py`,
  `tests_leakage_certificate.py`, `tests_train_config.py` and
  `tests_blacklist_integrity.py`: passed.

Production dry-run, launched from outside the repository, passed with:

- total 753,128 utterances; train 704,360;
- nASAP validation/test 539/603;
- ASAP-Beyer 14 works / 25 real recordings;
- validation/test/quarantine kept separate;
- missing current MinHash certificate reported as a warning in dry-run and a
  hard block for formal training.

## Remaining operational gate

Do not run the full leakage scan while the current training job is competing
for CPU/IO.  When it is idle, run:

```powershell
& 'D:\ProgramData\envs\nemo_test\python.exe' `
  'D:\vscode_projects\ee_download\Rubato\scripts\certify_pdmx_leakage.py'
```

Only a `status=pass`, zero-leak, zero-parse-failure certificate permits the next
formal training start.  This is deliberately not auto-waived.

The Python process that was already running when these files changed retains the
old imported code. The fixes take effect only on the next process start.
