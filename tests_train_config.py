"""生产训练配置接线测试。运行: python tests_train_config.py"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import yaml

from scripts.build_dataset import (
    DEFAULT_TRAIN_CONFIG, DEFAULT_VOCAB_SPEC,
    apply_train_config_defaults, configure_cuda_allocator, load_train_config)


PASS = 0


def check(name, cond, detail=""):
    global PASS
    if not cond:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)
    PASS += 1
    print(f"  ok  {name}")


def args(**overrides):
    base = {
        "smoke": 0,
        "from_scratch": False,
        "max_batch_sec": None,
        "clip_norm": None,
        "eval_max": None,
        "eval_every": None,
        "eval_decode_every": None,
        "pitch_loss_weight": None,
        "lr_enc": None,
        "lr_dec": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


ROOT = Path(__file__).resolve().parent
cfg = load_train_config(ROOT / "configs" / "train.yaml")

print("[1] 仓库生产配置能解析并接入默认值")
check("defaults_are_cwd_independent",
      DEFAULT_TRAIN_CONFIG.is_file() and DEFAULT_VOCAB_SPEC.is_file(),
      (DEFAULT_TRAIN_CONFIG, DEFAULT_VOCAB_SPEC))
a = apply_train_config_defaults(args(), cfg)
check("batch_from_yaml", a.max_batch_sec == 60.0, a.max_batch_sec)
check("eval_from_yaml", (a.eval_every, a.eval_max) == (1000, 48),
      (a.eval_every, a.eval_max))
check("hot_encoder_lr", a.lr_enc == 1e-4, a.lr_enc)
check("decoder_lr", a.lr_dec == 5e-4, a.lr_dec)
check("memory_policy_loaded",
      cfg["memory"]["allocator_conf"] == "expandable_segments:True"
      and cfg["memory"]["check_every_steps"] == 200,
      cfg["memory"])

print("[2] from-scratch 不得误用热启动 encoder 学习率")
b = apply_train_config_defaults(args(from_scratch=True), cfg)
check("scratch_encoder_matches_decoder", b.lr_enc == 5e-4, b.lr_enc)
cfg2 = {**cfg, "optim": {**cfg["optim"], "lr_encoder_from_scratch": 7e-4}}
c = apply_train_config_defaults(args(from_scratch=True), cfg2)
check("scratch_explicit_yaml", c.lr_enc == 7e-4, c.lr_enc)

print("[3] 显式 CLI 必须压过 YAML")
d = apply_train_config_defaults(
    args(max_batch_sec=42, clip_norm=25, eval_every=77,
         pitch_loss_weight=2.5, lr_enc=2e-4, lr_dec=3e-4), cfg)
check("cli_wins", (
    d.max_batch_sec, d.clip_norm, d.eval_every, d.pitch_loss_weight,
    d.lr_enc, d.lr_dec) == (42, 25, 77, 2.5, 2e-4, 3e-4))

print("[4] 写了但生产未实现的开关必须拒绝")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "bad.yaml"
    bad = {**cfg, "specaugment": True}
    p.write_text(yaml.safe_dump(bad), encoding="utf-8")
    try:
        load_train_config(p)
    except ValueError as e:
        check("specaugment_rejected", "无生产实现" in str(e), str(e))
    else:
        check("specaugment_rejected", False, "未抛错")

print("[5] 未消费键和伪可配置不变量必须拒绝")
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    cases = [
        ("unknown_top", {**cfg, "model": {"route": "auto"}},
         "未消费的顶层键"),
        ("unknown_nested",
         {**cfg, "data": {**cfg["data"], "score_seg": {"max_sec": 40}}},
         "未消费键"),
        ("unsupported_schedule",
         {**cfg, "optim": {**cfg["optim"], "schedule": "linear"}},
         "只实现 cosine"),
        ("wrong_len_power",
         {**cfg, "loss": {**cfg["loss"], "len_weight_pow": 1.0}},
         "1/sqrt(T)"),
    ]
    for name, bad, needle in cases:
        p = root / f"{name}.yaml"
        p.write_text(yaml.safe_dump(bad), encoding="utf-8")
        try:
            load_train_config(p)
        except ValueError as e:
            check(name, needle in str(e), str(e))
        else:
            check(name, False, "未抛错")

print("[6] CUDA allocator 必须早于 torch 初始化，且显式环境优先")
env = {}
effective = configure_cuda_allocator(cfg, environ=env, loaded_modules={})
check("allocator_installed_early",
      effective == "expandable_segments:True"
      and env["PYTORCH_ALLOC_CONF"] == effective, env)
env2 = {"PYTORCH_ALLOC_CONF": "backend:cudaMallocAsync"}
check("operator_env_wins",
      configure_cuda_allocator(cfg, environ=env2, loaded_modules={"torch": object()})
      == "backend:cudaMallocAsync")
legacy_env = {"PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb:512"}
check("legacy_operator_env_wins",
      configure_cuda_allocator(
          cfg, environ=legacy_env, loaded_modules={"torch": object()})
      == "max_split_size_mb:512"
      and legacy_env["PYTORCH_ALLOC_CONF"] == "max_split_size_mb:512",
      legacy_env)
try:
    configure_cuda_allocator(
        cfg,
        environ={"PYTORCH_ALLOC_CONF": "expandable_segments:True",
                 "PYTORCH_CUDA_ALLOC_CONF": "backend:cudaMallocAsync"},
        loaded_modules={})
except RuntimeError as e:
    check("allocator_alias_conflict_rejected", "冲突" in str(e), str(e))
else:
    check("allocator_alias_conflict_rejected", False, "未抛错")
try:
    configure_cuda_allocator(cfg, environ={}, loaded_modules={"torch": object()})
except RuntimeError as e:
    check("late_config_rejected", "import torch" in str(e), str(e))
else:
    check("late_config_rejected", False, "未抛错")

print(f"\n全部通过: {PASS} 项")
