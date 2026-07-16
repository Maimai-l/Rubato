
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
