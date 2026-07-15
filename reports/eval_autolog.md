
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
