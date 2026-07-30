"""CUDA memory policy tests with a fake allocator. Run: python tests_cuda_memory.py"""
from __future__ import annotations

from rubato.model.train import (
    cuda_memory_snapshot, format_cuda_memory_event, maintain_cuda_memory)


PASS = 0


def check(name, cond, detail=""):
    global PASS
    if not cond:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)
    PASS += 1
    print(f"  ok  {name}")


MiB = 1024 ** 2


class FakeCuda:
    def __init__(self, *, alloc=4000, reserved=5000, free=6000,
                 inactive=0, available=True):
        self.alloc = alloc * MiB
        self.reserved = reserved * MiB
        self.free = free * MiB
        self.total = 16_000 * MiB
        self.inactive = inactive * MiB
        self.available = available
        self.empty_calls = 0
        self.reset_calls = 0

    def is_available(self):
        return self.available

    def memory_stats(self):
        return {
            "inactive_split_bytes.all.current": self.inactive,
            "num_alloc_retries": 2,
            "num_ooms": 0,
        }

    def mem_get_info(self):
        return self.free, self.total

    def get_allocator_backend(self):
        return "native"

    def memory_allocated(self):
        return self.alloc

    def memory_reserved(self):
        return self.reserved

    def max_memory_allocated(self):
        return self.alloc + 100 * MiB

    def max_memory_reserved(self):
        return self.reserved + 200 * MiB

    def empty_cache(self):
        self.empty_calls += 1
        released = self.reserved - self.alloc
        self.reserved = self.alloc
        self.free += released

    def reset_peak_memory_stats(self):
        self.reset_calls += 1


class FakeTorch:
    def __init__(self, cuda):
        self.cuda = cuda


print("[1] CPU/no-CUDA path is a no-op")
cpu = FakeTorch(FakeCuda(available=False))
check("cpu_snapshot_none", cuda_memory_snapshot(cpu) is None)
check("cpu_maintenance_none",
      maintain_cuda_memory("cpu", torch_module=cpu,
                           collect_cycles=lambda: None) is None)

print("[2] healthy headroom records telemetry without cache churn")
healthy_cuda = FakeCuda(alloc=4000, reserved=5000, free=6000, inactive=123)
healthy_gc_calls = []
healthy = maintain_cuda_memory(
    "healthy", torch_module=FakeTorch(healthy_cuda),
    collect_cycles=lambda: healthy_gc_calls.append(1))
check("healthy_observe", healthy["action"] == "observe", healthy)
check("healthy_no_empty_cache", healthy_cuda.empty_calls == 0)
check("healthy_skips_full_gc", not healthy_gc_calls, healthy_gc_calls)
check("inactive_split_visible",
      healthy["after"]["inactive_split"] == 123 * MiB)

print("[3] low headroom plus reclaimable cache triggers release")
low_cuda = FakeCuda(alloc=4000, reserved=5500, free=1000)
low = maintain_cuda_memory(
    "low", torch_module=FakeTorch(low_cuda), min_free_mb=1024,
    min_reclaimable_mb=512, collect_cycles=lambda: None)
check("low_releases", low["action"] == "empty_cache", low)
check("low_empty_once", low_cuda.empty_calls == 1)
check("low_reserved_reclaimed", low["after"]["reserved"] == 4000 * MiB)
line = format_cuda_memory_event(low)
check("line_grep_friendly",
      "CUDA_MEM reason=low action=empty_cache" in line
      and "inactive_split=" in line and "driver_untracked=" in line
      and "retries=2" in line, line)

print("[4] low headroom with live allocations only does not churn")
live_cuda = FakeCuda(alloc=5000, reserved=5100, free=1000)
live = maintain_cuda_memory(
    "live", torch_module=FakeTorch(live_cuda), min_free_mb=1024,
    min_reclaimable_mb=512, collect_cycles=lambda: None)
check("live_observe", live["action"] == "observe", live)
check("live_no_empty", live_cuda.empty_calls == 0)

print("[5] post-eval force releases temporary cache")
eval_cuda = FakeCuda(alloc=4000, reserved=4700, free=6000)
event = maintain_cuda_memory(
    "eval", force=True, torch_module=FakeTorch(eval_cuda),
    collect_cycles=lambda: None)
check("eval_forced", event["action"] == "empty_cache", event)
check("eval_empty_once", eval_cuda.empty_calls == 1)

print("[6] post-eval with no meaningful cache skips global release")
lean_cuda = FakeCuda(alloc=4000, reserved=4100, free=6000)
lean = maintain_cuda_memory(
    "eval_lean", force=True, torch_module=FakeTorch(lean_cuda),
    collect_cycles=lambda: None)
check("lean_observe", lean["action"] == "observe", lean)
check("lean_no_empty", lean_cuda.empty_calls == 0)

print(f"\n全部通过: {PASS} 项")
