
## 对齐审计 @ 2026-07-16 14:13:16(per-source=8;判读:OK=corr0≥0.25 且 |lag|≤50ms / SHIFTED=峰值≥0.25 但偏移 / UNCORRELATED=峰值<0.25)
  maestro maestro_MIDI-Unprocessed_R2_D2-19-21-22_mid--AUDIO-from_mp3_21_R2_2015_wav--2_077/AMT: OK corr0=0.539 peak=0.539 lag=0ms onsets=43 帧=464
  maestro maestro_MIDI-Unprocessed_13_R1_2006_01-06_ORIG_MID--AUDIO_13_R1_2006_05_Track05_wav_092/AMT: OK corr0=0.294 peak=0.294 lag=0ms onsets=43 帧=249
  maestro maestro_MIDI-UNPROCESSED_19-20_R1_2014_MID--AUDIO_19_R1_2014_wav--2_225/AMT: OK corr0=0.33 peak=0.451 lag=-10ms onsets=50 帧=615
  maestro maestro_MIDI-Unprocessed_XP_15_R1_2004_04_ORIG_MID--AUDIO_15_R1_2004_04_Track04_wav_142/AMT: OK corr0=0.455 peak=0.475 lag=-10ms onsets=17 帧=732
  maestro maestro_MIDI-Unprocessed_16_R1_2011_MID--AUDIO_R1-D6_15_Track15_wav_065/AMT: SHIFTED corr0=0.319 peak=0.36 lag=-1080ms onsets=38 帧=219
  maestro maestro_MIDI-Unprocessed_17_R1_2009_01-03_ORIG_MID--AUDIO_17_R1_2009_17_R1_2009_01_WAV_066/AMT: OK corr0=0.692 peak=0.707 lag=-10ms onsets=16 帧=116
  maestro maestro_MIDI-Unprocessed_Schubert10-12_MID--AUDIO_17_R2_2018_wav_290/AMT: OK corr0=0.457 peak=0.617 lag=-10ms onsets=22 帧=309
  maestro maestro_ORIG-MIDI_01_7_10_13_Group_MID--AUDIO_02_R3_2013_wav--1_052/AMT: UNCORRELATED corr0=0.087 peak=0.175 lag=-1950ms onsets=17 帧=834
  == maestro: {'OK': 6, 'SHIFTED': 1, 'UNCORRELATED': 1} → OK
  nasap nasap_Shychko02M_61a00b4f_015/TAST: UNCORRELATED corr0=0.224 peak=0.224 lag=0ms onsets=312 帧=3954
  nasap nasap_HuangSW06M_eaf5dddd_001/TAST: UNCORRELATED corr0=-0.015 peak=0.081 lag=1680ms onsets=197 帧=3088
  nasap nasap_MiyashitaM04M_acb3aaa7_013/TAST: UNCORRELATED corr0=0.203 peak=0.203 lag=0ms onsets=54 帧=3708
  nasap nasap_HuNY08M_33f23190_031/TAST: OK corr0=0.297 peak=0.297 lag=0ms onsets=137 帧=2178
  nasap nasap_Kurz04M_b5066a98_034/TAST: UNCORRELATED corr0=0.152 peak=0.169 lag=-10ms onsets=181 帧=1588
  nasap nasap_Bult-ItoS05M_b4b8097c_010/TAST: OK corr0=0.28 peak=0.28 lag=0ms onsets=116 帧=2223
  nasap nasap_Bult-ItoS02M_171360e0_004/TAST: SHIFTED corr0=0.246 peak=0.269 lag=-270ms onsets=80 帧=3661
  nasap nasap_Tario07M_fa9cfb66_006/TAST: UNCORRELATED corr0=0.016 peak=0.073 lag=1680ms onsets=282 帧=3875
  == nasap: {'UNCORRELATED': 5, 'OK': 2, 'SHIFTED': 1} → 对齐故障
  pdmx pdmxperf_QmU17n3jWr8bhwn7NyNykz1wtFubBNFHVpbkpXk2T8d1q2_000/TAST: OK corr0=0.24 peak=0.329 lag=10ms onsets=107 帧=3234
  pdmx pdmxperf_QmZ5ZyJUp7ctnHBPNMRMvZK8SaxP96VdEnZhL4YCnwmLJT_000/TAST: OK corr0=0.413 peak=0.438 lag=-10ms onsets=206 帧=3940
  pdmx pdmxperf_QmQjHc7i1meAvSf25vajtPo3i8kjsJ18eH3TKY4tQUdmFe_000/TAST: OK corr0=0.675 peak=0.688 lag=-10ms onsets=98 帧=3938
  pdmx pdmxperf_QmV43bmCE9BoBLkJqp1xFkQEZzdLNvwgQJFWLbmWvZT731_000/TAST: OK corr0=0.361 peak=0.361 lag=0ms onsets=64 帧=1378
  pdmx pdmxperf_QmedmJPDEdynAFTsN8sErSHsuAXvDPZ6REFgVC99yprTNe_000/TAST: OK corr0=0.544 peak=0.563 lag=-10ms onsets=32 帧=1021
  pdmx pdmxperf_QmTAytojHpVVTRTi1r6KmXNzhorA6R4m5QcwnNquNbLSGL_000/TAST: OK corr0=0.532 peak=0.532 lag=0ms onsets=212 帧=3894
  pdmx pdmxperf_QmaEq1GegKkXyVRQfQRrXQoxV9yZFq9U5J9eNo77ExDtRU_000/TAST: OK corr0=0.572 peak=0.572 lag=0ms onsets=80 帧=3813
  pdmx pdmxperf_QmZ9avkysvDzTx8iHV9k821MCx1mtxw2m2FAU2nNvsRWVr_000/TAST: OK corr0=0.577 peak=0.577 lag=0ms onsets=85 帧=2425
  == pdmx: {'OK': 8} → OK
  总判定: maestro:OK / nasap:对齐故障 / pdmx:OK

