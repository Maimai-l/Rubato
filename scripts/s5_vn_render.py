"""
S5 表现性渲染驱动 —— 调【你本地的 VirtuosoNet】(不是重写它),按 VIRTUOSO_GUIDE 的 CLI/CSV。

诊断:SPEC 设计了 S5(R-S5.1-5.9)但从未落地脚本,历史上只有 S4 直排 —— 这就是"没有 VN 管线"的原因。
本脚本补上:每曲用 `virtuoso <xml> --csv` 产【表现性演奏 MIDI + 音符级 CSV】,
CSV 的 (xml_idx,start,end,pitch,velocity) 给出音符↔演奏秒(GUIDE §2.4,即 SPEC R-S5.6 主路径),
据此建 tmap;VN 的演奏 MIDI 直接渲成音频。音频与 TAST 同一 tmap ⇒ 天然对齐。

VN 主路径(默认)。humanize 只是 SPEC R-S5.9 的失败兜底(VN 超时/非零退出/无 CSV 时才用),
不是与 VN 并列的选项 —— 你有 VN,VN 就是管线。

用法(执行端,py312 环境已装 virtuoso):
  python scripts/s5_vn_render.py \
    --out-labels work/pdmx_perf_labels.jsonl --out-corpus work/a2s_corpus.txt \
    --out-audio-dir work/pdmx_audio
  # 想只在 VN 挂掉时兜底、或先干验:见 --allow-humanize-fallback / --limit。
"""
from __future__ import annotations
import argparse
import csv as _csv
import json
import os
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from rubato.platform import read_jsonl
from rubato.intermo.partitura_adapter import part_to_ir
from rubato.data.segment import segment_score, make_labels
from rubato.data.nasap_timemap import build_timemap
from rubato.render.core import (
    render_midi_to_wav44, finalize, assign_source_and_preset,
)

ROOT = Path(r"D:\vscode_projects\ee_download")


# ---------------------------------------------------------------- VN 调用(GUIDE §2/§4)

