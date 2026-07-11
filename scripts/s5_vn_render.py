"""
S5 表现性渲染驱动 —— 调【你本地的 VirtuosoNet】(不是重写它),按 VIRTUOSO_GUIDE 的 CLI/CSV。

诊断:SPEC 设计了 S5(R-S5.1-5.9)但从未落地脚本,历史上只有 S4 直排 —— 这就是"没有 VN 管线"的原因。
本脚本补上:每曲用 `virtuoso <xml> --csv` 产【表现性演奏 MIDI + 音符级 CSV】,
CSV 的 (xml_idx,start,end,pitch,velocity) 给出音符↔演奏秒(GUIDE §2.4,即 SPEC R-S5.6 主路径),
据此建 tmap;VN 的演奏 MIDI 直接渲成音频。音频与 TAST 同一 tmap ⇒ 天然对齐。

VN 是【唯一】路径(用户拍板,humanize 兜底已删除):VN 超时/非零退出/无 CSV = 该曲失败,
计入 failures,按标签续跑机制重试;绝不用假的恒速"人性化"顶替真演奏。

用法(执行端,py312 环境已装 virtuoso):
  python scripts/s5_vn_render.py \
    --out-labels work/pdmx_perf_labels.jsonl --out-corpus work/a2s_corpus.txt \
    --out-audio-dir work/pdmx_audio
  # 先干验:--limit 20。
"""
from __future__ import annotations
import argparse
import csv as _csv
import json
import multiprocessing as _mp
import os
import queue as _queue
import subprocess
import sys
import threading as _threading
import time
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 【必须最先做】关 wandb 的 stdout 拦截 + 硬化控制台编码,否则 Windows GBK 下打印 '−'/作曲家名即崩
# (执行端 S5 五次全崩在这,VN 一次没跑成)。在 import virtuoso(带出 wandb)之前设好。
from rubato.platform import read_jsonl, harden_stdout, quiet_wandb
quiet_wandb()
harden_stdout()

import yaml

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


def _labeled_piece_ids(path) -> set:
    """out_labels 里【真的写过标签行】的 piece_id 集合。
    【续跑正确性】只有真有标签才算这曲做完 —— 光有 .done 标记【不算】:执行端有 7514 个旧 CLI 跑的
    .done,若按 .done 跳过,而这些曲的标签没进当前 out_labels,就会把它们【静默丢出训练集】。
    按标签在不在算数:有标签→跳过(不重复);.done 但无标签→重跑(补回来,不静默丢)。"""
    ids = set()
    if not path or not os.path.exists(path):
        return ids
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                pid = json.loads(line).get("piece_id")
            except Exception:
                continue
            if pid is not None:
                ids.add(pid)
    return ids


def _main_rss_gb() -> float:
    """主进程(VN 常驻)自身的 RSS(GB)。自诊断关键:worker 回收管不到主进程,
    若这个数随曲数一直涨 = 泄漏在【主进程 VN】,不在 worker —— 一眼看出到底谁在涨。"""
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e9
    except Exception:
        return 0.0


def _free_gpu_and_gc(full: bool = False):
    """每曲 VN 前向后清一次:释放 CUDA 缓存(不还就棘轮式涨)+(full 时)gc 断循环引用。
    主进程随曲数涨的第一道止血;彻底的累积由 _rebuild 定期重建引擎兜底。"""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    if full:
        import gc
        gc.collect()


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


# ---------------------------------------------------------------- VN 子进程(把泄漏关进可回收进程)

def _vn_child_main(req_q, resp_q, checkpoint, out_dir):
    """VN 子进程主循环:构造 InferenceModel【一次】,循环收 (xml,composer) → infer → 回 (status,mid,csv)。
    为什么在子进程:torch 模型常驻会随时间棘轮式泄漏主机 RSS(~1GB/5s,GPU 显存却是静态的 —— 是
    CUDA 驱动/WDDM 在 RTX50 上占的主机内存,Python 侧 empty_cache/gc/重建对象都收不回)。放子进程里,
    一 kill,OS 全额回收;主进程只发路径收路径,始终平坦(执行端 CLI 模式已实测主进程平)。"""
    try:
        from rubato.platform import quiet_wandb, harden_stdout
        quiet_wandb(); harden_stdout()
    except Exception:
        pass
    try:
        eng = VNEngine(checkpoint, out_dir=out_dir)
        resp_q.put(("ready", None, None))
    except Exception as e:
        resp_q.put(("init_fail", f"{type(e).__name__}: {str(e)[:150]}", None))
        return
    while True:
        try:
            item = req_q.get()
        except (EOFError, OSError):
            return
        if item is None:                 # 收到停止信号
            return
        xml, composer = item
        try:
            mid, csv = eng.infer(xml, composer)
            resp_q.put(("ok", mid, csv))
        except Exception as e:
            resp_q.put(("infer_fail", f"{type(e).__name__}: {str(e)[:150]}", None))


