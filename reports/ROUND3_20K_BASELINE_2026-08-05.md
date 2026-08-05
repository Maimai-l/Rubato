# Round-3 20k pre-registered comparison baseline

Frozen before round-3 startup and before any round-3 metric is observed.

Source: `reports/eval_autolog.md`, `eval @ step 20000
(2026-07-29 07:22:25)`.  This is the round-2 run used by D93 and is after the
2026-07-28 validator-generation change noted in D85.

## Criterion A: DYCK rejection count

Round-2 at step 20,000 rejected `DYCK=43 / n=48`.  D93 requires round-3 to be
at most half of this value.  Because the count is integral, the machine-readable
pass condition is:

`round3_dyck <= floor(43 / 2) = 21`.

## Criterion B: raw NED

`raw_ned` had not yet been wired into this round-2 checkpoint's autolog.  D93
therefore defines an absolute, not relative, pass line:

`round3_raw_ned <= 0.85` with all 48 examples scored.

## Criterion C: probe semantic score

The four fixed round-2 probes reported true semantic scores:

- nASAP/TAST: 0.53
- MAESTRO/AMT: 0.73
- PDMX/TAST probe 1: 0.53
- PDMX/TAST probe 2: 0.58

Their pre-registered macro baseline is `(0.53 + 0.73 + 0.53 + 0.58) / 4 =
0.5925`.  Interpreting "degradation no more than 5%" multiplicatively, the pass
condition is:

`round3_probe_true_sem_macro >= 0.5925 * 0.95 = 0.562875`.

The same four probe identities and the same macro must be used; substituting a
training-loss `sem=` field or selecting the best probe would change the metric.

## Decision table

- 2 or 3 criteria pass: continue round-3.
- 0 criteria pass: stop and report, as ordered by D93.
- Exactly 1 criterion passes: D93 does not specify this branch; pause and report
  without automatically continuing or declaring failure.

This report freezes interpretation before round-3 data and does not claim that
the comparison controls every code change.  The isolated round-3 checkpoint and
autolog directory must preserve the run boundary.
