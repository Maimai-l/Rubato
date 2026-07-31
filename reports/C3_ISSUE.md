# C3 文件争抢问题

## 现象
C3 渲染 700/12000 中 99 次 PermissionError。sfizz 写 opus 到 pdmx_audio/ 时与训练进程冲突。

## 根因
训练 resolve_audio 用 soundfile.info() 读 flac/opus 时长，C3 的 sfizz 同时创建新 opus 到同一目录（pdmx_audio/），Windows 锁文件不允许多进程同时操作。

## 期望修复
sfizz 输出到临时目录，渲染完成再原子移入 pdmx_audio/；或训练时跳过正在渲染的曲。
