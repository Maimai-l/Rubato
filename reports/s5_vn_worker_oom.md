# S5 VN Worker OOM — soundfont weight underestimated

## Finding
`mem_budget_map` uses source directory **file size** as weight. ExperienceNY files=6.9GB, but sfizz **decodes samples in memory** to ~12GB actual RSS. Budget calculation allows 2 concurrent ExperienceNY workers (6.9×2=13.8 < 22.8GB budget), but real usage is 12×2=24GB → OOM.

## Evidence (memtrace, VN --limit 5)
```
elapsed  sys_used%  main_VN  workers_RSS  n_workers
  154s       94%     0.04GB    25.36GB      2
  159s       95%     0.04GB    25.84GB      2
```

- Main process flat 0.04GB (subprocess fix confirmed)
- 2 workers × ~13GB each = 26GB total
- system OOM at 95%

## Fix direction
- Weight should be actual RSS (12GB) not file size (6.9GB)
- Or cap ExperienceNY concurrency to 1
