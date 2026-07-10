# S5 VN Memory Leak — Comprehensive Report

## TL;DR
- VN InferenceModel loads on GPU ✅ (0.4s infer, device=cuda confirmed)
- Workers flat at 0.19GB ✅ (recycling works)
- **Main process RSS climbs 1GB/5s → OOM in 2min** — root cause unknown

## Evidence

### 1. memtrace (every 3s during --limit 5)
```
elapsed  sys_used%  main_VN_RSS_GB  n_workers  workers_RSS_sum  virtuso_GB
    2s       23%            1.42          0            0.00        0.02
    7s       26%            2.18          1            0.19        0.02
   12s       28%            2.98          1            0.19        0.02
   17s       30%            3.74          1            0.19        0.02
   22s       33%            4.59          1            0.19        0.02
   98s       67%           16.48          1            0.19        0.02
  103s       69%           16.93          1            0.19        0.02
  108s       69%           17.22          1            0.19        0.02
  113s       73%           18.30          1            0.19        0.02
  119s       76%           19.38          1            0.19        0.02
  124s       79%           20.46          1            0.19        0.02
```

- **Main process grows ~1GB per 5 seconds, relentless, even when idle**
- Workers absolute flat (0.19GB) — recycling working
- Crashed ~130s with sys_used hitting 79%+

### 2. GPU status (nvidia-smi)
- `Device=cuda` confirmed by VNEngine diagnostic
- `[infer] Qmbb4MXzbgmP9cQzUaXFK9Mp5pMK4UCwrM9YKuS2pF3mt6.mxl 0.4s GPU=0.1GB` — inference on GPU, fast
- nvidia-smi: 0% GPU utilization, VN process PID NOT in GPU process list during main RSS climb phase
- GPU memory: 1454MB static (framebuffer only, no CUDA growth)

### 3. What was ruled out
- **NOT workers**: RSS flat at 0.19GB, n_workers=1
- **NOT virtuso.exe**: 0.02GB, CLI not spawned
- **NOT VNEngine.infer()**: only called once, 0.4s, 0.1GB GPU
- **NOT `rep["failures"]`**: only stores strings, no tracebacks
- **NOT soundfonts**: worker process, not main
- **NOT Python API reference leak**: `gpu_stage` returns dict of strings, no tensor references held

### 4. Where the main process spends time after first inference
- `pipeline_map` main loop (rubato/ops.py:204)
- `_reap()` waiting for CPU worker → on_result writes labels
- Items list: 53k dicts × ~500 bytes ≈ 26MB — not the cause
- `fut_item` dict cleaned on every reap (line 256: `del fut_item[f]`)
- No obvious accumulation point found

### 5. Hypothesis (unconfirmed)
- CUDA allocator holding pinned memory visible as RSS (WDDM)
- glibc malloc arena fragmentation (GUIDE §4.5), Windows equivalent
- Python heap fragmentation from partitura objects in gpu_stage path

### 6. CLI mode comparison
- CLI mode (vn_infer via subprocess): main process FLAT at 0.54GB
- But workers climb (sfizz soundfont accumulation)
- CLI survives longer but still eventually OOMs from workers

## Environment
- Windows 11, 34.1GB RAM, RTX 5070 Ti 16GB
- Python py312 (virtuoso), nemo_test (sfizz)
- CUDA available: True
- Soundfont sizes: Salamander 1.5, Splendid 0.2, ExperienceNY 6.9, Kamoepiano 0.2, ABChase5 0.4, Softify 1.2 (GB)

## Logs
- `work/vn_diag.log` — VN diagnostic output
- `work/mem_diag.log` — memtrace CSV data
- `work/mem_cli.log` — CLI mode memtrace for comparison
- `reports/memtrace.csv` — full sampling data
