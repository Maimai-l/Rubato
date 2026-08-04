# Decoder formal-language pre-pretraining: infrastructure audit and CPU smoke

Date: 2026-08-05 (Asia/Shanghai)

## Scope and current decision

Pulled `064003d..a64494b`, including the D91 formal-language decoder pre-pretraining
toolchain.  The full 20k GPU run has **not** started yet: the existing main training
is being allowed to reach its next durable checkpoint (step 73000) before GPU
ownership changes.  The CPU smoke below is connectivity evidence only and its
artifact is explicitly rejected by `build_model` for round-3 initialization.

## Infrastructure gaps found and fixed

1. Corpus and decoder artifacts were written directly to their final paths.
   Corpus, resume state and final decoder artifacts now use same-directory temp
   files, flush/fsync and atomic replacement.  Existing corpus output is refused
   unless `--overwrite` is explicit.
2. A 20k interruption previously lost optimizer, sampler and RNG state.  The run
   now writes an exact resume containing decoder/output weights, AdamW state,
   Python batch RNG, Torch/CUDA RNG, recent-loss window, step and skip count.
   Corpus/tokenizer hashes and training configuration form a strict signature;
   changed inputs are refused rather than approximately resumed.
3. The pretrain previously inherited Canary decoder weights despite being
   described as decoder-from-scratch.  `--init-mode scratch` is now the default
   and resets all decoder/output modules; `canary` remains an explicit ablation.
4. The only health signal was teacher-forced CE.  A decoder-only greedy
   continuation gauge now feeds a short reference prefix, then no target tokens,
   uses zero encoder context, and checks the produced text with the production
   parser/validator.  Full artifacts need finite CE within the registered band
   and at least 50% parseable free continuations by default.
5. Full, incomplete, unhealthy and smoke artifacts now carry distinct metadata.
   The production model loader refuses incomplete, failed, or smoke artifacts.
6. The first actual smoke exposed a wrong default model path
   (`Rubato/canary-180m-flash.nemo`); the workspace model is one directory above.
   The default now follows the actual `build_dataset` layout with a repo-local
   fallback.
7. Smoke logging previously said to use its artifact for round-3.  It now states
   that smoke is diagnostic only and must be followed by the formal pretrain.

## Corpus evidence

- Path: `D:\vscode_projects\ee_download\work\formal_corpus.jsonl`
- Rows: 200,000
- Size: 173,271,907 bytes
- Dialects: TAST 99,447; A2S 100,553
- Mean atoms: 64.5; overlength resamples: 0
- SHA-256: `b58f74c036de89e8e896708be5b0aea1c04ee1416989e485d1e0839b6e4a91c6`
- Every row passed the production `text_to_units` + `validate_units` check.
- Generation time: 504 seconds.
- Logs: `work/gen_formal.out.log`, `work/gen_formal.err.log` (stderr empty).

## CPU smoke evidence

- Command shape: 300 steps, batch_rows=8, CPU, scratch decoder, LR 3e-4,
  warmup 500; 83,582,784 trainable and 110,073,856 frozen parameters.
- Runtime: 22.8 minutes; 0 overlength skips; no NaN or OOM.
- avg50 curve: step 50 7.9065; 100 5.7337; 150 4.9623; 200 4.6449;
  250 4.4342; 300 4.2998.
- Free continuation: 0/4 parseable after only 300 steps.  This is not the full
  gate; it proves the non-teacher-forced evaluator runs and supplies the baseline
  the 20k run must improve.
- Final artifact: `work/decoder_init_smoke.pt` (338,570,591 bytes).
- Exact resume: `work/decoder_init_smoke.pt.resume.pt` (1,007,333,057 bytes).
- Logs: `work/pretrain_smoke_2.out.log`, `work/pretrain_smoke_2.err.log`.
- The first failed path-resolution attempt remains in
  `work/pretrain_smoke.out.log` / `.err.log` as fault evidence.

The smoke consumed about 7.6--8.0 GiB RAM and approximately ten logical CPU
cores.  Running it beside the main GPU training increased main `tc` from about
7.9 s to about 10.4 s, so the formal GPU run must not overlap main training.

## Regression evidence

- `tests_pretrain_decoder.py`: PASS 6/6
- `tests_formal_corpus.py`: PASS 5/5
- `tests_model_build.py`: PASS 33/33
- `tests_cli_help.py`: PASS 12/12
- `py_compile`: pass for all changed Python files

## Safe continuation

At capture time the main process was alive and past step 72475; D: had 52.15 GiB
free.  Wait for the step-73000 checkpoint and evaluation to finish, verify the
checkpoint really records step 73000, then stop the main process.  With the GPU
exclusive, run a tiny CUDA integration smoke using a separate output path.  Only
after CUDA memory, resume, artifact metadata and free-generation code all pass
should the 20k run start.  The 20k artifact is accepted only if its registered
health gates pass; it is for a later round-3 start and must not be injected into
the current main run.