## 对齐审计 @ 2026-07-17 14:44:54(per-source=16;判读:OK=corr0≥0.25 且 |lag|≤50ms / SHIFTED=峰值≥0.25 但偏移 / UNCORRELATED=峰值<0.25)
  maestro maestro_MIDI-Unprocessed_R2_D2-19-21-22_mid--AUDIO-from_mp3_21_R2_2015_wav--2_077/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_13_R1_2006_01-06_ORIG_MID--AUDIO_13_R1_2006_05_Track05_wav_092/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-UNPROCESSED_19-20_R1_2014_MID--AUDIO_19_R1_2014_wav--2_225/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_XP_15_R1_2004_04_ORIG_MID--AUDIO_15_R1_2004_04_Track04_wav_142/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_16_R1_2011_MID--AUDIO_R1-D6_15_Track15_wav_065/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_17_R1_2009_01-03_ORIG_MID--AUDIO_17_R1_2009_17_R1_2009_01_WAV_066/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_Schubert10-12_MID--AUDIO_17_R2_2018_wav_290/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_ORIG-MIDI_01_7_10_13_Group_MID--AUDIO_02_R3_2013_wav--1_052/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_042_PIANO042_MID--AUDIO-split_07-06-17_Piano-e_1-02_wav--1_035/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_23_R3_2011_MID--AUDIO_R3-D8_04_Track04_wav_055/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-UNPROCESSED_06-08_R1_2014_MID--AUDIO_08_R1_2014_wav--2_059/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_15_R1_2009_03-06_ORIG_MID--AUDIO_15_R1_2009_15_R1_2009_03_WAV_174/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-UNPROCESSED_04-05_R1_2014_MID--AUDIO_05_R1_2014_wav--8_109/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-UNPROCESSED_04-08-12_R3_2014_MID--AUDIO_08_R3_2014_wav_206/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_Recital5-7_MID--AUDIO_05_R1_2018_wav--3_212/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  maestro maestro_MIDI-Unprocessed_24_R1_2006_01-05_ORIG_MID--AUDIO_24_R1_2006_04_Track04_wav_001/AMT: ERROR NameError: name 'pitch_verdict' is not defined
  == maestro: {'OK': 13, 'ERROR': 16, 'SHIFTED': 2, 'UNCORRELATED': 1} → 对齐故障
  nasap nasap_Shychko02M_61a00b4f_015/TAST: UNCORRELATED corr0=0.224 peak=0.224 lag=0ms onsets=312 帧=3954
  nasap nasap_HuangSW06M_eaf5dddd_001/TAST: UNCORRELATED corr0=-0.015 peak=0.081 lag=1680ms onsets=197 帧=3088
  nasap nasap_MiyashitaM04M_acb3aaa7_013/TAST: UNCORRELATED corr0=0.203 peak=0.203 lag=0ms onsets=54 帧=3708
  nasap nasap_HuNY08M_33f23190_031/TAST: OK corr0=0.297 peak=0.297 lag=0ms onsets=137 帧=2178
  nasap nasap_Kurz04M_b5066a98_034/TAST: UNCORRELATED corr0=0.152 peak=0.169 lag=-10ms onsets=181 帧=1588
  nasap nasap_Bult-ItoS05M_b4b8097c_010/TAST: OK corr0=0.28 peak=0.28 lag=0ms onsets=116 帧=2223
  nasap nasap_Bult-ItoS02M_171360e0_004/TAST: SHIFTED corr0=0.246 peak=0.269 lag=-270ms onsets=80 帧=3661
  nasap nasap_Tario07M_fa9cfb66_006/TAST: UNCORRELATED corr0=0.016 peak=0.073 lag=1680ms onsets=282 帧=3875
  nasap nasap_ChenW04M_c7cb5cd6_019/TAST: OK corr0=0.242 peak=0.28 lag=10ms onsets=136 帧=3763
  nasap nasap_Hou01M_adeab67f_001/TAST: SHIFTED corr0=0.275 peak=0.288 lag=140ms onsets=289 帧=3918
  nasap nasap_LeeN04M_f52cc53d_007/TAST: OK corr0=0.287 peak=0.332 lag=-10ms onsets=105 帧=2100
  nasap nasap_KabuliL02M_115267f9_014/TAST: OK corr0=0.342 peak=0.342 lag=0ms onsets=150 帧=3986
  nasap nasap_WangH06M_0f25b92e_012/TAST: UNCORRELATED corr0=0.008 peak=0.107 lag=110ms onsets=105 帧=2419
  nasap nasap_ChenGuang03M_379d35e9_016/TAST: UNCORRELATED corr0=0.241 peak=0.241 lag=0ms onsets=78 帧=3964
  nasap nasap_LiA04M_1f8e5fcd_011/TAST: OK corr0=0.372 peak=0.372 lag=0ms onsets=172 帧=2843
  nasap nasap_GarritsonL02M_3a7c5056_001/TAST: UNCORRELATED corr0=0.162 peak=0.192 lag=-80ms onsets=33 帧=1572
  == nasap: {'UNCORRELATED': 8, 'OK': 6, 'SHIFTED': 2} → 对齐故障
  pdmx pdmxperf_QmU17n3jWr8bhwn7NyNykz1wtFubBNFHVpbkpXk2T8d1q2_000/TAST: OK corr0=0.24 peak=0.329 lag=10ms onsets=107 帧=3234
  pdmx pdmxperf_QmZ5ZyJUp7ctnHBPNMRMvZK8SaxP96VdEnZhL4YCnwmLJT_000/TAST: OK corr0=0.413 peak=0.438 lag=-10ms onsets=206 帧=3940
  pdmx pdmxperf_QmQjHc7i1meAvSf25vajtPo3i8kjsJ18eH3TKY4tQUdmFe_000/TAST: OK corr0=0.675 peak=0.688 lag=-10ms onsets=98 帧=3938
  pdmx pdmxperf_QmV43bmCE9BoBLkJqp1xFkQEZzdLNvwgQJFWLbmWvZT731_000/TAST: OK corr0=0.361 peak=0.361 lag=0ms onsets=64 帧=1378
  pdmx pdmxperf_QmedmJPDEdynAFTsN8sErSHsuAXvDPZ6REFgVC99yprTNe_000/TAST: OK corr0=0.544 peak=0.563 lag=-10ms onsets=32 帧=1021
  pdmx pdmxperf_QmTAytojHpVVTRTi1r6KmXNzhorA6R4m5QcwnNquNbLSGL_000/TAST: OK corr0=0.532 peak=0.532 lag=0ms onsets=212 帧=3894
  pdmx pdmxperf_QmaEq1GegKkXyVRQfQRrXQoxV9yZFq9U5J9eNo77ExDtRU_000/TAST: OK corr0=0.572 peak=0.572 lag=0ms onsets=80 帧=3813
  pdmx pdmxperf_QmZ9avkysvDzTx8iHV9k821MCx1mtxw2m2FAU2nNvsRWVr_000/TAST: OK corr0=0.577 peak=0.577 lag=0ms onsets=85 帧=2425
  pdmx pdmxperf_QmRizgGfwCQ4NTnydCoU6JMHNZd38uyznGWd4E71i8jgSY_000/TAST: OK corr0=0.282 peak=0.311 lag=-10ms onsets=267 帧=3967
  pdmx pdmxperf_QmUWWjAFRL9m8EaD8KmaEhrLkapEPEh1tosfFp33R4DdKs_000/TAST: OK corr0=0.737 peak=0.74 lag=-10ms onsets=82 帧=2964
  pdmx pdmxperf_QmRX1gfijt3WQWUBzAK1PgPVYpKHJTcyu3oyUj49JK8GY4_000/TAST: OK corr0=0.657 peak=0.657 lag=0ms onsets=96 帧=3967
  pdmx pdmxperf_QmfU7UNX4se5CG8vzDFGK1ZUyh7gGo5fgrikQNR6169e9p_000/TAST: OK corr0=0.655 peak=0.74 lag=-10ms onsets=118 帧=3443
  pdmx pdmxperf_QmTLbGoMbZyKpCRCEJCFKqHkkq3fQ3BvGtu4svqqfe6foW_000/TAST: OK corr0=0.621 peak=0.621 lag=0ms onsets=93 帧=1625
  pdmx pdmxperf_QmbugpTc8Mn4LijK68jAwSsJr966ZNuHdQQJcgsa77DR3W_000/TAST: UNCORRELATED corr0=0.054 peak=0.101 lag=70ms onsets=184 帧=2967
  pdmx pdmxperf_QmNpCJCPTTpcDRgnEM4CDRjsVNBZ32ixCth9XFyQqKjGgp_000/TAST: OK corr0=0.572 peak=0.572 lag=0ms onsets=27 帧=1105
  pdmx pdmxperf_QmTeKdY8fQau7CKYWhxbQLhZRpAyXHKf1V9Qa3ekxg6b3U_000/TAST: OK corr0=0.683 peak=0.758 lag=-10ms onsets=86 帧=3358
  == pdmx: {'OK': 15, 'UNCORRELATED': 1} → OK
  总判定: maestro:对齐故障 / nasap:对齐故障 / pdmx:OK

