# D95 ammunition rework and round-3 v2 start (2026-08-05)

This is the immutable execution record for the D95 same-scale decoder-init selection window.

## 1. Preflight and discarded r3-v1 run

- Pulled through `33697b4`; the new best-checkpoint sidecar tests passed `7/7` using the test file's built-in runner.
- The first round-3 process (PID 20708) was precisely stopped at step 500.
- Its checkpoint directory was preserved at `D:\vscode_projects\ee_download\outputs\ckpt_r3_v1_5h_discard`; no recursive deletion was performed.
- The archive target did not exist before the move.

## 2. v3 replay with best-checkpoint preservation

The v2 recipe was replayed on `formal_corpus_v2.jsonl` for 40,000 steps. The launch included `--min-free-parseable 0.60` so artifact eligibility matches the D95 floor (at least 29/48); the obsolete DYCK hard gate was not enabled. This changes only artifact eligibility, not the training trajectory.

- Process: PID 10040, started 2026-08-05 14:31:38 Asia/Shanghai.
- Runtime: 130.2 minutes; final avg50 1.8877; no overlength rows skipped; no NaN/OOM/fatal error.
- Final artifact: `D:\vscode_projects\ee_download\work\decoder_init_v3.pt`
  - SHA-256: `7AE2E735C9E77E110A651A8416C55165F334F9DA7B142575333A2B98B08A321F`
  - step 40000, complete/health PASS, free eval 36/48, DYCK 5.
- Best artifact: `D:\vscode_projects\ee_download\work\decoder_init_v3_best.pt`
  - SHA-256: `3819F21318B33F477FC0842696121384E6EBA16F7991E3EDC45CDE7FB1CE6305`
  - step 30000, complete/health PASS, free eval 45/48, DYCK 2.

The run reproduced the previously observed trajectory and the new sidecar retained the step-30000 optimum instead of overwriting it with the weaker final state.

## 3. v1 same-scale evaluation

The accepted v1 exact state resumed from step 20000 for 50 steps using its original corpus, then ran the same fixed-size `n=48` free evaluation.

- Exact recovery line confirmed decoder, optimizer, both RNG states, and recent-loss state.
- Result: step 20050, 38/48 parseable, DYCK 3, EOT 48/48, health PASS.
- Output: `D:\vscode_projects\ee_download\work\decoder_init_v1eval.pt`
- SHA-256: `47486A32154EEB78FB8A5A4F2B90AD7187E186FB0D10B9FFE63166EF05DE2426`
- Runtime: 0.3 minutes; no fatal error.

Execution note: the current pretrainer treats an explicit `--resume-state` path as both input and subsequent save target, so `decoder_init.pt.resume.pt` was advanced in place from step 20000 to 20050. The accepted immutable `decoder_init.pt` itself was not modified. This behavior should be considered before any future diagnostic continuation that must preserve the original resume sidecar byte-for-byte.

## 4. Preregistered four-candidate selection

Ranking rule: maximize `(parseable, -DYCK)` with an eligibility floor of at least 29/48 parseable.

| Candidate | Step | Parseable | DYCK | Artifact health | Rank |
|---|---:|---:|---:|---|---|
| v1@n48 | 20050 | 38/48 | 3 | PASS | (38, -3) |
| v2-final | 40000 | 36/48 | 5 | FAIL under the old absolute-DYCK gate | (36, -5) |
| **v3-best** | **30000** | **45/48** | **2** | **PASS** | **(45, -2)** |
| v3-final | 40000 | 36/48 | 5 | PASS under the revised parseable gate | (36, -5) |

Winner: `D:\vscode_projects\ee_download\work\decoder_init_v3_best.pt`.

The selection was made from artifact metadata loaded with PyTorch, not inferred from filenames or log prose.

## 5. Fresh round-3 v2 start

Started PID 36080 at 2026-08-05 16:49:46 Asia/Shanghai:

```powershell
D:\ProgramData\envs\nemo_test\python.exe -u scripts/build_dataset.py --clip-norm 25 --lr-dec 3e-4 --eval-decode-every 5000 --augment-acoustic --pitch-loss-weight 2.5 --decoder-init D:\vscode_projects\ee_download\work\decoder_init_v3_best.pt --ckpt-dir D:\vscode_projects\ee_download\outputs\ckpt_r3_v2
```

Startup checks passed:

- Dataset assembly: 752,792 utterances total; 704,024 train; PDMX content-leakage certificate PASS.
- Explicit init load: `decoder_init_v3_best.pt`, pretrain step 30000.
- No `续训:恢复` line: the isolated `ckpt_r3_v2` run is fresh.
- Configuration: clip norm 25, decoder LR 3e-4, decode eval every 5000, acoustic augmentation on, pitch mask 346 pieces weighted 2.5, prefetch off.
- Forbidden controls remained off: input dropout 0 and audio-dependency loss weight 0.
- First optimizer step completed with no traceback, NaN, OOM, or fatal error:

```text
step 1 loss=210.7616 avg50=210.7616 sem=8.7549 ts=12.3142 pv=12.719 gn=190.9/avg190.9 enc=32.5 dec=188.1 lrE=6.67e-08 lrD=2.00e-07 audio=2004s micro=49 seq=73 td=6.2s/avg6.2 tc=9.4s/avg9.4 | A2S=7.69 A2S_lite=13.23 AMT=8.75 TAST=5.98
```

Logs:

- `D:\vscode_projects\ee_download\work\train_r3_v2.out.log`
- `D:\vscode_projects\ee_download\work\train_r3_v2.err.log`
- Future eval evidence: `D:\vscode_projects\ee_download\outputs\ckpt_r3_v2\eval_autolog.md`

## 6. Next gates

- At 5k and 10k: copy the external r3-v2 eval autolog into a new repository report and record parseable/DYCK trend; do not decide early.
- At 20k: apply the frozen criteria without modification: DYCK <=21/48, raw_ned <=0.85, and four-probe true-sem macro mean >=0.562875.
- Decision: 2-3 passes continue; 0 passes stop; exactly 1 pass pauses for review.
