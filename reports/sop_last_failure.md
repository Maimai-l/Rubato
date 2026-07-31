# [P5c2] 失败 — nASAP utt 唯一化(ASAP 谱文件全叫 xml_score → 同演奏者跨曲撞 id;修 P5d 泄漏根因)
- time: 2026-07-12 20:51:03
- dup_before = 681
- rewritten = 7098
- dup_after = 584

## 日志尾部
```
  $ D:\ProgramData\envs\nemo_test\python.exe scripts/s7_fix_uttids.py --apply
共 7098 行:重写前重复 utt_id = 681,需重写 7098 行,work_key 校正 1075 行,无法规范 0 行
已重写 7098 行(重写 7098 行,备份 nasap_labels.bak2)
===== 唯一化验证(复扫)=====
  ✗ 重写后重复 utt_id = 584
  ✓ 一 piece 多 work_key = 0
  结论: 【异常,贴回给规划端】
```
