
## eval @ step 18000 (2026-07-16 02:31:30)
  eval 探针[nasap_Bult-ItoS02M_171360e0_004/TAST]: acc=0.41 前缀acc=0.31 eotP@首位=0.0001 n=389
  eval 探针argmax: 'F3C5 <|0.09|> 1/8PL:c3c4C3C4a-4 <|0.12|> 1/16PL:D-5 <|0.37|> 1/16 <|0.79|> 1/16c'
  eval 探针参照:   '|4/4k-4PL:C3C4PR:A-4 <|0.00|> 1/16C5 <|0.28|> 1/16c5F5 <|0.56|> 1/16f5E5 <|0.83|'
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['parse_error:ParseError'], 'raw': '|12/8k-6PL:G-2PR:B-5 <|0.02|> 1/8PL:g-2D-3 <|0.12|> 1/8d-3G-3 <|0.31|> 1/8g-3D-3 <|0.54|> 1/8d-3G-3 <|0.73|> 1/8g-3D-3 <|0.92|> 1/8d-3G-3 <|1.05|> 1/8g-3D-3 <|1', 'truncated': '|12/8k-6PL:G-2PR:B-5 <|0.02|> 1/8PL:g-2D-3 <|0.12|> 1/8d-3G-3 <|0.31|> 1/8g-3D-3 <|0.54|> 1/8d-3G-3 '}
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.41/前缀0.31 eotP0=0.0001
  eval 指标: parseable=0.00 amt_f1=0.0 omr_ned=None n_nasap=48 n_maestro=48

## eval @ step 19000 (2026-07-16 05:12:55)
  eval 探针[nasap_Bult-ItoS02M_171360e0_004/TAST]: acc=0.40 前缀acc=0.34 eotP@首位=0.0000 n=389
  eval 探针argmax: 'F3C5 <|0.04|> 1/8PL:c3c4a-4 <|0.38|> 1/16A-4 <|0.50|> 1/16 <|0.66|> 1/16c3c4PR:e'
  eval 探针参照:   '|4/4k-4PL:C3C4PR:A-4 <|0.00|> 1/16C5 <|0.28|> 1/16c5F5 <|0.56|> 1/16f5E5 <|0.83|'
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PR', SPitch(step='B', alter=-1, octave=3))@7/8", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='B', alter=-1, octave=3))@3/2", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='B', alter=-1, octave=3))@37/16", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='B', alter=-1, octave=3))@43/16"], 'raw': '|2/2k-6PL:G-2PR:B-3 <|0.06|> 1/16b-3D-4 <|0.27|> 1/16d-4B-3 <|0.38|> 1/16b-3D-4 <|0.50|> 1/16d-4B-3 <|0.50|> 1/16b-3D-4 <|0.61|> 1/16d-4B-3 <|0.73|> 1/16b-3D-4 ', 'truncated': '|2/2k-6PL:G-2PR:B-3 <|0.06|> 1/16b-3D-4 <|0.27|> 1/16d-4B-3 <|0.38|> 1/16b-3D-4 <|0.50|> 1/16d-4B-3 '}
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.40/前缀0.34 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.0 omr_ned=None n_nasap=48 n_maestro=48

## eval @ step 20000 (2026-07-16 07:54:35)
  eval 探针[nasap_Bult-ItoS02M_171360e0_004/TAST]: acc=0.41 前缀acc=0.34 eotP@首位=0.0000 n=389
  eval 探针argmax: '|4/4k0PL:F3E4 <|0.01|> 1/8PL:c3c4C3C4a-4 <|0.30|> 1/16PL:D-5 <|0.39|> 1/16 <|0.6'
  eval 探针参照:   '|4/4k-4PL:C3C4PR:A-4 <|0.00|> 1/16C5 <|0.28|> 1/16c5F5 <|0.56|> 1/16f5E5 <|0.83|'
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='C', alter=0, octave=4))]", 'TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PL:C4 <|0.02|> 1/16c4C4 <|0.26|> 1/16c4C4 <|0.39|> 1/16c4 <|0.52|> 1/16C4 <|0.52|> 1/16c4 <|0.52|> 1/16C4 <|0.74|> 1/16c4 <|0.84|> 1/16C4 <|0.88|> 1/16c4 ', 'truncated': '|4/4k0PL:C4 <|0.02|> 1/16c4C4 <|0.26|> 1/16c4C4 <|0.39|> 1/16c4 <|0.52|> 1/16C4 <|0.52|> 1/16c4 <|0.'}
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.41/前缀0.34 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.0 omr_ned=None n_nasap=48 n_maestro=48

