# S5 VN Render Issues

## 1. GBK UnicodeEncodeError (BLOCKER)

**Location**: `scripts/s5_vn_render.py:450`
**Error**: `UnicodeEncodeError: 'gbk' codec can't encode character '−'`

Root cause: f-string uses Unicode minus sign (−) in memory budget print. Windows GBK codec cannot encode this character. wandb's console_capture intercepts stdout, attempts GBK encoding, crashes.

**Fix needed**: Replace `−` with ASCII hyphen `-` in the f-string, or wrap stdout with utf-8 TextIOWrapper.

## 2. OOM on full run

**Symptom**: Memory climbs from 60% to 96% then system kills process.
**Occurrences**: 5+ times during attempts to run full VN pipeline.

**Current mitigation in code**: `mem_budget_map`, RSS recycling (TASKS_PER_CHILD), worker recycling — but never reached execution due to issue #1.

**Note**: --limit 20 never successfully completed. Can't verify vn_ok>0 or TAST>0.

## 3. wandb dependency

wandb.sdk.lib.console_capture intercepts stdout. Setting WANDB_MODE=disabled via env var may not propagate correctly through Git Bash on Windows.

## Current State

- S4 flat render: DONE (48,451/48,451 opus)
- S5 VN render: 0 successful runs
- .done markers: 7,514 (from old CLI runs)
- Remaining: ~40,937 pieces need VN