class VNSubprocess:
    """把 VN 推理关进【可回收的子进程】,按 RSS 水位 kill+重开,封死 torch 模型的时间型泄漏。
    - 模型在子进程里【只加载一次】、跨曲复用(比 CLI 每曲重载快);子进程 RSS 越过 cap 才回收(重载~2s)。
    - 监控线程在【渲染长等待期间】也盯 RSS(泄漏与推理无关、空闲也涨),越界即回收,主进程不 OOM。
    - 推理卡死(未在 timeout 内返回)→ 杀掉重开,本曲判失败(续跑按标签重试)。
    ctx/child_target/rss_fn 可注入,便于在无 GPU 沙盒里测回收机制。"""
    def __init__(self, checkpoint, out_dir, rss_cap_gb=4.0, infer_timeout=180.0,
                 monitor_sec=3.0, load_timeout=600.0, ctx=None, child_target=None, rss_fn=None):
        self.checkpoint = checkpoint; self.out_dir = str(out_dir)
        self.rss_cap_gb = rss_cap_gb; self.infer_timeout = infer_timeout
        self.load_timeout = load_timeout
        self.ctx = ctx or _mp.get_context("spawn")     # Windows 天然 spawn;CUDA 必须 spawn(不能 fork)
        self._child = child_target or _vn_child_main
        self._rss_override = rss_fn
        self._lock = _threading.RLock()
        self.proc = None; self.req_q = None; self.resp_q = None
        self.recycles = 0; self.n_infer = 0
        self.gen = 0                     # 进程代号:每次 kill+重开 +1;在飞推理据此发现"子进程已被换掉"
        self._rss_warned = False
        self._start()
        self._stop = _threading.Event()
        self._mon = _threading.Thread(target=self._monitor, args=(monitor_sec,), daemon=True)
        self._mon.start()

    def _start(self):
        self.req_q = self.ctx.Queue(); self.resp_q = self.ctx.Queue()
        self.proc = self.ctx.Process(target=self._child,
                                     args=(self.req_q, self.resp_q, self.checkpoint, self.out_dir),
                                     daemon=True)
        self.proc.start()
        self.gen += 1
        status, msg, _ = self.resp_q.get(timeout=self.load_timeout)
        if status != "ready":
            raise RuntimeError(f"VN 子进程加载失败: {msg}")

    def _rss_gb(self):
        if self._rss_override is not None:
            return self._rss_override(self.proc)
        try:
            import psutil
            if self.proc and self.proc.pid:
                return psutil.Process(self.proc.pid).memory_info().rss / 1e9
        except ImportError:
            # 【必须响】psutil 缺失 = RSS cap 监控整个失效 → 泄漏无界。绝不能静默装作 0.0。
            if not self._rss_warned:
                self._rss_warned = True
                print("  [mem][警告] 此环境无 psutil,VN 子进程 RSS 监控失效(泄漏将无界)!"
                      "请在运行 S5 的 env 里 pip install psutil", flush=True)
        except Exception:
            pass
        return 0.0

    def _kill(self):
        p = self.proc; self.proc = None
        for q in (self.req_q, self.resp_q):
            try: q.close()
            except Exception: pass
        try:
            if p is not None and p.is_alive():
                p.terminate(); p.join(10)
                if p.is_alive():
                    p.kill(); p.join(5)
        except Exception:
            pass

    def _recycle(self):
        self._kill(); self._start(); self.recycles += 1

    def _monitor(self, sec):
        # 【执行端实锤的教训】旧版 infer() 全程握锁等结果:某曲一卡 180s,监控被锁死 180s,
        # 泄漏的子进程(~1GB/5s)不受 cap 约束地涨到 25GB→OOM。现在 infer 等待期不握锁,
        # 监控随时能进来【推理进行中也照样砍】超标子进程;在飞的那曲经 gen 变化发现、判失败(续跑重试)。
        while not self._stop.wait(sec):
            with self._lock:
                if self.proc is not None and self._rss_gb() >= self.rss_cap_gb:
                    print(f"  [mem] VN 子进程 RSS 超 {self.rss_cap_gb}GB → 回收重开"
                          f"(第 {self.recycles + 1} 次)", flush=True)
                    try:
                        self._recycle()
                    except Exception as ex:      # 重载失败也不能让监控线程死掉(死了=永不回收)
                        print(f"  [mem] VN 子进程重开失败({type(ex).__name__}: {str(ex)[:60]}),"
                              f"下曲 infer 时再试", flush=True)

    def infer(self, xml, composer):
        with self._lock:                 # 只在收发瞬间握锁;等待期【不握】,让监控能随时回收
            if self.proc is None or not self.proc.is_alive():
                self._start()
            gen0, resp_q = self.gen, self.resp_q
            try:
                self.req_q.put((xml, composer))
            except Exception:
                return None, None
        deadline = time.time() + self.infer_timeout
        while True:
            try:
                status, mid, csv = resp_q.get(timeout=1.0)     # 1s 心跳轮询,不长期占锁
                break
            except _queue.Empty:
                with self._lock:
                    if self.gen != gen0:         # 监控在推理中砍了超标子进程 → 本曲判失败,续跑重试
                        return None, None
                if time.time() >= deadline:      # 真卡死:自己动手杀重开
                    with self._lock:
                        if self.gen == gen0:
                            try: self._recycle()
                            except Exception: pass
                    return None, None
            except (EOFError, OSError, ValueError):   # 队列随子进程被杀而关闭/失效 → 同 gen 变化处理
                return None, None
        with self._lock:
            self.n_infer += 1
            if self.gen == gen0 and self._rss_gb() >= self.rss_cap_gb:   # 推理后也查一次,及时回收
                try: self._recycle()
                except Exception: pass
        return (mid, csv) if status == "ok" else (None, None)

    def close(self):
        try: self._stop.set()
        except Exception: pass
        with self._lock:
            try:
                if self.proc is not None and self.proc.is_alive():
                    self.req_q.put(None); self.proc.join(5)
            except Exception:
                pass
            self._kill()


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