def vn_infer(xml_path: str, composer: str, out_mid: str, timeout_s: float = 300.0) -> str | None:
    """
    调本地 virtuoso CLI 产表现性演奏 MIDI + CSV(GUIDE §2.4)。成功返回 CSV 路径,失败返回 None。
    R-S5.2:--pedal(bool_pedal) --no-plot;--csv 导出音符级时间。R-S5.9:超时/非零退出 → None。
    """
    cmd = [r"D:\ProgramData\envs\py312\Scripts\virtuoso.exe", xml_path, "-c", composer, "--pedal", "--no-plot", "--csv", "-o", out_mid]
    try:
        subprocess.run(cmd, check=True, timeout=timeout_s,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None
    # GUIDE §2.4:CSV 与 MIDI 同级,名为 {midi文件名}_midi_notes.csv (不剥 .mid 后缀)
    csv_path = str(out_mid) + "_midi_notes.csv"
    return csv_path if Path(csv_path).exists() and Path(out_mid).exists() else None


def _find_vn_checkpoint() -> str | None:
    """按 VIRTUOSO_GUIDE §1 的标准布局自动定位权重,不用用户手传(CLI 本就 --checkpoint 自动查找)。
    找 virtuoso 包旁的 pretrained_weights/han_measnote_gru/checkpoint_best.pt。找不到返回 None。"""
    rel = Path("pretrained_weights") / "han_measnote_gru" / "checkpoint_best.pt"
    try:
        import virtuoso
        base = Path(virtuoso.__file__).resolve().parent
        for up in (base, base.parent, base.parent.parent):
            if (up / rel).exists():
                return str(up / rel)
    except Exception:
        pass
    for up in (Path.cwd(), Path.cwd().parent):     # 兜底:从当前目录找
        if (up / rel).exists():
            return str(up / rel)
    return None


class VNEngine:
    """
    按 GUIDE §5 Python API【只加载一次】172MB 模型,循环 infer_xml —— 不再每曲重载(R-S5.1)。
    构造一次(主进程),之后每曲只做前向。midi_decode_options 冻结 save_csv/bool_pedal/no_plot(R-S5.2)。
    """
    def __init__(self, checkpoint: str, out_dir: str, device: str | None = None):
        import torch
        from virtuoso.inference import InferenceModel
        self.out_dir = Path(out_dir); self.out_dir.mkdir(parents=True, exist_ok=True)
        self.model = InferenceModel(
            checkpoint_path=checkpoint,
            device=device or ("cuda" if torch.cuda.is_available() else "cpu"),
            output_path=str(self.out_dir),
            midi_decode_options={"save_csv": True, "bool_pedal": True, "no_plot": True},
        )

    def infer(self, xml_path: str, composer: str):
        """一曲前向(复用已载模型)。返回 (mid_path, csv_path) 或 (None, None)。"""
        import torch
        before = set(self.out_dir.glob("*.mid"))
        # 【内存】no_grad:VN 常驻主进程;若 virtuoso 内部没关 autograd,每曲前向都会把一张
        # 计算图挂在输出 tensor 上,主进程 RSS 随曲数线性涨。推理永不需要梯度。
        with torch.no_grad():
            self.model.infer_xml(xml_path=xml_path, composer_name=composer, qpm_primo=None)
        # 定位本曲产物:优先 GUIDE §2.3 命名,兜底取本次新增的 .mid(不受命名版本差异影响)
        stem, parent = Path(xml_path).stem, Path(xml_path).parent.name
        mid = self.out_dir / f"{parent}_{stem}_by_isgn_{composer}.mid"
        if not mid.exists():
            new = sorted(set(self.out_dir.glob("*.mid")) - before, key=lambda p: p.stat().st_mtime)
            mid = new[-1] if new else None
        if not mid or not mid.exists():
            return None, None
        for cand in (Path(str(mid) + "_midi_notes.csv"),                 # 执行端 CLI 实测的后缀
                     mid.parent / f"{mid.stem}_midi_notes.csv"):          # GUIDE §2.4 的另一种写法
            if cand.exists():
                return str(mid), str(cand)
        return str(mid), None


def csv_to_tmap(csv_path: str, part):
    """
    VN 的 CSV(xml_idx,start,end,pitch,velocity)→ 演奏 tmap(R-S5.6 主路径)。
    xml_idx = 音符在 MusicXML 的序号;对上 partitura 音符的乐谱起点(全音符单位)→ 锚点。
    复用 nasap_timemap.build_timemap(同样是"乐谱位置↔演奏秒"+单调化),含 pitch 一致性抽检。
    返回 (tmap, diag) 或 (None, diag)。
    """
    import numpy as np
    notes = list(part.notes_tied if hasattr(part, "notes_tied") else part.notes)
    qmap = np.atleast_2d(part.quarter_durations())
    dpq = int(qmap[0][1]) if qmap.size else 480
    whole = dpq * 4
    xmlid_pos, alignment = {}, []
    mismatch = 0
    with open(csv_path, encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            try:
                idx = int(r["xml_idx"]); start = float(r["start"]); pitch = int(r["pitch"])
            except (KeyError, ValueError):
                continue
            if idx < 0 or idx >= len(notes):
                continue
            n = notes[idx]
            nid = str(idx)
            xmlid_pos[nid] = Fraction(int(n.start.t), whole)
            alignment.append({"xml_id": nid, "perf_onset_sec": start, "pitch": pitch})
            npitch = n.midi_pitch if hasattr(n, "midi_pitch") else None
            if npitch is not None and npitch != pitch:
                mismatch += 1
    diag = {"anchors_in": len(alignment), "pitch_mismatch": mismatch}
    if len(alignment) < 2:
        return None, diag
    tmap, stats = build_timemap(alignment, xmlid_pos)
    diag.update(stats)
    return tmap, diag


def render_midi(midi_path: str, utt_id: str, sources_cfg, presets_cfg, out_path: str):
    """VN 演奏 MIDI → 44.1k wav → 预设链 → 16k opus 落盘(复用 S4 渲染链)。"""
    import tempfile
    src_id, preset_id = assign_source_and_preset(utt_id, sources_cfg, presets_cfg)
    source = sources_cfg["sources"][src_id]
    preset = presets_cfg["presets"][preset_id] if "presets" in presets_cfg else {"id": preset_id}
    with tempfile.TemporaryDirectory() as td:
        wav = str(Path(td) / "r.wav")
        render_midi_to_wav44(midi_path, source, sources_cfg, wav, utt_id=utt_id)
        finalize(wav, preset, sources_cfg, presets_cfg, utt_id, out_path)
    return out_path


def _read_audio(path: str):
    """整曲音频【只读一次】进内存,供逐段切片复用。返回 (audio, sr) 或 (None, None)。"""
    import soundfile as sf
    try:
        return sf.read(path, dtype="float32")
    except Exception:
        return None, None


def _slice_audio(audio, sr: int, t0: float, t1: float, out_path: str) -> str | None:
    """从【已载入】的整曲音频切 [t0,t1] 秒(段级 utt)。返回路径或 None。
    【内存修复】旧版每段各自 sf.read 整曲 —— 一首 30 段的曲把整曲反复读 30 次,worker 峰值分配
    被顶高且 heap 不还 OS(棘轮)。现在 cpu_stage 读一次、把数组传进来。"""
    a, b = max(0, int(t0 * sr)), min(len(audio), int(t1 * sr))
    if b - a < int(0.2 * sr):
        return None
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    # soundfile 不支持 .opus 写;统一用 .wav 落盘(后续 build_dataset 的 resolve_audio 会搜 .wav)
    wav_path = str(Path(out_path).with_suffix('.wav'))
    sf.write(wav_path, audio[a:b], sr)
    return wav_path


def _safe_unlink(p):
    if p and Path(p).exists():
        try:
            Path(p).unlink()
        except OSError:
            pass


def _piece_meta(piece, i):
    pid = piece.get("piece_id", f"p{i}")
    xml_rel = piece.get("xml_norm") or piece.get("xml_raw")
    xml_path = None
    if xml_rel:
        xml_path = xml_rel if Path(xml_rel).is_absolute() else str(ROOT / "work" / "xml_norm" / xml_rel)
    composer = piece.get("vn", {}).get("composer_used") or piece.get("composer") or "Beethoven"
    return pid, xml_path, composer


# ---------------------------------------------------------------- CPU 阶段(worker 并行,慢)
# worker 全局:由 initializer 每进程设一次(Windows spawn 也安全)。
_W: dict = {}


def _cpu_init(sources_cfg, presets_cfg, out_audio_dir, allow_hum, seed):
    _W.update(sources=sources_cfg, presets=presets_cfg,
              out=Path(out_audio_dir), allow_hum=allow_hum, seed=seed)


def cpu_stage(mid: dict) -> dict:
    """
    CPU 阶段(worker 进程,~5s):载谱 → tmap(VN CSV / humanize)→ 渲染整曲 → 按段切 + 打标签。
    段级音频落盘;返回 rows 给主进程统一写标签/语料(单写者,免并发写冲突)。
    """
    import partitura
    from rubato.render.humanize import humanize_timemap
    pid = mid["pid"]; xml_path = mid["xml_path"]
    perf_mid = mid["perf_mid"]; csv_path = mid["csv_path"]
    out = _W["out"]
    res = {"pid": pid, "vn_ok": 0, "vn_fail": 0, "humanized": 0, "rows": [], "fail": None}
    whole_audio = str(out / f"{pid}_whole.opus")
    try:   # 【清理】finally 兜底删所有中间产物 —— 旧版异常路径会把 _perf.mid/_whole.opus/csv 留在盘上
        try:
            s = partitura.load_musicxml(xml_path)
            part = s.parts[0] if hasattr(s, "parts") and s.parts else s
            ir = part_to_ir(part)
        except Exception as e:
            res["fail"] = f"load:{type(e).__name__}"
            return res

        tmap = None
        if csv_path:
            tmap, _ = csv_to_tmap(csv_path, part)
            _safe_unlink(csv_path)     # 【清理】CSV 用完即删 —— 旧版从不删,_vn/ 随曲数无限堆积
            csv_path = None
        if tmap is None:
            res["vn_fail"] = 1
            _safe_unlink(perf_mid)     # 【清理】兜底路径也删 VN 的 mid(旧版置 None 后文件漏在盘上)
            perf_mid = None
            if not _W["allow_hum"]:
                res["fail"] = "vn_no_tmap"
                return res
            tmap = humanize_timemap(ir, seed=_W["seed"], piece_id=pid)   # R-S5.9 兜底
            res["humanized"] = 1
        else:
            res["vn_ok"] = 1

        audio = None; sr = 0
        if perf_mid:
            try:
                render_midi(perf_mid, pid, _W["sources"], _W["presets"], whole_audio)
            except Exception as e:
                res["fail"] = f"render:{type(e).__name__}"
                return res
            audio, sr = _read_audio(whole_audio)   # 【内存】整曲【只读一次】,逐段切片复用
            if audio is None:
                res["fail"] = "read_audio"
                return res

        bounds = [m.start for m in ir.measures] + [ir.score_end]
        for si, (sub_ir, (a, b)) in enumerate(
                segment_score(ir, min_measures=2, max_measures=16, max_sec=40.0, sec_per_whole=2.0)):
            utt_id = f"pdmxperf_{pid}_{si:03d}"
            score_off = bounds[a] if a < len(bounds) else bounds[-1]
            labels, _ = make_labels(sub_ir, "human", tmap=tmap, score_offset=score_off)
            if not labels.get("A2S"):
                continue
            seg_audio = None
            if audio is not None:
                t_lo = float(tmap(bounds[a])); t_hi = float(tmap(bounds[min(b, len(bounds) - 1)]))
                seg_audio = _slice_audio(audio, sr, t_lo, t_hi, str(out / f"{utt_id}.opus"))
            res["rows"].append({"utt_id": utt_id, "piece_id": pid, "kind": "human",
                                "audio_path": seg_audio,
                                **{k: labels.get(k) for k in ("A2S", "A2S_lite", "TAST")}, "AMT": None})
        (out / f"{pid}.done").touch()                       # 断点标记
        return res
    finally:
        _safe_unlink(perf_mid); _safe_unlink(whole_audio); _safe_unlink(csv_path)


def run(manifest, sources_cfg, presets_cfg, out_labels, out_corpus, out_audio_dir,
        allow_humanize_fallback=False, seed=20260706, limit=None, offset=0, n_cpu=0,
        vn_checkpoint=None):
    """
    GPU/CPU 流水线:主进程顺序跑 VN 推理(GPU,~0.5s),非阻塞把渲染交给 CPU worker 池(~5s),
    GPU 不再干等 CPU —— CPU 渲染第 N 曲时,GPU 已在推理 N+1...(见 rubato.ops.pipeline_map)。
    VN 用 InferenceModel【只加载一次】(GUIDE §5),每曲只前向;vn_checkpoint=None 时退回 CLI(每曲重载,慢)。
    """
    import itertools
    from rubato.ops import pipeline_map
    # 生成器 + islice 应用 offset/limit,避免大 manifest 多次拷贝(执行端的内存优化),最后 materialize 一次
    gen = read_jsonl(manifest)
    if offset:
        gen = itertools.islice(gen, offset, None)
    if limit:
        gen = itertools.islice(gen, limit)
    pieces = list(gen)
    out_audio_dir = Path(out_audio_dir); out_audio_dir.mkdir(parents=True, exist_ok=True)
    label_fh = open(out_labels, "a", encoding="utf-8") if out_labels else None
    corpus_fh = open(out_corpus, "a", encoding="utf-8") if out_corpus else None
    rep = {"pieces": len(pieces), "vn_ok": 0, "vn_fail": 0, "humanized": 0,
           "utts": 0, "tast": 0, "failures": []}

    # VN 引擎:InferenceModel【只加载一次】(GUIDE §5)。ckpt 不传就【自动定位】virtuoso 标准权重
    # (你不用传 --vn-checkpoint);找不到才退回 CLI(CLI 本就自动查权重,只是每曲重载)。
    if not vn_checkpoint:
        vn_checkpoint = _find_vn_checkpoint()
    engine = None
    if vn_checkpoint:
        try:
            engine = VNEngine(vn_checkpoint, out_dir=str(out_audio_dir / "_vn"))
            print(f"VN: InferenceModel 已加载一次(复用),ckpt={vn_checkpoint}")
        except Exception as e:
            print(f"VN: InferenceModel 构造失败({type(e).__name__}: {str(e)[:80]}),退回 CLI(自动查权重,每曲重载)")
            engine = None
    else:
        print("VN: 未定位到标准权重,用 CLI(自动查权重,每曲重载)。若知道 .pt 路径可传 --vn-checkpoint 换成只加载一次。")

    def gpu_stage(piece):
        # 主进程:只做 VN 推理(GPU,快)。engine 复用已载模型;无 engine 才用 CLI(每曲重载)。
        pid, xml_path, composer = _piece_meta(piece, piece.get("_i", 0))
        if not xml_path:
            return None
        if engine is not None:
            mid, csv_path = engine.infer(xml_path, composer)
            return {"pid": pid, "xml_path": xml_path, "perf_mid": mid, "csv_path": csv_path}
        perf_mid = str(out_audio_dir / f"{pid}_perf.mid")
        csv_path = vn_infer(xml_path, composer, perf_mid)
        return {"pid": pid, "xml_path": xml_path, "perf_mid": perf_mid, "csv_path": csv_path}

    def done_fn(piece):
        pid, _, _ = _piece_meta(piece, piece.get("_i", 0))
        return (out_audio_dir / f"{pid}.done").exists()

    def on_result(piece, res):
        rep["vn_ok"] += res["vn_ok"]; rep["vn_fail"] += res["vn_fail"]
        rep["humanized"] += res["humanized"]
        if res.get("fail"):
            rep["failures"].append({"piece_id": res["pid"], "reason": res["fail"]})
        for row in res["rows"]:
            rep["utts"] += 1
            if row.get("TAST"):
                rep["tast"] += 1
            if label_fh:
                label_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            if corpus_fh:
                for d in ("A2S", "A2S_lite"):
                    if row.get(d):
                        corpus_fh.write(row[d].strip() + "\n")

    for idx, p in enumerate(pieces):
        p["_i"] = idx

    # 【内存预算】CPU 渲染阶段和 S4 一样会加载 sfizz 音源(146MB~6.5GB)。按音源大小准入,
    # 同时运行的音源内存和 ≤ 预算 → S5 渲染也【不 OOM】。权重 = 该曲要用的音源目录大小。
    from rubato.render.core import soundfont_weights, assign_source_and_preset
    from rubato.ops import available_gb
    repo_root = Path(__file__).resolve().parent.parent
    mem_factor = float(os.environ.get("S5_MEM_FACTOR", "1.0"))
    reserve = float(os.environ.get("S5_RESERVE_GB", "4"))
    # 每次渲染除了音源,还占【整曲音频缓冲】(sf.read + 重采样 + 卷积混响 + ffmpeg)≈1GB。
    # 【必须】把这块也计入权重,否则小音源会放行太多并发、各自的音频缓冲把内存吃爆。
    overhead = float(os.environ.get("S5_RENDER_OVERHEAD_GB", "1.0"))
    # 【内存·关键补漏】worker 每跑几曲就回收重开:清掉 partitura/numpy 顶出来的 RSS 棘轮
    # (预算只管【同时】占用,管不住 worker RSS【随曲数累积】上涨 —— 那才是"越跑越高最后炸"的真凶)。
    # Windows(spawn)默认开;Linux fork 平台默认关(设 S5_TASKS_PER_CHILD>0 强制开,自动换 forkserver)。
    recycle = int(os.environ.get("S5_TASKS_PER_CHILD", "16" if os.name == "nt" else "0"))
    src_gb = soundfont_weights(sources_cfg, repo_root, mem_factor=mem_factor)
    budget = max(2.0, available_gb() - reserve)

    def weight_fn(mid):
        try:
            sid, _ = assign_source_and_preset(mid["pid"], sources_cfg, presets_cfg)
            sf_gb = src_gb.get(sid, 2.0)
        except Exception:
            sf_gb = 2.0                       # 取不到音源 → 保守
        return sf_gb + overhead               # 音源 + 每次渲染的音频缓冲开销

    n_cpu = n_cpu or (os.cpu_count() or 4)
    print(f"S5 VN pipeline: {len(pieces)} pieces | 渲染内存预算 {budget:.1f}GB(可用 {available_gb():.1f} "
          f"− 留 {reserve}) | max_workers={n_cpu} | 回收 {recycle or '关'} 曲/进程 | "
          f"GPU 推理与 CPU 渲染重叠、按音源大小准入不 OOM")
    print(f"  权重 = 音源目录大小 + 每渲染开销 {overhead}GB(音频缓冲)。音源(GB): "
          + ", ".join(f"{k}={v:.1f}" for k, v in sorted(src_gb.items())))
    stats = pipeline_map(pieces, gpu_stage, cpu_stage, n_cpu=n_cpu, on_result=on_result,
                         done_fn=done_fn, key_fn=lambda p: p.get("piece_id"),
                         weight_fn=weight_fn, budget_gb=budget,
                         initializer=_cpu_init, max_tasks_per_child=recycle or None,
                         initargs=(sources_cfg, presets_cfg, str(out_audio_dir),
                                   allow_humanize_fallback, seed))
    if label_fh:
        label_fh.close()
    if corpus_fh:
        corpus_fh.close()
    print(f"\nDONE: vn_ok={rep['vn_ok']} vn_fail={rep['vn_fail']} humanized={rep['humanized']} "
          f"skipped={stats['done_skipped']} dropped={stats['dropped']} "
          f"utts={rep['utts']} TAST={rep['tast']} cpu_fail={stats['failed']}")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sources", default="configs/sources.yaml")
    ap.add_argument("--presets", default="configs/recording_presets.yaml")
    ap.add_argument("--out-labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--out-corpus", default=str(ROOT / "work" / "a2s_corpus.txt"))
    ap.add_argument("--out-audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--allow-humanize-fallback", action="store_true",
                    help="仅在 VN 失败/超时的曲上兜底(SPEC R-S5.9);默认关,VN 失败即计入 failures")
    ap.add_argument("--workers", type=int, default=0, help="CPU 渲染并发;0=按内存自动定")
    ap.add_argument("--vn-checkpoint", default="",
                    help="通常【不用传】——脚本自动定位 virtuoso 标准权重(GUIDE §1)。"
                         "仅当你的 .pt 在非标准位置才指定。")
    args = ap.parse_args()
    sources_cfg = yaml.safe_load(open(args.sources, encoding="utf-8"))
    presets_cfg = yaml.safe_load(open(args.presets, encoding="utf-8"))
    run(args.manifest, sources_cfg, presets_cfg, args.out_labels, args.out_corpus,
        args.out_audio_dir, offset=args.offset,
        allow_humanize_fallback=args.allow_humanize_fallback,
        limit=args.limit or None, n_cpu=args.workers,
        vn_checkpoint=(args.vn_checkpoint or None))


if __name__ == "__main__":
    main()
