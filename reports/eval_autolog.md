
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
