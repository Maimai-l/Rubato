# build_dataset.py NameError: args not defined

P8 全绿后跑 `build_dataset.py --smoke 100`，装配统计正常输出但崩溃：

```
NameError: name 'args' is not defined (line 224: if args.dry_run:)
```

## 根因

`ap.add_argument(...)` 行都在（188-195 行），但 `args = ap.parse_args()` 整行缺失。commit `00756b0` 加 `--smoke` 时误删。

## 数据无损失

装配统计已打印：
```
pdmx: 171,265 -> 111,605 kept
nasap: 7,098 -> 7,098 kept
maestro: 23,657 -> 23,657 kept
train=133,415 nasap_val=1,142 maestro_val=4,695
```
