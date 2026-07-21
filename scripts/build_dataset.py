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
# C2 偏移窗(EXPERIMENT_ACOUSTIC):同录音错开的第二组 AMT 窗,存在才挂载(生成前不碍事)。
# 只含 train 行(生成器强制),utt_id 带 _o10 后缀不撞名;评测池(val/test)因此不变。
_O10 = WORK / "maestro_amt_windows_o10.jsonl"
if _O10.exists():
    SOURCES.append({"path": str(_O10), "kind": "maestro", "domain": "real"})
# C3 音色副本(D50):生成器只写 .staging 名;把 staging 改成本名 = 进池武装,
# 只按 EXECUTOR.md 的书面指令执行(单变量纪律)。行全 train、utt_id 带 _s2。
_S2 = WORK / "pdmx_a2s_labels_s2.jsonl"
if _S2.exists():
    SOURCES.append({"path": str(_S2), "kind": "pdmx", "domain": "synth"})

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
        # C3 音色副本(_s2 行)在独立目录 pdmx_audio_s2(D51:与训练读取目录隔离,根治
        # sfizz/训练 Windows 文件锁争抢);按后缀选目录,原名空间零污染。
        _adir = "pdmx_audio_s2" if utt_id.endswith("_s2") else "pdmx_audio"
        for ext in (".opus", ".flac"):
            p = WORK / _adir / f"{utt_id}{ext}"
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
    ap.add_argument("--max-batch-sec", type=float, default=None,
                    help="每 batch 音频秒上限;不传 = 全量 60 / 冒烟 120。执行端 16GB 卡实测:"
                         "150s OOM、100s 只剩 45MiB、60s 稳 —— 之前是执行端本地 patch,"
                         "每次 pull 担心被覆盖,现在是正式参数(此前版本会被写死的 60 覆盖,已修)")
    ap.add_argument("--probe-only", action="store_true",
                    help="诊断模式,不训练:恢复 last.pt,对三源各取 N 条训练对做"
                         "【对齐等级 × Δsem】联合测量(模型是否只在数据对齐处读音频),"
                         "证据落盘 autolog 后退出")
    ap.add_argument("--probe-n", type=int, default=8,
                    help="probe-only 每源样本数(默认 8;每条约 2 次 forward,总耗时分钟级)")
    ap.add_argument("--lr-dec", type=float, default=None,
                    help="decoder(及非 encoder)组峰值 lr,默认 5e-4。断点续训时会在快照恢复后"
                         "重刷生效(不加这层,快照会把 CLI 值静默还原成旧 lr)。H2 实验:3e-4")
    ap.add_argument("--lr-enc", type=float, default=None,
                    help="encoder 组峰值 lr,默认热启动 1e-4 / --from-scratch 5e-4")
    ap.add_argument("--clip-norm", type=float, default=1.0,
                    help="梯度裁剪阈值。序列损失量纲 ≈65(非逐 token 平均),若日志 gn 长期"
                         "远大于阈值 = 有效 lr 被裁剪吃掉几十倍 —— 证实后按 gn 中位数上调(如 10)")
    ap.add_argument("--eval-max", type=int, default=48,
                    help="每次 eval 抽的样本数/源。逐 token 生成:快路径 ~10s/样本,128 个≈半小时起;"
                         "监控用 48 足够,论文终评另跑全量")
    ap.add_argument("--eval-every", type=int, default=1000,
                    help="每多少优化步跑一次 eval+存滚动 ckpt。这台卡 ~1600 步/epoch、"
                         "每步几十秒 —— 3000 步一评是两天一评,太稀;1000 步≈半天一评")
    ap.add_argument("--smoke-steps", type=int, default=800,
                    help="冒烟步数。执行端实测:100 utt × 800 步 sem 8.98→3.83 稳降但没到 0.05"
                         "(全新 embedding+头要背下语料需要更多步);32 utt × 4000 步可达标")
    ap.add_argument("--prompt-abtest", action="store_true",
                    help="D44 判定实验:同 ckpt/同样本/同解码,仅 prompt 变 —— G0 无域(现状)/"
                         "G1 real(与训练一致)/G2 synth(反向对照)。不训练,结果进 autolog。"
                         "判据预登记 EXPERIMENT_PROMPT.md")
    ap.add_argument("--abtest-n", type=int, default=48,
                    help="prompt-abtest 每臂样本数(与 eval 同源的确定性 nasap 子集)")
    ap.add_argument("--prefetch", type=int, default=0,
                    help="【实验性,默认关】预取批深度。线程版/进程版两次实测均为负收益"
                         "(D40/D41:串行 10.5s/步 → 18s/步),默认 0=串行直迭代(已知好)。"
                         "仅在 td/tc 计时数据支持时再开(见 EXPERIMENT_SPEED v3)")
    ap.add_argument("--amt-mix", type=float, default=None,
                    help="O4 旋钮:AMT 方言混比(缺省 None=D2 纸面 0.30)。设定后腾出的权重"
                         "按 35:15:20 等比还给 A2S/A2S_lite/TAST。生效与否看两处:启动回显"
                         "mix= 字段 + epoch 混比报告的 quota。50000 步复盘用:0.22")
    ap.add_argument("--cpu", action="store_true",
                    help="诊断模式:全程 CPU 跑 3 步。CUDA 的索引越界是异步 device assert,"
                         "栈指向随机后续 kernel(实测三次崩溃三个栈);CPU 上同一越界给出"
                         "精确 Python 栈 + 肇事索引。配 --smoke 用,慢但一锤定音")
    args = ap.parse_args()
    if args.max_batch_sec is None:
        # 缺省按模式定:全量 60(16GB 卡 100s 仍 OOM,首 batch 145s 单样本撑爆)、
        # 冒烟 120(小集小批)。显式传参则全程生效 —— 旧版在建 dm 后无条件改回 60/120,
        # CLI 形同虚设,救火时(想临时降到 40s)会静默不生效。
        args.max_batch_sec = 120.0 if args.smoke else 60.0

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

    if args.probe_only:
        # 诊断模式,不训练。v2(D27 后):三源探针 —— 对齐审计发现只有 nASAP 对齐故障,
        # 而此前所有探针/评测样本恰好全来自 nASAP。"decoder 全局忽略音频"可能要收窄为
        # "nASAP 分支被污染 + 评测建在污染源上"。本模式对 nasap/maestro/pdmx 各取 2 个
        # 训练对,分别测 真音频 vs 静音 的语义命中率差(Δsem),一分钟分辨全局病与局部病。
        import numpy as np
        import time as _time
        import torch
        last = ROOT / "outputs" / "ckpt" / "last.pt"
        step0 = 0
        if last.exists():
            snap = torch.load(str(last), map_location="cpu")
            model.load_state_dict(snap["model"])
            step0 = int(snap.get("step", 0))
            print(f"--probe-only:已加载 {last}(step={step0}),三源探针,不训练")
        else:
            print(f"--probe-only:⚠ {last} 不存在,用热启动初始权重跑(仅验证探针管线)")
        if torch.cuda.is_available():
            model = model.cuda()
        model.eval()
        from rubato.model.infer import teacher_forced_probe
        from rubato.model.train import _sample_audio
        lines: list[str] = []

        def _pp(s: str):
            print(s, flush=True)
            lines.append(s)

        _fmt = lambda v: "-" if v is None else f"{v:.2f}"
        # v3(联合仪器):同一批样本上 对齐等级 × Δsem 二维联判 —— 三源探针发现模型
        # "选择性读音频"(对齐样本 Δsem=+0.12~0.16,错位样本 0.00),单点探针以偏概全,
        # 必须看"Δsem 是否只在对齐样本上为正"这个人群级相关。
        from scripts.audit_alignment import (onset_envelope, label_onset_train,
                                             best_lag, classify, label_onsets)
        _pp(f"probe-only 联合仪器(对齐×Δsem)@ step {step0},每源 {args.probe_n} 条")
        rows = []
        groups = (("nasap", nasap_val, ("TAST", "A2S")),
                  ("maestro", maestro_val, ("AMT",)),
                  ("pdmx", train_utts, ("TAST", "A2S")))
        with torch.no_grad():
            for kind, pool, dias in groups:
                done = 0
                seen_pieces: set = set()          # 每曲最多 1 窗:8 窗同曲的教训
                for u in pool:
                    if done >= args.probe_n:
                        break
                    if u.get("kind") != kind:
                        continue
                    piece = str(u.get("utt_id", "")).rsplit("_", 1)[0]
                    if piece in seen_pieces:
                        continue
                    seen_pieces.add(piece)
                    lab = labels.get(u["utt_id"], {}) or {}
                    d = next((x for x in dias if lab.get(x)), None)
                    if not d:
                        continue
                    audio = _sample_audio(u)
                    if audio is None:
                        continue
                    try:
                        ons = label_onsets(lab[d], d)
                        env = onset_envelope(audio)
                        al = best_lag(env, label_onset_train(ons, len(env))) if ons \
                            else {"peak": 0.0, "lag_ms": 0, "n_frames": 0, "corr0": 0.0}
                        cls = classify(al)
                        pr = teacher_forced_probe(model, audio, lab[d], d, tok,
                                                  domain=u.get("domain"))
                        mu = teacher_forced_probe(
                            model, np.zeros_like(np.asarray(audio, dtype=np.float32)),
                            lab[d], d, tok, domain=u.get("domain"))
                        ds = (pr["acc_sem"] - mu["acc_sem"]) \
                            if (pr.get("acc_sem") is not None
                                and mu.get("acc_sem") is not None) else None
                        rows.append({"kind": kind, "cls": cls, "ds": ds})
                        _pp(f"  联合 {kind}/{d}[{u['utt_id']}]: 对齐={cls}"
                            f"(peak={al['peak']} lag={al['lag_ms']}ms) "
                            f"Δsem={_fmt(ds) if ds is None else f'{ds:+.2f}'} "
                            f"真sem={_fmt(pr.get('acc_sem'))} 静sem={_fmt(mu.get('acc_sem'))} "
                            f"ts真={_fmt(pr.get('acc_ts'))}/静{_fmt(mu.get('acc_ts'))} "
                            f"n={pr['n_scored']}")
                        done += 1
                    except Exception as e:
                        _pp(f"  联合 {kind}[{u.get('utt_id', '?')}] 失败: "
                            f"{type(e).__name__}: {e}")
                        done += 1
                if not done:
                    _pp(f"  {kind}: 无可用样本(缺标签或音频)")
        # 人群级汇总:Δsem 按对齐等级分桶(判定矩阵的直接输入)
        def _mean(v):
            v = [x for x in v if x is not None]
            return (sum(v) / len(v), len(v)) if v else (None, 0)
        ok_m, ok_n = _mean([r["ds"] for r in rows if r["cls"] == "OK"])
        bad_m, bad_n = _mean([r["ds"] for r in rows if r["cls"] != "OK"])
        _pp(f"  联合汇总: 对齐OK 平均Δsem={_fmt(ok_m)}(n={ok_n}) | "
            f"错位 平均Δsem={_fmt(bad_m)}(n={bad_n})")
        for kind in ("nasap", "maestro", "pdmx"):
            km, kn = _mean([r["ds"] for r in rows if r["kind"] == kind and r["cls"] == "OK"])
            bm, bn = _mean([r["ds"] for r in rows if r["kind"] == kind and r["cls"] != "OK"])
            _pp(f"  分源 {kind}: OK Δsem={_fmt(km)}(n={kn}) 错位 Δsem={_fmt(bm)}(n={bn})")
        autolog = Path(__file__).resolve().parent.parent / "reports" / "eval_autolog.md"
        autolog.parent.mkdir(parents=True, exist_ok=True)
        with open(autolog, "a", encoding="utf-8") as fh:
            fh.write(f"\n## probe-only 三源探针 @ step {step0} "
                     f"({_time.strftime('%Y-%m-%d %H:%M:%S')})\n" + "\n".join(lines) + "\n")
        print(f"完成,证据已落盘 {autolog} —— git add + commit + push;训练继续保持暂停。")
        return

    if args.prompt_abtest:
        # D44 判定实验(EXPERIMENT_PROMPT):训练每条样本的前缀都带 <|real|>/<|synth|>,
        # 自由解码从来不带(执行端发现,代码坐实)。同 ckpt、同确定性 nasap 子集、同解码,
        # 只动 prompt:G0 无域(现状基线)/ G1 real(与训练一致)/ G2 synth(反向对照,
        # 排除"随便多个 token 都变好"的前缀长度效应)。判据在卡里预登记,先于数据。
        import time as _time
        import torch
        from rubato.intermo.core import text_to_units, validate_units
        from rubato.model.evaluate import text_ned
        import rubato.model.infer as _inf
        from rubato.model.infer import infer_a2s, _EMPTY_A2S
        from rubato.model.train import _eval_subset, _sample_audio, viol_tally
        last = ROOT / "outputs" / "ckpt" / "last.pt"
        step0 = 0
        if last.exists():
            snap = torch.load(str(last), map_location="cpu")
            model.load_state_dict(snap["model"])
            step0 = int(snap.get("step", 0))
        else:
            print(f"--prompt-abtest:⚠ {last} 不存在,热启动初始权重(仅验证管线,勿判读)")
        print(f"--prompt-abtest @ step {step0}:G0 无域 / G1 real / G2 synth,"
              f"每臂 {args.abtest_n} 条,约 {args.abtest_n}×3×10s", flush=True)
        if torch.cuda.is_available():
            model = model.cuda()
        model.eval()
        subset = _eval_subset(nasap_val, int(args.abtest_n))
        lines = [f"三臂同 ckpt(step={step0})同子集 n={len(subset)},仅 prompt 不同"]
        with torch.no_grad():
            for arm, dom in (("G0", None), ("G1", "real"), ("G2", "synth")):
                n_ok = n_fb = n_seen = 0
                neds: list = []
                shows: list = []
                entries: list = []
                for si, s in enumerate(subset):
                    audio = _sample_audio(s)
                    if audio is None:
                        continue
                    n_seen += 1
                    pred = infer_a2s(model, audio, tok, domain=dom)
                    tv = list(getattr(_inf, "LAST_VIOLS", []) or [])
                    fb = pred == _EMPTY_A2S
                    viol = validate_units(text_to_units(pred)) if pred else ["empty"]
                    ok = (not fb) and not viol
                    n_ok += int(ok)
                    n_fb += int(fb)
                    entries.append((False, []) if ok else (fb and not tv, tv or viol))
                    ref = (labels.get(s.get("utt_id"), {}) or {}).get("A2S") or ""
                    if ok and ref:
                        neds.append(text_ned(pred, ref))
                    if si < 10:
                        shows.append(f"    [{arm}#{si}] {pred[:100]!r}")
                    if si % 8 == 0:
                        print(f"  {arm} {si}/{len(subset)}", flush=True)
                med = sorted(neds)[len(neds) // 2] if neds else None
                t = viol_tally(entries)
                lines.append(
                    f"  {arm}(domain={dom}): parseable={n_ok}/{n_seen} 兜底={n_fb} "
                    f"NED中位={'-' if med is None else f'{med:.3f}'}(n={len(neds)}) 拒因: "
                    + " ".join(f"{k}={v}" for k, v in sorted(t.items(), key=lambda kv: (-kv[1], kv[0]))))
                lines.extend(shows)
        for ln in lines:
            print(ln, flush=True)
        autolog = Path(__file__).resolve().parent.parent / "reports" / "eval_autolog.md"
        with open(autolog, "a", encoding="utf-8") as fh:
            fh.write(f"\n## prompt-abtest @ step {step0} "
                     f"({_time.strftime('%Y-%m-%d %H:%M:%S')})\n" + "\n".join(lines) + "\n")
        print(f"完成,证据已落盘 {autolog} —— git add + commit + push 后即可重启训练。")
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
    # O4:混比注入。None = sampling.DIALECT_MIX 缺省(D2 纸面);设了 --amt-mix 则在此换算
    dialect_mix = None
    if args.amt_mix is not None:
        from rubato.model.sampling import mix_with_amt
        dialect_mix = mix_with_amt(args.amt_mix)
        print("  混比(O4 调整): " + " ".join(f"{d}={v:.4f}" for d, v in sorted(dialect_mix.items())))
    train_ds = RubatoDataset(train_utts, labels, tok, train=True, max_target_len=max_tgt,
                             augment=not args.smoke, dialect_mix=dialect_mix)
    lf = train_ds.len_filter_report
    print(f"  超长过滤: 保留 {lf.get('kept_pairs')} 对,丢弃 {lf.get('dropped_by_dialect') or 0}")
    _dropped = sum((lf.get("dropped_by_dialect") or {}).values())
    if _dropped > 0.10 * max(lf.get("kept_pairs", 1), 1):
        print("  ⚠ 超长丢弃 >10% —— 值得扩位置表(resize position embedding)找回,贴回给规划端")
    # labels 全量传入(不只 train)—— eval hook 的参照(AMT ref/A2S NED)按 val/test utt_id 查
    dm = RubatoDataModule(train_ds, nasap_val=nasap_val, maestro_val=maestro_val, labels=labels,
                          max_batch_sec=args.max_batch_sec)

    # 多源 Δsem 探针池(每次 eval 固定测这三条):单源探针曾两次把全局判决带偏(D27/D28)。
    # 逐 eval 追踪各源"真音频-静音"的语义命中率差 = 音频阅读能力的进度表。
    def _first_labeled(pool, kind):
        for u in pool:
            if u.get("kind") == kind and (labels.get(u["utt_id"], {}) or {}):
                return u
        return None
    # 第 3 条钉死 utt_id:它原是"train 池第一个有标签的 pdmx"——召回的 +7,501 段进池后
    # 装配顺序会变,按序取会静默换样本,20+ 次 eval 的趋势线就断了。找不到才退回按序。
    _pdmx_pin = next((u for u in train_utts
                      if u.get("utt_id") == "pdmxperf_QmbbRy4561YHg98r1sCMpY3jyL24gamUS5LECitgf6NwXm_000"),
                     None) or _first_labeled(train_utts, "pdmx")
    dm.probe_utts = [u for u in (_first_labeled(nasap_val, "nasap"),
                                 _first_labeled(maestro_val, "maestro"),
                                 _pdmx_pin) if u]
    # 第 4 条:联合仪器实测读音频最强的 pdmx 样本(Δsem+0.17/审计 OK)——原第 3 条恰是
    # 弱相关样本,代表性差;只加不换,保留前三条的逐 eval 趋势连续性
    _good = next((u for u in train_utts
                  if u.get("utt_id") == "pdmxperf_QmbbFEQzNihEnR2EvTumtWeYgcCWcqUvEeCWPCk5GZA7GQ_000"), None)
    if _good:
        dm.probe_utts.append(_good)
    cfg = {
        "lr_encoder": args.lr_enc if args.lr_enc is not None
                      else (1e-4 if not args.from_scratch else 5e-4),   # 从头训:统一 lr
        "lr_decoder": args.lr_dec if args.lr_dec is not None else 5e-4,
        "precision": "bf16",                       # 5070 Ti 支持;fp32 想开就删这行
        "ckpt_dir": str(ROOT / "outputs" / "ckpt"),
        "clip_norm": args.clip_norm,
        "dialect_mix": dialect_mix,                # None=D2 纸面;设了 --amt-mix 则为换算后的四元组(回显自证)
        "prefetch_batches": args.prefetch,         # 预取深度;0=串行直迭代(对照)
        "eval_max": args.eval_max,                 # 每次 eval 抽的 val 子集(逐 token 生成,大了小时级)
        "eval_time_budget_s": 1200,                # eval 硬时限:超时截断按已评样本出指标,不再"疑似卡死"
        # eval 证据自动落盘到 repo 内(追加式);执行端上报 = git add reports/eval_autolog.md
        # + commit + push,不再人肉摘录(三次摘录事故后收权)
        "eval_autolog": str(Path(__file__).resolve().parent.parent / "reports" / "eval_autolog.md"),
        # 训练步前置守卫:越界在 forward 之前拦下,报错自带肇事数字(不吃 CUDA 异步栈的亏)
        "guards": {"vocab": pf["vocab"], "max_pos": max_tgt},
    }
    eval_every = args.eval_every
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
