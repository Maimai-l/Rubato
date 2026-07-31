# Environment change log

| Date | Environment | Command | Why |
| --- | --- | --- | --- |
| 2026-07-22 | `m2st/venv_m2st` | `python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple beautifulsoup4 lxml` | D56 M2ST smoke stopped because vendored `score_transformer` imports `bs4`; `lxml-xml` is the parser explicitly requested by its local MusicXML tokenizer. D57 green-zone venv repair. |
| 2026-07-22 | `m2st/venv_m2st` | Preserve the Python 3.13 venv as `venv_m2st_py313.bak`; recreate `venv_m2st` with `D:\ProgramData\envs\midi2score\python.exe -m venv --system-site-packages` | PyTorch 2.13 defaulted to weights-only checkpoint loading and rejected the legacy checkpoint configuration. Reuse the local Python 3.11 / PyTorch 2.12 / Transformers 4.29.2 M2ST-compatible stack without changing any production environment. D57 green-zone venv repair. |
| 2026-07-22 | `m2st/venv_m2st` | `python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple torch==2.5.1` | The inherited Torch 2.12 build still applied the post-2.6 weights-only checkpoint default. Pin the venv-local Torch version before that default change so the official legacy M2ST checkpoint can load without patching project code or relaxing serialization policy. D57 green-zone venv repair. |