## 对齐审计 @ 2026-07-17 16:01:32(per-source=16;判读:OK=corr0≥0.25 且 |lag|≤50ms / SHIFTED=峰值≥0.25 但偏移 / UNCORRELATED=峰值<0.25)
  maestro maestro_MIDI-Unprocessed_R2_D2-19-21-22_mid--AUDIO-from_mp3_21_R2_2015_wav--2_077/AMT: OK corr0=0.539 peak=0.539 lag=0ms onsets=43 帧=464 | 音高: PITCH_OK sim=0.746 base=0.489 Δ=0.257
  maestro maestro_MIDI-Unprocessed_13_R1_2006_01-06_ORIG_MID--AUDIO_13_R1_2006_05_Track05_wav_092/AMT: OK corr0=0.294 peak=0.294 lag=0ms onsets=43 帧=249 | 音高: PITCH_OK sim=0.743 base=0.589 Δ=0.154
  maestro maestro_MIDI-UNPROCESSED_19-20_R1_2014_MID--AUDIO_19_R1_2014_wav--2_225/AMT: OK corr0=0.33 peak=0.451 lag=-10ms onsets=50 帧=615 | 音高: PITCH_OK sim=0.731 base=0.293 Δ=0.438
  maestro maestro_MIDI-Unprocessed_XP_15_R1_2004_04_ORIG_MID--AUDIO_15_R1_2004_04_Track04_wav_142/AMT: OK corr0=0.455 peak=0.475 lag=-10ms onsets=17 帧=732 | 音高: PITCH_OK sim=0.775 base=0.605 Δ=0.169
  maestro maestro_MIDI-Unprocessed_16_R1_2011_MID--AUDIO_R1-D6_15_Track15_wav_065/AMT: SHIFTED corr0=0.319 peak=0.36 lag=-1080ms onsets=38 帧=219 | 音高: PITCH_MISMATCH sim=0.759 base=0.753 Δ=0.006
  maestro maestro_MIDI-Unprocessed_17_R1_2009_01-03_ORIG_MID--AUDIO_17_R1_2009_17_R1_2009_01_WAV_066/AMT: OK corr0=0.692 peak=0.707 lag=-10ms onsets=16 帧=116 | 音高: PITCH_OK sim=0.734 base=0.572 Δ=0.162
  maestro maestro_MIDI-Unprocessed_Schubert10-12_MID--AUDIO_17_R2_2018_wav_290/AMT: OK corr0=0.457 peak=0.617 lag=-10ms onsets=22 帧=309 | 音高: PITCH_OK sim=0.828 base=0.581 Δ=0.247
  maestro maestro_ORIG-MIDI_01_7_10_13_Group_MID--AUDIO_02_R3_2013_wav--1_052/AMT: UNCORRELATED corr0=0.087 peak=0.175 lag=-1950ms onsets=17 帧=834 | 音高: PITCH_OK sim=0.817 base=0.477 Δ=0.341
  maestro maestro_MIDI-Unprocessed_042_PIANO042_MID--AUDIO-split_07-06-17_Piano-e_1-02_wav--1_035/AMT: OK corr0=0.556 peak=0.556 lag=0ms onsets=43 帧=644 | 音高: PITCH_OK sim=0.768 base=0.412 Δ=0.356
  maestro maestro_MIDI-Unprocessed_23_R3_2011_MID--AUDIO_R3-D8_04_Track04_wav_055/AMT: SHIFTED corr0=0.376 peak=0.431 lag=-770ms onsets=20 帧=167 | 音高: PITCH_OK sim=0.78 base=0.672 Δ=0.109
  maestro maestro_MIDI-UNPROCESSED_06-08_R1_2014_MID--AUDIO_08_R1_2014_wav--2_059/AMT: OK corr0=0.306 peak=0.306 lag=0ms onsets=47 帧=1034 | 音高: PITCH_OK sim=0.565 base=0.352 Δ=0.213
  maestro maestro_MIDI-Unprocessed_15_R1_2009_03-06_ORIG_MID--AUDIO_15_R1_2009_15_R1_2009_03_WAV_174/AMT: OK corr0=0.356 peak=0.397 lag=-10ms onsets=36 帧=181 | 音高: PITCH_AMBIG sim=0.827 base=0.739 Δ=0.088
  maestro maestro_MIDI-UNPROCESSED_04-05_R1_2014_MID--AUDIO_05_R1_2014_wav--8_109/AMT: OK corr0=0.456 peak=0.456 lag=0ms onsets=55 帧=501 | 音高: PITCH_OK sim=0.729 base=0.415 Δ=0.315
  maestro maestro_MIDI-UNPROCESSED_04-08-12_R3_2014_MID--AUDIO_08_R3_2014_wav_206/AMT: OK corr0=0.386 peak=0.42 lag=10ms onsets=29 帧=998 | 音高: PITCH_OK sim=0.613 base=0.289 Δ=0.324
  maestro maestro_MIDI-Unprocessed_Recital5-7_MID--AUDIO_05_R1_2018_wav--3_212/AMT: OK corr0=0.307 peak=0.311 lag=10ms onsets=43 帧=601 | 音高: PITCH_OK sim=0.817 base=0.408 Δ=0.408
  maestro maestro_MIDI-Unprocessed_24_R1_2006_01-05_ORIG_MID--AUDIO_24_R1_2006_04_Track04_wav_001/AMT: OK corr0=0.514 peak=0.523 lag=-10ms onsets=57 帧=1018 | 音高: PITCH_OK sim=0.781 base=0.494 Δ=0.287
  == maestro: {'OK': 13, 'SHIFTED': 2, 'UNCORRELATED': 1} | 音高: {'PITCH_OK': 14, 'PITCH_MISMATCH': 1, 'PITCH_AMBIG': 1} → 音高OK → OK
  nasap nasap_Shychko02M_61a00b4f_015/TAST: UNCORRELATED corr0=0.224 peak=0.224 lag=0ms onsets=312 帧=3954
  nasap nasap_HuangSW06M_eaf5dddd_001/TAST: UNCORRELATED corr0=-0.015 peak=0.081 lag=1680ms onsets=197 帧=3088
  nasap nasap_MiyashitaM04M_acb3aaa7_013/TAST: UNCORRELATED corr0=0.203 peak=0.203 lag=0ms onsets=54 帧=3708
  nasap nasap_HuNY08M_33f23190_031/TAST: OK corr0=0.297 peak=0.297 lag=0ms onsets=137 帧=2178
  nasap nasap_Kurz04M_b5066a98_034/TAST: UNCORRELATED corr0=0.152 peak=0.169 lag=-10ms onsets=181 帧=1588
  nasap nasap_Bult-ItoS05M_b4b8097c_010/TAST: OK corr0=0.28 peak=0.28 lag=0ms onsets=116 帧=2223
  nasap nasap_Bult-ItoS02M_171360e0_004/TAST: SHIFTED corr0=0.246 peak=0.269 lag=-270ms onsets=80 帧=3661
  nasap nasap_Tario07M_fa9cfb66_006/TAST: UNCORRELATED corr0=0.016 peak=0.073 lag=1680ms onsets=282 帧=3875
  nasap nasap_ChenW04M_c7cb5cd6_019/TAST: OK corr0=0.242 peak=0.28 lag=10ms onsets=136 帧=3763
  nasap nasap_Hou01M_adeab67f_001/TAST: SHIFTED corr0=0.275 peak=0.288 lag=140ms onsets=289 帧=3918
  nasap nasap_LeeN04M_f52cc53d_007/TAST: OK corr0=0.287 peak=0.332 lag=-10ms onsets=105 帧=2100
  nasap nasap_KabuliL02M_115267f9_014/TAST: OK corr0=0.342 peak=0.342 lag=0ms onsets=150 帧=3986
  nasap nasap_WangH06M_0f25b92e_012/TAST: UNCORRELATED corr0=0.008 peak=0.107 lag=110ms onsets=105 帧=2419
  nasap nasap_ChenGuang03M_379d35e9_016/TAST: UNCORRELATED corr0=0.241 peak=0.241 lag=0ms onsets=78 帧=3964
  nasap nasap_LiA04M_1f8e5fcd_011/TAST: OK corr0=0.372 peak=0.372 lag=0ms onsets=172 帧=2843
  nasap nasap_GarritsonL02M_3a7c5056_001/TAST: UNCORRELATED corr0=0.162 peak=0.192 lag=-80ms onsets=33 帧=1572
  == nasap: {'UNCORRELATED': 8, 'OK': 6, 'SHIFTED': 2} → 对齐故障
  pdmx pdmxperf_QmU17n3jWr8bhwn7NyNykz1wtFubBNFHVpbkpXk2T8d1q2_000/TAST: OK corr0=0.24 peak=0.329 lag=10ms onsets=107 帧=3234
  pdmx pdmxperf_QmZ5ZyJUp7ctnHBPNMRMvZK8SaxP96VdEnZhL4YCnwmLJT_000/TAST: OK corr0=0.413 peak=0.438 lag=-10ms onsets=206 帧=3940
  pdmx pdmxperf_QmQjHc7i1meAvSf25vajtPo3i8kjsJ18eH3TKY4tQUdmFe_000/TAST: OK corr0=0.675 peak=0.688 lag=-10ms onsets=98 帧=3938
  pdmx pdmxperf_QmV43bmCE9BoBLkJqp1xFkQEZzdLNvwgQJFWLbmWvZT731_000/TAST: OK corr0=0.361 peak=0.361 lag=0ms onsets=64 帧=1378
  pdmx pdmxperf_QmedmJPDEdynAFTsN8sErSHsuAXvDPZ6REFgVC99yprTNe_000/TAST: OK corr0=0.544 peak=0.563 lag=-10ms onsets=32 帧=1021
  pdmx pdmxperf_QmTAytojHpVVTRTi1r6KmXNzhorA6R4m5QcwnNquNbLSGL_000/TAST: OK corr0=0.532 peak=0.532 lag=0ms onsets=212 帧=3894
  pdmx pdmxperf_QmaEq1GegKkXyVRQfQRrXQoxV9yZFq9U5J9eNo77ExDtRU_000/TAST: OK corr0=0.572 peak=0.572 lag=0ms onsets=80 帧=3813
  pdmx pdmxperf_QmZ9avkysvDzTx8iHV9k821MCx1mtxw2m2FAU2nNvsRWVr_000/TAST: OK corr0=0.577 peak=0.577 lag=0ms onsets=85 帧=2425
  pdmx pdmxperf_QmRizgGfwCQ4NTnydCoU6JMHNZd38uyznGWd4E71i8jgSY_000/TAST: OK corr0=0.282 peak=0.311 lag=-10ms onsets=267 帧=3967
  pdmx pdmxperf_QmUWWjAFRL9m8EaD8KmaEhrLkapEPEh1tosfFp33R4DdKs_000/TAST: OK corr0=0.737 peak=0.74 lag=-10ms onsets=82 帧=2964
  pdmx pdmxperf_QmRX1gfijt3WQWUBzAK1PgPVYpKHJTcyu3oyUj49JK8GY4_000/TAST: OK corr0=0.657 peak=0.657 lag=0ms onsets=96 帧=3967
  pdmx pdmxperf_QmfU7UNX4se5CG8vzDFGK1ZUyh7gGo5fgrikQNR6169e9p_000/TAST: OK corr0=0.655 peak=0.74 lag=-10ms onsets=118 帧=3443
  pdmx pdmxperf_QmTLbGoMbZyKpCRCEJCFKqHkkq3fQ3BvGtu4svqqfe6foW_000/TAST: OK corr0=0.621 peak=0.621 lag=0ms onsets=93 帧=1625
  pdmx pdmxperf_QmbugpTc8Mn4LijK68jAwSsJr966ZNuHdQQJcgsa77DR3W_000/TAST: UNCORRELATED corr0=0.054 peak=0.101 lag=70ms onsets=184 帧=2967
  pdmx pdmxperf_QmNpCJCPTTpcDRgnEM4CDRjsVNBZ32ixCth9XFyQqKjGgp_000/TAST: OK corr0=0.572 peak=0.572 lag=0ms onsets=27 帧=1105
  pdmx pdmxperf_QmTeKdY8fQau7CKYWhxbQLhZRpAyXHKf1V9Qa3ekxg6b3U_000/TAST: OK corr0=0.683 peak=0.758 lag=-10ms onsets=86 帧=3358
  == pdmx: {'OK': 15, 'UNCORRELATED': 1} → OK
  总判定: maestro:OK / nasap:对齐故障 / pdmx:OK
