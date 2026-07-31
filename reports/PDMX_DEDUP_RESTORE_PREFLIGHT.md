# PDMX deduplication restoration — rendering preflight

This is a no-render, no-write capacity check for restoring only audit-confirmed nonduplicates from `work/pdmx_dedup_restore_candidates.jsonl`.

## Filter dry-run

The existing S3 filters were preserved: no-license-conflict, non-draft, 1/2-track piano, MIDI-exists, the non-piano blacklist, and nASAP/ASAP leakage safeguards. No manifest was written and the active round-2 pool was untouched.

| Item | Original upstream-dedup filter | Audit-confirmed restoration | Change |
| --- | ---: | ---: | ---: |
| PDMX pieces after all current filters | 38,371 | 180,717 | +142,346 |
| Train pieces | 34,898 | 163,230 | +128,332 |
| Validation pieces | 1,491 | 8,581 | +7,090 |
| Test pieces | 1,982 | 8,906 | +6,924 |

## Disk estimate

The added-piece estimate uses realised first-timbre S5 label segment counts, grouped by score bar count, and the observed file sizes of both existing Opus output directories.

- Expected additional segments: **183,773**.
- Observed completed Opus file size: **507,534–518,239 bytes/segment**.
- Expected additional final audio: **93.27–95.24 GB**.
- D: free space at measurement: **91.38 GB**.

The current free space cannot contain the final audio, even before temporary whole-piece WAVs, staging labels, retries, and a safety margin. Do not start rendering under **120 GB** free; **125 GB+** is the appropriate target for the established two-worker pipeline. Use a separate round-3 audio directory and staging labels; do not alter the active round-2 pool until QC and final assembly dry-run pass.
