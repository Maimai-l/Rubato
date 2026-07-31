# S5 VN Memory Leak — memtrace confirmed

## Root cause: main process VN leak, NOT workers

memtrace sampled every 5s during `--limit 20` run:

| elapsed | sys_used% | main_VN_RSS_GB | workers_RSS_sum_GB |
|---------|----------|----------------|-------------------|
| 2s | 16% | 0.05 | 0.00 |
| 9s | 22% | 1.82 | 0.20 |
| 16s | 25% | 2.82 | 0.19 |
| 23s | 28% | 3.82 | 0.19 |

- **Main VN process RSS grows ~1GB per 7 seconds**
- Worker RSS is flat at ~0.19GB (worker recycling is working)
- System memory goes from 16% → 28% in 23 seconds, projected OOM in ~2 minutes

## Verdict
Leak is in the main VN process — likely virtuoso InferenceModel accumulating
CUDA cache, intermediate tensors, or output buffers per infer_xml call.
GC_EVERY empty_cache + gc is not sufficient. VN_RECYCLE=100 may be too infrequent
(recycling only every 100 pieces — but process dies from OOM long before).

## Suggested fixes
1. Set S5_VN_RECYCLE=1 to rebuild VN engine every piece (test if this stops leak)
2. Deep-free CUDA memory after each inference: torch.cuda.empty_cache() + gc.collect()
3. If still leaks, run VN inference in a subprocess that gets killed after each piece
