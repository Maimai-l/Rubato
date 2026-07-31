# VN native-batch decision (2026-07-24)

- The restored PDMX VN run reported `vn_ok=705`, `vn_fail=114502`; this is **not** evidence that 114,502 scores are unusable.
- A tail item recorded as `vn_no_tmap` succeeds through the official `virtuoso` CLI with `Bach`, producing both MIDI and CSV; its CSV also builds a valid Rubato time map.
- A 100-piece old-failure canary completed with `vn_ok=100`, `vn_fail=0`, and 113 TAST segments.
- `VIRTUOSO_GUIDE.md` documents a supported native directory-batch mode: one model load, per-score MIDI/CSV output, per-score exception isolation. The CLI is non-recursive.
- Decision: do not use Rubato's custom long-lived `InferenceModel` subprocess as the main inference path. Use native `virtuoso <leaf-directory> -c Bach --pedal --csv -o <matching-output-directory>` batches, then let Rubato consume the generated MIDI/CSV for audio, time maps, and labels.
- The optional `ScoreData` scan was stopped at user request; it is not an execution gate. No main rendering or training is currently running.
