# third_party —— 校准线依赖搬运(D56)

执行端到 pypi/github 的 TLS 间歇故障 + M2ST 上游一条对所有人都断的 git 依赖(muster),
在此钉版搬运,离线可装。

| 文件 | 来源(精确 pin) | 用途 | 许可 |
|---|---|---|---|
| music21_fork_0ed70bb.zip | github.com/TimFelixBeyer/music21 @ 0ed70bb | M2ST 依赖的 music21 定制分叉 | BSD(见包内 LICENSE) |
| score_transformer_934a228.zip | github.com/TimFelixBeyer/ScoreTransformer @ 934a228 | M2ST 的谱面 tokenizer | 按上游;仅内部研究用 |

muster 不在此列:该依赖仓库是评测工具发布页(无 setup.py),推理链不需要它 ——
由 scripts/calib_m2st_infer.py 的显式垫片处理(D56)。
安装:`pip install <zip>`(pip 认 github zipball 源码包)。仅私仓内部使用,不再分发。
