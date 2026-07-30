# Training CUDA memory / speed fix (2026-07-30)

## Incident

The current run was fast through step 28300 (`tc=8.8s`) and changed abruptly at
step 28350 (`tc=19.5s`). Data wait remained about one second and there was no
eval, epoch boundary, checkpoint event, thermal throttle, or competing CUDA
compute process at the transition. Driver-committed GPU memory kept growing
afterward; restarting from the complete step-29600 snapshot reset that state.

This establishes GPU memory pressure/migration as the immediate slowdown
mechanism. It does **not** by itself prove that every byte reported by Windows
belongs to PyTorch: WDDM counters can include driver/third-party/other-process
memory. The old process had no in-process allocator telemetry, so the exact
split between live tensors, reusable cache and fragmentation was previously
unobservable.

## Code fix

- Configure `PYTORCH_ALLOC_CONF=expandable_segments:True` before importing
  PyTorch. This targets the job's variable-duration/variable-shape batch
  allocation pattern.
- Drop completed `parts` and `batch` references immediately after backward /
  metric extraction, including gradient-accumulation micro-batches.
- Every 200 optimizer steps, log a grep-friendly `CUDA_MEM` line containing
  allocated, reserved, cached, inactive-split, driver-free, driver-untracked,
  peak-reserved, allocation-retry and OOM counters.
- At a safe boundary, run Python GC only after eval or when driver-free memory is
  below 1 GiB. Call `empty_cache()` only if at least 512 MiB is actually
  reclaimable. Healthy training does neither, avoiding periodic GC/cache churn.
- After eval, apply the same reclaimability gate to its temporary allocation
  shapes. `empty_cache()` is not treated as a cure for live-tensor retention.
- Make `zero_grad(set_to_none=True)` explicit.

## Verification

- `py_compile`: passed.
- `tests_cuda_memory.py`: 16/16 passed (CPU no-op, healthy no-GC path,
  low-headroom thresholds, forced eval thresholds, telemetry).
- `tests_train_config.py`: 19/19 passed (including early allocator wiring and
  old/new environment-alias conflict handling).
- `tests_train.py`: 23/23 passed.
- `tests_resume.py`: 21/21 passed.
- PyTorch 2.11 accepted the configured allocator string in a GPU-hidden parser
  check.

## Rollout

PID 33424 was started from the step-29600 complete snapshot before this patch
was imported, solely to restore useful training throughput while the fix was
implemented. Let it reach the next complete 200-step snapshot, then perform one
short restart with the same command. The replacement process must show both:

1. `CUDA allocator 预配置: ... expandable_segments:True`
2. training config echo with `allocator=...` followed by `CUDA_MEM` telemetry

Only the replacement process validates the long-running fix.