def _slice_audio(audio, sr: int, t0: float, t1: float, out_path: str,
                 min_sec: float = 2.0) -> str | None:
    """从【已载入】的整曲音频切 [t0,t1] 秒(段级 utt)。返回路径或 None。
    【内存修复】旧版每段各自 sf.read 整曲 —— 一首 30 段的曲把整曲反复读 30 次,worker 峰值分配
    被顶高且 heap 不还 OS(棘轮)。现在 cpu_stage 读一次、把数组传进来。"""
    import soundfile as sf     # 拆函数时 import 曾漏在 _read_audio 里 → NameError(执行端实测),必须在此
    a, b = max(0, int(t0 * sr)), min(len(audio), int(t1 * sr))
    if b - a < int(min_sec * sr):      # 【实际长度】保底与守卫同标准(旧版 0.2s 是漏洞:截断残段能溜过)
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


def _cpu_init(sources_cfg, presets_cfg, out_audio_dir):
    _W.update(sources=sources_cfg, presets=presets_cfg, out=Path(out_audio_dir))


def cpu_stage(mid: dict) -> dict:
    """
    CPU 阶段(worker 进程,~5s):载谱 → tmap(仅 VN CSV)→ 渲染整曲 → 按段切 + 打标签。
    段级音频落盘;返回 rows 给主进程统一写标签/语料(单写者,免并发写冲突)。
    """
    import partitura
    pid = mid["pid"]; xml_path = mid["xml_path"]
    perf_mid = mid["perf_mid"]; csv_path = mid["csv_path"]
    out = _W["out"]
    res = {"pid": pid, "vn_ok": 0, "vn_fail": 0, "rows": [], "fail": None}
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
        if tmap is None:               # VN 是唯一路径:无 tmap = 该曲失败,续跑重试,不造假演奏
            res["vn_fail"] = 1
            res["fail"] = "vn_no_tmap"
            return res
        res["vn_ok"] = 1

        bounds = [m.start for m in ir.measures] + [ir.score_end]
        bounds_end = bounds[-1] if bounds else None
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
            # 【截断校验】渲染被超时杀/中途失败 → 音频比 tmap 预期短,后段会被夹成残段
            # (守卫只查"计划时长",管不住实际音频不够长)。差超容差 → 整曲判失败重跑,不出残段。
            expected_end = float(tmap(bounds_end)) if bounds_end is not None else 0.0
            if expected_end - (len(audio) / max(sr, 1)) > 2.0:
                res["fail"] = f"render_truncated:{len(audio)/max(sr,1):.0f}s<{expected_end:.0f}s"
                return res

        # 【分段必须用真 tmap】(执行端听音频抓出的 bug):旧版传 sec_per_whole=2.0(恒速 120bpm 假设)
        # 决定"切哪几小节",而音频切片用真 tmap —— 两个时间源打架:快曲被切成 0.2s 碎片、慢曲切出
        # 93s 超长段(max_sec=40 形同虚设)。segment_score 本就支持 tmap(nASAP 同款),传入即按
        # 【真实演奏秒】约束段长;到这里必有 VN 的真 tmap(没有就已判失败返回)。
        min_sec = float(os.environ.get("S5_SEG_MIN_SEC", "2.0"))   # 用户定:<2s 即退化样本
        # 段参数 = 论文/SPEC R-S8.1 规格:4≤小节数≤32 且 ≤40s(与文本标签、nASAP 同一规格)。
        # 旧值 2/16 是编写时偏离规格的私设(无依据、未报告);min=2 在快曲上正是 <2s 碎片的来源之一。
        for si, (sub_ir, (a, b)) in enumerate(
                segment_score(ir, min_measures=4, max_measures=32, max_sec=40.0, tmap=tmap)):
            utt_id = f"pdmxperf_{pid}_{si:03d}"
            score_off = bounds[a] if a < len(bounds) else bounds[-1]
            t_lo = float(tmap(bounds[a])); t_hi = float(tmap(bounds[min(b, len(bounds) - 1)]))
            if t_hi - t_lo < min_sec:      # 真实时长过短的段(极快小曲)是退化样本,直接不产出
                res["seg_too_short"] = res.get("seg_too_short", 0) + 1
                continue
            labels, _ = make_labels(sub_ir, "human", tmap=tmap, score_offset=score_off)
            if not labels.get("A2S"):
                continue
            seg_audio = None
            if audio is not None:
                seg_audio = _slice_audio(audio, sr, t_lo, t_hi, str(out / f"{utt_id}.opus"),
                                         min_sec=min_sec)
                if seg_audio is None:      # 应有音频却切不出 → 不产出残行(human 段无音频没意义)
                    res["seg_no_audio"] = res.get("seg_no_audio", 0) + 1
                    continue
            res["rows"].append({"utt_id": utt_id, "piece_id": pid, "kind": "human",
                                "measure_range": [a, b],                 # 与 S5 文本标签 schema 对齐
                                "audio_path": seg_audio,
                                **{k: labels.get(k) for k in ("A2S", "A2S_lite", "TAST")}, "AMT": None})
        (out / f"{pid}.done").touch()                       # 断点标记
        return res
    finally:
        _safe_unlink(perf_mid); _safe_unlink(whole_audio); _safe_unlink(csv_path)


