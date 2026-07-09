"""
S8 装配 + 训练启动:把三份 labels.jsonl(+音频)合成 RubatoDataModule,再交给 train()。

这补上了此前【缺失的胶水】—— 标签落盘后没有任何代码把它们 + 音频喂进 RubatoDataset。

用法:
  # 只装配、不训练(无 GPU 也能跑,先验证胶水对不对):
  python scripts/build_dataset.py --dry-run
  # 装配 + 训练:
  python scripts/build_dataset.py --tokenizer work/rubato_spm.model --nemo canary-180m-flash.nemo

音频路径解析(audio_resolver)是执行端唯一要按真实环境确认的地方——见下面三个 resolver 里的
【EXECUTOR】注释。--dry-run 会打印每源 kept/no_audio/no_dialect,配不上音频的数目一眼可见。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.data.assemble import assemble, partition_by_split

ROOT = Path(r"D:\vscode_projects\ee_download")
WORK = ROOT / "work"

# 三份 labels.jsonl(与 s5/s7/gen_amt 的输出对齐)
SOURCES = [
    {"path": str(WORK / "pdmx_a2s_labels.jsonl"), "kind": "pdmx",    "domain": "synth"},
    {"path": str(WORK / "nasap_labels.jsonl"),    "kind": "nasap",   "domain": "real"},
    {"path": str(WORK / "maestro_amt_labels.jsonl"), "kind": "maestro", "domain": "real"},
]

# ---------------------------------------------------------------- 音频时长缓存
_DUR_CACHE: dict[str, float] = {}


def _flac_dur(path: str) -> float | None:
    if path in _DUR_CACHE:
        return _DUR_CACHE[path]
    try:
        import soundfile as sf
        info = sf.info(path)
        d = info.frames / info.samplerate
    except Exception:
        return None
    _DUR_CACHE[path] = d
    return d


# ---------------------------------------------------------------- audio resolver(执行端确认)

def _maestro_csv_map():
    """midi_filename → audio_filename(从 MAESTRO CSV)。缓存一次。"""
    if hasattr(_maestro_csv_map, "_m"):
        return _maestro_csv_map._m
    import csv
    m = {}
    csv_path = ROOT / "maestro-v3.0.0.csv"
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                m[row["midi_filename"]] = row["audio_filename"]
    _maestro_csv_map._m = m
    return m


def resolve_audio(utt_id: str, kind: str, row: dict):
    """
    返回 (audio_path, dur_s) 或 None(无音频 → assemble 计入 no_audio,不静默)。
    【EXECUTOR】三处路径约定按你的真实目录核对:
      - pdmx:   S4 渲染产物。约定 work/pdmx_audio/<utt_id>.flac(每段一个渲染 wav/flac)。
      - maestro:MAESTRO CSV 把 midi_filename→audio_filename,FLAC 落在 work/maestro_audio/<base>.flac。
      - nasap:  用 MAESTRO 子集的真实录音(asap metadata 的 maestro_audio_performance)。
                若 nasap 标签行未带音频引用,这里返回 None 会把 nasap 全判 no_audio ——
                需要在 s7 的标签行里加上 audio 引用,或在此按你的 nasap↔flac 映射补全。
    """
    if kind == "pdmx":
        p = WORK / "pdmx_audio" / f"{utt_id}.flac"
        d = _flac_dur(str(p))
        return (str(p), d) if d is not None else None
    if kind == "maestro":
        mid = row.get("midi_file")
        audio_rel = _maestro_csv_map().get(mid)
        if not audio_rel:
            return None
        base = Path(audio_rel).with_suffix(".flac").name
        p = WORK / "maestro_audio" / base
        d = _flac_dur(str(p))
        return (str(p), d) if d is not None else None
    if kind == "nasap":
        ref = row.get("audio_path") or row.get("perf_audio")   # s7 若带上音频引用则用之
        if ref:
            d = _flac_dur(ref)
            return (ref, d) if d is not None else None
        return None                                            # 见 docstring:需补 nasap↔flac 映射
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只装配 + 打印 stats,不建模型/不训练")
    ap.add_argument("--tokenizer", default=str(WORK / "rubato_spm.model"))
    ap.add_argument("--nemo", default=str(ROOT / "canary-180m-flash.nemo"))
    ap.add_argument("--vocab-spec", default="configs/vocab_spec.json")
    ap.add_argument("--from-scratch", action="store_true")
    args = ap.parse_args()

    utts, labels, stats = assemble(SOURCES, resolve_audio)
    print("=== 装配统计(每一步丢弃都计数,不静默)===")
    for kind, s in stats["per_source"].items():
        print(f"  {kind:8s} rows={s['rows']:>7} kept={s['kept']:>7} "
              f"no_audio={s['no_audio']:>7} no_dialect={s['no_dialect']:>6} "
              f"bad_schema={s['bad_schema']:>5} dup={s['dup']:>5}")
    print(f"  TOTAL utts={stats['totals']['utts']} by_dialect={stats['totals']['by_dialect']}")
    print(f"        by_kind={stats['totals']['by_kind']} by_split={stats['totals']['by_split']}")
    if stats["dup_utt_ids"]:
        print(f"  ⚠ 撞名 utt_id 样本: {stats['dup_utt_ids']}")

    # 健壮性红线:任何一源 kept==0 或 no_audio 占绝大多数 → 停,别拿半个数据集去训。
    for kind, s in stats["per_source"].items():
        if s["rows"] and s["kept"] == 0:
            print(f"  ✗ 源 {kind} kept=0(rows={s['rows']})—— 音频全配不上或标签全空,先修 resolve_audio/标签,别训。")

    part = partition_by_split(utts)
    train_utts = part["train"]
    nasap_val = [u for u in (part["val"] + part["test"]) if u["kind"] == "nasap"]
    maestro_val = [u for u in (part["val"] + part["test"]) if u["kind"] == "maestro"]
    print(f"  train={len(train_utts)} nasap_val={len(nasap_val)} maestro_val={len(maestro_val)}")

    if args.dry_run:
        print("\n--dry-run:装配 OK。确认上面 kept/no_audio 合理后去掉 --dry-run 开训。")
        return

    # ---- 建模型 + 训练(需 GPU/NeMo)----
    import sentencepiece as spm
    from rubato.data.dataset import RubatoDataset, RubatoDataModule
    from rubato.model.build import build_model
    from rubato.model.train import build_optimizer, train

    tok = spm.SentencePieceProcessor(model_file=args.tokenizer)
    model, report = build_model(args.nemo, args.tokenizer, args.vocab_spec,
                                from_scratch=args.from_scratch)
    print(f"build_model: {report.get('vocab_swap')} encoder_ok={report['encoder_verify']['ok']}")

    train_ds = RubatoDataset(train_utts, labels, tok, train=True)
    dm = RubatoDataModule(train_ds, nasap_val=nasap_val, maestro_val=maestro_val)
    cfg = {"lr_encoder": 1e-4, "lr_decoder": 5e-4} if not args.from_scratch \
        else {"lr_encoder": 5e-4, "lr_decoder": 5e-4}   # 从头训:统一 lr
    opt, sched = build_optimizer(model, cfg)
    train(model, dm, cfg, tok)


if __name__ == "__main__":
    main()
