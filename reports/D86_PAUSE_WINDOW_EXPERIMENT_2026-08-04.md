# D86 pause-window experiment (step 63800)

Date: 2026-08-03/04 (Asia/Shanghai)

## Outcome

The proposed v5 intervention was **not promoted**. It activated as intended and
remained numerically stable, but failed both preregistered cost/loss gates. The
main run was therefore restored with the original baseline recipe from the
unchanged production checkpoint at step 63800.

## Locked starting point

- Production checkpoint: `D:\vscode_projects\ee_download\outputs\ckpt\last.pt`
- Metadata: `step=63800`, `epoch=7`, `batch_cursor=174414`
- A and B were copied from this same file into isolated checkpoint directories.
- Both copies were read back and verified as step 63800 before either arm ran.
- GPU stages were serialized: decode sweep -> A -> B -> production resume.

## 16-arm decode sweep

Configuration: beam 1, repetition penalty in `{1.0, 1.1, 1.3, 1.5}`,
EOT boost in `{0, 1, 2, 4}`, 24 identical evaluation items per arm, greedy
fallback disabled.

| rep | EOT 0 | EOT 1 | EOT 2 | EOT 4 |
|---:|---:|---:|---:|---:|
| 1.0 | 0/24 | 0/24 | 0/24 | 0/24 |
| 1.1 | 0/24 | 0/24 | 0/24 | 1/24 |
| 1.3 | 0/24 | 0/24 | 0/24 | 1/24 |
| 1.5 | 0/24 | 0/24 | 0/24 | 1/24 |

All three arm-level successes were the same item,
`nasap_LeeN01M_ad221e3a_005`, and each result was only partial (one of two
windows still failed validation). Thus EOT=4 can rescue a narrow termination
case, but decode-only tuning does not explain or fix the broad structural
failure. The dominant violations remained DYCK, missing terminal bar, and
missing/invalid time signatures.

## A/B 100-step safety experiment

Both arms resumed independently from step 63800 and stopped at step 63900.

- A: original recipe.
- B: A plus `input_dropout=0.10`, `input_dropout_ramp=5000`,
  `audio_dep_weight=0.10`, and `audio_dep_margin=0.10`.

| Arm / step | avg50 loss | tc running avg | input dropout | audio-dep |
|---|---:|---:|---:|---:|
| A / 63850 | 43.4588 | 7.8 s | off | off |
| A / 63900 | 43.3288 | 7.7 s | off | off |
| B / 63850 | 55.6437 | 27.7 s | 0.10 | +0.829 |
| B / 63900 | 52.3447 | 13.6 s | 0.10 | +0.862 |

Preregistered gates, evaluated from the final logged running averages:

| Gate | Limit | Result | Verdict |
|---|---:|---:|---|
| No NaN/OOM/bounds failure | required | none observed | PASS |
| B input dropout and audio-dep visible | required | `id=0.10`, `ad>0` | PASS |
| B tc <= A tc x 1.20 | <= 9.24 s | 13.6 s (+76.6%) | **FAIL** |
| B avg50 loss <= A x 1.10 | <= 47.6617 | 52.3447 (+20.8%) | **FAIL** |

B also drove peak reserved memory much higher than A, although cache release
prevented an OOM. The intervention is therefore functional but too expensive
and too disruptive in its current form. Its 100-step checkpoint must not be
used as the production continuation.

## Production decision and resume certificate

The production run was restarted without the four experimental flags, using:

```text
python -u scripts\build_dataset.py --clip-norm 25 --lr-dec 3e-4
  --eval-decode-every 5000 --augment-acoustic --pitch-loss-weight 2.5
```

Resume log:
`D:\vscode_projects\ee_download\work\train_r2_v4_resume_after_d86_gatefail.out.log`

Observed certificate:

```text
续训:恢复 step=63800 epoch=7 batch_cursor=174414
遮上文 input_dropout=0(关) | 音频依赖损失 weight=0(关)
```

This confirms the safety fallback: the main run resumed from the locked
production snapshot, not from either experimental arm.

## Evidence

- `reports/DECODE_SWEEP_STEP63800.json`: per-sample, per-arm decode evidence.
- `reports/eval_autolog.md`: generated sweep summary.
- `reports/D86_DECODE_SWEEP_STEP63800.out.log` and `.err.log`: raw sweep logs.
- `reports/D86_AB_A_STEP63800_63900.out.log` and `.err.log`: raw A logs.
- `reports/D86_AB_B_STEP63800_63900.out.log` and `.err.log`: raw B logs.