def run(manifest, sources_cfg, presets_cfg, out_labels, out_corpus, out_audio_dir,
        limit=None, offset=0, n_cpu=0, vn_checkpoint=None):
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
    # 【续跑正确性】按"真有标签"判断做没做完,而不是 .done 标记。统计有多少 .done 是无标签空壳(旧 CLI
    # 遗留),这些会被重跑补回来 —— 明确打印出来,不让任何曲被静默跳过丢出训练集。
    labeled = _labeled_piece_ids(out_labels)
    stale = sum(1 for dm in out_audio_dir.glob("*.done") if dm.stem not in labeled)
    if labeled or stale:
        print(f"续跑:{len(labeled)} 曲已有标签(跳过);{stale} 个 .done 无对应标签(旧 CLI 遗留,将重跑补回)")
    label_fh = open(out_labels, "a", encoding="utf-8") if out_labels else None
    corpus_fh = open(out_corpus, "a", encoding="utf-8") if out_corpus else None
    rep = {"pieces": len(pieces), "vn_ok": 0, "vn_fail": 0,
           "utts": 0, "tast": 0, "failures": []}

    # VN 推理:默认放【可回收子进程】(VNSubprocess)—— 执行端实测证明 torch 模型常驻【主进程】会以
    # ~1GB/5s 泄漏主机 RSS(RTX50/WDDM 驱动侧,Python 收不回),而 CLI(子进程)模式主进程恒平。
    # 子进程按 RSS 水位 kill+重开:主进程始终平坦、模型跨曲复用(比 CLI 每曲重载快)。
    # ckpt 不传就【自动定位】;S5_VN_INPROCESS=1 强制退回旧的主进程内联(仅调试/沙盒);都没有才退 CLI。
    if not vn_checkpoint:
        vn_checkpoint = _find_vn_checkpoint()
    in_process = os.environ.get("S5_VN_INPROCESS", "0") == "1"
    rss_cap = float(os.environ.get("S5_VN_RSS_CAP_GB", "4.0"))     # 子进程 RSS 超此值即回收(重载~2s)
    infer_to = float(os.environ.get("S5_VN_INFER_TIMEOUT", "180"))  # 单曲推理超时→杀重开,本曲续跑重试
    mon_sec = float(os.environ.get("S5_VN_MONITOR_SEC", "3"))       # 监控线程盯 RSS 的间隔
    gc_every = int(os.environ.get("S5_GC_EVERY", "20"))
    vn_recycle_n = int(os.environ.get("S5_VN_RECYCLE", "100"))
    vn = None                         # VNSubprocess(默认)
    eng = {"m": None, "seen": 0}      # 主进程内联 VNEngine(S5_VN_INPROCESS=1 / 测试用)
    if vn_checkpoint and not in_process:
        try:
            vn = VNSubprocess(vn_checkpoint, out_dir=str(out_audio_dir / "_vn"),
                              rss_cap_gb=rss_cap, infer_timeout=infer_to, monitor_sec=mon_sec)
            harden_stdout()
            print(f"VN: 子进程模式(模型驻子进程,RSS>{rss_cap}GB 自动回收→主进程恒平不 OOM),ckpt={vn_checkpoint}")
        except Exception as e:
            print(f"VN: 子进程构造失败({type(e).__name__}: {str(e)[:80]}),退回 CLI(每曲重载)")
            vn = None
    elif vn_checkpoint and in_process:
        try:
            eng["m"] = VNEngine(vn_checkpoint, out_dir=str(out_audio_dir / "_vn"))
            harden_stdout()
            print(f"VN: 主进程内联(S5_VN_INPROCESS=1;注意会泄漏),ckpt={vn_checkpoint}")
        except Exception as e:
            print(f"VN: InferenceModel 构造失败({type(e).__name__}: {str(e)[:80]}),退回 CLI")
    else:
        print("VN: 未定位到标准权重,用 CLI(自动查权重,每曲重载)。")

    def _rebuild_vn():   # 仅内联模式的主进程累积兜底(子进程模式不用)
        import gc
        old = eng["m"]; eng["m"] = None
        try:
            if old is not None and hasattr(old, "model"):
                del old.model
        except Exception:
            pass
        del old
        gc.collect(); _free_gpu_and_gc(full=True)
        if vn_checkpoint:
            try:
                eng["m"] = VNEngine(vn_checkpoint, out_dir=str(out_audio_dir / "_vn"))
            except Exception as ex:
                print(f"  [mem] VN 引擎重建失败({type(ex).__name__}: {str(ex)[:60]}),暂退 CLI", flush=True)

    def gpu_stage(piece):
        # 主进程:只做 VN 推理(GPU,快)。子进程模式发路径给子进程;内联模式复用已载模型;都无则 CLI。
        pid, xml_path, composer = _piece_meta(piece, piece.get("_i", 0))
        if not xml_path:
            return None
        if vn is not None:
            mid, csv_path = vn.infer(xml_path, composer)     # 子进程推理,主进程恒平;超 cap 自动回收
            return {"pid": pid, "xml_path": xml_path, "perf_mid": mid, "csv_path": csv_path}
        e = eng["m"]
        if e is not None:
            mid, csv_path = e.infer(xml_path, composer)
            eng["seen"] += 1; n = eng["seen"]
            if gc_every and n % gc_every == 0:
                _free_gpu_and_gc(full=True)
            if vn_recycle_n and n % vn_recycle_n == 0:
                _rebuild_vn()
            return {"pid": pid, "xml_path": xml_path, "perf_mid": mid, "csv_path": csv_path}
        perf_mid = str(out_audio_dir / f"{pid}_perf.mid")
        csv_path = vn_infer(xml_path, composer, perf_mid)
        return {"pid": pid, "xml_path": xml_path, "perf_mid": perf_mid, "csv_path": csv_path}

    def done_fn(piece):
        pid, _, _ = _piece_meta(piece, piece.get("_i", 0))
        return pid in labeled     # 真有标签才算做完(不靠 .done,避免旧 CLI 遗留标记静默丢曲)

    def on_result(piece, res):
        rep["vn_ok"] += res["vn_ok"]; rep["vn_fail"] += res["vn_fail"]
        rep["seg_too_short"] = rep.get("seg_too_short", 0) + res.get("seg_too_short", 0)
        rep["seg_no_audio"] = rep.get("seg_no_audio", 0) + res.get("seg_no_audio", 0)
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
        # 【自诊断】每 25 曲打印:主进程(VN)RSS + 系统可用。主进程 RSS 涨=泄漏在主进程 VN;
        #   主进程 RSS 平、系统可用却掉=在 worker(回收应已封住)。把这几行贴回来就知道该拧哪。
        rep["_done"] = rep.get("_done", 0) + 1
        if rep["_done"] % 25 == 0:
            print(f"  [mem] 已完成 {rep['_done']} 曲 | 主进程(VN)RSS={_main_rss_gb():.1f}GB "
                  f"| 系统可用={available_gb():.1f}GB", flush=True)

    for idx, p in enumerate(pieces):
        p["_i"] = idx
    # 【音源亲和】按分配到的音源排序:同音源的曲连续渲染 → 页缓存热(大 FLAC 不必每曲重读)、
    # 同时段任务权重同质(准入并发稳定,不再大/小音源混排切碎预算)。hash 分配不变;续跑按标签,不受排序影响。
    def _piece_source(p):
        try:
            pid, _, _ = _piece_meta(p, p.get("_i", 0))
            sid, _ = assign_source_and_preset(pid, sources_cfg, presets_cfg)
            return sid
        except Exception:
            return "~"
    pieces.sort(key=lambda p: (_piece_source(p), p.get("piece_id", "")))

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
          f"- 留 {reserve}) | max_workers={n_cpu} | 回收 {recycle or '关'} 曲/进程 | "
          f"GPU 推理与 CPU 渲染重叠、按音源大小准入不 OOM")
    print(f"  权重 = 音源目录大小 + 每渲染开销 {overhead}GB(音频缓冲)。音源(GB): "
          + ", ".join(f"{k}={v:.1f}" for k, v in sorted(src_gb.items())))
    stats = pipeline_map(pieces, gpu_stage, cpu_stage, n_cpu=n_cpu, on_result=on_result,
                         done_fn=done_fn, key_fn=lambda p: p.get("piece_id"),
                         weight_fn=weight_fn, budget_gb=budget,
                         initializer=_cpu_init, max_tasks_per_child=recycle or None,
                         initargs=(sources_cfg, presets_cfg, str(out_audio_dir)))
    if vn is not None:
        rep["vn_recycles"] = vn.recycles         # 子进程被回收几次(RSS 超 cap 的次数)
        vn.close()
    if label_fh:
        label_fh.close()
    if corpus_fh:
        corpus_fh.close()
    print(f"\nDONE: vn_ok={rep['vn_ok']} vn_fail={rep['vn_fail']} "
          f"skipped={stats['done_skipped']} dropped={stats['dropped']} "
          f"utts={rep['utts']} TAST={rep['tast']} cpu_fail={stats['failed']} "
          f"过短段弃={rep.get('seg_too_short', 0)} 无音频段弃={rep.get('seg_no_audio', 0)}"
          + (f" vn_子进程回收={rep['vn_recycles']}次" if vn is not None else ""))
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
    ap.add_argument("--workers", type=int, default=0, help="CPU 渲染并发;0=按内存自动定")
    ap.add_argument("--vn-checkpoint", default="",
                    help="通常【不用传】——脚本自动定位 virtuoso 标准权重(GUIDE §1)。"
                         "仅当你的 .pt 在非标准位置才指定。")
    args = ap.parse_args()
    sources_cfg = yaml.safe_load(open(args.sources, encoding="utf-8"))
    presets_cfg = yaml.safe_load(open(args.presets, encoding="utf-8"))
    run(args.manifest, sources_cfg, presets_cfg, args.out_labels, args.out_corpus,
        args.out_audio_dir, offset=args.offset,
        limit=args.limit or None, n_cpu=args.workers,
        vn_checkpoint=(args.vn_checkpoint or None))


if __name__ == "__main__":
    main()
