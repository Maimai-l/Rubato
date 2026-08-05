# D93 pretrain-v2 gate and round-3 start evidence (2026-08-05)

This report is an immutable execution record for the D93 transition. It records the actual artifacts and startup evidence; it does not alter the frozen round-3 recipe or the 20k comparison gate.

## 1. Round-2 archive preflight

- Archived checkpoint: `D:\vscode_projects\ee_download\outputs\ckpt_r2_73k\last.pt`
- SHA-256: `8b08f5af945a639911f86b4436f48673c7875bcc35c075659a94d2c7fb795b1d`
- Loaded state: `step=72600`, `epoch=8`, `batch_cursor=186996`
- Default `D:\vscode_projects\ee_download\outputs\ckpt` was absent.
- Target `D:\vscode_projects\ee_download\outputs\ckpt_r3_v1` and both `work\train_r3_v1` logs were absent before launch.
- No project Python/GPU job was active before launch; D: free space was 51,608,981,504 bytes.

## 2. pretrain-v2 result and selection

- Output: `D:\vscode_projects\ee_download\work\decoder_init_v2.pt`
- SHA-256: `177fa447dcec95e3550a37e7d6be1f48fdec7abb3420d58d1db7e63538275dd9`
- Training completed all 40,000 steps in 119.6 minutes; final `avg50=1.8877`; no overlength rows were skipped.
- Artifact metadata: `complete=true`, `target_steps=40000`, `artifact_role=decoder_init`, required parts `transf_decoder` and `log_softmax` present.
- Final fixed free evaluation: `n=48`, `parseable=36` (75%, parseable gate PASS), `DYCK=5` (required 0, DYCK gate FAIL), hence `health_pass=false`.
- Decision: v2 was rejected exactly as preregistered. Round-3 uses the previously accepted v1 artifact, not v2.

Free-generation trajectory (`step: parseable/48, DYCK`):

```text
 2000:  1, 44    4000:  6, 33    6000:  6, 26    8000: 11, 19
10000: 24,  9   12000: 31,  8   14000: 20,  3   16000: 11,  9
18000: 16, 12   20000: 21,  9   22000: 29,  8   24000: 17, 19
26000: 34,  3   28000: 39,  3   30000: 45,  2   32000: 38,  3
34000: 41,  2   36000: 42,  3   38000: 36,  4   40000: 36,  5
```

Selected v1:

- Artifact: `D:\vscode_projects\ee_download\work\decoder_init.pt`
- SHA-256: `6dfa62af268a614d10f37e08ad2f98a4107220a88c12c0e22e0cf73e22129579`
- Metadata: `complete=true`, `target_steps=20000`, `artifact_role=decoder_init`, `health_pass=true`; required decoder/output parts present.

## 3. Round-3 launch and verification

Started PID 20708 at 2026-08-05 13:06:38 Asia/Shanghai with the exact command:

```powershell
D:\ProgramData\envs\nemo_test\python.exe -u scripts/build_dataset.py --clip-norm 25 --lr-dec 3e-4 --eval-decode-every 5000 --augment-acoustic --pitch-loss-weight 2.5 --decoder-init D:\vscode_projects\ee_download\work\decoder_init.pt --ckpt-dir D:\vscode_projects\ee_download\outputs\ckpt_r3_v1
```

Logs:

- `D:\vscode_projects\ee_download\work\train_r3_v1.out.log`
- `D:\vscode_projects\ee_download\work\train_r3_v1.err.log`

Startup checks:

- Dataset assembly: 752,792 utterances total; 704,024 train; PDMX content leakage certificate PASS.
- Decoder init load was explicitly confirmed from the selected v1 artifact (`pretrain steps=20000`).
- No `续训:恢复` line appeared: this is a fresh round-3 start.
- Echoed configuration: `clip_norm=25.0`, `lr_dec=3.0e-04`, `eval_decode_every=5000`, `aug_acoustic=开`, `pitch-loss-weight=2.5` (346 pitch-mask pieces), `prefetch=关`.
- Forbidden controls remained off: `input_dropout=0(关)` and audio-dependency loss `weight=0(关)`.
- First training step completed without traceback, NaN, OOM, or fatal error:

```text
step 1 loss=204.2727 avg50=204.2727 sem=8.5738 ts=12.2422 pv=12.084 gn=341.2/avg341.2 enc=30.0 dec=339.9 lrE=6.67e-08 lrD=2.00e-07 audio=2004s micro=49 seq=73 td=6.1s/avg6.1 tc=9.4s/avg9.4 | A2S=7.46 A2S_lite=12.57 AMT=8.74 TAST=5.72
```

The NeMo restore path emitted its known class-reflection diagnostic on stderr, but model restoration, decoder initialization, and the first optimizer step all completed; it was therefore non-fatal in this run.

## 4. Outcome

D93 transition completed successfully: v2 was correctly rejected by the strict DYCK gate, the accepted v1 was selected, and a fresh isolated round-3 process started with the frozen recipe. The next formal decision remains the separately frozen round-3 20k comparison gate.
