
## nasap-train × maestro val/test 音频对账 @ 2026-07-21 23:43:37
  maestro CSV: 场次=1276 其中 val/test=314
  nasap 行按自身 split: test=603 train=5956 val=539
  nasap 行按所引录音的 maestro 切分: maestro-test=1043 maestro-train=5435 maestro-validation=620
  【泄漏集】nasap-train 引用 maestro val/test 录音: 场次=78 涉及行=1239
    - MIDI-Unprocessed_10_R1_2006_01-04_ORIG_MID--AUDIO_10_R1_2006_03_Track03_wav.flac(test): 74 行
    - MIDI-Unprocessed_080_PIANO080_MID--AUDIO-split_07-09-17_Piano-e_1-06_wav--3.flac(test): 71 行
    - MIDI-Unprocessed_01_R1_2011_MID--AUDIO_R1-D1_06_Track06_wav.flac(validation): 44 行
    - ORIG-MIDI_03_7_6_13_Group__MID--AUDIO_10_R1_2013_wav--4.flac(validation): 44 行
    - MIDI-Unprocessed_07_R1_2011_MID--AUDIO_R1-D3_05_Track05_wav.flac(validation): 44 行
    - MIDI-Unprocessed_09_R1_2009_01-04_ORIG_MID--AUDIO_09_R1_2009_09_R1_2009_03_WAV.flac(test): 40 行
    - MIDI-Unprocessed_Recital1-3_MID--AUDIO_02_R1_2018_wav--1.flac(validation): 28 行
    - MIDI-Unprocessed_R1_D1-1-8_mid--AUDIO-from_mp3_06_R1_2015_wav--2.flac(test): 25 行
    - MIDI-Unprocessed_17_R1_2009_01-03_ORIG_MID--AUDIO_17_R1_2009_17_R1_2009_01_WAV.flac(test): 24 行
    - MIDI-Unprocessed_04_R3_2008_01-07_ORIG_MID--AUDIO_04_R3_2008_wav--7.flac(test): 23 行
    - MIDI-Unprocessed_Recital4_MID--AUDIO_04_R1_2018_wav--3.flac(validation): 22 行
    - MIDI-Unprocessed_R1_D1-9-12_mid--AUDIO-from_mp3_09_R1_2015_wav--2.flac(test): 22 行
    - MIDI-UNPROCESSED_04-05_R1_2014_MID--AUDIO_04_R1_2014_wav--2.flac(test): 20 行
    - MIDI-UNPROCESSED_11-13_R1_2014_MID--AUDIO_13_R1_2014_wav--4.flac(test): 20 行
    - MIDI-Unprocessed_XP_15_R1_2004_03_ORIG_MID--AUDIO_15_R1_2004_03_Track03_wav.flac(test): 19 行
    - MIDI-Unprocessed_21_R1_2011_MID--AUDIO_R1-D8_10_Track10_wav.flac(validation): 18 行
    - MIDI-Unprocessed_R1_D1-1-8_mid--AUDIO-from_mp3_03_R1_2015_wav--3.flac(validation): 18 行
    - MIDI-Unprocessed_066_PIANO066_MID--AUDIO-split_07-07-17_Piano-e_3-02_wav--2.flac(test): 18 行
    - MIDI-Unprocessed_09_R1_2008_01-05_ORIG_MID--AUDIO_09_R1_2008_wav--2.flac(test): 18 行
    - MIDI-Unprocessed_18_R1_2008_01-04_ORIG_MID--AUDIO_18_R1_2008_wav--2.flac(test): 18 行
    …共 78 场,余略(全清单以本脚本重跑 + grep 提取)
  判定: 存在泄漏 —— 涉事行须移出训练,规划端出补丁前先贴回本报告