## eval @ step 22000 (2026-07-16 13:20:34)
  eval 探针[nasap_Bult-ItoS02M_171360e0_004/TAST]: acc=0.39 前缀acc=0.38 sem=0.48 ts=0.08 eotP@首位=0.0001 n=389
  eval 探针argmax: 'C4E4 <|0.00|> 1/8PL:c3c4a-4G4 <|0.16|> 1/16PL:D-5 <|0.50|> 1/16PL: <|0.71|> 1/16'
  eval 探针参照:   '|4/4k-4PL:C3C4PR:A-4 <|0.00|> 1/16C5 <|0.28|> 1/16c5F5 <|0.56|> 1/16f5E5 <|0.83|'
  eval 探针(静音对照): acc=0.39 sem=0.48 ts=0.08 Δsem=+0.00(真音频语义命中 − 静音;≈0 = decoder 没在读音频内容)
  eval 探针失败(AcceleratorError: CUDA error: device-side assert triggered
Search for `cudaErrorAssert' in https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__TYPES.html for more information.
CUDA kernel errors might be asynchronously reported at some other API call, so the stacktrace below might be incorrect.
For debugging consider passing CUDA_LAUNCH_BLOCKING=1
Compile with `TORCH_USE_CUDA_DSA` to enable device-side assertions.
)—— 贴回本行
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'decode_exception', 'err': "AcceleratorError: CUDA error: device-side assert triggered\nSearch for `cudaErrorAssert' in https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__TYPES.html for more information.\nCUDA kernel errors might be asynchronously reported at some other API call, so the stacktrace below might be incorrect.\nFor debugging consider passing CUDA_LAUNCH_BLOCKING=1\nCompile with `TORCH_USE_CUDA_DSA` to enable device-side assertions.\n", 'tb': 'Traceback (most recent call last):\n  File "D:\\vscode_projects\\ee_download\\Rubato\\rubato\\model\\infer.py", line 261, in single_window_tast\n    raw = _decode(beam)\n          ^^^^^^^^^^^^^\n  File "D:\\vscode_projects\\ee_download\\Rubato\\rubato\\model\\infer.py", line 250, in _decode\n    return autoregressive_decode(model, audio_window, tokenizer, prompt)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File "D:\\vscode_projects\\ee_download\\Rubato\\rubato\\model\\infer.py", line 171, in autoregressive_decode\n    audio_t = torch.as_tensor(audio, dtype=torch.float32, device=device).reshape(1, -1)\n              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\ntorch.AcceleratorError: CUDA error: device-side assert triggered\nSearch for `cudaErrorAssert\' in https://docs.nvidia.com/cuda/cuda-runtime-api/group__CUDART__TYPES.html for more information.\nCUDA kernel errors might be asynchronously reported at some other API call, so the stacktrace below might be incorrect.\nFor debugging consider passing CUDA_LAUNCH_BLOCKING=1\nCompile with `TORCH_USE_CUDA_DSA` to enable device-side assertions.\n\n'}
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.39/前缀0.38 eotP0=0.0001
  eval 指标: parseable=0.00 amt_f1=0.0 omr_ned=None n_nasap=48 n_maestro=48

## eval @ step 22000 (2026-07-16 13:52:02)
  eval 探针[nasap_Bult-ItoS02M_171360e0_004/TAST]: acc=0.39 前缀acc=0.38 sem=0.48 ts=0.08 eotP@首位=0.0001 n=389 rms=0.0166 enc帧=458.0 enc_std=0.10
  eval 探针argmax: 'C4E4 <|0.00|> 1/8PL:c3c4a-4G4 <|0.16|> 1/16PL:D-5 <|0.50|> 1/16PL: <|0.71|> 1/16'
  eval 探针参照:   '|4/4k-4PL:C3C4PR:A-4 <|0.00|> 1/16C5 <|0.28|> 1/16c5F5 <|0.56|> 1/16f5E5 <|0.83|'
  eval 探针(静音对照): acc=0.39 sem=0.48 ts=0.08 rms=0.0000 enc_std=0.12 Δsem=+0.00(真音频语义命中 − 静音;≈0 = decoder 没在读音频内容)
  eval 探针[nasap_Hou01M_adeab67f_001/TAST]: acc=0.55 前缀acc=0.47 sem=0.66 ts=0.08 eotP@首位=0.0001 n=995 rms=0.1075 enc帧=490.0 enc_std=0.09 截断至1000
  eval 探针(错配音频): acc=0.39 sem=0.49 ts=0.08 rms=0.1075(样本0 的谱 × 本样本音频;与样本0行一致 = 没在读音频)
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['MEASURE_SUM:3 got 9/8 want 1', 'MEASURE_SUM:4 got 7/8 want 1', 'MEASURE_SUM:5 got 9/8 want 1', 'MEASURE_SUM:9 got 9/8 want 1'], 'raw': '|4/4k0PR:C4 <|0.05|> 1/8c4C4 <|0.28|> 1/8c4C4 <|0.50|> 1/8c4C4 <|0.71|> 1/8c4C4 <|0.93|> 1/8c4C4 <|1.13|> 1/8c4 <|1.33|> |4/4k0C4 <|1.33|> 1/8c4C4 <|1.55|> 1/8c', 'truncated': '|4/4k0PR:C4 <|0.05|> 1/8c4C4 <|0.28|> 1/8c4C4 <|0.50|> 1/8c4C4 <|0.71|> 1/8c4C4 <|0.93|> 1/8c4C4 <|1'}
  eval 汇总: parseable=0.12 empty=0.875 n=8 样本0='|4/4k0' 探针acc=0.39/前缀0.38 eotP0=0.0001
  eval 指标: parseable=0.12 amt_f1=None omr_ned=0.941944847605225 n_nasap=8 n_maestro=0

## probe-only 三源探针 @ step 22000 (2026-07-16 14:23:55)
probe-only 三源探针 @ step 22000
  探针 nasap/TAST[nasap_Shi05M_63322b36_000]: 真 sem=0.63 ts=0.20 acc=0.52 | 静音 sem=0.47 | Δsem=+0.16 rms=0.0541 n=704 domain=real
  探针 nasap/TAST[nasap_Shi05M_63322b36_001]: 真 sem=0.64 ts=0.15 acc=0.52 | 静音 sem=0.52 | Δsem=+0.12 rms=0.0652 n=704 domain=real
  探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: 真 sem=0.72 ts=0.28 acc=0.62 | 静音 sem=0.72 | Δsem=+0.00 rms=0.0667 n=660 domain=real
  探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_001]: 真 sem=0.65 ts=0.34 acc=0.58 | 静音 sem=0.67 | Δsem=-0.02 rms=0.0970 n=530 domain=real
  探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: 真 sem=0.57 ts=0.14 acc=0.49 | 静音 sem=0.54 | Δsem=+0.03 rms=0.0923 n=479 domain=synth
  探针 pdmx/TAST[pdmxperf_Qmbb4MXzbgmP9cQzUaXFK9Mp5pMK4UCwrM9YKuS2pF3mt6_000]: 真 sem=0.72 ts=0.34 acc=0.61 | 静音 sem=0.62 | Δsem=+0.10 rms=0.1184 n=413 domain=synth

## probe-only 三源探针 @ step 22000 (2026-07-16 14:46:29)
probe-only 联合仪器(对齐×Δsem)@ step 22000,每源 8 条
  联合 nasap/TAST[nasap_Shi05M_63322b36_000]: 对齐=SHIFTED(peak=0.334 lag=-230ms) Δsem=+0.16 真sem=0.63 静sem=0.47 ts真=0.20/静0.06 n=704
  联合 nasap/TAST[nasap_Shi05M_63322b36_001]: 对齐=SHIFTED(peak=0.304 lag=-230ms) Δsem=+0.12 真sem=0.64 静sem=0.52 ts真=0.15/静0.05 n=704
  联合 nasap/TAST[nasap_Shi05M_63322b36_002]: 对齐=UNCORRELATED(peak=0.213 lag=-240ms) Δsem=+0.08 真sem=0.65 静sem=0.57 ts真=0.16/静0.08 n=714
  联合 nasap/TAST[nasap_Shi05M_63322b36_003]: 对齐=UNCORRELATED(peak=0.185 lag=240ms) Δsem=+0.06 真sem=0.71 静sem=0.65 ts真=0.14/静0.08 n=734
  联合 nasap/TAST[nasap_Shi05M_63322b36_004]: 对齐=UNCORRELATED(peak=0.147 lag=-490ms) Δsem=+0.02 真sem=0.68 静sem=0.67 ts真=0.13/静0.06 n=736
  联合 nasap/TAST[nasap_Shi05M_63322b36_005]: 对齐=UNCORRELATED(peak=0.123 lag=10ms) Δsem=+0.08 真sem=0.65 静sem=0.57 ts真=0.14/静0.07 n=649
  联合 nasap/TAST[nasap_Shi05M_63322b36_006]: 对齐=UNCORRELATED(peak=0.167 lag=520ms) Δsem=+0.00 真sem=0.58 静sem=0.58 ts真=0.11/静0.11 n=297
  联合 nasap/TAST[nasap_Denisova06M_41baa5ba_000]: 对齐=SHIFTED(peak=0.366 lag=100ms) Δsem=+0.08 真sem=0.73 静sem=0.66 ts真=0.23/静0.10 n=995
  联合 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: 对齐=OK(peak=0.277 lag=-10ms) Δsem=+0.00 真sem=0.72 静sem=0.72 ts真=0.28/静0.27 n=660
  联合 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_001]: 对齐=OK(peak=0.3 lag=-10ms) Δsem=-0.02 真sem=0.65 静sem=0.67 ts真=0.34/静0.30 n=530
  联合 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_002]: 对齐=OK(peak=0.316 lag=-10ms) Δsem=-0.00 真sem=0.68 静sem=0.68 ts真=0.31/静0.26 n=591
  联合 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_003]: 对齐=OK(peak=0.481 lag=-10ms) Δsem=-0.01 真sem=0.65 静sem=0.66 ts真=0.24/静0.25 n=516
  联合 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_004]: 对齐=OK(peak=0.406 lag=-10ms) Δsem=-0.01 真sem=0.66 静sem=0.67 ts真=0.26/静0.22 n=546
  联合 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_005]: 对齐=OK(peak=0.308 lag=-10ms) Δsem=-0.01 真sem=0.64 静sem=0.65 ts真=0.13/静0.13 n=495
  联合 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_006]: 对齐=UNCORRELATED(peak=0.036 lag=-10ms) Δsem=+0.04 真sem=0.68 静sem=0.64 ts真=0.37/静0.23 n=139
  联合 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_007]: 对齐=OK(peak=0.433 lag=-10ms) Δsem=+0.01 真sem=0.67 静sem=0.65 ts真=0.31/静0.23 n=917
  联合 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: 对齐=UNCORRELATED(peak=0.226 lag=0ms) Δsem=+0.03 真sem=0.57 静sem=0.54 ts真=0.14/静0.10 n=479
  联合 pdmx/TAST[pdmxperf_Qmbb4MXzbgmP9cQzUaXFK9Mp5pMK4UCwrM9YKuS2pF3mt6_000]: 对齐=OK(peak=0.315 lag=-10ms) Δsem=+0.10 真sem=0.72 静sem=0.62 ts真=0.34/静0.20 n=413
  联合 pdmx/TAST[pdmxperf_QmbbCoyosnMgyAsivgrBzw2TQVhvx6QvJP2zcwKJk6PMjZ_000]: 对齐=UNCORRELATED(peak=0.055 lag=0ms) Δsem=+0.15 真sem=0.59 静sem=0.44 ts真=0.21/静0.13 n=775
  联合 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: 对齐=OK(peak=0.646 lag=10ms) Δsem=+0.17 真sem=0.65 静sem=0.49 ts真=0.29/静0.12 n=724
  联合 pdmx/TAST[pdmxperf_QmbbC9divwbeJnZKTkAsavfFXgo7qbLbq82kKepH1fDBCA_000]: 对齐=UNCORRELATED(peak=0.22 lag=10ms) Δsem=+0.12 真sem=0.47 静sem=0.35 ts真=0.22/静0.10 n=995
  联合 pdmx/A2S[pdmxperf_QmbbC9divwbeJnZKTkAsavfFXgo7qbLbq82kKepH1fDBCA_001]: 对齐=TOO_SHORT(peak=0.0 lag=0ms) Δsem=+0.03 真sem=0.34 静sem=0.31 ts真=-/静- n=74
  联合 pdmx/TAST[pdmxperf_QmbbYRhJ3Kdpty8yYNCDSbbMJDY3RZQPko9QztHWyt7BWN_000]: 对齐=UNCORRELATED(peak=0.222 lag=50ms) Δsem=+0.13 真sem=0.77 静sem=0.64 ts真=0.28/静0.25 n=204
  联合 pdmx/TAST[pdmxperf_QmbbcLC4vffHsAno2UgaJhwPduTRdgZUyhTRHuumakUe9j_000]: 对齐=OK(peak=0.698 lag=10ms) Δsem=+0.10 真sem=0.62 静sem=0.53 ts真=0.27/静0.11 n=761
  联合汇总: 对齐OK 平均Δsem=0.03(n=10) | 错位 平均Δsem=0.08(n=14)
  分源 nasap: OK Δsem=-(n=0) 错位 Δsem=0.07(n=8)
  分源 maestro: OK Δsem=-0.00(n=7) 错位 Δsem=0.04(n=1)
  分源 pdmx: OK Δsem=0.12(n=3) 错位 Δsem=0.09(n=5)

## eval @ step 23000 (2026-07-16 17:43:37)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.16 Δts=+0.13 真sem=0.62 静sem=0.46 acc=0.52 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.03 真sem=0.73 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.06 Δts=+0.03 真sem=0.58 静sem=0.52 acc=0.50 n=479
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=0, octave=4))@13/16", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='C', alter=0, octave=6))@77/16", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='C', alter=0, octave=6))@49/8", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='C', alter=0, octave=6))@107/16"], 'raw': '|4/4k0PL:C4PR:C5 <|0.09|> 1/16c5E5 <|0.16|> 1/16e5C5 <|0.16|> 1/16c5E5 <|0.16|> 1/16e5C5 <|0.16|> 1/16c5E5 <|0.16|> 1/16e5C5 <|0.16|> 1/16c5E5 <|0.16|> 1/16e5C5', 'truncated': '|4/4k0PL:C4PR:C5 <|0.09|> 1/16c5E5 <|0.16|> 1/16e5C5 <|0.16|> 1/16c5E5 <|0.16|> 1/16e5C5 <|0.16|> 1/'}
  eval 汇总: parseable=0.02 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.52/前缀0.56 eotP0=0.0001
  eval 指标: parseable=0.02 amt_f1=0.0 omr_ned=0.941944847605225 n_nasap=48 n_maestro=48

## eval @ step 24000 (2026-07-16 20:32:03)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.15 Δts=+0.15 真sem=0.62 静sem=0.47 acc=0.52 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.05 Δts=+0.06 真sem=0.72 静sem=0.67 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.10 Δts=+0.09 真sem=0.58 静sem=0.48 acc=0.50 n=479
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=0, octave=4))@15/16", "DYCK_UNCLOSED:[('PL', SPitch(step='C', alter=0, octave=4)), ('PR', SPitch(step='G', alter=0, octave=4))]", 'TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PL:C4PR:C5 <|0.11|> 1/16c5E5 <|0.31|> 1/16e5C5 <|0.41|> 1/16c5E5 <|0.48|> 1/16e5C5 <|0.59|> 1/16c5E5 <|0.71|> 1/16e5C5 <|0.82|> 1/16c5E5 <|0.93|> 1/16e5C5', 'truncated': '|4/4k0PL:C4PR:C5 <|0.11|> 1/16c5E5 <|0.31|> 1/16e5C5 <|0.41|> 1/16c5E5 <|0.48|> 1/16e5C5 <|0.59|> 1/'}
  eval 汇总: parseable=0.02 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.52/前缀0.53 eotP0=0.0001
  eval 指标: parseable=0.02 amt_f1=0.0 omr_ned=0.9292694276407631 n_nasap=48 n_maestro=48

## eval @ step 25000 (2026-07-16 23:25:17)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.12 Δts=+0.17 真sem=0.65 静sem=0.53 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.06 真sem=0.72 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.02 Δts=+0.01 真sem=0.57 静sem=0.56 acc=0.49 n=479
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=0, octave=4))@13/16", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=0, octave=4))@2", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='C', alter=0, octave=4))@33/16", "DYCK_DOUBLE_ONSET:('PR', SPitch(step='C', alter=0, octave=5))@35/16"], 'raw': '|4/4k0PL:C4PR:C5 <|0.03|> 1/16c5E5 <|0.26|> 1/16e5C5 <|0.41|> 1/16c5E5 <|0.59|> 1/16e5C5 <|0.71|> 1/16c5E5 <|0.82|> 1/16e5C5 <|0.93|> 1/16c5E5 <|1.05|> 1/16e5C5', 'truncated': '|4/4k0PL:C4PR:C5 <|0.03|> 1/16c5E5 <|0.26|> 1/16e5C5 <|0.41|> 1/16c5E5 <|0.59|> 1/16e5C5 <|0.71|> 1/'}
  eval 汇总: parseable=0.02 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.55/前缀0.56 eotP0=0.0000
  eval 指标: parseable=0.02 amt_f1=0.0 omr_ned=0.9050445103857567 n_nasap=48 n_maestro=48

## eval @ step 26000 (2026-07-17 03:24:50)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.18 真sem=0.62 静sem=0.56 acc=0.53 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.12 真sem=0.72 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.00 Δts=+0.05 真sem=0.55 静sem=0.55 acc=0.48 n=479
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PR', SPitch(step='E', alter=0, octave=5))@1", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=0, octave=4))@17/16", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='G', alter=0, octave=5))@37/16", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=0, octave=4))@19/8"], 'raw': '|4/4k0PL:C4PR:C5 <|0.07|> 1/16c5E5 <|0.26|> 1/16e5C5 <|0.45|> 1/16c5E5 <|0.56|> 1/16e5C5 <|0.67|> 1/16c5E5 <|0.78|> 1/16e5C5 <|0.88|> 1/16c5E5 <|1.01|> 1/16e5C5', 'truncated': '|4/4k0PL:C4PR:C5 <|0.07|> 1/16c5E5 <|0.26|> 1/16e5C5 <|0.45|> 1/16c5E5 <|0.56|> 1/16e5C5 <|0.67|> 1/'}
  eval 汇总: parseable=0.02 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.53/前缀0.59 eotP0=0.0001
  eval 指标: parseable=0.02 amt_f1=0.0 omr_ned=0.912884834663626 n_nasap=48 n_maestro=48

## eval @ step 27000 (2026-07-17 06:05:44)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.11 Δts=+0.20 真sem=0.64 静sem=0.53 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.11 真sem=0.72 静sem=0.71 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.03 Δts=+0.08 真sem=0.56 静sem=0.53 acc=0.49 n=479
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='C', alter=0, octave=4))]", 'MEASURE_SUM:1 got 9/8 want 1', 'MEASURE_SUM:2 got 19/16 want 1', 'MEASURE_SUM:4 got 9/8 want 1'], 'raw': '|4/4k0PL:C4PR:E5 <|0.07|> 1/16e5D5 <|0.25|> 1/16d5E5 <|0.38|> 1/16e5D5 <|0.50|> 1/16d5E5 <|0.63|> 1/16e5D5 <|0.73|> 1/16d5E5 <|0.85|> 1/16e5D5 <|0.97|> 1/16d5E5', 'truncated': '|4/4k0PL:C4PR:E5 <|0.07|> 1/16e5D5 <|0.25|> 1/16d5E5 <|0.38|> 1/16e5D5 <|0.50|> 1/16d5E5 <|0.63|> 1/'}
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.55/前缀0.56 eotP0=0.0001
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.8808815866106734 n_nasap=48 n_maestro=48

## eval @ step 28000 (2026-07-17 08:46:43)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.10 Δts=+0.18 真sem=0.63 静sem=0.53 acc=0.54 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.03 真sem=0.72 静sem=0.70 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.02 Δts=+0.02 真sem=0.57 静sem=0.54 acc=0.48 n=479
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=0, octave=4))@15/16", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=0, octave=4))@51/16", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='C', alter=0, octave=4))@103/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='E', alter=0, octave=4))@13/2"], 'raw': '|4/4k0PL:C4PR:C5 <|0.02|> 1/16c5E5 <|0.23|> 1/16e5C5 <|0.39|> 1/16c5E5 <|0.56|> 1/16e5C5 <|0.67|> 1/16c5E5 <|0.77|> 1/16e5C5 <|0.92|> 1/16c5E5 <|1.08|> 1/16e5C5', 'truncated': '|4/4k0PL:C4PR:C5 <|0.02|> 1/16c5E5 <|0.23|> 1/16e5C5 <|0.39|> 1/16c5E5 <|0.56|> 1/16e5C5 <|0.67|> 1/'}
  eval 汇总: parseable=0.02 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.54/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.02 amt_f1=0.0 omr_ned=0.8884484711211778 n_nasap=48 n_maestro=48

## eval @ step 29000 (2026-07-17 11:30:18)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.07 Δts=+0.18 真sem=0.65 静sem=0.58 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.11 真sem=0.73 静sem=0.71 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.02 真sem=0.57 静sem=0.53 acc=0.49 n=479
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='C', alter=0, octave=4))]", 'MEASURE_SUM:0 got 17/16 want 1', 'MEASURE_SUM:1 got 21/16 want 1', 'MEASURE_SUM:2 got 19/16 want 1'], 'raw': '|4/4k0PL:C4PR:C5 <|0.01|> 1/16c5E5 <|0.21|> 1/16e5C5 <|0.32|> 1/16c5E5 <|0.42|> 1/16e5C5 <|0.53|> 1/16c5E5 <|0.63|> 1/16e5C5 <|0.73|> 1/16c5E5 <|0.84|> 1/16e5C5', 'truncated': '|4/4k0PL:C4PR:C5 <|0.01|> 1/16c5E5 <|0.21|> 1/16e5C5 <|0.32|> 1/16c5E5 <|0.42|> 1/16e5C5 <|0.53|> 1/'}
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.55/前缀0.53 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.0 omr_ned=0.8742775430124813 n_nasap=48 n_maestro=48

## eval @ step 30000 (2026-07-17 14:21:38)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.09 Δts=+0.20 真sem=0.68 静sem=0.59 acc=0.58 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.00 真sem=0.73 静sem=0.71 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.01 真sem=0.56 静sem=0.51 acc=0.48 n=479
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='C', alter=0, octave=4))]", 'TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PL:C4PR:C5 <|0.01|> 1/16c5E5 <|0.23|> 1/16e5C5 <|0.24|> 1/16c5E5 <|0.32|> 1/16e5C5 <|0.43|> 1/16c5E5 <|0.53|> 1/16e5C5 <|0.62|> 1/16c5E5 <|0.72|> 1/16e5C5', 'truncated': '|4/4k0PL:C4PR:C5 <|0.01|> 1/16c5E5 <|0.23|> 1/16e5C5 <|0.24|> 1/16c5E5 <|0.32|> 1/16e5C5 <|0.43|> 1/'}
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.58/前缀0.69 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.0 omr_ned=0.9102351654709496 n_nasap=48 n_maestro=48

## eval @ step 31000 (2026-07-17 17:34:45)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.15 Δts=+0.17 真sem=0.64 静sem=0.49 acc=0.54 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.08 真sem=0.73 静sem=0.71 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.06 Δts=+0.02 真sem=0.58 静sem=0.53 acc=0.50 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.25 Δts=+0.23 真sem=0.67 静sem=0.43 acc=0.62 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['MEASURE_SUM:3 got 9/8 want 1', 'MEASURE_SUM:8 got 7/8 want 1', 'MEASURE_SUM:13 got 9/8 want 1', 'MEASURE_SUM:19 got 7/8 want 1'], 'raw': '|4/4k0PR:C5 <|0.00|> 1/8c5E5 <|0.25|> 1/8e5C5 <|0.47|> 1/8c5E5 <|0.68|> 1/8e5C5 <|0.88|> 1/8c5 <|1.02|> 1/8C5 <|1.20|> 1/8c5 <|1.37|> |4/4k0B4 <|1.37|> 1/8b4G5 ', 'truncated': '|4/4k0PR:C5 <|0.00|> 1/8c5E5 <|0.25|> 1/8e5C5 <|0.47|> 1/8c5E5 <|0.68|> 1/8e5C5 <|0.88|> 1/8c5 <|1.0'}
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.54/前缀0.56 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.05520833333333333 omr_ned=0.9032767270935762 n_nasap=48 n_maestro=48

## eval @ step 32000 (2026-07-17 20:32:00)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.09 Δts=+0.17 真sem=0.65 静sem=0.56 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.03 真sem=0.72 静sem=0.71 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.02 真sem=0.57 静sem=0.53 acc=0.49 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.20 Δts=+0.20 真sem=0.67 静sem=0.46 acc=0.61 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='B', alter=0, octave=3))]", 'TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PL:C4PR:C5 <|0.01|> 1/16c5E5 <|0.21|> 1/16PL:c4B3PR:e5D5 <|0.40|> 1/16PL:b3C4PR:d5E5 <|0.51|> 1/16PL:c4B3PR:e5D5 <|0.62|> 1/16PL:b3A3PR:d5C5 <|0.72|> 1/16', 'truncated': '|4/4k0PL:C4PR:C5 <|0.01|> 1/16c5E5 <|0.21|> 1/16PL:c4B3PR:e5D5 <|0.40|> 1/16PL:b3C4PR:d5E5 <|0.51|> '}
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.55/前缀0.53 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.8824796908725986 n_nasap=48 n_maestro=48

## eval @ step 33000 (2026-07-17 23:35:40)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.09 Δts=+0.15 真sem=0.66 静sem=0.57 acc=0.56 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.10 真sem=0.72 静sem=0.71 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.03 Δts=+0.02 真sem=0.56 静sem=0.54 acc=0.49 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.16 真sem=0.68 静sem=0.50 acc=0.62 n=724
  eval 时限 1200s 用尽,截断于 41/48(指标按已评样本)
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=0, octave=3))@93/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@27/2", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='F', alter=0, octave=3))@29/2", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='C', alter=0, octave=3))@31/2"], 'raw': '|4/4k0PL:A3PR:A4 <|0.01|> 1/8PL:a3G3 <|0.31|> 1/8g3F3 <|0.50|> 1/8f3E3 <|0.69|> 1/8e3D3 <|0.88|> 1/8d3C3 <|1.04|> 1/8c3PR:a4 <|1.27|> |4/4k0PL:D3PR:A4 <|1.27|> ', 'truncated': '|4/4k0PL:A3PR:A4 <|0.01|> 1/8PL:a3G3 <|0.31|> 1/8g3F3 <|0.50|> 1/8f3E3 <|0.69|> 1/8e3D3 <|0.88|> 1/8'}
  eval 汇总: parseable=0.05 empty=0.9512195121951219 n=41 样本0='|4/4k0' 探针acc=0.56/前缀0.56 eotP0=0.0000
  eval 指标: parseable=0.05 amt_f1=0.0 omr_ned=0.9553463854177169 n_nasap=41 n_maestro=48

## eval @ step 34000 (2026-07-18 02:37:46)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.10 Δts=+0.16 真sem=0.66 静sem=0.56 acc=0.56 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.14 真sem=0.73 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=-0.01 真sem=0.57 静sem=0.54 acc=0.49 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.20 Δts=+0.19 真sem=0.68 静sem=0.47 acc=0.62 n=724
  eval 时限 1200s 用尽,截断于 39/48(指标按已评样本)
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='F', alter=0, octave=3)), ('PL', SPitch(step='G', alter=0, octave=3))]", 'MEASURE_SUM:0 got 17/16 want 1', 'MEASURE_SUM:1 got 17/16 want 1', 'MEASURE_SUM:3 got 17/16 want 1'], 'raw': '|4/4k0PL:A3PR:C4 <|0.00|> 1/16c4D4 <|0.25|> 1/16d4E4 <|0.38|> 1/16PL:a3F3PR:e4F4 <|0.50|> 1/16f4E4 <|0.63|> 1/16e4F4 <|0.83|> 1/16f4G4 <|1.00|> 1/16PL:f3E3PR:g4', 'truncated': '|4/4k0PL:A3PR:C4 <|0.00|> 1/16c4D4 <|0.25|> 1/16d4E4 <|0.38|> 1/16PL:a3F3PR:e4F4 <|0.50|> 1/16f4E4 <'}
  eval 汇总: parseable=0.00 empty=1.0 n=39 样本0='|4/4k0' 探针acc=0.56/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.0 omr_ned=None n_nasap=39 n_maestro=48

## eval @ step 35000 (2026-07-18 05:39:57)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.13 真sem=0.65 静sem=0.60 acc=0.54 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.04 真sem=0.73 静sem=0.71 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.03 Δts=+0.01 真sem=0.58 静sem=0.54 acc=0.49 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.14 Δts=+0.22 真sem=0.67 静sem=0.53 acc=0.62 n=724
  eval 时限 1200s 用尽,截断于 44/48(指标按已评样本)
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PR', SPitch(step='C', alter=0, octave=4))@7/4", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='E', alter=0, octave=3))@19/4", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='E', alter=0, octave=3))@23/4", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='E', alter=0, octave=3))@41/4"], 'raw': '|4/4k0PL:A2C3E3PR:C4 <|0.00|> 1/4PL:a2c3e3PR:c4 <|0.50|> 1/4PL:A2C3E3PR:C4 <|0.68|> 1/4PL:a2c3e3PR:c4 <|0.89|> |4/4k0PL:A2C3E3PR:C4 <|0.89|> 1/4PL:a2c3e3A2C3E3P', 'truncated': '|4/4k0PL:A2C3E3PR:C4 <|0.00|> 1/4PL:a2c3e3PR:c4 <|0.50|> 1/4PL:A2C3E3PR:C4 <|0.68|> 1/4PL:a2c3e3PR:c'}
  eval 汇总: parseable=0.02 empty=0.9772727272727273 n=44 样本0='|4/4k0' 探针acc=0.54/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.02 amt_f1=0.0 omr_ned=0.8576051779935275 n_nasap=44 n_maestro=48

## eval @ step 36000 (2026-07-18 08:40:51)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.09 Δts=+0.11 真sem=0.67 静sem=0.58 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.06 真sem=0.72 静sem=0.71 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.02 真sem=0.58 静sem=0.53 acc=0.49 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.22 真sem=0.68 静sem=0.50 acc=0.62 n=724
  eval 时限 1200s 用尽,截断于 43/48(指标按已评样本)
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PR', SPitch(step='G', alter=0, octave=3))@0", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='C', alter=0, octave=4))@0", "DYCK_UNCLOSED:[('PL', SPitch(step='C', alter=0, octave=4)), ('PR', SPitch(step='C', alter=0, octave=5))]", 'TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PL:C4PR:C5 <|0.00|> <|0.00|> g3c4 <|0.22|> <|0.22|> <|0.22|> <|0.44|> <|0.44|> <|0.44|> <|0.44|> <|0.44|> <|0.44|> <|0.44|> <|0.44|> <|0.44|> <|0.44|> <|0', 'truncated': '|4/4k0PL:C4PR:C5 <|0.00|> <|0.00|> g3c4 <|0.22|> <|0.22|> <|0.22|> <|0.44|> <|0.44|> <|0.44|> <|0.44'}
  eval 汇总: parseable=0.05 empty=0.9534883720930233 n=43 样本0='|4/4k0' 探针acc=0.55/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.05 amt_f1=0.0 omr_ned=0.881825741643517 n_nasap=43 n_maestro=48

## eval @ step 37000 (2026-07-18 11:42:05)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.09 Δts=+0.09 真sem=0.64 静sem=0.55 acc=0.52 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=-0.01 真sem=0.73 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.03 真sem=0.57 静sem=0.53 acc=0.49 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.27 Δts=+0.19 真sem=0.72 静sem=0.44 acc=0.65 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['MEASURE_SUM:2 got 7/8 want 1'], 'raw': '|4/4k0PL:C4PR:C5 <|0.00|> 1/8PL:c4D4PR:c5F5 <|0.34|> 1/8PL:d4C4PR:f5E5 <|0.58|> 1/8PL:c4B3PR:e5D5 <|0.77|> 1/8PL:b3A3PR:d5C5 <|0.96|> 1/8PL:a3G3PR:c5B4 <|1.16|>', 'truncated': '|4/4k0PL:C4PR:C5 <|0.00|> 1/8PL:c4D4PR:c5F5 <|0.34|> 1/8PL:d4C4PR:f5E5 <|0.58|> 1/8PL:c4B3PR:e5D5 <|'}
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.52/前缀0.69 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.8613898543191959 n_nasap=48 n_maestro=48

## eval @ step 38000 (2026-07-18 14:38:42)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.06 Δts=+0.09 真sem=0.67 静sem=0.61 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.03 真sem=0.72 静sem=0.72 acc=0.61 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.06 真sem=0.57 静sem=0.53 acc=0.50 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.14 真sem=0.68 静sem=0.48 acc=0.62 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='A', alter=0, octave=3)), ('PR', SPitch(step='D', alter=0, octave=5))]", 'TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PL:C4PR:C5 <|0.01|> 1/8PL:c4B3PR:c5B4 <|0.22|> 1/8PL:b3A3PR:b4A4 <|0.44|> 1/8PL:a3G3PR:a4G4 <|0.63|> 1/8PL:g3A3PR:g4A4 <|0.84|> 1/8PL:a3B3PR:a4B4 <|1.00|>', 'truncated': '|4/4k0PL:C4PR:C5 <|0.01|> 1/8PL:c4B3PR:c5B4 <|0.22|> 1/8PL:b3A3PR:b4A4 <|0.44|> 1/8PL:a3G3PR:a4G4 <|'}
  eval 汇总: parseable=0.08 empty=0.9166666666666666 n=48 样本0='|4/4k0' 探针acc=0.55/前缀0.72 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.8882317653461482 n_nasap=48 n_maestro=48

## eval @ step 39000 (2026-07-18 17:36:24)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.04 Δts=+0.06 真sem=0.65 静sem=0.62 acc=0.52 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.04 真sem=0.73 静sem=0.72 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.05 真sem=0.58 静sem=0.53 acc=0.50 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.24 真sem=0.68 静sem=0.50 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PR:C4 <|0.01|> 1/8c4E4 <|0.23|> 1/8e4C4 <|0.42|> 1/8c4E4 <|0.53|> 1/8e4C4 <|0.65|> 1/8c4E4 <|0.79|> 1/8e4C4 <|0.97|> 1/8c4 <|1.10|> |4/4k0B3 <|1.10|> 1/8b', 'truncated': '|4/4k0PR:C4 <|0.01|> 1/8c4E4 <|0.23|> 1/8e4C4 <|0.42|> 1/8c4E4 <|0.53|> 1/8e4C4 <|0.65|> 1/8c4E4 <|0'}
  eval 汇总: parseable=0.10 empty=0.8958333333333334 n=48 样本0='|4/4k0' 探针acc=0.52/前缀0.56 eotP0=0.0000
  eval 指标: parseable=0.10 amt_f1=0.0 omr_ned=0.8825374082552659 n_nasap=48 n_maestro=48

## eval @ step 40000 (2026-07-18 20:34:10)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.04 Δts=+0.12 真sem=0.66 静sem=0.62 acc=0.54 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.00 真sem=0.72 静sem=0.71 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.08 Δts=+0.03 真sem=0.59 静sem=0.52 acc=0.51 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.16 Δts=+0.17 真sem=0.69 静sem=0.53 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['MEASURE_SUM:3 got 7/8 want 1', 'MEASURE_SUM:4 got 7/8 want 1', 'MEASURE_SUM:5 got 7/8 want 1', 'MEASURE_SUM:6 got 7/8 want 1'], 'raw': '|4/4k0PR:C4 <|0.00|> 1/8c4E4 <|0.27|> 1/8e4C4 <|0.48|> 1/8c4E4 <|0.64|> 1/8e4C4 <|0.81|> 1/8c4E4 <|0.99|> 1/8e4C4 <|1.14|> 1/8c4 <|1.30|> |4/4k0B3 <|1.30|> 1/8b', 'truncated': '|4/4k0PR:C4 <|0.00|> 1/8c4E4 <|0.27|> 1/8e4C4 <|0.48|> 1/8c4E4 <|0.64|> 1/8e4C4 <|0.81|> 1/8c4E4 <|0'}
  eval 汇总: parseable=0.08 empty=0.9166666666666666 n=48 样本0='|4/4k0' 探针acc=0.54/前缀0.59 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.9184108003793332 n_nasap=48 n_maestro=48

## eval @ step 41000 (2026-07-18 23:30:11)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.03 Δts=+0.14 真sem=0.66 静sem=0.63 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.01 Δts=+0.04 真sem=0.72 静sem=0.72 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.01 真sem=0.58 静sem=0.54 acc=0.50 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.15 Δts=+0.14 真sem=0.69 静sem=0.54 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PL:C4PR:E5 <|0.01|> 1/8PL:c4B3PR:e5D5 <|0.28|> 1/8PL:b3A3PR:d5C5 <|0.48|> 1/8PL:a3G3PR:c5B4 <|0.70|> 1/8PL:g3A3PR:b4C5 <|0.89|> 1/8PL:a3B3PR:c5D5 <|1.07|>', 'truncated': '|4/4k0PL:C4PR:E5 <|0.01|> 1/8PL:c4B3PR:e5D5 <|0.28|> 1/8PL:b3A3PR:d5C5 <|0.48|> 1/8PL:a3G3PR:c5B4 <|'}
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.55/前缀0.56 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.11270833333333334 omr_ned=0.890731781556004 n_nasap=48 n_maestro=48

## eval @ step 42000 (2026-07-19 02:25:08)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.06 Δts=+0.12 真sem=0.71 静sem=0.65 acc=0.58 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.01 Δts=+0.07 真sem=0.71 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.06 Δts=+0.01 真sem=0.59 静sem=0.54 acc=0.50 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.16 Δts=+0.18 真sem=0.69 静sem=0.52 acc=0.64 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['MEASURE_SUM:2 got 9/8 want 1', 'MEASURE_SUM:3 got 9/8 want 1', 'MEASURE_SUM:4 got 7/8 want 1', 'MEASURE_SUM:5 got 7/8 want 1'], 'raw': '|4/4k0PL:C4PR:C5 <|0.00|> 1/8PL:c4B3PR:c5B4 <|0.37|> 1/8PL:b3A3PR:b4C5 <|0.63|> 1/8PL:a3B3PR:c5D5 <|0.81|> 1/8PL:b3C4PR:d5E5 <|0.97|> 1/8PL:c4B3PR:e5F5 <|1.14|>', 'truncated': '|4/4k0PL:C4PR:C5 <|0.00|> 1/8PL:c4B3PR:c5B4 <|0.37|> 1/8PL:b3A3PR:b4C5 <|0.63|> 1/8PL:a3B3PR:c5D5 <|'}
  eval 汇总: parseable=0.10 empty=0.8958333333333334 n=48 样本0='|4/4k0' 探针acc=0.58/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.10 amt_f1=0.0 omr_ned=0.8995695280130402 n_nasap=48 n_maestro=48

## eval @ step 43000 (2026-07-19 05:20:27)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.06 Δts=+0.12 真sem=0.67 静sem=0.62 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.01 Δts=+0.01 真sem=0.71 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.03 真sem=0.58 静sem=0.53 acc=0.50 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.08 真sem=0.69 静sem=0.51 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['MEASURE_SUM:4 got 9/8 want 1', 'MEASURE_SUM:5 got 7/8 want 1', 'MEASURE_SUM:8 got 9/8 want 1', 'MEASURE_SUM:16 got 7/8 want 1'], 'raw': '|4/4k0PL:C4PR:E4 <|0.02|> 1/8PL:c4A3PR:e4F4 <|0.32|> 1/8PL:a3G3PR:f4E4 <|0.55|> 1/8PL:g3F3PR:e4F4 <|0.78|> 1/8PL:f3E3PR:f4E4 <|0.98|> 1/8PL:e3D3PR:e4D4 <|1.17|>', 'truncated': '|4/4k0PL:C4PR:E4 <|0.02|> 1/8PL:c4A3PR:e4F4 <|0.32|> 1/8PL:a3G3PR:f4E4 <|0.55|> 1/8PL:g3F3PR:e4F4 <|'}
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.55/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.0 omr_ned=0.8466225477379711 n_nasap=48 n_maestro=48

## eval @ step 44000 (2026-07-19 08:17:16)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.06 Δts=+0.11 真sem=0.71 静sem=0.64 acc=0.58 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.01 Δts=-0.03 真sem=0.72 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.07 Δts=+0.02 真sem=0.60 静sem=0.53 acc=0.51 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.20 Δts=+0.12 真sem=0.70 静sem=0.50 acc=0.64 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@97/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='G', alter=0, octave=2))@119/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@67/4", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@75/4"], 'raw': '|4/4k0PL:G3PR:E4 <|0.00|> 1/8PL:g3A3PR:e4C4 <|0.39|> 1/8PL:a3B3PR:c4 <|0.63|> 1/8PL:b3A3 <|0.85|> 1/8a3G3 <|1.04|> 1/8g3F3 <|1.23|> 1/8f3E3 <|1.41|> 1/8e3 <|1.5', 'truncated': '|4/4k0PL:G3PR:E4 <|0.00|> 1/8PL:g3A3PR:e4C4 <|0.39|> 1/8PL:a3B3PR:c4 <|0.63|> 1/8PL:b3A3 <|0.85|> 1/'}
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.58/前缀0.72 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.9521121361443561 n_nasap=48 n_maestro=48

## eval @ step 45000 (2026-07-19 11:13:02)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.01 Δts=+0.14 真sem=0.67 静sem=0.67 acc=0.56 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.01 真sem=0.72 静sem=0.70 acc=0.61 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.09 Δts=+0.01 真sem=0.62 静sem=0.53 acc=0.53 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.23 Δts=+0.18 真sem=0.69 静sem=0.46 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PR', SPitch(step='F', alter=0, octave=3))@63/4", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='D', alter=0, octave=3))@135/8", "DYCK_UNCLOSED:[('PR', SPitch(step='A', alter=0, octave=3)), ('PR', SPitch(step='F', alter=0, octave=3))]", 'MEASURE_SUM:1 got 9/8 want 1'], 'raw': '|4/4k0PL:C4PR:E4 <|0.04|> 1/8PL:c4B3PR:e4D4 <|0.26|> 1/8PL:b3A3PR:d4C4 <|0.47|> 1/8PL:a3G3PR:c4B3 <|0.66|> 1/8PL:g3F3PR:b3C4 <|0.86|> 1/8PL:f3E3PR:c4B3 <|1.04|>', 'truncated': '|4/4k0PL:C4PR:E4 <|0.04|> 1/8PL:c4B3PR:e4D4 <|0.26|> 1/8PL:b3A3PR:d4C4 <|0.47|> 1/8PL:a3G3PR:c4B3 <|'}
  eval 汇总: parseable=0.10 empty=0.8958333333333334 n=48 样本0='|4/4k0' 探针acc=0.56/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.10 amt_f1=0.0 omr_ned=0.8354282764645946 n_nasap=48 n_maestro=48

## eval @ step 46000 (2026-07-19 14:14:52)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.08 真sem=0.70 静sem=0.65 acc=0.57 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.03 真sem=0.71 静sem=0.71 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.03 真sem=0.60 静sem=0.55 acc=0.52 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.15 Δts=+0.17 真sem=0.68 静sem=0.53 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='C', alter=0, octave=3))@89/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=0, octave=3))@105/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@15", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='C', alter=0, octave=3))@129/8"], 'raw': '|4/4k0PL:G3PR:G4 <|0.00|> 1/8PL:g3A3 <|0.28|> 1/8a3G3 <|0.49|> 1/8g3F3 <|0.68|> 1/8f3E3 <|0.85|> 1/8e3D3 <|0.98|> 1/8d3C3 <|1.16|> 1/8c3B2 <|1.30|> 1/8b2PR:g4 <', 'truncated': '|4/4k0PL:G3PR:G4 <|0.00|> 1/8PL:g3A3 <|0.28|> 1/8a3G3 <|0.49|> 1/8g3F3 <|0.68|> 1/8f3E3 <|0.85|> 1/8'}
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.57/前缀0.69 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.8255290696004955 n_nasap=48 n_maestro=48

## eval @ step 47000 (2026-07-19 17:10:57)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.11 Δts=+0.05 真sem=0.70 静sem=0.59 acc=0.56 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.03 真sem=0.72 静sem=0.71 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.07 Δts=+0.06 真sem=0.62 静sem=0.55 acc=0.53 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.12 真sem=0.68 静sem=0.51 acc=0.62 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PR', SPitch(step='E', alter=0, octave=4))]", 'MEASURE_SUM:1 got 7/8 want 1', 'MEASURE_SUM:3 got 7/8 want 1', 'MEASURE_SUM:5 got 9/8 want 1'], 'raw': '|4/4k0PL:G3PR:E4 <|0.09|> 1/8PL:g3A3 <|0.32|> 1/8a3G3 <|0.50|> 1/8g3A3 <|0.67|> 1/8a3G3 <|0.82|> 1/8g3A3 <|0.94|> 1/8a3G3 <|1.05|> 1/8g3A3 <|1.17|> 1/8a3 <|1.29', 'truncated': '|4/4k0PL:G3PR:E4 <|0.09|> 1/8PL:g3A3 <|0.32|> 1/8a3G3 <|0.50|> 1/8g3A3 <|0.67|> 1/8a3G3 <|0.82|> 1/8'}
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.56/前缀0.69 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.9339543692741368 n_nasap=48 n_maestro=48

## eval @ step 48000 (2026-07-19 20:05:24)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.09 Δts=+0.11 真sem=0.68 静sem=0.59 acc=0.56 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.01 Δts=+0.04 真sem=0.72 静sem=0.73 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.01 真sem=0.60 静sem=0.56 acc=0.52 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.20 Δts=+0.17 真sem=0.69 静sem=0.49 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=3))@11/2", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=3))@13/2", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=3))@15/2", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=3))@33/4"], 'raw': '|4/4k0PL:G3PR:G4 <|0.04|> 1/8PL:g3A3 <|0.23|> 1/8a3G3 <|0.47|> 1/8g3A3 <|0.65|> 1/8a3G3 <|0.83|> 1/8g3A3 <|0.93|> 1/8a3PR:g4 <|1.08|> |4/4k0PL:G3 <|1.08|> 1/8g3', 'truncated': '|4/4k0PL:G3PR:G4 <|0.04|> 1/8PL:g3A3 <|0.23|> 1/8a3G3 <|0.47|> 1/8g3A3 <|0.65|> 1/8a3G3 <|0.83|> 1/8'}
  eval 汇总: parseable=0.08 empty=0.9166666666666666 n=48 样本0='|4/4k0' 探针acc=0.56/前缀0.72 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.9131696769978843 n_nasap=48 n_maestro=48

## eval @ step 49000 (2026-07-19 22:59:41)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.17 Δts=+0.11 真sem=0.72 静sem=0.55 acc=0.59 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.04 真sem=0.72 静sem=0.71 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.07 Δts=+0.03 真sem=0.62 静sem=0.55 acc=0.53 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.24 Δts=+0.18 真sem=0.71 静sem=0.47 acc=0.65 n=724
  eval 样本预测[0]: '|4/4k-1PL:D2A2D3PR:A3 1/8a3D4 1/8d4E4 1/8e4F4 1/8f4E4 1/8e4D4 1/8d4C#4 1/8c#4D4 1/8PL:d2a2d3PR:d4 |4/4k-1PL:D2A2D3PR:A3 1/8a3D4 1/8d4E4 1/8e4D4 1/8d4C#4 1/8c#4D'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@11/2", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@51/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@29/4", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='C', alter=0, octave=3))@63/8"], 'raw': '|4/4k0PL:G3PR:E4 <|0.02|> 1/8PL:g3A3PR:e4 <|0.32|> 1/8PL:a3G3 <|0.51|> 1/8g3A3 <|0.72|> 1/8a3G3 <|0.93|> 1/8g3F3 <|1.12|> 1/8f3E3 <|1.31|> 1/8e3 <|1.48|> |4/4k0', 'truncated': '|4/4k0PL:G3PR:E4 <|0.02|> 1/8PL:g3A3PR:e4 <|0.32|> 1/8PL:a3G3 <|0.51|> 1/8g3A3 <|0.72|> 1/8a3G3 <|0.'}
  eval 汇总: parseable=0.08 empty=0.9166666666666666 n=48 样本0='|4/4k-1PL:D2A2D3PR:A3 1/8a3D4 1/8d4E4 1/8e4F4 1/8f4E4 1/8e4D' 探针acc=0.59/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.8355726196897306 n_nasap=48 n_maestro=48

## eval @ step 50000 (2026-07-20 01:53:51)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.11 Δts=+0.16 真sem=0.70 静sem=0.59 acc=0.60 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.07 真sem=0.72 静sem=0.70 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.06 Δts=+0.01 真sem=0.60 静sem=0.54 acc=0.52 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.14 Δts=+0.17 真sem=0.68 静sem=0.54 acc=0.62 n=724
  eval 样本预测[0]: '|4/4k-1PL:D3F3A3PR:F4 1/8f4E4 1/8e4D4 1/8d4C#4 1/8c#4D4 1/8d4C#4 1/8c#4D4 1/8PL:d3f3a3PR:d4 |4/4k-1PL:C#3E3A3PR:C#4 1/8c#4E4 1/8e4C#4 1/8c#4E4 1/8e4C#4 1/8c#4E4'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=0, octave=3))@11/2", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=0, octave=3))@107/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='F', alter=0, octave=3))@63/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=0, octave=3))@141/16"], 'raw': '|4/4k0PL:A3PR:A4 <|0.00|> 1/16PL:a3G3 <|0.26|> 1/16g3F3 <|0.39|> 1/16f3E3 <|0.52|> 1/16e3D3 <|0.63|> 1/16d3C3 <|0.75|> 1/16c3B2 <|0.88|> 1/16b2A2 <|0.99|> 1/16a', 'truncated': '|4/4k0PL:A3PR:A4 <|0.00|> 1/16PL:a3G3 <|0.26|> 1/16g3F3 <|0.39|> 1/16f3E3 <|0.52|> 1/16e3D3 <|0.63|>'}
  eval 汇总: parseable=0.10 empty=0.8958333333333334 n=48 样本0='|4/4k-1PL:D3F3A3PR:F4 1/8f4E4 1/8e4D4 1/8d4C#4 1/8c#4D4 1/8d' 探针acc=0.60/前缀0.69 eotP0=0.0000
  eval 指标: parseable=0.10 amt_f1=0.0 omr_ned=0.8809060079117771 n_nasap=48 n_maestro=48

## eval @ step 51000 (2026-07-20 04:47:05)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.12 Δts=+0.09 真sem=0.74 静sem=0.62 acc=0.60 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.01 真sem=0.72 静sem=0.72 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.10 Δts=-0.01 真sem=0.64 静sem=0.54 acc=0.54 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.10 真sem=0.69 静sem=0.51 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['MEASURE_SUM:2 got 9/8 want 1', 'MEASURE_SUM:10 got 9/8 want 1', 'MEASURE_SUM:13 got 9/8 want 1', 'MEASURE_SUM:14 got 9/8 want 1'], 'raw': '|4/4k0PL:G3PR:G4 <|0.00|> 1/8PL:g3A3 <|0.27|> 1/8a3G3 <|0.47|> 1/8g3F3 <|0.66|> 1/8f3E3 <|0.80|> 1/8e3D3 <|0.92|> 1/8d3C3 <|1.05|> 1/8c3B2 <|1.17|> 1/8b2PR:g4 <', 'truncated': '|4/4k0PL:G3PR:G4 <|0.00|> 1/8PL:g3A3 <|0.27|> 1/8a3G3 <|0.47|> 1/8g3F3 <|0.66|> 1/8f3E3 <|0.80|> 1/8'}
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.60/前缀0.72 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.0 omr_ned=0.8542797506930708 n_nasap=48 n_maestro=48

## eval @ step 52000 (2026-07-20 07:40:30)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.12 Δts=+0.23 真sem=0.71 静sem=0.60 acc=0.61 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.01 真sem=0.72 静sem=0.71 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.02 真sem=0.65 静sem=0.52 acc=0.55 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.15 Δts=+0.08 真sem=0.68 静sem=0.54 acc=0.62 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=0, octave=3))@57/8", "DYCK_UNCLOSED:[('PR', SPitch(step='C', alter=0, octave=5))]", 'MEASURE_SUM:0 got 9/8 want 1', 'MEASURE_SUM:1 got 19/16 want 1'], 'raw': '|4/4k0PL:E3PR:C5 <|0.02|> 1/16PL:e3G3 <|0.26|> 1/16g3E3 <|0.43|> 1/16e3G3 <|0.53|> 1/16g3E3 <|0.63|> 1/16e3G3 <|0.78|> 1/16g3E3 <|0.89|> 1/16e3G3 <|1.02|> 1/16g', 'truncated': '|4/4k0PL:E3PR:C5 <|0.02|> 1/16PL:e3G3 <|0.26|> 1/16g3E3 <|0.43|> 1/16e3G3 <|0.53|> 1/16g3E3 <|0.63|>'}
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.61/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.0 omr_ned=0.892668305359621 n_nasap=48 n_maestro=48

## eval @ step 53000 (2026-07-20 10:45:08)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.23 Δts=+0.19 真sem=0.76 静sem=0.53 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.00 Δts=+0.03 真sem=0.72 静sem=0.72 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.10 Δts=-0.05 真sem=0.66 静sem=0.56 acc=0.56 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.22 Δts=+0.12 真sem=0.70 静sem=0.48 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_GiacomelliN04M_861c59b0_016]: '|4/4k#2PR:D5 3/16d5 |4/4k#2'
  eval 同样本参照:              '|3/4k#1PL:D#5PR:A5C6 1/4PL:d#5PR:a5c6 1/4E5E6 1/4 |3/4k#1PL:G2E3B3 3/8PR:e5e6D#5D#6 1/8d#5d#6E5E6 1/4PL:g2e3b3PR:e5e6 |3/4k#1PL:A2PR:C4E4F#4 1/2PL:a2A#2PR:c4e4f'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='G', alter=0, octave=2))@47/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=0, octave=2))@61/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='C', alter=0, octave=3))@137/16", "DYCK_UNCLOSED:[('PR', SPitch(step='C', alter=0, octave=5))]"], 'raw': '|4/4k0PL:E3PR:C5 <|0.02|> 1/16PL:e3G3 <|0.23|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.45|> 1/16g3E3 <|0.56|> 1/16e3G3 <|0.67|> 1/16g3E3 <|0.82|> 1/16e3G3 <|0.92|> 1/16g', 'truncated': '|4/4k0PL:E3PR:C5 <|0.02|> 1/16PL:e3G3 <|0.23|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.45|> 1/16g3E3 <|0.56|>'}
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.64/前缀0.59 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.9508553955434704 n_nasap=48 n_maestro=48

## eval @ step 55000 (2026-07-20 17:29:59)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.26 Δts=+0.14 真sem=0.73 静sem=0.48 acc=0.60 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=-0.02 真sem=0.72 静sem=0.72 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.14 Δts=+0.01 真sem=0.65 静sem=0.51 acc=0.56 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.26 Δts=+0.18 真sem=0.70 静sem=0.44 acc=0.64 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/2g3F#3 1/2f#3 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='E', alter=0, octave=3))@27/4", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='G', alter=0, octave=3))@27/4", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='E', alter=0, octave=3))@113/16", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='G', alter=0, octave=3))@113/16"], 'raw': '|4/4k0PL:E3PR:E5 <|0.00|> 1/16PL:e3G3 <|0.11|> 1/16g3E3 <|0.22|> 1/16e3G3 <|0.34|> 1/16g3E3 <|0.45|> 1/16e3G3 <|0.53|> 1/16g3E3 <|0.63|> 1/16e3G3 <|0.73|> 1/16g', 'truncated': '|4/4k0PL:E3PR:E5 <|0.00|> 1/16PL:e3G3 <|0.11|> 1/16g3E3 <|0.22|> 1/16e3G3 <|0.34|> 1/16g3E3 <|0.45|>'}
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.60/前缀0.69 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.0 omr_ned=0.8630808886235095 n_nasap=48 n_maestro=48

## eval @ step 56000 (2026-07-20 20:34:50)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.22 Δts=+0.22 Δpitch=+0.44 真sem=0.75 静sem=0.53 真pitch=0.71 acc=0.63 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.03 Δpitch=-0.01 真sem=0.72 静sem=0.72 真pitch=0.17 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.03 Δpitch=+0.28 真sem=0.65 静sem=0.53 真pitch=0.49 acc=0.56 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.20 Δts=+0.17 Δpitch=+0.24 真sem=0.70 静sem=0.50 真pitch=0.77 acc=0.64 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/2g3A3 1/2a3 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='G', alter=0, octave=2))@45/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='G', alter=0, octave=2))@15/4", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=0, octave=2))@91/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=0, octave=2))@61/8"], 'raw': '|4/4k0PL:E3PR:E4 <|0.00|> 1/16PL:e3G3 <|0.23|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.53|> 1/16g3E3 <|0.63|> 1/16e3G3 <|0.76|> 1/16g3E3 <|0.89|> 1/16e3G3 <|1.00|> 1/16g', 'truncated': '|4/4k0PL:E3PR:E4 <|0.00|> 1/16PL:e3G3 <|0.23|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.53|> 1/16g3E3 <|0.63|>'}
  eval 拒因(样本数): 兜底=45 通过=3 /共48
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.63/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.34229166666666666 omr_ned=0.8897009810217664 n_nasap=48 n_maestro=48

## eval @ step 57000 (2026-07-20 23:36:46)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.31 Δts=+0.19 Δpitch=+0.60 真sem=0.75 静sem=0.44 真pitch=0.70 acc=0.62 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.01 Δts=+0.03 Δpitch=-0.06 真sem=0.72 静sem=0.73 真pitch=0.17 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.18 Δts=+0.07 Δpitch=+0.49 真sem=0.67 静sem=0.50 真pitch=0.56 acc=0.58 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.28 Δts=+0.24 Δpitch=+0.32 真sem=0.70 静sem=0.42 真pitch=0.74 acc=0.64 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/4g3A3 1/4a3 1/4A3 1/4a3 |4/4k#2G3 1/4g3A3 1/4a3 1/4A3 1/4a3 |4/4k#2G3 1/4g3A3 1/4a3 1/4A3 1/4a3 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PR', SPitch(step='G', alter=0, octave=4))]", 'MEASURE_SUM:0 got 9/8 want 1', 'MEASURE_SUM:1 got 9/8 want 1', 'MEASURE_SUM:2 got 9/8 want 1'], 'raw': '|4/4k0PL:E3PR:G4 <|0.00|> 1/16PL:e3G3 <|0.28|> 1/16g3E3 <|0.37|> 1/16e3G3 <|0.45|> 1/16g3E3 <|0.54|> 1/16e3G3 <|0.65|> 1/16g3E3 <|0.78|> 1/16e3G3 <|0.89|> 1/16g', 'truncated': '|4/4k0PL:E3PR:G4 <|0.00|> 1/16PL:e3G3 <|0.28|> 1/16g3E3 <|0.37|> 1/16e3G3 <|0.45|> 1/16g3E3 <|0.54|>'}
  eval 拒因(样本数): 兜底=44 通过=4 /共48
  eval 汇总: parseable=0.08 empty=0.9166666666666666 n=48 样本0='|4/4k0' 探针acc=0.62/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.8864373791752135 n_nasap=48 n_maestro=48

## eval @ step 58000 (2026-07-21 02:40:00)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.27 Δts=+0.29 Δpitch=+0.58 真sem=0.76 静sem=0.49 真pitch=0.71 acc=0.65 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.04 Δpitch=-0.02 真sem=0.72 静sem=0.72 真pitch=0.15 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.16 Δts=+0.02 Δpitch=+0.36 真sem=0.67 静sem=0.51 真pitch=0.51 acc=0.57 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.27 Δts=+0.17 Δpitch=+0.31 真sem=0.72 静sem=0.44 真pitch=0.76 acc=0.65 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=0, octave=2))@31/16", "DYCK_UNCLOSED:[('PR', SPitch(step='E', alter=0, octave=4))]", 'MEASURE_SUM:0 got 17/16 want 1', 'MEASURE_SUM:1 got 7/8 want 1'], 'raw': '|4/4k0PL:E3PR:E4 <|0.00|> 1/16PL:e3G3 <|0.25|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.45|> 1/16g3E3 <|0.53|> 1/16e3G3 <|0.65|> 1/16g3E3 <|0.78|> 1/16e3G3 <|0.89|> 1/16g', 'truncated': '|4/4k0PL:E3PR:E4 <|0.00|> 1/16PL:e3G3 <|0.25|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.45|> 1/16g3E3 <|0.53|>'}
  eval 拒因(样本数): 兜底=46 通过=2 /共48
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.65/前缀0.59 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.8972751501406332 n_nasap=48 n_maestro=48

## eval @ step 59000 (2026-07-21 05:42:07)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.31 Δts=+0.34 Δpitch=+0.60 真sem=0.75 静sem=0.44 真pitch=0.69 acc=0.66 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.01 Δpitch=-0.02 真sem=0.73 静sem=0.72 真pitch=0.19 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.18 Δts=+0.05 Δpitch=+0.33 真sem=0.67 静sem=0.49 真pitch=0.49 acc=0.57 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.28 Δts=+0.21 Δpitch=+0.32 真sem=0.70 静sem=0.42 真pitch=0.76 acc=0.64 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/4g3A3 1/4a3 1/4A3 1/4a3 |4/4k#2G3 1/4g3A3 1/4a3 1/4A3 1/4a3 |4/4k#2G3 1/4g3A3 1/4a3 1/4A3 1/4a3 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='G', alter=0, octave=3)), ('PR', SPitch(step='E', alter=0, octave=4))]", 'MEASURE_SUM:0 got 17/16 want 1', 'MEASURE_SUM:1 got 9/8 want 1', 'MEASURE_SUM:2 got 19/16 want 1'], 'raw': '|4/4k0PL:E3PR:E4 <|0.00|> 1/16PL:e3G3 <|0.22|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.50|> 1/16g3E3 <|0.63|> 1/16e3G3 <|0.75|> 1/16g3E3 <|0.87|> 1/16e3G3 <|0.96|> 1/16g', 'truncated': '|4/4k0PL:E3PR:E4 <|0.00|> 1/16PL:e3G3 <|0.22|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.50|> 1/16g3E3 <|0.63|>'}
  eval 拒因(样本数): 兜底=45 通过=3 /共48
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.66/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.0 omr_ned=0.8118796745001551 n_nasap=48 n_maestro=48

## eval @ step 60000 (2026-07-21 08:45:13)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.34 Δts=+0.23 Δpitch=+0.49 真sem=0.77 静sem=0.43 真pitch=0.72 acc=0.65 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.01 Δts=+0.03 Δpitch=-0.04 真sem=0.72 静sem=0.72 真pitch=0.16 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.17 Δts=+0.00 Δpitch=+0.36 真sem=0.69 静sem=0.52 真pitch=0.54 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.26 Δts=+0.21 Δpitch=+0.26 真sem=0.72 静sem=0.46 真pitch=0.78 acc=0.66 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/8a3D4 1/8d4A3 1/8a3D4 1/8d4A3 1/8a3D4 1/8d4A3 1/8a3D4 1/8d4 |4/4k#2A3 1/8a3D4 1/8d4A3 1/8a3D4 1/8d4A3 1/8a3D4 1/8d4A3 1/8a3D4 1/8d4 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='E', alter=0, octave=3))@79/16", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='G', alter=0, octave=3))@79/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='E', alter=0, octave=3))@23/4", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='G', alter=0, octave=3))@23/4"], 'raw': '|4/4k0PL:E3PR:E5 <|0.00|> 1/16PL:e3G3 <|0.23|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.47|> 1/16g3E3 <|0.59|> 1/16e3G3 <|0.68|> 1/16g3E3 <|0.78|> 1/16e3G3 <|0.90|> 1/16g', 'truncated': '|4/4k0PL:E3PR:E5 <|0.00|> 1/16PL:e3G3 <|0.23|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.47|> 1/16g3E3 <|0.59|>'}
  eval 拒因(样本数): 兜底=46 通过=2 /共48
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.65/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.8861329109367124 n_nasap=48 n_maestro=48

## eval @ step 61000 (2026-07-21 11:48:23)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.33 Δts=+0.39 Δpitch=+0.57 真sem=0.77 静sem=0.44 真pitch=0.71 acc=0.68 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.00 Δts=-0.03 Δpitch=-0.02 真sem=0.72 静sem=0.72 真pitch=0.17 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.17 Δts=+0.08 Δpitch=+0.46 真sem=0.67 静sem=0.50 真pitch=0.54 acc=0.58 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.33 Δts=+0.24 Δpitch=+0.39 真sem=0.73 静sem=0.40 真pitch=0.78 acc=0.67 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_Sham03M_dec99a67_001]: '|4/4k#2PL:G2D3G3PR:B3 1/2PL:g2d3g3PR:b3 |4/4k#2PL:F#2D3G3PR:B3 1/2PL:f#2d3g3A2C#3G3PR:b3C#4 1/2PL:a2c#3g3PR:c#4 |4/4k#2PL:D2A2D3PR:F#3D4 1/1PL:d2a2d3PR:f#3d4 |4'
  eval 同样本参照:              '|2/4k-3PL:G2G3PR:E-4E-5 1/8PL:g3A3PR:e-4E-4F#4 1/16e-5C5 1/16PL:a3B3PR:e-4f#4c5D4G4B4 1/8PL:g2b3PR:d4g4b4G5 1/16g5E-6 1/16e-6 |2/4k-3PL:G3G4PR:E-5E-6 1/8PL:g4A4'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=0, octave=2))@29/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=0, octave=2))@21/8", "DYCK_UNCLOSED:[('PL', SPitch(step='E', alter=0, octave=2)), ('PR', SPitch(step='G', alter=0, octave=4))]", 'TERMINAL_BAR_MISSING'], 'raw': '|4/4k0PL:E3PR:G4 <|0.01|> 1/16PL:e3G3 <|0.23|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.47|> 1/16g3E3 <|0.59|> 1/16e3G3 <|0.70|> 1/16g3E3 <|0.82|> 1/16e3G3 <|0.94|> 1/16g', 'truncated': '|4/4k0PL:E3PR:G4 <|0.01|> 1/16PL:e3G3 <|0.23|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.47|> 1/16g3E3 <|0.59|>'}
  eval 拒因(样本数): 兜底=45 通过=3 /共48
  eval 汇总: parseable=0.06 empty=0.9375 n=48 样本0='|4/4k0' 探针acc=0.68/前缀0.69 eotP0=0.0000
  eval 指标: parseable=0.06 amt_f1=0.0 omr_ned=0.9092096457678949 n_nasap=48 n_maestro=48

## eval @ step 62000 (2026-07-21 14:52:19)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.33 Δts=+0.26 Δpitch=+0.57 真sem=0.77 静sem=0.43 真pitch=0.69 acc=0.65 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.03 Δpitch=-0.02 真sem=0.73 静sem=0.73 真pitch=0.19 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.19 Δts=+0.07 Δpitch=+0.46 真sem=0.69 静sem=0.50 真pitch=0.51 acc=0.58 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.38 Δts=+0.31 Δpitch=+0.44 真sem=0.73 静sem=0.35 真pitch=0.78 acc=0.68 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/2 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PR', SPitch(step='E', alter=0, octave=5))]", 'MEASURE_SUM:0 got 17/16 want 1', 'MEASURE_SUM:1 got 9/8 want 1', 'MEASURE_SUM:2 got 19/16 want 1'], 'raw': '|4/4k0PL:E3PR:E5 <|0.00|> 1/16PL:e3G3 <|0.20|> 1/16g3E3 <|0.32|> 1/16e3G3 <|0.43|> 1/16g3E3 <|0.53|> 1/16e3G3 <|0.63|> 1/16g3E3 <|0.74|> 1/16e3G3 <|0.84|> 1/16g', 'truncated': '|4/4k0PL:E3PR:E5 <|0.00|> 1/16PL:e3G3 <|0.20|> 1/16g3E3 <|0.32|> 1/16e3G3 <|0.43|> 1/16g3E3 <|0.53|>'}
  eval 拒因(样本数): 兜底=41 通过=7 /共48
  eval 汇总: parseable=0.15 empty=0.8541666666666666 n=48 样本0='|4/4k0' 探针acc=0.65/前缀0.56 eotP0=0.0000
  eval 指标: parseable=0.15 amt_f1=0.0 omr_ned=0.8877712693150989 n_nasap=48 n_maestro=48

## eval @ step 63000 (2026-07-21 17:56:24)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.37 Δts=+0.26 Δpitch=+0.59 真sem=0.79 静sem=0.42 真pitch=0.70 acc=0.67 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.01 Δpitch=-0.03 真sem=0.73 静sem=0.72 真pitch=0.17 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.20 Δts=+0.07 Δpitch=+0.54 真sem=0.69 静sem=0.49 真pitch=0.59 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.31 Δts=+0.25 Δpitch=+0.35 真sem=0.73 静sem=0.42 真pitch=0.78 acc=0.67 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_Sham03M_dec99a67_001]: '|3/4k0PL:G2B2D3G3PR:D4F4D5 1/4PL:g2b2d3g3PR:d4f4d5 1/8PL:G3PR:D4F4B4 1/8PL:g3PR:d4f4b4 1/8G5 1/8g5 |3/4k0D6 1/8PL:G3PR:d6E5 1/8PL:g3E4PR:e5G5 1/8g5C6 1/8PL:e4G4'
  eval 同样本参照:              '|2/4k-3PL:G2G3PR:E-4E-5 1/8PL:g3A3PR:e-4E-4F#4 1/16e-5C5 1/16PL:a3B3PR:e-4f#4c5D4G4B4 1/8PL:g2b3PR:d4g4b4G5 1/16g5E-6 1/16e-6 |2/4k-3PL:G3G4PR:E-5E-6 1/8PL:g4A4'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='G', alter=0, octave=3)), ('PR', SPitch(step='G', alter=0, octave=5))]", 'MEASURE_SUM:0 got 9/8 want 1', 'MEASURE_SUM:1 got 19/16 want 1', 'MEASURE_SUM:2 got 21/16 want 1'], 'raw': '|4/4k0PL:E3PR:G5 <|0.00|> 1/16PL:e3G3 <|0.20|> 1/16g3E3 <|0.32|> 1/16e3G3 <|0.42|> 1/16g3E3 <|0.53|> 1/16e3G3 <|0.65|> 1/16g3E3 <|0.75|> 1/16e3G3 <|0.83|> 1/16g', 'truncated': '|4/4k0PL:E3PR:G5 <|0.00|> 1/16PL:e3G3 <|0.20|> 1/16g3E3 <|0.32|> 1/16e3G3 <|0.42|> 1/16g3E3 <|0.53|>'}
  eval 拒因(样本数): 兜底=43 通过=5 /共48
  eval 汇总: parseable=0.10 empty=0.8958333333333334 n=48 样本0='|4/4k0' 探针acc=0.67/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.10 amt_f1=0.0 omr_ned=0.8473367322863478 n_nasap=48 n_maestro=48

## prompt-abtest @ step 63000 (2026-07-21 19:11:35)
三臂同 ckpt(step=63000)同子集 n=48,仅 prompt 不同
  G0(domain=None): parseable=5/48 兜底=43 NED中位=0.801(n=5) 拒因: DYCK=34 MEASURE=24 parse_error=22 TERMINAL=21 通过=3
    [G0#0] '|4/4k0'
    [G0#1] '|4/4k0'
    [G0#2] '|4/4k0'
    [G0#3] '|4/4k0'
    [G0#4] '|4/4k0'
    [G0#5] '|3/4k0PL:G2B2D3G3PR:D4F4D5 1/4PL:g2b2d3g3PR:d4f4d5 1/8PL:G3PR:D4F4B4 1/8PL:g3PR:d4f4b4 1/8G5 1/8g5 |'
    [G0#6] '|4/4k0'
    [G0#7] '|4/4k0'
    [G0#8] '|4/4k0'
    [G0#9] '|4/4k0'
  G1(domain=real): parseable=5/48 兜底=43 NED中位=0.877(n=5) 拒因: DYCK=37 MEASURE=29 parse_error=23 TERMINAL=19 通过=1
    [G1#0] '|4/4k0'
    [G1#1] '|4/4k0'
    [G1#2] '|4/4k0'
    [G1#3] '|4/4k0'
    [G1#4] '|4/4k0'
    [G1#5] '|4/4k0'
    [G1#6] '|4/4k0'
    [G1#7] '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/4'
    [G1#8] '|4/4k0'
    [G1#9] '|4/4k0'
  G2(domain=synth): parseable=4/48 兜底=44 NED中位=0.941(n=4) 拒因: DYCK=35 MEASURE=35 TERMINAL=22 parse_error=17 通过=1
    [G2#0] '|4/4k0'
    [G2#1] '|4/4k0'
    [G2#2] '|4/4k0'
    [G2#3] '|4/4k0'
    [G2#4] '|4/4k0'
    [G2#5] '|4/4k0'
    [G2#6] '|4/4k0'
    [G2#7] '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/4g3A3 1/4a3B3 1/4b3A3 1/4a3 |4/4k#2G3 1/4g3A3 1/4a3B3 1/4'
    [G2#8] '|4/4k0'
    [G2#9] '|4/4k0'

## eval @ step 64000 (2026-07-21 23:33:31)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.32 Δts=+0.26 Δpitch=+0.57 真sem=0.76 静sem=0.44 真pitch=0.70 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.07 Δts=-0.06 Δpitch=+0.00 真sem=0.73 静sem=0.65 真pitch=0.18 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.22 Δts=+0.06 Δpitch=+0.54 真sem=0.71 静sem=0.48 真pitch=0.59 acc=0.60 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.38 Δts=+0.25 Δpitch=+0.37 真sem=0.74 静sem=0.36 真pitch=0.79 acc=0.68 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_Gasanov08M_f9ac827c_000]: '|3/4k-4PL:A-3PR:C5 1/4PL:a-3C4PR:c5C5 1/4PL:c4D-4PR:c5C5 1/4PL:d-4PR:c5 |3/4k-4PL:C4PR:C5 1/4PL:c4C4PR:c5C5 1/4PL:c4C4PR:c5C5 1/4PL:c4PR:c5 |3/4k-4PL:A-3PR:C5 1'
  eval 同样本参照:              '|6/8k-1PL:C4PR:C5 1/8PL:c4C4PR:c5C5 1/4PL:c4C4PR:c5C5 1/8PL:c4PR:c5 |6/8k-1PL:C4PR:C5 1/4PL:c4C4PR:c5C5 1/8PL:c4C4PR:c5C5 1/4PL:c4C4PR:c5C5 1/8PL:c4PR:c5 |6/8k-'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PR', SPitch(step='G', alter=0, octave=5))]", 'MEASURE_SUM:0 got 9/8 want 1', 'MEASURE_SUM:1 got 9/8 want 1', 'MEASURE_SUM:2 got 17/16 want 1'], 'raw': '|4/4k0PL:E3PR:G5 <|0.00|> 1/16PL:e3G3 <|0.11|> 1/16g3E3 <|0.22|> 1/16e3G3 <|0.34|> 1/16g3E3 <|0.45|> 1/16e3G3 <|0.55|> 1/16g3E3 <|0.65|> 1/16e3C3 <|0.75|> 1/16c', 'truncated': '|4/4k0PL:E3PR:G5 <|0.00|> 1/16PL:e3G3 <|0.11|> 1/16g3E3 <|0.22|> 1/16e3G3 <|0.34|> 1/16g3E3 <|0.45|>'}
  eval 拒因(样本数): DYCK=33 MEASURE=28 TERMINAL=19 parse_error=19 通过=5 /共48
  eval 汇总: parseable=0.10 empty=0.8958333333333334 n=48 样本0='|4/4k0' 探针acc=0.64/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.10 amt_f1=0.0 omr_ned=0.8754035183282646 n_nasap=48 n_maestro=48

## eval @ step 65000 (2026-07-22 02:39:51)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.32 Δts=+0.26 Δpitch=+0.50 真sem=0.75 静sem=0.43 真pitch=0.72 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.06 Δts=-0.01 Δpitch=+0.01 真sem=0.73 静sem=0.67 真pitch=0.20 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.19 Δts=+0.01 Δpitch=+0.38 真sem=0.69 静sem=0.50 真pitch=0.59 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.28 Δts=+0.15 Δpitch=+0.27 真sem=0.75 静sem=0.48 真pitch=0.79 acc=0.68 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PR', SPitch(step='G', alter=0, octave=4))]", 'MEASURE_SUM:0 got 9/8 want 1', 'MEASURE_SUM:1 got 5/4 want 1', 'MEASURE_SUM:2 got 21/16 want 1'], 'raw': '|4/4k0PL:E3PR:G4 <|0.01|> 1/16PL:e3G3 <|0.20|> 1/16g3E3 <|0.32|> 1/16e3G3 <|0.42|> 1/16g3E3 <|0.56|> 1/16e3G3 <|0.67|> 1/16g3E3 <|0.77|> 1/16e3G3 <|0.87|> 1/16g', 'truncated': '|4/4k0PL:E3PR:G4 <|0.01|> 1/16PL:e3G3 <|0.20|> 1/16g3E3 <|0.32|> 1/16e3G3 <|0.42|> 1/16g3E3 <|0.56|>'}
  eval 拒因(样本数): DYCK=27 MEASURE=26 parse_error=25 TERMINAL=15 通过=4 /共48
  eval 汇总: parseable=0.08 empty=0.9166666666666666 n=48 样本0='|4/4k0' 探针acc=0.64/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.8805036838008947 n_nasap=48 n_maestro=48

## eval @ step 66000 (2026-07-22 05:18:54)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.18 Δts=+0.30 Δpitch=+0.23 真sem=0.78 静sem=0.60 真pitch=0.70 acc=0.68 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=-0.04 Δpitch=-0.02 真sem=0.72 静sem=0.68 真pitch=0.16 acc=0.61 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.17 Δts=+0.01 Δpitch=+0.33 真sem=0.70 静sem=0.53 真pitch=0.64 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.25 Δts=+0.21 Δpitch=+0.26 真sem=0.74 静sem=0.49 真pitch=0.78 acc=0.67 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2G3 1/2g3 1/4A3 1/4a3 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['MEASURE_SUM:0 got 9/8 want 1', 'MEASURE_SUM:1 got 5/4 want 1', 'MEASURE_SUM:2 got 9/8 want 1', 'MEASURE_SUM:3 got 9/8 want 1'], 'raw': '|4/4k0PL:E3PR:G5 <|0.00|> 1/16PL:e3G3 <|0.20|> 1/16g3E3PR:g5 <|0.31|> 1/16PL:e3G3 <|0.41|> 1/16g3E3 <|0.56|> 1/16e3G3 <|0.67|> 1/16g3E3 <|0.79|> 1/16e3G3 <|0.90', 'truncated': '|4/4k0PL:E3PR:G5 <|0.00|> 1/16PL:e3G3 <|0.20|> 1/16g3E3PR:g5 <|0.31|> 1/16PL:e3G3 <|0.41|> 1/16g3E3 '}
  eval 拒因(样本数): DYCK=31 parse_error=24 MEASURE=22 TERMINAL=18 通过=6 /共48
  eval 汇总: parseable=0.12 empty=0.875 n=48 样本0='|4/4k0' 探针acc=0.68/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.12 amt_f1=0.0 omr_ned=0.8910582528478482 n_nasap=48 n_maestro=48

## eval @ step 67000 (2026-07-22 07:58:21)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.29 Δts=+0.27 Δpitch=+0.44 真sem=0.77 静sem=0.48 真pitch=0.71 acc=0.66 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.01 Δpitch=-0.03 真sem=0.72 静sem=0.71 真pitch=0.18 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.18 Δts=+0.02 Δpitch=+0.38 真sem=0.71 静sem=0.53 真pitch=0.62 acc=0.60 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.28 Δts=+0.20 Δpitch=+0.29 真sem=0.72 静sem=0.43 真pitch=0.79 acc=0.66 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_Sham03M_dec99a67_001]: '|4/4k#2PL:B2D3G3PR:B3 1/2PL:b2d3g3PR:b3 |4/4k#2PL:G2D3G3PR:B3 1/2PL:g2d3g3PR:b3 1/2 |4/4k#2PL:F#2C#3F#3PR:A#3 1/2PL:f#2c#3f#3PR:a#3 1/2 |4/4k#2PL:G2D3G3PR:B3 1/'
  eval 同样本参照:              '|2/4k-3PL:G2G3PR:E-4E-5 1/8PL:g3A3PR:e-4E-4F#4 1/16e-5C5 1/16PL:a3B3PR:e-4f#4c5D4G4B4 1/8PL:g2b3PR:d4g4b4G5 1/16g5E-6 1/16e-6 |2/4k-3PL:G3G4PR:E-5E-6 1/8PL:g4A4'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PR', SPitch(step='G', alter=0, octave=5))]", 'MEASURE_SUM:1 got 7/8 want 1', 'MEASURE_SUM:2 got 7/8 want 1', 'MEASURE_SUM:3 got 7/8 want 1'], 'raw': '|4/4k0PL:E3PR:G5 <|0.00|> 1/16PL:e3G3 <|0.24|> 1/16g3A3 <|0.34|> 1/16a3G3 <|0.45|> 1/16g3A3 <|0.56|> 1/16a3G3 <|0.67|> 1/16g3A3 <|0.79|> 1/16a3G3 <|0.90|> 1/16g', 'truncated': '|4/4k0PL:E3PR:G5 <|0.00|> 1/16PL:e3G3 <|0.24|> 1/16g3A3 <|0.34|> 1/16a3G3 <|0.45|> 1/16g3A3 <|0.56|>'}
  eval 拒因(样本数): DYCK=32 MEASURE=27 parse_error=25 TERMINAL=17 通过=4 /共48
  eval 汇总: parseable=0.08 empty=0.9166666666666666 n=48 样本0='|4/4k0' 探针acc=0.66/前缀0.72 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.892754207481333 n_nasap=48 n_maestro=48

## eval @ step 70000 (2026-07-25 19:03:24)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.21 Δts=+0.18 Δpitch=+0.32 真sem=0.80 静sem=0.59 真pitch=0.76 acc=0.66 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=-0.03 Δpitch=-0.05 真sem=0.72 静sem=0.68 真pitch=0.17 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.15 Δts=+0.10 Δpitch=+0.41 真sem=0.70 静sem=0.54 真pitch=0.62 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.30 Δts=+0.20 Δpitch=+0.30 真sem=0.74 静sem=0.44 真pitch=0.80 acc=0.68 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_Gasanov08M_f9ac827c_000]: '|3/4k-4PL:A-3PR:C5 1/4PL:a-3C4PR:c5C5 1/4PL:c4A-3C4PR:c5C5 1/4PL:a-3c4PR:c5 |3/4k-4PL:A-3C4PR:C5 1/4PL:a-3c4A-3C4PR:c5C5 1/4PL:a-3c4A-3C4PR:c5C5 1/4PL:a-3c4PR:c'
  eval 同样本参照:              '|6/8k-1PL:C4PR:C5 1/8PL:c4C4PR:c5C5 1/4PL:c4C4PR:c5C5 1/8PL:c4PR:c5 |6/8k-1PL:C4PR:C5 1/4PL:c4C4PR:c5C5 1/8PL:c4C4PR:c5C5 1/4PL:c4C4PR:c5C5 1/8PL:c4PR:c5 |6/8k-'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PR', SPitch(step='E', alter=0, octave=5))]", 'MEASURE_SUM:0 got 9/8 want 1', 'MEASURE_SUM:1 got 19/16 want 1', 'MEASURE_SUM:2 got 19/16 want 1'], 'raw': '|4/4k0PL:E3PR:E5 <|0.00|> 1/16PL:e3G3 <|0.20|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.50|> 1/16g3E3 <|0.62|> 1/16e3G3 <|0.75|> 1/16g3E3 <|0.89|> 1/16e3G3 <|0.99|> 1/16g3E3 <|1.08|> 1/16e3G3 <|1.20|> 1/16g3E3 <|1.35|> 1/16e3G3 <|1.50|> 1/16g3E3 <|1.63|> 1/16e3G3 <|1.76|> 1/16g3E3 <|1.85|> 1/16e3G3 <|1.94|> 1/16g3E3 <|2.06|> 1/1', 'truncated': '|4/4k0PL:E3PR:E5 <|0.00|> 1/16PL:e3G3 <|0.20|> 1/16g3E3 <|0.36|> 1/16e3G3 <|0.50|> 1/16g3E3 <|0.62|>', 'gen': {'n_new': 642, 'stop': 'eot', 'fast': True}}
  eval 拒因(样本数): parse_error=31 DYCK=28 MEASURE=25 TERMINAL=16 通过=2 /共48
  eval 汇总: parseable=0.04 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.66/前缀0.62 eotP0=0.0000
  eval 指标: parseable=0.04 amt_f1=0.0 omr_ned=0.7868109169714208 n_nasap=48 n_maestro=48

## eval @ step 71000 (2026-07-25 22:38:00)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.27 Δts=+0.22 Δpitch=+0.45 真sem=0.77 静sem=0.50 真pitch=0.74 acc=0.65 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.03 Δts=-0.03 Δpitch=-0.03 真sem=0.73 静sem=0.70 真pitch=0.18 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.18 Δts=+0.08 Δpitch=+0.38 真sem=0.70 静sem=0.52 真pitch=0.62 acc=0.60 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.31 Δts=+0.25 Δpitch=+0.34 真sem=0.72 静sem=0.41 真pitch=0.79 acc=0.66 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#2PR:A3 1/2a3 1/4A3 1/4a3 |4/4k#2G3 1/2g3F#3 1/2f#3 |4/4k#2G3 1/2g3F#3 1/2f#3 |4/4k#2G3 1/2g3F#3 1/2f#3 |4/4k#2G3 1/2g3F#3 1/2f#3 |4/4k#2'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='B', alter=0, octave=3)), ('PR', SPitch(step='B', alter=0, octave=3)), ('PR', SPitch(step='B', alter=0, octave=4))]", 'MEASURE_SUM:0 got 25/16 want 3/4', 'MEASURE_SUM:1 got 25/16 want 3/4', 'MEASURE_SUM:2 got 29/16 want 3/4'], 'raw': '|6/8k#3PL:D#3PR:B4 <|0.00|> 1/16PL:d#3F#3 <|0.22|> 1/16f#3G#3 <|0.33|> 1/16g#3A#3 <|0.47|> 1/16a#3B3 <|0.59|> 1/16b3A#3 <|0.70|> 1/16a#3B3 <|0.82|> 1/16b3A#3 <|0.94|> 1/16a#3B3 <|1.03|> 1/16b3A#3 <|1.17|> 1/16a#3B3 <|1.29|> 1/16b3A#3 <|1.40|> 1/16a#3B3 <|1.52|> 1/16b3A#3 <|1.62|> 1/16a#3B3 <|1.72|> 1/16b3A#3 <|1.83|> 1', 'truncated': '|6/8k#3PL:D#3PR:B4 <|0.00|> 1/16PL:d#3F#3 <|0.22|> 1/16f#3G#3 <|0.33|> 1/16g#3A#3 <|0.47|> 1/16a#3B3', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True}}
  eval 拒因(样本数): parse_error=33 DYCK=25 MEASURE=20 TERMINAL=13 通过=4 /共48
  eval 汇总: parseable=0.08 empty=0.9166666666666666 n=48 样本0='|4/4k0' 探针acc=0.65/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.8420164756223328 n_nasap=48 n_maestro=48

## eval @ step 72000 (2026-07-26 01:50:13)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.24 Δts=+0.17 Δpitch=+0.41 真sem=0.79 静sem=0.56 真pitch=0.77 acc=0.65 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.02 Δpitch=-0.05 真sem=0.73 静sem=0.72 真pitch=0.17 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.16 Δts=+0.05 Δpitch=+0.31 真sem=0.69 静sem=0.54 真pitch=0.59 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.29 Δts=+0.21 Δpitch=+0.29 真sem=0.74 静sem=0.46 真pitch=0.80 acc=0.68 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 73000 (2026-07-26 04:19:54)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.31 Δts=+0.23 Δpitch=+0.65 真sem=0.78 静sem=0.47 真pitch=0.75 acc=0.66 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.04 Δpitch=-0.04 真sem=0.72 静sem=0.71 真pitch=0.16 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.19 Δts=+0.08 Δpitch=+0.51 真sem=0.70 静sem=0.51 真pitch=0.62 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.28 Δts=+0.24 Δpitch=+0.34 真sem=0.74 静sem=0.45 真pitch=0.80 acc=0.68 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 74000 (2026-07-26 06:49:11)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.32 Δts=+0.30 Δpitch=+0.54 真sem=0.80 静sem=0.47 真pitch=0.74 acc=0.69 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.06 Δts=-0.03 Δpitch=+0.04 真sem=0.73 静sem=0.67 真pitch=0.20 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.20 Δts=+0.09 Δpitch=+0.56 真sem=0.69 静sem=0.50 真pitch=0.59 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.33 Δts=+0.25 Δpitch=+0.37 真sem=0.73 静sem=0.40 真pitch=0.80 acc=0.67 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 75000 (2026-07-26 09:47:11)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.37 Δts=+0.33 Δpitch=+0.65 真sem=0.80 静sem=0.43 真pitch=0.80 acc=0.70 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.07 Δts=-0.03 Δpitch=+0.03 真sem=0.72 静sem=0.65 真pitch=0.17 acc=0.61 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.21 Δts=+0.13 Δpitch=+0.51 真sem=0.70 静sem=0.49 真pitch=0.56 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.38 Δts=+0.24 Δpitch=+0.44 真sem=0.74 静sem=0.36 真pitch=0.82 acc=0.68 n=724
  eval 时限 1200s 用尽,截断于 38/48(指标按已评样本)
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 样本预测[首个通过 nasap_LeeN01M_ad221e3a_005]: '|4/4k#3PR:A3 1/4a3A3 1/4a3A3 1/4a3 |4/4k#3A3 1/4a3A3 1/4a3 1/4A3 1/4a3 |4/4k#3A3 1/4a3 1/4A3 1/4a3 1/4 |4/4k#3A3 1/4a3 1/4A3 1/4a3 1/4 |4/4k#3 1/4A3 1/4a3 1/4A3'
  eval 同样本参照:              '|6/8k#5PL:B2PR:A#4D#5 1/16d#5C#5 1/16a#4c#5G#4B4 1/16b4D#5 1/16PL:b2E3PR:d#5C#5 1/16c#5A#4 1/16PL:e3C#3PR:g#4a#4B4 1/16b4A#4 1/16PL:c#3D#3PR:a#4G#4 1/16g#4B4 1/'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PR', SPitch(step='D', alter=0, octave=4))@113/16", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='G', alter=0, octave=2))@8", "DYCK_UNCLOSED:[('PL', SPitch(step='F', alter=1, octave=2)), ('PR', SPitch(step='C', alter=1, octave=4))]", 'TERMINAL_BAR_MISSING'], 'raw': '|12/8k#1PL:G2PR:B3 <|0.01|> 1/16b3C4 <|0.21|> 1/16PL:g2F#2PR:c4F#4 <|0.32|> 1/16PL:f#2G2PR:f#4B3 <|0.41|> 1/16PL:g2F#2PR:b3F#4 <|0.50|> 1/16PL:f#2G2PR:f#4B3 <|0.63|> 1/16PL:g2F#2PR:b3F#4 <|0.79|> 1/16PL:f#2G2PR:f#4B3 <|0.91|> 1/16PL:g2F#2PR:b3F#4 <|1.01|> 1/16PL:f#2G2PR:f#4B3 <|1.12|> 1/16PL:g2F#2PR:b3F#4 <|1.25|> 1/16', 'truncated': '|12/8k#1PL:G2PR:B3 <|0.01|> 1/16b3C4 <|0.21|> 1/16PL:g2F#2PR:c4F#4 <|0.32|> 1/16PL:f#2G2PR:f#4B3 <|0', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True}}
  eval 拒因(样本数): DYCK=25 parse_error=25 TERMINAL=14 MEASURE=13 通过=3 /共38
  eval 汇总: parseable=0.08 empty=0.9210526315789473 n=38 样本0='|4/4k0' 探针acc=0.70/前缀0.66 eotP0=0.0000
  eval 指标: parseable=0.08 amt_f1=0.0 omr_ned=0.8719634257842858 n_nasap=38 n_maestro=48

## eval @ step 76000 (2026-07-26 12:15:46)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.26 Δts=+0.35 Δpitch=+0.37 真sem=0.79 静sem=0.53 真pitch=0.76 acc=0.70 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.05 Δts=-0.05 Δpitch=-0.01 真sem=0.73 静sem=0.67 真pitch=0.19 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.17 Δts=+0.00 Δpitch=+0.28 真sem=0.70 静sem=0.54 真pitch=0.59 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.22 Δts=+0.19 Δpitch=+0.23 真sem=0.73 静sem=0.51 真pitch=0.79 acc=0.67 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 77000 (2026-07-26 14:44:30)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.26 Δts=+0.30 Δpitch=+0.46 真sem=0.78 静sem=0.52 真pitch=0.77 acc=0.67 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.07 Δts=-0.07 Δpitch=+0.00 真sem=0.72 静sem=0.65 真pitch=0.17 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.17 Δts=+0.07 Δpitch=+0.33 真sem=0.71 静sem=0.54 真pitch=0.62 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.24 Δts=+0.18 Δpitch=+0.26 真sem=0.73 静sem=0.50 真pitch=0.80 acc=0.67 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 78000 (2026-07-26 17:13:21)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.17 Δts=+0.23 Δpitch=+0.30 真sem=0.79 静sem=0.62 真pitch=0.77 acc=0.67 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.05 Δts=-0.07 Δpitch=-0.05 真sem=0.72 静sem=0.67 真pitch=0.17 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.14 Δts=+0.02 Δpitch=+0.33 真sem=0.70 静sem=0.56 真pitch=0.64 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.25 Δts=+0.23 Δpitch=+0.24 真sem=0.74 静sem=0.49 真pitch=0.80 acc=0.68 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 79000 (2026-07-26 19:41:55)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.22 Δts=+0.27 Δpitch=+0.41 真sem=0.79 静sem=0.57 真pitch=0.78 acc=0.68 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.08 Δts=-0.03 Δpitch=+0.00 真sem=0.72 静sem=0.64 真pitch=0.18 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.17 Δts=+0.06 Δpitch=+0.33 真sem=0.71 静sem=0.54 真pitch=0.59 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.27 Δts=+0.15 Δpitch=+0.31 真sem=0.75 静sem=0.48 真pitch=0.82 acc=0.67 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 1000 (2026-07-27 00:32:10)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.00 Δts=+0.00 Δpitch=+0.00 真sem=0.33 静sem=0.32 真pitch=0.00 acc=0.25 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.00 Δpitch=+0.00 真sem=0.69 静sem=0.67 真pitch=0.00 acc=0.53 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.00 Δts=+0.00 Δpitch=+0.05 真sem=0.38 静sem=0.38 真pitch=0.05 acc=0.31 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=-0.01 Δts=+0.00 Δpitch=-0.01 真sem=0.17 静sem=0.18 真pitch=0.04 acc=0.15 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 2000 (2026-07-27 03:03:11)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=-0.00 Δts=+0.00 Δpitch=-0.08 真sem=0.43 静sem=0.43 真pitch=0.10 acc=0.32 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.00 Δpitch=+0.00 真sem=0.68 静sem=0.68 真pitch=0.00 acc=0.53 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.00 Δts=+0.00 Δpitch=-0.03 真sem=0.37 静sem=0.36 真pitch=0.05 acc=0.30 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=-0.00 Δts=+0.00 Δpitch=+0.01 真sem=0.24 静sem=0.24 真pitch=0.26 acc=0.20 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 3000 (2026-07-27 05:37:00)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.08 Δts=+0.02 Δpitch=+0.10 真sem=0.47 静sem=0.39 真pitch=0.34 acc=0.36 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.00 Δpitch=+0.00 真sem=0.70 静sem=0.70 真pitch=0.09 acc=0.54 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.01 Δts=+0.00 Δpitch=-0.03 真sem=0.42 静sem=0.41 真pitch=0.15 acc=0.34 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=-0.01 Δts=+0.00 Δpitch=-0.02 真sem=0.27 静sem=0.28 真pitch=0.42 acc=0.23 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 4000 (2026-07-27 08:11:25)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.04 Δts=+0.00 Δpitch=+0.02 真sem=0.46 静sem=0.43 真pitch=0.35 acc=0.35 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.00 Δpitch=-0.01 真sem=0.71 静sem=0.71 真pitch=0.12 acc=0.55 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.01 Δts=+0.00 Δpitch=-0.05 真sem=0.45 静sem=0.45 真pitch=0.18 acc=0.37 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.00 Δts=+0.00 Δpitch=-0.01 真sem=0.37 静sem=0.37 真pitch=0.50 acc=0.31 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 5000 (2026-07-27 11:10:45)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.10 Δts=+0.00 Δpitch=+0.06 真sem=0.47 静sem=0.38 真pitch=0.32 acc=0.36 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.00 Δpitch=+0.05 真sem=0.72 静sem=0.71 真pitch=0.17 acc=0.56 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.00 Δpitch=-0.05 真sem=0.49 静sem=0.45 真pitch=0.23 acc=0.40 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.06 Δts=+0.00 Δpitch=+0.04 真sem=0.41 静sem=0.35 真pitch=0.60 acc=0.35 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PR', SPitch(step='D', alter=0, octave=4))@1/8", "DYCK_UNCLOSED:[('PL', SPitch(step='D', alter=0, octave=3))]", 'TERMINAL_BAR_MISSING'], 'raw': '|12/8k#1PL:D3PR:D4 <|1.06|> 1/8PL:d3D3PR:D4 <|1.06|> 1/8PL:d3D3PR:d4D4 <|1.06|> 1/8PL:d3D3PR:d4 <|1.06|> 1/8PL:d3D3 <|1.06|> 1/8PL:d3D3 <|1.06|> 1/8PL:d3D3 <|1.70|> 1/8PL:d3D3 <|1.70|> 1/8PL:d3D3 <|1.70|> 1/8PL:d3D3 <|1.70|> 1/8PL:d3D3 <|1.70|> 1/8PL:d3D3 <|1.70|> 1/8PL:d3D3 <|1.70|> 1/8PL:d3D3 <|2.85|> 1/8PL:d3D3 <|2.', 'truncated': '|12/8k#1PL:D3PR:D4 <|1.06|> 1/8PL:d3D3PR:D4 <|1.06|> 1/8PL:d3D3PR:d4D4 <|1.06|> 1/8PL:d3D3PR:d4 <|1.', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True}}
  eval 拒因(样本数): parse_error=41 TERMINAL=24 DYCK=22 MEASURE=1 /共48
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.36/前缀0.41 eotP0=0.0002
  eval 指标: parseable=0.00 amt_f1=0.0 omr_ned=None n_nasap=48 n_maestro=48

## eval @ step 6000 (2026-07-27 13:44:52)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.06 Δts=+0.00 Δpitch=+0.02 真sem=0.48 静sem=0.42 真pitch=0.34 acc=0.36 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.00 Δpitch=+0.03 真sem=0.72 静sem=0.72 真pitch=0.17 acc=0.56 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.03 Δts=+0.00 Δpitch=-0.03 真sem=0.49 静sem=0.47 真pitch=0.28 acc=0.41 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.03 Δts=+0.00 Δpitch=+0.05 真sem=0.42 静sem=0.39 真pitch=0.61 acc=0.36 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 7000 (2026-07-27 16:28:38)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.06 Δts=+0.00 Δpitch=+0.01 真sem=0.53 静sem=0.47 真pitch=0.39 acc=0.40 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.08 Δpitch=+0.01 真sem=0.72 静sem=0.71 真pitch=0.14 acc=0.57 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.00 Δts=+0.03 Δpitch=-0.03 真sem=0.50 静sem=0.51 真pitch=0.31 acc=0.42 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.05 Δts=+0.05 Δpitch=+0.10 真sem=0.45 静sem=0.41 真pitch=0.64 acc=0.40 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 8000 (2026-07-27 19:14:27)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.02 Δts=+0.01 Δpitch=-0.05 真sem=0.51 静sem=0.49 真pitch=0.34 acc=0.39 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.05 Δpitch=-0.01 真sem=0.70 静sem=0.68 真pitch=0.12 acc=0.56 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.01 Δts=+0.02 Δpitch=+0.05 真sem=0.51 静sem=0.50 真pitch=0.28 acc=0.42 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.08 Δts=+0.05 Δpitch=+0.15 真sem=0.48 静sem=0.40 真pitch=0.67 acc=0.42 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 9000 (2026-07-27 22:01:27)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.02 Δpitch=+0.01 真sem=0.51 静sem=0.46 真pitch=0.39 acc=0.39 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.07 Δpitch=+0.04 真sem=0.73 静sem=0.71 真pitch=0.21 acc=0.59 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.02 Δts=+0.00 Δpitch=-0.08 真sem=0.52 静sem=0.53 真pitch=0.31 acc=0.43 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.07 Δts=+0.12 Δpitch=+0.11 真sem=0.51 静sem=0.44 真pitch=0.70 acc=0.45 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 10000 (2026-07-28 01:18:50)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.04 Δts=+0.03 Δpitch=+0.05 真sem=0.50 静sem=0.46 真pitch=0.45 acc=0.39 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.03 Δpitch=+0.02 真sem=0.72 静sem=0.70 真pitch=0.17 acc=0.58 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.00 Δts=+0.03 Δpitch=+0.05 真sem=0.52 静sem=0.53 真pitch=0.31 acc=0.44 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.06 Δts=+0.09 Δpitch=+0.15 真sem=0.49 静sem=0.43 真pitch=0.72 acc=0.43 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['parse_error:ParseError', 'TS_PARSE:ParseError'], 'raw': '|12/8k#1PR:E4 |12/8k#1D4 |12/8k#1E4 |12/8k#1D4 |12/8k#1E4 |12/8k#1D4 |1E4 |12/8k#1D4 |12/8k#1E4 |12/8k#1D4 |12/8k#1E4 |1D4 |12/8k#1E4 |12/8k#1D4 |12/8k#1E4 |1D4 |12/8k#1E4 |12/8k#1D4 |12/8k#1E4 |1D4 |12/8k#1D4 |12/8k#1E4 |12/8k#1D4 |12/8k#1D4 |1E4 |12/8k#1D4 |12/8k#1D4 |12/8k#1E4 |1D4 |12/8k#1D4 |12/8k#1E4 |12/8k#1D4 |', 'truncated': '|12/8k#1PR:E4 |12/8k#1D4 |12/8k#1E4 |12/8k#1D4 |12/8k#1E4 |12/8k#1D4 |1E4 |12/8k#1D4 |12/8k#1E4 |12/', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): TS_PARSE=48 parse_error=46 DYCK=23 TERMINAL=18 TS_MISSING=13 TS_NONMONOTONE=4 MEASURE=3 /共48
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.39/前缀0.44 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.12604166666666666 omr_ned=None omr_scored=0/48 n_maestro=48

## eval @ step 11000 (2026-07-28 03:56:40)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.02 Δts=+0.00 Δpitch=+0.04 真sem=0.51 静sem=0.49 真pitch=0.48 acc=0.40 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=+0.05 Δpitch=+0.05 真sem=0.72 静sem=0.68 真pitch=0.18 acc=0.59 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.01 Δts=+0.08 Δpitch=+0.00 真sem=0.51 静sem=0.52 真pitch=0.31 acc=0.43 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.12 Δts=+0.15 Δpitch=+0.16 真sem=0.52 静sem=0.40 真pitch=0.71 acc=0.47 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 12000 (2026-07-28 06:34:21)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.03 Δts=+0.03 Δpitch=+0.02 真sem=0.51 静sem=0.48 真pitch=0.48 acc=0.40 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.03 Δpitch=+0.03 真sem=0.72 静sem=0.70 真pitch=0.19 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.02 Δts=+0.08 Δpitch=+0.08 真sem=0.52 静sem=0.50 真pitch=0.36 acc=0.44 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.12 Δts=+0.18 Δpitch=+0.19 真sem=0.53 静sem=0.41 真pitch=0.74 acc=0.48 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 13000 (2026-07-28 09:12:14)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.01 Δts=+0.04 Δpitch=+0.04 真sem=0.49 静sem=0.48 真pitch=0.48 acc=0.39 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.01 Δpitch=+0.00 真sem=0.72 静sem=0.71 真pitch=0.15 acc=0.61 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.01 Δts=+0.07 Δpitch=+0.05 真sem=0.52 静sem=0.53 真pitch=0.31 acc=0.44 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.07 Δts=+0.20 Δpitch=+0.11 真sem=0.53 静sem=0.46 真pitch=0.73 acc=0.48 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 14000 (2026-07-28 12:00:05)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.04 Δts=+0.01 Δpitch=+0.04 真sem=0.50 静sem=0.47 真pitch=0.50 acc=0.40 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.01 Δpitch=+0.05 真sem=0.72 静sem=0.70 真pitch=0.18 acc=0.61 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.01 Δts=+0.03 Δpitch=-0.05 真sem=0.51 静sem=0.52 真pitch=0.28 acc=0.44 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.10 Δts=+0.23 Δpitch=+0.12 真sem=0.54 静sem=0.44 真pitch=0.74 acc=0.49 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 15000 (2026-07-28 17:03:07)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.05 Δpitch=+0.06 真sem=0.53 静sem=0.48 真pitch=0.54 acc=0.42 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.06 Δts=+0.12 Δpitch=+0.03 真sem=0.73 静sem=0.66 真pitch=0.21 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.02 Δts=+0.08 Δpitch=+0.00 真sem=0.52 静sem=0.50 真pitch=0.33 acc=0.44 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.24 Δpitch=+0.21 真sem=0.55 静sem=0.38 真pitch=0.74 acc=0.50 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ['parse_error:ParseError', 'TS_PARSE:ParseError'], 'raw': '|12/8k-1PL:F2PR:F3 <|0.41|> 1/8f3 <|0.59|> 1/8F3 <|0.62|> 1/8f3F3 <|0.76|> 1/8f3F3 <|0.97|> 1/8f3F3 <|1.15|> 1/8f3F3 |12/8k-1 <|1.15|> 1/8F3 <|1.16|> 1/8f3F3 <|1.18|> 1/8f3F3 <|1.20|> 1/8f3F3 |12/8k-1 <|1.20|> <|1.20|> <|1.20|> <|1.39|> |1/8k-1 <|1.39|> <|1.39|> <|1.39|> <|1.39|> <|1.41|> |1/8k-1/8k-1 <|1.41|> |1/8k-1 ', 'truncated': '|12/8k-1PL:F2PR:F3 <|0.41|> 1/8f3 <|0.59|> 1/8F3 <|0.62|> 1/8f3F3 <|0.76|> 1/8f3F3 <|0.97|> 1/8f3F3 ', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): TS_PARSE=34 parse_error=34 DYCK=30 TERMINAL=26 TS_MISSING=26 MEASURE=8 TS_NONMONOTONE=8 /共48
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.42/前缀0.44 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.0 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 16000 (2026-07-28 19:45:40)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.04 Δts=+0.02 Δpitch=+0.10 真sem=0.53 静sem=0.49 真pitch=0.54 acc=0.42 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.03 Δts=+0.11 Δpitch=+0.03 真sem=0.73 静sem=0.70 真pitch=0.21 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.01 Δts=+0.08 Δpitch=+0.00 真sem=0.52 静sem=0.51 真pitch=0.31 acc=0.44 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.24 Δpitch=+0.23 真sem=0.57 静sem=0.38 真pitch=0.76 acc=0.52 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 17000 (2026-07-28 22:32:52)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.03 Δts=+0.02 Δpitch=+0.07 真sem=0.53 静sem=0.50 真pitch=0.52 acc=0.42 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.05 Δts=+0.13 Δpitch=+0.04 真sem=0.73 静sem=0.68 真pitch=0.22 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.02 Δts=+0.10 Δpitch=+0.03 真sem=0.52 静sem=0.51 真pitch=0.33 acc=0.45 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.25 Δpitch=+0.22 真sem=0.56 静sem=0.37 真pitch=0.77 acc=0.51 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 18000 (2026-07-29 01:19:56)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.02 Δpitch=+0.08 真sem=0.56 静sem=0.51 真pitch=0.58 acc=0.44 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.13 Δpitch=+0.01 真sem=0.73 静sem=0.71 真pitch=0.20 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.01 Δts=+0.10 Δpitch=+0.03 真sem=0.53 静sem=0.52 真pitch=0.36 acc=0.45 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.12 Δts=+0.25 Δpitch=+0.15 真sem=0.56 静sem=0.44 真pitch=0.77 acc=0.52 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 19000 (2026-07-29 04:07:28)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.07 Δts=+0.05 Δpitch=+0.08 真sem=0.54 静sem=0.47 真pitch=0.54 acc=0.43 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.03 Δts=+0.20 Δpitch=+0.01 真sem=0.73 静sem=0.70 真pitch=0.20 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.02 Δts=+0.05 Δpitch=+0.00 真sem=0.51 静sem=0.53 真pitch=0.33 acc=0.43 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.14 Δts=+0.22 Δpitch=+0.15 真sem=0.57 静sem=0.43 真pitch=0.76 acc=0.52 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 20000 (2026-07-29 07:22:25)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.08 Δpitch=+0.05 真sem=0.53 静sem=0.48 真pitch=0.53 acc=0.42 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=+0.11 Δpitch=+0.02 真sem=0.73 静sem=0.70 真pitch=0.22 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.03 Δts=+0.13 Δpitch=+0.08 真sem=0.53 静sem=0.50 真pitch=0.33 acc=0.46 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.30 Δpitch=+0.19 真sem=0.58 静sem=0.41 真pitch=0.78 acc=0.54 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_UNCLOSED:[('PL', SPitch(step='G', alter=0, octave=2))]", 'MEASURE_SUM:1 got 13/8 want 3/2', 'MEASURE_SUM:2 got 7/4 want 3/2', 'MEASURE_SUM:3 got 13/8 want 3/2'], 'raw': '|12/8k#1PL:G2PR:G3 <|0.02|> 1/8g3 <|0.32|> 1/8G3 <|0.34|> 1/8g3D4 <|0.59|> 1/8d4G3 <|0.77|> 1/8g3D4 <|0.98|> 1/8d4G3 <|1.06|> 1/8g3D4 <|1.24|> 1/8d4G3 <|1.24|> 1/8g3D4 <|1.46|> 1/8d4G3 <|1.69|> 1/8g3 <|1.87|> |12/8k#1 <|1.87|> 1/8D4 <|1.87|> 1/8d4G3 <|2.09|> 1/8g3D4 <|2.28|> 1/8d4G3 <|2.45|> 1/8g3D4 <|2.61|> 1/8d4G3 <|', 'truncated': '|12/8k#1PL:G2PR:G3 <|0.02|> 1/8g3 <|0.32|> 1/8G3 <|0.34|> 1/8g3D4 <|0.59|> 1/8d4G3 <|0.77|> 1/8g3D4 ', 'gen': {'n_new': 695, 'stop': 'eot', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=43 TERMINAL=35 TS_MISSING=35 TS_PARSE=24 parse_error=24 MEASURE=18 TS_NONMONOTONE=4 /共48
  eval 汇总: parseable=0.00 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.42/前缀0.47 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.0 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 21000 (2026-07-29 10:10:31)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.02 Δts=+0.03 Δpitch=-0.04 真sem=0.55 静sem=0.52 真pitch=0.52 acc=0.43 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.00 Δpitch=-0.02 真sem=0.73 静sem=0.72 真pitch=0.21 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=-0.01 Δts=+0.00 Δpitch=-0.03 真sem=0.55 静sem=0.55 真pitch=0.31 acc=0.46 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.15 Δts=+0.20 Δpitch=+0.14 真sem=0.60 静sem=0.45 真pitch=0.78 acc=0.55 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 22000 (2026-07-29 15:20:48)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=-0.01 Δpitch=+0.09 真sem=0.55 静sem=0.51 真pitch=0.60 acc=0.43 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.01 Δts=+0.02 Δpitch=-0.05 真sem=0.73 静sem=0.73 真pitch=0.21 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.02 Δts=-0.01 Δpitch=+0.00 真sem=0.55 静sem=0.52 真pitch=0.33 acc=0.46 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.14 Δts=+0.22 Δpitch=+0.13 真sem=0.60 静sem=0.46 真pitch=0.77 acc=0.55 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 23000 (2026-07-29 20:50:47)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.02 Δpitch=+0.13 真sem=0.58 静sem=0.53 真pitch=0.68 acc=0.46 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.05 Δpitch=-0.01 真sem=0.73 静sem=0.72 真pitch=0.21 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.02 Δts=+0.00 Δpitch=+0.08 真sem=0.54 静sem=0.52 真pitch=0.36 acc=0.46 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.16 Δts=+0.11 Δpitch=+0.14 真sem=0.61 静sem=0.45 真pitch=0.79 acc=0.56 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 24000 (2026-07-30 01:12:30)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.07 Δts=-0.01 Δpitch=+0.09 真sem=0.60 静sem=0.53 真pitch=0.67 acc=0.47 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.08 Δpitch=-0.04 真sem=0.73 静sem=0.71 真pitch=0.20 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.06 Δpitch=+0.00 真sem=0.55 静sem=0.52 真pitch=0.33 acc=0.47 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.20 Δpitch=+0.17 真sem=0.60 静sem=0.43 真pitch=0.80 acc=0.55 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 25000 (2026-07-30 04:09:13)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.05 Δts=+0.04 Δpitch=+0.04 真sem=0.60 静sem=0.54 真pitch=0.63 acc=0.47 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.01 Δpitch=+0.02 真sem=0.74 静sem=0.72 真pitch=0.27 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.07 Δts=+0.08 Δpitch=+0.10 真sem=0.57 静sem=0.51 真pitch=0.38 acc=0.50 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.15 Δpitch=+0.18 真sem=0.62 静sem=0.44 真pitch=0.80 acc=0.56 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=-1, octave=2))@7/2", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=-1, octave=2))@31/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=-1, octave=2))@41/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='B', alter=-1, octave=2))@23/4"], 'raw': '|12/8k-2PL:E-2PR:B-3 <|0.02|> 1/8PL:e-2B-2 <|0.27|> 1/8b-2E-2PR:b-3B-3 <|0.36|> 1/8PL:e-2B-2 <|0.54|> 1/8b-2E-2PR:b-3B-3 <|0.76|> 1/8PL:e-2B-2 <|0.89|> 1/8b-2E-2PR:b-3 <|0.97|> 1/8PL:e-2B-2 <|1.16|> 1/8b-2E-2 <|1.26|> 1/8e-2B-2 <|1.40|> 1/8b-2E-2 <|1.58|> 1/8e-2B-2 <|1.76|> 1/8b-2E-2 <|1.94|> 1/8e-2B-2 <|2.12|> 1/8b-2E', 'truncated': '|12/8k-2PL:E-2PR:B-3 <|0.02|> 1/8PL:e-2B-2 <|0.27|> 1/8b-2E-2PR:b-3B-3 <|0.36|> 1/8PL:e-2B-2 <|0.54|', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=40 TS_MISSING=36 TERMINAL=35 TS_PARSE=19 parse_error=18 MEASURE=14 TS_NONMONOTONE=9 /共48
  eval 汇总: parseable=0.00 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.47/前缀0.50 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.24687499999999998 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 26000 (2026-07-30 06:49:50)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.08 Δts=+0.02 Δpitch=+0.09 真sem=0.62 静sem=0.53 真pitch=0.67 acc=0.48 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.03 Δpitch=-0.08 真sem=0.73 静sem=0.72 真pitch=0.20 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.01 Δpitch=+0.05 真sem=0.57 静sem=0.53 真pitch=0.33 acc=0.48 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.20 Δpitch=+0.17 真sem=0.60 静sem=0.40 真pitch=0.77 acc=0.55 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 27000 (2026-07-30 09:30:38)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.09 Δts=+0.02 Δpitch=+0.07 真sem=0.62 静sem=0.53 真pitch=0.66 acc=0.49 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.00 Δpitch=-0.04 真sem=0.73 静sem=0.71 真pitch=0.22 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.03 Δts=-0.02 Δpitch=+0.05 真sem=0.56 静sem=0.53 真pitch=0.36 acc=0.48 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.15 Δts=+0.13 Δpitch=+0.11 真sem=0.61 静sem=0.46 真pitch=0.79 acc=0.56 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 28000 (2026-07-30 12:22:00)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.09 Δts=+0.01 Δpitch=+0.11 真sem=0.65 静sem=0.56 真pitch=0.70 acc=0.51 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.01 Δpitch=-0.03 真sem=0.73 静sem=0.71 真pitch=0.23 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.06 Δts=-0.01 Δpitch=+0.05 真sem=0.59 静sem=0.53 真pitch=0.36 acc=0.51 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.12 Δts=+0.08 Δpitch=+0.09 真sem=0.61 静sem=0.48 真pitch=0.79 acc=0.56 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 29000 (2026-07-30 16:56:32)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.12 Δts=+0.05 Δpitch=+0.08 真sem=0.68 静sem=0.56 真pitch=0.70 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.03 Δpitch=-0.09 真sem=0.73 静sem=0.71 真pitch=0.20 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.02 Δpitch=+0.05 真sem=0.56 静sem=0.51 真pitch=0.38 acc=0.48 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.12 Δpitch=+0.10 真sem=0.61 静sem=0.44 真pitch=0.78 acc=0.56 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 30000 (2026-07-30 22:04:28)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.10 Δts=+0.07 Δpitch=+0.09 真sem=0.69 静sem=0.59 真pitch=0.70 acc=0.55 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.03 Δts=+0.01 Δpitch=-0.09 真sem=0.73 静sem=0.70 真pitch=0.21 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.06 Δpitch=+0.03 真sem=0.56 静sem=0.52 真pitch=0.33 acc=0.48 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.16 Δts=+0.13 Δpitch=+0.13 真sem=0.62 静sem=0.47 真pitch=0.79 acc=0.57 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PR', SPitch(step='C', alter=0, octave=4))@27/8", "DYCK_UNCLOSED:[('PL', SPitch(step='A', alter=-1, octave=2)), ('PL', SPitch(step='E', alter=-1, octave=3)), ('PR', SPitch(step='A', alter=-1, octave=4))]", 'TERMINAL_BAR_MISSING', 'TS_MISSING:102'], 'raw': '|6/8k-4PL:A-2PR:C4 <|0.08|> 1/8PL:a-2E-3PR:c4D-4 <|0.32|> 1/8PL:e-3A-3PR:d-4C4 <|0.50|> 1/8PL:a-3A-2E-3PR:c4D-4 <|0.69|> 1/8PL:a-2e-3A-2E-3PR:d-4C4 <|0.90|> 1/8PL:a-2e-3A-2E-3PR:c4D-4 <|1.06|> 1/8PL:a-2e-3A-2E-3PR:d-4C4 <|1.20|> 1/8PL:a-2e-3PR:c4 <|1.39|> |6/8k-4PL:A-2E-3PR:C4 <|1.39|> 1/8PL:a-2e-3A-2E-3PR:c4D-4 <|1.59', 'truncated': '|6/8k-4PL:A-2PR:C4 <|0.08|> 1/8PL:a-2E-3PR:c4D-4 <|0.32|> 1/8PL:e-3A-3PR:d-4C4 <|0.50|> 1/8PL:a-3A-2', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=47 TERMINAL=43 TS_MISSING=41 MEASURE=22 TS_PARSE=5 parse_error=5 TS_NONMONOTONE=2 /共48
  eval 汇总: parseable=0.00 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.55/前缀0.56 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.2691666666666667 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 31000 (2026-07-31 01:16:26)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.04 Δpitch=+0.25 真sem=0.69 静sem=0.55 真pitch=0.72 acc=0.56 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.00 Δts=+0.00 Δpitch=-0.07 真sem=0.73 静sem=0.73 真pitch=0.21 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.04 Δts=+0.00 Δpitch=+0.05 真sem=0.58 静sem=0.55 真pitch=0.38 acc=0.51 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.10 Δts=+0.18 Δpitch=+0.09 真sem=0.62 静sem=0.52 真pitch=0.79 acc=0.58 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 32000 (2026-07-31 03:36:17)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.09 Δpitch=+0.13 真sem=0.71 静sem=0.57 真pitch=0.73 acc=0.57 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.03 Δpitch=-0.07 真sem=0.73 静sem=0.72 真pitch=0.21 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.05 Δts=+0.03 Δpitch=+0.13 真sem=0.58 静sem=0.53 真pitch=0.46 acc=0.50 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.13 Δts=+0.19 Δpitch=+0.07 真sem=0.63 静sem=0.50 真pitch=0.78 acc=0.58 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 33000 (2026-07-31 06:10:13)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.11 Δts=+0.12 Δpitch=+0.18 真sem=0.68 静sem=0.58 真pitch=0.77 acc=0.56 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.03 Δts=-0.03 Δpitch=-0.08 真sem=0.74 静sem=0.71 真pitch=0.22 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.08 Δts=+0.03 Δpitch=+0.18 真sem=0.60 静sem=0.53 真pitch=0.49 acc=0.52 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.21 Δts=+0.23 Δpitch=+0.17 真sem=0.64 静sem=0.43 真pitch=0.78 acc=0.59 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 34000 (2026-07-31 08:29:50)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.13 Δts=+0.13 Δpitch=+0.20 真sem=0.70 静sem=0.57 真pitch=0.77 acc=0.58 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.03 Δpitch=-0.05 真sem=0.74 静sem=0.72 真pitch=0.26 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.07 Δts=+0.09 Δpitch=+0.13 真sem=0.60 静sem=0.53 真pitch=0.44 acc=0.52 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.20 Δpitch=+0.15 真sem=0.64 静sem=0.44 真pitch=0.79 acc=0.59 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 35000 (2026-07-31 11:09:16)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.11 Δts=+0.16 Δpitch=+0.27 真sem=0.67 静sem=0.57 真pitch=0.76 acc=0.57 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.00 Δts=-0.01 Δpitch=-0.10 真sem=0.72 静sem=0.72 真pitch=0.17 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.08 Δts=+0.01 Δpitch=+0.13 真sem=0.61 静sem=0.53 真pitch=0.44 acc=0.52 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.08 Δts=+0.08 Δpitch=+0.03 真sem=0.60 静sem=0.52 真pitch=0.76 acc=0.55 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='A', alter=-1, octave=3))@2", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='A', alter=-1, octave=3))@35/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=-1, octave=3))@57/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='A', alter=-1, octave=3))@15/2"], 'raw': '|6/8k-4PL:F3 <|0.01|> 1/8f3A-3 <|0.24|> 1/8a-3A-3 <|0.42|> 1/8a-3A-3 <|0.59|> 1/8a-3A-3 <|0.78|> 1/8a-3A-3 <|0.95|> 1/8a-3A-3 <|1.16|> 1/8a-3A-3 <|1.36|> 1/8a-3A-3 <|1.54|> 1/8a-3A-3 <|1.68|> 1/8a-3A-3 <|1.83|> 1/8a-3A-3 <|1.93|> 1/8a-3A-3 <|2.09|> 1/8a-3A-3 <|2.22|> 1/8a-3A-3 <|2.33|> 1/8a-3A-3 <|2.49|> 1/8a-3A-3 <|2.', 'truncated': '|6/8k-4PL:F3 <|0.01|> 1/8f3A-3 <|0.24|> 1/8a-3A-3 <|0.42|> 1/8a-3A-3 <|0.59|> 1/8a-3A-3 <|0.78|> 1/8', 'gen': {'n_new': 866, 'stop': 'eot', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=48 TERMINAL=45 TS_MISSING=39 MEASURE=16 TS_PARSE=13 parse_error=13 TS_NONMONOTONE=7 /共48
  eval 汇总: parseable=0.00 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.57/前缀0.53 eotP0=0.0001
  eval 指标: parseable=0.00 amt_f1=0.6356250000000001 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 36000 (2026-07-31 18:40:59)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.13 Δts=+0.10 Δpitch=+0.20 真sem=0.71 静sem=0.57 真pitch=0.80 acc=0.58 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.11 Δpitch=-0.04 真sem=0.73 静sem=0.71 真pitch=0.22 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.09 Δts=+0.01 Δpitch=+0.21 真sem=0.61 静sem=0.52 真pitch=0.46 acc=0.53 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.15 Δts=+0.11 Δpitch=+0.12 真sem=0.66 静sem=0.50 真pitch=0.80 acc=0.60 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 37000 (2026-08-01 01:10:36)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.11 Δts=+0.15 Δpitch=+0.13 真sem=0.67 静sem=0.56 真pitch=0.75 acc=0.57 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=-0.05 Δpitch=-0.08 真sem=0.72 静sem=0.72 真pitch=0.19 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.08 Δts=+0.03 Δpitch=+0.21 真sem=0.62 静sem=0.53 真pitch=0.51 acc=0.53 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.17 Δpitch=+0.09 真sem=0.65 静sem=0.49 真pitch=0.79 acc=0.60 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 38000 (2026-08-01 03:38:01)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.15 Δts=+0.15 Δpitch=+0.19 真sem=0.72 静sem=0.57 真pitch=0.82 acc=0.60 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.00 Δts=-0.04 Δpitch=-0.10 真sem=0.73 静sem=0.73 真pitch=0.21 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.10 Δts=+0.08 Δpitch=+0.18 真sem=0.63 静sem=0.53 真pitch=0.51 acc=0.55 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.16 Δts=+0.17 Δpitch=+0.10 真sem=0.65 静sem=0.49 真pitch=0.79 acc=0.60 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 39000 (2026-08-01 06:05:30)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.18 Δpitch=+0.19 真sem=0.70 静sem=0.57 真pitch=0.79 acc=0.59 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.00 Δts=+0.03 Δpitch=-0.07 真sem=0.73 静sem=0.73 真pitch=0.24 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.13 Δts=+0.10 Δpitch=+0.21 真sem=0.64 静sem=0.51 真pitch=0.54 acc=0.56 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.18 Δpitch=+0.13 真sem=0.65 静sem=0.48 真pitch=0.78 acc=0.60 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 40000 (2026-08-01 08:53:49)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.16 Δpitch=+0.16 真sem=0.72 静sem=0.59 真pitch=0.80 acc=0.60 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.00 Δts=-0.01 Δpitch=-0.05 真sem=0.72 静sem=0.73 真pitch=0.23 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.11 Δts=+0.05 Δpitch=+0.13 真sem=0.64 静sem=0.53 真pitch=0.51 acc=0.55 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.10 Δpitch=+0.14 真sem=0.67 静sem=0.48 真pitch=0.81 acc=0.61 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='F', alter=0, octave=3))@33/8", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='F', alter=0, octave=3))@61/8", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='F', alter=0, octave=3))@35/4", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='F', alter=0, octave=3))@103/8"], 'raw': '|12/8k-2PL:B-2 <|0.00|> 1/8b-2F3 <|0.21|> 1/8f3F3 <|0.36|> 1/8f3F3 <|0.46|> 1/8f3F3 <|0.55|> 1/8f3F3 <|0.75|> 1/8f3F3 <|0.89|> 1/8f3F3 <|1.06|> 1/8f3F3 <|1.17|> 1/8f3F3 <|1.28|> 1/8f3F3 <|1.44|> 1/8f3F3 <|1.52|> 1/8f3F3 <|1.68|> 1/8f3F3 <|1.77|> 1/8f3 <|1.94|> |12/8k-2F3 <|1.94|> 1/8f3F3 <|2.10|> 1/8f3F3 <|2.21|> 1/8f3', 'truncated': '|12/8k-2PL:B-2 <|0.00|> 1/8b-2F3 <|0.21|> 1/8f3F3 <|0.36|> 1/8f3F3 <|0.46|> 1/8f3F3 <|0.55|> 1/8f3F3', 'gen': {'n_new': 756, 'stop': 'eot', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=48 TERMINAL=39 TS_MISSING=38 MEASURE=16 TS_PARSE=7 parse_error=6 TS_NONMONOTONE=3 /共48
  eval 汇总: parseable=0.00 empty=0.9583333333333334 n=48 样本0='|4/4k0' 探针acc=0.60/前缀0.59 eotP0=0.0000
  eval 指标: parseable=0.00 amt_f1=0.5835416666666667 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 41000 (2026-08-01 11:21:39)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.16 Δpitch=+0.34 真sem=0.72 静sem=0.57 真pitch=0.85 acc=0.60 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=-0.02 Δts=-0.05 Δpitch=-0.06 真sem=0.72 静sem=0.73 真pitch=0.22 acc=0.62 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.11 Δts=+0.01 Δpitch=+0.18 真sem=0.64 静sem=0.53 真pitch=0.51 acc=0.54 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.20 Δts=+0.13 Δpitch=+0.18 真sem=0.67 静sem=0.47 真pitch=0.82 acc=0.62 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 42000 (2026-08-01 13:49:18)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.15 Δts=+0.18 Δpitch=+0.25 真sem=0.72 静sem=0.57 真pitch=0.87 acc=0.61 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.00 Δts=+0.02 Δpitch=-0.08 真sem=0.71 静sem=0.71 真pitch=0.21 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.08 Δts=+0.00 Δpitch=+0.21 真sem=0.62 静sem=0.55 真pitch=0.54 acc=0.53 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.11 Δpitch=+0.11 真sem=0.66 静sem=0.49 真pitch=0.81 acc=0.60 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 43000 (2026-08-01 16:17:54)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.15 Δts=+0.12 Δpitch=+0.19 真sem=0.72 静sem=0.57 真pitch=0.83 acc=0.60 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=+0.01 Δpitch=-0.03 真sem=0.73 静sem=0.71 真pitch=0.26 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.11 Δpitch=+0.21 真sem=0.65 静sem=0.52 真pitch=0.54 acc=0.57 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.10 Δpitch=+0.08 真sem=0.68 静sem=0.50 真pitch=0.82 acc=0.62 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 44000 (2026-08-01 18:46:19)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.16 Δpitch=+0.17 真sem=0.74 静sem=0.59 真pitch=0.83 acc=0.62 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=+0.01 Δpitch=+0.00 真sem=0.72 静sem=0.71 真pitch=0.28 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.11 Δts=+0.10 Δpitch=+0.28 真sem=0.66 静sem=0.55 真pitch=0.62 acc=0.58 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.13 Δpitch=+0.12 真sem=0.69 静sem=0.51 真pitch=0.84 acc=0.64 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 45000 (2026-08-01 21:34:20)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.11 Δts=+0.15 Δpitch=+0.26 真sem=0.72 静sem=0.60 真pitch=0.87 acc=0.60 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.05 Δpitch=-0.05 真sem=0.73 静sem=0.71 真pitch=0.24 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.14 Δts=+0.09 Δpitch=+0.28 真sem=0.67 静sem=0.53 真pitch=0.56 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.16 Δts=+0.12 Δpitch=+0.11 真sem=0.67 静sem=0.51 真pitch=0.81 acc=0.62 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='D', alter=-1, octave=3))@15/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=-1, octave=3))@75/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=-1, octave=3))@85/8", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='F', alter=0, octave=3))@85/8"], 'raw': '|3/4k-5PL:D-3F3 <|0.02|> 1/8d-3f3D-3F3 <|0.38|> 1/8d-3f3D-3F3 <|0.54|> 1/8d-3f3D-3F3 <|0.74|> 1/8d-3f3D-3F3 <|0.88|> 1/8d-3f3D-3F3 <|1.08|> 1/8d-3f3D-3F3 <|1.21|> 1/8d-3f3 <|1.38|> |3/4k-5D-3F3 <|1.38|> 1/8d-3f3D-3F3 <|1.55|> 1/8d-3f3D-3F3 <|1.74|> 1/8d-3f3D-3F3 <|1.95|> 1/8d-3f3D-3F3 <|2.11|> 1/8d-3f3D-3F3 <|2.25|> 1/', 'truncated': '|3/4k-5PL:D-3F3 <|0.02|> 1/8d-3f3D-3F3 <|0.38|> 1/8d-3f3D-3F3 <|0.54|> 1/8d-3f3D-3F3 <|0.74|> 1/8d-3', 'gen': {'n_new': 772, 'stop': 'eot', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=47 TERMINAL=40 TS_MISSING=36 MEASURE=16 TS_PARSE=12 parse_error=11 TS_NONMONOTONE=3 /共48
  eval 汇总: parseable=0.00 empty=0.9791666666666666 n=48 样本0='|4/4k0' 探针acc=0.60/前缀0.59 eotP0=0.0001
  eval 指标: parseable=0.00 amt_f1=1.0018749999999998 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 46000 (2026-08-02 00:02:01)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.16 Δts=+0.13 Δpitch=+0.26 真sem=0.75 静sem=0.59 真pitch=0.88 acc=0.62 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.03 Δts=-0.03 Δpitch=-0.04 真sem=0.73 静sem=0.70 真pitch=0.24 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.10 Δts=+0.09 Δpitch=+0.21 真sem=0.65 静sem=0.54 真pitch=0.56 acc=0.57 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.13 Δpitch=+0.11 真sem=0.68 静sem=0.50 真pitch=0.83 acc=0.62 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 47000 (2026-08-02 02:29:31)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.12 Δpitch=+0.29 真sem=0.75 静sem=0.62 真pitch=0.86 acc=0.62 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.01 Δpitch=-0.02 真sem=0.72 静sem=0.72 真pitch=0.30 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.02 Δpitch=+0.28 真sem=0.68 静sem=0.57 真pitch=0.62 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.12 Δpitch=+0.12 真sem=0.70 静sem=0.52 真pitch=0.83 acc=0.64 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 48000 (2026-08-02 04:57:42)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.15 Δpitch=+0.23 真sem=0.75 静sem=0.61 真pitch=0.88 acc=0.62 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.05 Δts=-0.03 Δpitch=+0.02 真sem=0.73 静sem=0.69 真pitch=0.32 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.15 Δts=+0.03 Δpitch=+0.23 真sem=0.69 静sem=0.55 真pitch=0.62 acc=0.60 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.17 Δts=+0.13 Δpitch=+0.11 真sem=0.69 静sem=0.51 真pitch=0.82 acc=0.63 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 49000 (2026-08-02 07:26:04)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.19 Δts=+0.19 Δpitch=+0.26 真sem=0.74 静sem=0.54 真pitch=0.85 acc=0.62 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.01 Δts=-0.01 Δpitch=-0.03 真sem=0.72 静sem=0.71 真pitch=0.26 acc=0.63 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.07 Δpitch=+0.23 真sem=0.65 静sem=0.53 真pitch=0.56 acc=0.56 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.17 Δpitch=+0.13 真sem=0.69 静sem=0.50 真pitch=0.83 acc=0.64 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 50000 (2026-08-02 10:14:23)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.13 Δts=+0.25 Δpitch=+0.22 真sem=0.73 静sem=0.60 真pitch=0.89 acc=0.63 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.05 Δts=-0.03 Δpitch=+0.05 真sem=0.75 静sem=0.70 真pitch=0.35 acc=0.66 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.15 Δpitch=+0.23 真sem=0.67 静sem=0.55 真pitch=0.56 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.16 Δts=+0.14 Δpitch=+0.11 真sem=0.69 静sem=0.53 真pitch=0.85 acc=0.63 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=1, octave=3))@41/16", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=1, octave=3))@23/8", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='B', alter=0, octave=2))@53/16", "DYCK_DOUBLE_ONSET:('PL', SPitch(step='B', alter=0, octave=2))@59/16"], 'raw': '|3/8k#2PL:D3PR:A3 <|0.17|> 1/8PL:d3F#3PR:a3F#4 <|0.37|> 1/8PL:f#3F#3PR:f#4F#4 <|0.53|> 1/16PL:f#3F#3PR:f#4F#4 <|0.71|> 1/16PL:f#3F#3PR:f#4F#4 <|0.88|> 1/16PL:f#3PR:f#4 <|1.03|> |3/8k#2PL:A3PR:F#4 <|1.03|> 1/16PL:a3F#3PR:f#4F#4 <|1.17|> 1/16PL:f#3A3PR:f#4E4 <|1.28|> 1/16PL:a3F#3PR:e4F#4 <|1.37|> 1/16PL:f#3A3PR:f#4E5 <|1', 'truncated': '|3/8k#2PL:D3PR:A3 <|0.17|> 1/8PL:d3F#3PR:a3F#4 <|0.37|> 1/8PL:f#3F#3PR:f#4F#4 <|0.53|> 1/16PL:f#3F#3', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=47 TERMINAL=39 TS_MISSING=38 MEASURE=15 TS_PARSE=7 parse_error=6 TS_NONMONOTONE=4 /共48
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.63/前缀0.59 eotP0=0.0001
  eval 指标: parseable=0.00 amt_f1=2.2725 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 51000 (2026-08-02 12:43:29)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.17 Δts=+0.19 Δpitch=+0.23 真sem=0.74 静sem=0.57 真pitch=0.85 acc=0.63 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=+0.00 Δpitch=-0.02 真sem=0.74 静sem=0.70 真pitch=0.27 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.11 Δpitch=+0.15 真sem=0.68 静sem=0.56 真pitch=0.56 acc=0.59 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.13 Δpitch=+0.12 真sem=0.70 静sem=0.51 真pitch=0.86 acc=0.64 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 52000 (2026-08-02 15:11:23)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.17 Δts=+0.10 Δpitch=+0.27 真sem=0.77 静sem=0.60 真pitch=0.89 acc=0.62 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.03 Δts=+0.01 Δpitch=+0.00 真sem=0.74 静sem=0.71 真pitch=0.31 acc=0.67 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.14 Δts=+0.05 Δpitch=+0.18 真sem=0.69 静sem=0.55 真pitch=0.59 acc=0.60 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.13 Δpitch=+0.14 真sem=0.70 静sem=0.52 真pitch=0.85 acc=0.64 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 53000 (2026-08-02 17:39:09)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.17 Δts=+0.22 Δpitch=+0.24 真sem=0.75 静sem=0.59 真pitch=0.88 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.05 Δts=-0.04 Δpitch=+0.02 真sem=0.75 静sem=0.69 真pitch=0.31 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.11 Δts=+0.13 Δpitch=+0.26 真sem=0.68 静sem=0.56 真pitch=0.67 acc=0.60 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.20 Δts=+0.17 Δpitch=+0.17 真sem=0.70 静sem=0.50 真pitch=0.86 acc=0.64 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 54000 (2026-08-02 20:08:20)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.17 Δts=+0.20 Δpitch=+0.25 真sem=0.77 静sem=0.61 真pitch=0.90 acc=0.65 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.01 Δpitch=+0.01 真sem=0.73 静sem=0.71 真pitch=0.35 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.05 Δpitch=+0.26 真sem=0.67 静sem=0.55 真pitch=0.59 acc=0.58 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.14 Δpitch=+0.12 真sem=0.69 静sem=0.51 真pitch=0.86 acc=0.64 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 55000 (2026-08-02 22:55:30)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.16 Δts=+0.20 Δpitch=+0.25 真sem=0.77 静sem=0.61 真pitch=0.89 acc=0.65 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=+0.04 Δpitch=+0.02 真sem=0.75 静sem=0.71 真pitch=0.34 acc=0.67 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.14 Δts=+0.09 Δpitch=+0.21 真sem=0.69 静sem=0.55 真pitch=0.62 acc=0.60 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.17 Δpitch=+0.16 真sem=0.70 静sem=0.51 真pitch=0.85 acc=0.65 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_ORPHAN_OFFSET:('PL', SPitch(step='G', alter=0, octave=3))@13/16", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='F', alter=1, octave=4))@13/16", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='A', alter=0, octave=3))@13/8", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='A', alter=0, octave=3))@19/8"], 'raw': '|3/8k#2PL:D3PR:A3 <|0.01|> 1/8PL:d3F#3PR:a3F#4 <|0.26|> 1/8PL:f#3G3PR:f#4F#4 <|0.44|> 1/16PL:g3F#3PR:f#4F#4 <|0.57|> 1/16PL:f#3F#3PR:f#4F#4 <|0.69|> 1/16PL:f#3PR:f#4 <|0.84|> |3/8k#2PL:G3PR:G4 <|0.84|> 1/16PL:g3A3PR:g4F#4 <|0.99|> 1/16PL:a3G3PR:f#4F#4 <|1.09|> 1/16PL:g3F#3PR:f#4E#4 <|1.20|> 1/16PL:f#3G3PR:e#4F#4 <|1.36', 'truncated': '|3/8k#2PL:D3PR:A3 <|0.01|> 1/8PL:d3F#3PR:a3F#4 <|0.26|> 1/8PL:f#3G3PR:f#4F#4 <|0.44|> 1/16PL:g3F#3PR', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=46 TERMINAL=38 TS_MISSING=38 MEASURE=23 TS_PARSE=9 parse_error=7 TS_NONMONOTONE=2 /共48
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.65/前缀0.62 eotP0=0.0001
  eval 指标: parseable=0.00 amt_f1=5.4925 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 56000 (2026-08-03 01:22:55)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.11 Δts=+0.20 Δpitch=+0.20 真sem=0.76 静sem=0.64 真pitch=0.87 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.02 Δpitch=+0.02 真sem=0.73 静sem=0.71 真pitch=0.33 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.13 Δts=+0.14 Δpitch=+0.23 真sem=0.70 静sem=0.57 真pitch=0.67 acc=0.62 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.18 Δts=+0.14 Δpitch=+0.17 真sem=0.70 静sem=0.52 真pitch=0.86 acc=0.64 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 57000 (2026-08-03 03:49:52)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.13 Δts=+0.22 Δpitch=+0.22 真sem=0.76 静sem=0.63 真pitch=0.87 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=-0.01 Δpitch=+0.02 真sem=0.73 静sem=0.69 真pitch=0.30 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.12 Δts=+0.09 Δpitch=+0.28 真sem=0.69 静sem=0.57 真pitch=0.69 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.12 Δpitch=+0.13 真sem=0.71 静sem=0.52 真pitch=0.88 acc=0.65 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 58000 (2026-08-03 06:17:09)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.16 Δpitch=+0.20 真sem=0.74 静sem=0.60 真pitch=0.87 acc=0.62 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=-0.01 Δpitch=+0.09 真sem=0.74 静sem=0.70 真pitch=0.37 acc=0.66 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.14 Δts=+0.16 Δpitch=+0.28 真sem=0.69 静sem=0.55 真pitch=0.69 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.19 Δts=+0.22 Δpitch=+0.12 真sem=0.71 静sem=0.51 真pitch=0.86 acc=0.66 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 59000 (2026-08-03 08:44:55)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.18 Δpitch=+0.21 真sem=0.77 静sem=0.63 真pitch=0.88 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=-0.01 Δpitch=+0.05 真sem=0.74 静sem=0.70 真pitch=0.34 acc=0.66 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.15 Δts=+0.06 Δpitch=+0.23 真sem=0.70 静sem=0.55 真pitch=0.64 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.21 Δts=+0.09 Δpitch=+0.15 真sem=0.72 静sem=0.51 真pitch=0.86 acc=0.65 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 60000 (2026-08-03 11:32:29)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.13 Δts=+0.17 Δpitch=+0.23 真sem=0.76 静sem=0.62 真pitch=0.85 acc=0.63 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.04 Δpitch=-0.01 真sem=0.74 静sem=0.72 真pitch=0.28 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.15 Δts=+0.07 Δpitch=+0.26 真sem=0.70 静sem=0.55 真pitch=0.69 acc=0.61 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.20 Δts=+0.22 Δpitch=+0.15 真sem=0.72 静sem=0.52 真pitch=0.87 acc=0.67 n=724
  eval 样本预测[0]: '|4/4k0'
  eval 样本预测[1]: '|4/4k0'
  eval 解码现场: {'stage': 'validate_reject', 'viol': ["DYCK_DOUBLE_ONSET:('PL', SPitch(step='C', alter=1, octave=3))@33/16", "DYCK_ORPHAN_OFFSET:('PR', SPitch(step='F', alter=1, octave=4))@139/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='D', alter=0, octave=3))@179/16", "DYCK_ORPHAN_OFFSET:('PL', SPitch(step='F', alter=1, octave=3))@191/16"], 'raw': '|3/8k#2PL:D3PR:D4 <|0.06|> 1/8PL:d3C#3 <|0.27|> 1/8c#3F#3 <|0.52|> 1/8f#3G3PR:d4F#4 <|0.75|> 1/16PL:g3F#3PR:f#4 <|0.89|> 1/16PL:f#3F#3 <|1.02|> 1/16f#3 <|1.17|> |3/8k#2G3PR:G4 <|1.17|> 1/16g4F#4 <|1.28|> 1/16PL:g3F#3PR:f#4E#4 <|1.36|> 1/16PL:f#3F#3PR:e#4F#4 <|1.50|> 1/16PL:f#3PR:f#4 <|1.61|> |3/8k#2PL:C#4PR:E5 <|1.61|>', 'truncated': '|3/8k#2PL:D3PR:D4 <|0.06|> 1/8PL:d3C#3 <|0.27|> 1/8c#3F#3 <|0.52|> 1/8f#3G3PR:d4F#4 <|0.75|> 1/16PL:', 'gen': {'n_new': 900, 'stop': 'cap', 'fast': True, 'beam_size': 1}}
  eval 拒因(样本数): DYCK=46 TERMINAL=35 TS_MISSING=34 MEASURE=23 TS_PARSE=9 parse_error=7 TS_NONMONOTONE=4 /共48
  eval 汇总: parseable=0.00 empty=1.0 n=48 样本0='|4/4k0' 探针acc=0.63/前缀0.56 eotP0=0.0001
  eval 指标: parseable=0.00 amt_f1=2.6456250000000003 text_ned_proxy=None proxy_scored=0/48 n_maestro=48/48 complete=True

## eval @ step 61000 (2026-08-03 14:01:20)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.20 Δpitch=+0.27 真sem=0.76 静sem=0.62 真pitch=0.90 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.02 Δpitch=+0.00 真sem=0.73 静sem=0.70 真pitch=0.31 acc=0.64 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.15 Δts=+0.10 Δpitch=+0.28 真sem=0.71 静sem=0.56 真pitch=0.72 acc=0.62 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.21 Δts=+0.15 Δpitch=+0.15 真sem=0.72 静sem=0.51 真pitch=0.86 acc=0.66 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## decode-abtest @ step 61200 (2026-08-03 14:38:07)
decode-abtest @ step 61200;同子集 n=4;beam→greedy 回退=关
  beam=1: parseable=0/4 fallback=4 elapsed=43.6s 拒因:DYCK=3 TERMINAL=3 TS_MISSING=3 TS_PARSE=3 parse_error=3
  beam=4: parseable=0/4 fallback=4 elapsed=136.8s 拒因:TS_PARSE=3 parse_error=3 DYCK=1 TERMINAL=1 TS_MISSING=1

## decode-abtest @ step 61200 (2026-08-03 14:45:24)
decode-abtest @ step 61200;同子集 n=4;domain=sample.domain;beam→greedy 回退=关
  beam=1: parseable=0/4 fallback=4 elapsed=45.6s 拒因:DYCK=4 TERMINAL=4 TS_PARSE=3 parse_error=3 TS_MISSING=2
  beam=4: parseable=0/4 fallback=4 elapsed=123.4s 拒因:TS_PARSE=3 parse_error=3 DYCK=2 TERMINAL=2 MEASURE=1 TS_MISSING=1

## eval @ step 62000 (2026-08-03 16:49:32)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.14 Δts=+0.16 Δpitch=+0.27 真sem=0.76 静sem=0.63 真pitch=0.90 acc=0.63 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.04 Δts=+0.01 Δpitch=+0.04 真sem=0.74 静sem=0.70 真pitch=0.35 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.17 Δts=+0.07 Δpitch=+0.28 真sem=0.71 静sem=0.54 真pitch=0.67 acc=0.62 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.21 Δts=+0.12 Δpitch=+0.18 真sem=0.72 静sem=0.51 真pitch=0.87 acc=0.66 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## eval @ step 63000 (2026-08-03 19:18:28)
  eval 多源探针 nasap/TAST[nasap_Shi05M_63322b36_000]: Δsem=+0.12 Δts=+0.18 Δpitch=+0.24 真sem=0.76 静sem=0.64 真pitch=0.90 acc=0.64 n=704
  eval 多源探针 maestro/AMT[maestro_MIDI-Unprocessed_11_R1_2009_06-09_ORIG_MID--AUDIO_11_R1_2009_11_R1_2009_06_WAV_000]: Δsem=+0.02 Δts=-0.01 Δpitch=-0.01 真sem=0.73 静sem=0.71 真pitch=0.28 acc=0.65 n=660
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000]: Δsem=+0.17 Δts=+0.14 Δpitch=+0.28 真sem=0.73 静sem=0.56 真pitch=0.72 acc=0.65 n=479
  eval 多源探针 pdmx/TAST[pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000]: Δsem=+0.21 Δts=+0.09 Δpitch=+0.17 真sem=0.71 静sem=0.50 真pitch=0.88 acc=0.65 n=724
  eval(仅探针;解码腿按 eval_decode_every 稀疏跑,本次跳过)

## decode-abtest @ step 63800 (2026-08-03 22:34:30)
decode-abtest @ step 63800;同子集 n=24;16 臂;domain=sample.domain;beam→greedy 回退=关
  beam=1 rep=1.0 eot=0.0: parseable=0/24 fallback=24 elapsed=256.7s 拒因:DYCK=24 TERMINAL=23 TS_MISSING=21 MEASURE=9 TS_PARSE=6 parse_error=6 TS_NONMONOTONE=5
  beam=1 rep=1.0 eot=1.0: parseable=0/24 fallback=24 elapsed=233.7s 拒因:DYCK=24 TERMINAL=22 TS_MISSING=21 MEASURE=10 TS_NONMONOTONE=5 TS_PARSE=5 parse_error=5
  beam=1 rep=1.0 eot=2.0: parseable=0/24 fallback=24 elapsed=224.5s 拒因:DYCK=24 TERMINAL=21 TS_MISSING=21 MEASURE=10 TS_NONMONOTONE=5 TS_PARSE=3 parse_error=3
  beam=1 rep=1.0 eot=4.0: parseable=0/24 fallback=24 elapsed=208.4s 拒因:DYCK=24 TS_MISSING=20 TERMINAL=19 MEASURE=12 TS_NONMONOTONE=4 TS_PARSE=3 parse_error=3
  beam=1 rep=1.1 eot=0.0: parseable=0/24 fallback=24 elapsed=250.8s 拒因:DYCK=24 TERMINAL=21 TS_MISSING=21 MEASURE=10 TS_PARSE=6 parse_error=6 TS_NONMONOTONE=3
  beam=1 rep=1.1 eot=1.0: parseable=0/24 fallback=24 elapsed=245.0s 拒因:DYCK=24 TERMINAL=21 TS_MISSING=21 MEASURE=11 TS_PARSE=5 parse_error=5 TS_NONMONOTONE=3
  beam=1 rep=1.1 eot=2.0: parseable=0/24 fallback=24 elapsed=234.9s 拒因:DYCK=24 TERMINAL=22 TS_MISSING=21 MEASURE=10 TS_PARSE=5 parse_error=5 TS_NONMONOTONE=3
  beam=1 rep=1.1 eot=4.0: parseable=1/24 fallback=23 elapsed=214.1s 拒因:DYCK=23 TS_MISSING=21 TERMINAL=20 MEASURE=10 TS_PARSE=3 parse_error=3 TS_NONMONOTONE=2 通过=1
  beam=1 rep=1.3 eot=0.0: parseable=0/24 fallback=24 elapsed=249.3s 拒因:DYCK=23 TERMINAL=22 TS_MISSING=21 MEASURE=8 TS_PARSE=6 parse_error=6 TS_NONMONOTONE=3
  beam=1 rep=1.3 eot=1.0: parseable=0/24 fallback=24 elapsed=242.8s 拒因:DYCK=23 TERMINAL=21 TS_MISSING=21 MEASURE=9 TS_PARSE=5 parse_error=5 TS_NONMONOTONE=3
  beam=1 rep=1.3 eot=2.0: parseable=0/24 fallback=24 elapsed=245.6s 拒因:DYCK=23 TERMINAL=21 TS_MISSING=20 MEASURE=8 TS_PARSE=5 parse_error=5 TS_NONMONOTONE=3
  beam=1 rep=1.3 eot=4.0: parseable=1/24 fallback=23 elapsed=218.9s 拒因:DYCK=23 TERMINAL=19 TS_MISSING=19 MEASURE=11 TS_PARSE=3 parse_error=3 TS_NONMONOTONE=2 通过=1
  beam=1 rep=1.5 eot=0.0: parseable=0/24 fallback=24 elapsed=245.6s 拒因:DYCK=23 TERMINAL=19 TS_MISSING=19 MEASURE=8 TS_PARSE=8 parse_error=8
  beam=1 rep=1.5 eot=1.0: parseable=0/24 fallback=24 elapsed=242.6s 拒因:DYCK=23 TERMINAL=20 TS_MISSING=19 MEASURE=8 TS_PARSE=7 parse_error=7
  beam=1 rep=1.5 eot=2.0: parseable=0/24 fallback=24 elapsed=231.5s 拒因:DYCK=24 TERMINAL=20 TS_MISSING=20 MEASURE=8 TS_PARSE=7 parse_error=7
  beam=1 rep=1.5 eot=4.0: parseable=1/24 fallback=23 elapsed=205.0s 拒因:DYCK=23 TERMINAL=20 TS_MISSING=18 MEASURE=8 TS_PARSE=3 parse_error=3 通过=1
