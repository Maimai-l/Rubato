# Decoder formal-language pre-pretraining: 20k final result

Date: 2026-08-05 (Asia/Shanghai)

## Verdict

The registered 20,000-step BF16 run completed without NaN, OOM, skipped rows,
or a fatal traceback.  The produced artifact passed the implemented two-part
health gate and is marked `artifact_role=decoder_init`, so the production loader
may use it for a later round-3 start.

This is an **operational pass but a teacher-forced gray result**:

- final avg50 CE: `2.005728` (`GRAY`; registered PASS was <=1.5);
- final decoder-only continuation: `3/4` parseable (`75%`, gate >=50%);
- EOT: `4/4`;
- remaining final violation: one `MEASURE` failure;
- metadata: `steps=target_steps=20000`, `complete=true`,
  `health_pass=true`, `init_mode=scratch`, `format_version=2`;
- both required state dictionaries are present.

The free gauge has only four fixed cases.  Passing it is a run-safety gate, not
enough evidence by itself for a scientific improvement claim; a larger held-out
formal-language evaluation should precede any such claim.

## Run configuration and resources

- corpus: 200,000 validated A2S/TAST formal examples;
- corpus SHA-256:
  `b58f74c036de89e8e896708be5b0aea1c04ee1416989e485d1e0839b6e4a91c6`;
- trainable: 83,582,784 decoder/output parameters;
- frozen: 110,073,856 parameters;
- batch rows: 16; LR: 3e-4; warmup: 500; precision: BF16;
- wall time: 47.8 minutes;
- observed step time at the end: about 0.14 s;
- peak CUDA allocated memory: 7,319 MiB;
- overlength skips: 0.

## Decoder-only trajectory

| Step | Parseable | EOT | Rejection tally |
|---:|---:|---:|---|
| 2,000 | 0/4 | 4/4 | MEASURE 3, DYCK 3, parse error 1 |
| 4,000 | 1/4 | 4/4 | MEASURE 3, DYCK 2 |
| 6,000 | 1/4 | 4/4 | MEASURE 3, DYCK 2 |
| 8,000 | 0/4 | 4/4 | MEASURE 2, DYCK 2, TERMINAL 1 |
| 10,000 | 1/4 | 4/4 | MEASURE 3 |
| 12,000 | 1/4 | 4/4 | MEASURE 3 |
| 14,000 | 1/4 | 3/4 | MEASURE 2, DYCK 2, TERMINAL 1 |
| 16,000 | 2/4 | 4/4 | MEASURE 2 |
| 18,000 | 2/4 | 4/4 | DYCK 1, MEASURE 1 |
| 20,000 | 3/4 | 4/4 | MEASURE 1 |

Despite small-sample noise, the endpoint improved from 0/4 to 3/4 and the final
failure spectrum contracted from mixed parse/DYCK/MEASURE errors to one MEASURE
error.  This is evidence that the run learned formal continuation behavior, not
only lower teacher-forced CE.

## Artifacts and integrity

- final decoder init: `work/decoder_init.pt`, 338,571,295 bytes,
  SHA-256 `6DFA62AF268A614D10F37E08AD2F98A4107220A88C12C0E22E0CF73E22129579`;
- exact resume: `work/decoder_init.pt.resume.pt`, 1,007,337,217 bytes,
  SHA-256 `7C2372D64D6B40771C79C21BC1E8E1EAD490C513CA7E1D34F690521EEA483AC1`;
- stdout: `work/pretrain_full.out.log`;
- stderr: `work/pretrain_full.err.log` (NeMo configuration warning only; fatal
  scan empty).

Large binary artifacts and runtime logs remain outside Git and are identified by
path and hash here.

## Main-training handoff

The previous main run was stopped only after `outputs/ckpt/last.pt` was loaded
and verified as step 72,600, epoch 8, batch cursor 186,996.  Its checkpoint is
2,329,081,797 bytes, timestamp 2026-08-05 01:03:08.  The pretrain artifact is
reserved for a later round-3 start and must not be injected into this already
running round.  The immediate operational next step is therefore to resume the
existing main recipe exactly from step 72,600.
