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

## Rollout result

PID 33424 was started from the step-29600 complete snapshot before this patch
was imported, solely to restore useful throughput while the fix was implemented.
It recovered to `tc avg=8.4s`, reached step 29800, and atomically replaced
`last.pt` at 21:08:37.

The patched process (PID 30344) then resumed the exact step-29800 snapshot with
the same training arguments. Both wiring gates appeared:

1. `CUDA allocator 预配置: PYTORCH_ALLOC_CONF=expandable_segments:True`
2. config echo `allocator=expandable_segments:True mem_check=200step/1024MiB`

Its initial in-process baseline was:

```text
CUDA_MEM reason=train_start action=observe alloc=2245MiB reserved=2246MiB
cached=1MiB inactive_split=1MiB driver_free=12763MiB
driver_untracked=1294MiB peak_reserved=2246MiB released=0MiB
retries=0 ooms=0 backend=native
```

The first completed 50-step window was step 29850 at `tc=7.3s/avg7.6s` and
`td=1.2s/avg1.2s`. This verifies the restart, exact resume, allocator wiring,
telemetry and immediate throughput. Long-horizon causal confirmation still
comes from subsequent `CUDA_MEM` lines: the patch must not be described as
proving fragmentation unless those counters support it.
