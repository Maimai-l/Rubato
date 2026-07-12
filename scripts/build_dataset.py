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

from rubato.platform import harden_stdout
from rubato.data.assemble import assemble, partition_by_split
harden_stdout()   # 执行端 P8 实测:第 155 行打 '⚠' 在 GBK 控制台崩;此前全库硬化时漏了本脚本

ROOT = Path(r"D:\vscode_projects\ee_download")
WORK = ROOT / "work"

# labels.jsonl 来源(与 s5/s5_vn/s7/gen_amt 的输出对齐)。
#   pdmx_perf(s5_vn_render):表现性音频 + TAST,行内带 audio_path。← 有它就优先,含 TAST。
#   pdmx_a2s(s5 文本):仅 A2S/A2S_lite 文本(TAST=null),需配 S4 直排音频。
SOURCES = [
    {"path": str(WORK / "pdmx_perf_labels.jsonl"), "kind": "pdmx", "domain": "synth"},
    {"path": str(WORK / "pdmx_a2s_labels.jsonl"),  "kind": "pdmx", "domain": "synth"},
    {"path": str(WORK / "nasap_labels.jsonl"),     "kind": "nasap",   "domain": "real"},
    # 【必须用切窗版】整曲版 maestro_amt_labels.jsonl 是几分钟长的不可训行(P8 实测只装出
    # 1,276 条、AMT 全灭);切窗版 23,657 条 12-25s 窗,行带 win=[t0,t1] + split(来自 MAESTRO CSV)。
    {"path": str(WORK / "maestro_amt_windows.jsonl"), "kind": "maestro", "domain": "real"},
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
    # 行内已带 audio_path(s5_vn_render / s7 写入)→ 直接用,最可靠。
    ref = row.get("audio_path")
    if ref:
        d = _flac_dur(ref)
        return (ref, d) if d is not None else None
    if kind == "pdmx":
        # 无 audio_path = 文本 s5 的行 → 找 S4 直排音频(仅 A2S/A2S_lite,该行 TAST 本就为 null)。
        for ext in (".opus", ".flac"):
            p = WORK / "pdmx_audio" / f"{utt_id}{ext}"
            d = _flac_dur(str(p))
            if d is not None:
                return (str(p), d)
        return None
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
        ref = row.get("audio_path") or row.get("perf_audio")   # s7 行带演奏音频引用(修 no_audio 全灭)
        if ref:
            cand = Path(str(ref))
            if not cand.exists():          # "{maestro}/2006/xx.wav" 是引用不是路径 → 映射到本地 FLAC
                cand = WORK / "maestro_audio" / Path(str(ref)).with_suffix(".flac").name
            d = _flac_dur(str(cand))
            if d is not None:
                return (str(cand), d)      # 引用能配上就用;配不上落到 xml_score 映射兜底
        # 【EXECUTOR】nASAP→MAESTRO FLAC 映射：从 ASAP metadata CSV 的
        # maestro_audio_performance 列找到 WAV 名→对应 FLAC 在 work/maestro_audio/
        import pandas as pd
        xml_rel = row.get("xml_score", "")
        if xml_rel and not hasattr(resolve_audio, "_nasap_map"):
            # 首次调用建映射:xml_score → maestro FLAC path
            csv_path = ROOT / "asap-dataset" / "asap-dataset" / "metadata.csv"
            m = {}
            if csv_path.exists():
                adf = pd.read_csv(str(csv_path))
                for _, r in adf.iterrows():
                    xr = str(r.get("xml_score", "") or "")
                    ma = str(r.get("maestro_audio_performance", "") or "")
                    if xr and ma and "{maestro}" in ma:
                        # {maestro}/2006/...wav → work/maestro_audio/...flac
                        wav_name = Path(ma.replace("{maestro}/", "")).with_suffix(".flac").name
                        flac_path = str(WORK / "maestro_audio" / wav_name)
                        if Path(flac_path).exists():
                            m[xr] = flac_path
            resolve_audio._nasap_map = m
        mapping = getattr(resolve_audio, "_nasap_map", {})
        flac = mapping.get(xml_rel)
        if flac:
            d = _flac_dur(flac)
            return (flac, d) if d is not None else None
        return None
    return None


def _pdmx_row_fn():
    """PDMX 行注入:manifest 的 split/work_key(标签行不带,P8 实测全体默认 train、val/test≈0);
    命中 nASAP-test/Beyer 黑名单的工作【过滤出训练】(问题#14 的装配层强制,P4 曾以空名单跑过)。"""
    import json as _json
    m = {}
    mani = WORK / "manifest_pieces.jsonl"
    if mani.exists():
        with open(mani, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = _json.loads(line)
                except Exception:
                    continue
                if r.get("piece_id"):
                    m[r["piece_id"]] = (r.get("split"), r.get("work_key"))
    bl = set()
    try:
        from scripts.s3_filter_pdmx import get_nasap_test_works, get_beyer_work_keys
        from rubato.data.pdmx import build_blacklist
        bl = build_blacklist(get_nasap_test_works(WORK),
                             get_beyer_work_keys(ROOT / "asap-dataset" / "asap-dataset" / "asap_annotations.json"))
    except Exception as e:
        print(f"  ⚠ 黑名单构建失败({type(e).__name__}),本次不过滤 —— 训练前必须解决,别静默带病训")
    if not m:
        print("  ⚠ manifest 缺失,PDMX split/work_key 无法注入(全体将默认 train)")

    def row_fn(row):
        info = m.get(row.get("piece_id"))
        if info:
            split, wk = info
            if wk and wk in bl:
                return None                # 黑名单工作:计 filtered,不进任何 split
            if split and not row.get("split"):
                row["split"] = split
        return row
    return row_fn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只装配 + 打印 stats,不建模型/不训练")
    ap.add_argument("--tokenizer", default=str(WORK / "rubato_spm.model"))
    ap.add_argument("--nemo", default=str(ROOT / "canary-180m-flash.nemo"))
    ap.add_argument("--vocab-spec", default="configs/vocab_spec.json")
    ap.add_argument("--from-scratch", action="store_true")
    ap.add_argument("--smoke", type=int, default=0, metavar="N",
                    help="过拟合冒烟:N 条 utt 小集反复过拟合,验证【代码链路】(模型/损失/"
                         "tokenizer/数据管线)没 bug —— 判据 final_sem<0.05(关标签平滑跑,"
                         "开着平滑时逐 token CE 有 ~1.2 的下界,0.05 永远达不到)")
    ap.add_argument("--smoke-steps", type=int, default=800,
                    help="冒烟步数。执行端实测:100 utt × 800 步 sem 8.98→3.83 稳降但没到 0.05"
                         "(全新 embedding+头要背下语料需要更多步);32 utt × 4000 步可达标")
    ap.add_argument("--cpu", action="store_true",
                    help="诊断模式:全程 CPU 跑 3 步。CUDA 的索引越界是异步 device assert,"
                         "栈指向随机后续 kernel(实测三次崩溃三个栈);CPU 上同一越界给出"
                         "精确 Python 栈 + 肇事索引。配 --smoke 用,慢但一锤定音")
    args = ap.parse_args()

    pdmx_fn = _pdmx_row_fn()
    for src in SOURCES:
        if src["kind"] == "pdmx":
            src["row_fn"] = pdmx_fn
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
    from rubato.model.train import train

    tok = spm.SentencePieceProcessor(model_file=args.tokenizer)
    model, report = build_model(args.nemo, args.tokenizer, args.vocab_spec,
                                from_scratch=args.from_scratch)
    print(f"build_model: {report.get('vocab_swap')} encoder_ok={report['encoder_verify']['ok']}")

    # 【训前体检,problems 非空禁止开训】把所有 Embedding/大 Linear 与 tokenizer 逐个对账,
    # 词表替换不完整/位置表上限在这里以明文数字暴露 —— 不再靠 GPU 异步 assert 的随机栈猜。
    from rubato.model.build import vocab_position_preflight
    pf = vocab_position_preflight(model, tok,
                                  old_vocab=(report.get("vocab_swap") or {}).get("old_vocab"))
    print(f"体检: tokenizer={pf['vocab']} 位置表最小={pf['max_pos']}")
    for n, num, dim in pf["embeddings"]:
        print(f"  Embedding {n}: {num} × {dim}")
    for n, of in pf["big_linears"]:
        print(f"  大 Linear {n}: out={of}")
    for w in pf.get("notes", []):
        print(f"  · {w}")
    if pf["problems"]:
        for p in pf["problems"]:
            print(f"  ✗ {p}")
        print("体检不过,禁止开训 —— 把上面整块贴回给规划端。")
        return

    if args.smoke:
        # 确定性小集,尽量均衡覆盖四方言(轮转取样;某方言池空则跳过)
        import hashlib
        by_d: dict = {}
        for u in sorted(train_utts,
                        key=lambda u: hashlib.sha256(u["utt_id"].encode()).hexdigest()):
            for d in u["dialects"]:
                by_d.setdefault(d, []).append(u)
        cycle = [d for d in ("A2S", "A2S_lite", "TAST", "AMT") if by_d.get(d)]
        picked, seen = [], set()
        di = 0
        while len(picked) < args.smoke and cycle:
            d = cycle[di % len(cycle)]
            di += 1
            pool = by_d[d]
            while pool and pool[0]["utt_id"] in seen:
                pool.pop(0)
            if not pool:
                cycle.remove(d)
                continue
            u = pool.pop(0)
            seen.add(u["utt_id"])
            picked.append(u)
        train_utts = picked
        print(f"--smoke:{len(train_utts)} utts,方言覆盖 "
              f"{sorted({d for u in picked for d in u['dialects']})}")

    # 【必须限长】decoder 位置编码表行数有限,AMT 密集窗可编出 1000+ token,
    # position_ids 越界 = CUDA device assert。上限以【体检读到的真实模块行数】为准
    # (yaml 可能与实际模块不一致),体检读不到才退回 yaml/512。
    max_tgt = pf["max_pos"]
    if not max_tgt:
        max_tgt = 512
        try:
            from rubato.model.build import extract_nemo_config
            _ncfg = extract_nemo_config(args.nemo)
            max_tgt = int((_ncfg.get("transf_decoder", {}).get("config_dict", {})
                           or {}).get("max_sequence_length") or 512)
        except Exception as e:
            print(f"  ⚠ 读 .nemo 配置失败({type(e).__name__}),max_target_len 用缺省 512")
    print(f"  目标序列上限 = {max_tgt} tok(体检实测位置表);超长样本将丢弃并记账…")
    # 冒烟关增强:alpha 重切分/tiling 每 epoch 换答案,"背下来"在增强下不可能(实测 sem 钉 1.1/
    # ts 钉 6.4)。全量训练保持增强(论文设计)。
    train_ds = RubatoDataset(train_utts, labels, tok, train=True, max_target_len=max_tgt,
                             augment=not args.smoke)
    lf = train_ds.len_filter_report
    print(f"  超长过滤: 保留 {lf.get('kept_pairs')} 对,丢弃 {lf.get('dropped_by_dialect') or 0}")
    _dropped = sum((lf.get("dropped_by_dialect") or {}).values())
    if _dropped > 0.10 * max(lf.get("kept_pairs", 1), 1):
        print("  ⚠ 超长丢弃 >10% —— 值得扩位置表(resize position embedding)找回,贴回给规划端")
    # labels 全量传入(不只 train)—— eval hook 的参照(AMT ref/A2S NED)按 val/test utt_id 查
    dm = RubatoDataModule(train_ds, nasap_val=nasap_val, maestro_val=maestro_val, labels=labels)
    cfg = {
        "lr_encoder": 1e-4 if not args.from_scratch else 5e-4,   # 从头训:统一 lr
        "lr_decoder": 5e-4,
        "precision": "bf16",                       # 5070 Ti 支持;fp32 想开就删这行
        "ckpt_dir": str(ROOT / "outputs" / "ckpt"),
        "eval_max": 128,                           # 每次 eval 抽的 val 子集(全量=数千段×beam,小时级)
        # 训练步前置守卫:越界在 forward 之前拦下,报错自带肇事数字(不吃 CUDA 异步栈的亏)
        "guards": {"vocab": pf["vocab"], "max_pos": max_tgt},
    }
    eval_every = 3000
    if args.smoke:
        cfg.update({
            "max_steps": args.smoke_steps, "warmup_steps": 50, "max_epochs": 10 ** 6,
            "grad_accum_to_audio_sec": 200,        # 小集上 2000s 累积一步太久,冒烟用小步
            "log_every": 20,
            "ckpt_dir": str(ROOT / "outputs" / "ckpt_smoke"),
            # 关平滑:判据是"逐 token 语义 NLL 压到 ~0",平滑开着有 ~1.2 下界
            "loss": {"sem_label_smooth": 0.0, "p_center": 0.999, "w": 1},
        })
        eval_every = 10 ** 9                       # 冒烟不跑 eval(生成路径另测)
        dm.max_batch_sec = 120                     # 冒烟小批:16GB 卡上先别一口 560s 音频
    else:
        dm.max_batch_sec = 100                     # 16GB 卡:150s 跑 649 步 OOM,再降到 100s
    if args.cpu:
        cfg.update({"device": "cpu", "max_steps": 3, "grad_accum_to_audio_sec": 30,
                    "log_every": 1, "precision": ""})
        print("--cpu 诊断:CPU 跑 3 步(慢),越界会给精确 Python 栈,把完整报错贴回。")
    report = train(model, dm, cfg, tok, eval_every_steps=eval_every)
    # optimizer/scheduler 由 train() 内部 build(别在这重复建一份)

    print(f"\ntrain 收尾: {report.get('final')} final_loss={report.get('final_loss')} "
          f"final_sem={report.get('final_sem')} final_ts={report.get('final_ts')}")
    if args.smoke:
        fs = report.get("final_sem")
        ok = fs is not None and fs < 0.05
        print("冒烟判定: " + (f"【通过】final_sem={fs}<0.05,代码链路无 bug,可开全量"
                             if ok else
                             f"【不通过】final_sem={fs}(目标 <0.05)—— 查 tokenizer 编码/"
                             "标签对齐/损失分流,别开全量;ts 参考值 final_ts="
                             f"{report.get('final_ts')}(目标 <0.2)"))


if __name__ == "__main__":
    main()
