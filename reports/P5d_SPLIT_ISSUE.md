# P5d nASAP split 受阻

P5c 完成（7,098 seg, 9 fail）。P5d `s7_assign_split.py --apply` 产出：

```
train=5883  val=598(目标512)  test=617
作品 train=66  val=13  test=17
```

## 问题

5 个 work_key 的段跨了 split（脚本标记为"不应发生"）：

```
bach|prelude               → train + val
beethoven|piano sonatas 17 3 → test + train
beethoven|piano sonatas 18 4 → train + val
beethoven|piano sonatas 26 3 → train + val
chopin|etudes 4            → test + train
```

sop_next 因此停在 P5d。sop_state.json 有 P5d 产出但 require 判据不过。

## 待办

请确认：跨 split 是否可以接受（这 5 首只有少量段受影响），还是需要改 split 分配逻辑。
