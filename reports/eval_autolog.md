
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
