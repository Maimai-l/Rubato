# Smoke test CUDA device-side assert — token index OOB

`build_dataset.py --smoke 100`：

## 通过的

- 装配: 142,360 utts, 4 方言
- 模型构建: embedding/linear 替换成功（5248→8000），encoder_ok=True
- 冒烟集: 100 utts, 方言覆盖 A2S/A2S_lite/AMT/TAST

## 崩溃

```
CUDA error: device-side assert triggered
IndexKernelUtils: ind >=0 && ind < ind_dim_size FAILED
```

调用栈: training_step_logic → model.forward → transf_decoder → embedding forward → dropout → CUDA assert

## 根因推测

tokenizer (vocab=8000) 产出的 token ID 超出 embedding 表范围。build_model 替换了 embedding（5248→8000），但 tokenizer 可能产出 >8000 的 token ID，或者旧 canary 模型的其他组件（如 lm_head/softmax）仍用旧 5248 词表。

需要加 `CUDA_LAUNCH_BLOCKING=1` 定位具体越界的 token ID 和值。

第二次运行（CUDA_LAUNCH_BLOCKING=1）：position embedding 处 launch timeout（GPU 污染）。

第三次运行（pull 后，含 dataset.py 长度过滤修复）：

依然崩溃，两次错误：
1. **CUDA device-side assert** — self_attn → dropout → 同 token index OOB
2. **CUDA OOM** — 0 bytes free, PyTorch allocated 28.89 GiB（GPU 仅 15.92 GiB）

**结论：** 词表替换（5248→8000）不完整。dataset 长度过滤没触及根因。GPU 每次 crash 后 OOM 需要重置。
