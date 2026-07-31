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
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rubato.platform import harden_stdout
from rubato.data.assemble import assemble, partition_by_split
harden_stdout()   # 执行端 P8 实测:第 155 行打 '⚠' 在 GBK 控制台崩;此前全库硬化时漏了本脚本

REPO_ROOT = Path(__file__).resolve().parent.parent
ROOT = Path(r"D:\vscode_projects\ee_download")
WORK = ROOT / "work"
DEFAULT_TRAIN_CONFIG = REPO_ROOT / "configs" / "train.yaml"
DEFAULT_VOCAB_SPEC = REPO_ROOT / "configs" / "vocab_spec.json"


def configure_cuda_allocator(train_spec: dict, environ=None,
                             loaded_modules=None) -> str:
    """Install the production CUDA allocator policy before importing torch.

    Variable-duration batches repeatedly request nearby-but-different allocation
    sizes.  PyTorch's expandable segments are designed for that pattern and
    avoid accumulating unusable slivers.  An operator-provided environment value
    wins, but a late configuration is rejected instead of being logged as if it
    had taken effect.
    """
    environ = os.environ if environ is None else environ
    loaded_modules = sys.modules if loaded_modules is None else loaded_modules
    requested = str((train_spec.get("memory") or {}).get(
        "allocator_conf", "expandable_segments:True")).strip()
    if not requested:
        raise ValueError("memory.allocator_conf 不能为空")
    existing = environ.get("PYTORCH_ALLOC_CONF")
    legacy = environ.get("PYTORCH_CUDA_ALLOC_CONF")
    if existing and legacy and str(existing) != str(legacy):
        raise RuntimeError(
            "PYTORCH_ALLOC_CONF 与旧别名 PYTORCH_CUDA_ALLOC_CONF 冲突；"
            "拒绝猜测 allocator 策略")
    if existing:
        return str(existing)
    if legacy:
        # PyTorch still accepts the old alias. Mirror it into the canonical
        # variable so the config echo states the allocator that actually wins.
        environ["PYTORCH_ALLOC_CONF"] = str(legacy)
        return str(legacy)
    if "torch" in loaded_modules:
        raise RuntimeError(
            "PYTORCH_ALLOC_CONF 必须在 import torch/CUDA 初始化前设置；"
            "当前入口配置过晚，拒绝静默失效")
    environ["PYTORCH_ALLOC_CONF"] = requested
    return requested

# labels.jsonl 来源(与 s5/s5_vn/s7/gen_amt 的输出对齐)。
#   pdmx_perf(s5_vn_render):表现性音频 + TAST,行内带 audio_path。← 有它就优先,含 TAST。
#   pdmx_a2s(s5 文本):仅 A2S/A2S_lite 文本(TAST=null),需配 S4 直排音频。
SOURCES = [
    {"path": str(WORK / "pdmx_perf_labels.jsonl"), "kind": "pdmx", "domain": "synth",
     "manifests": [str(WORK / "manifest_pieces.jsonl"),
                   str(WORK / "manifest_giant.jsonl")],
     "quarantine_unmapped": True},
    {"path": str(WORK / "pdmx_a2s_labels.jsonl"),  "kind": "pdmx", "domain": "synth",
     "manifests": [str(WORK / "manifest_pieces.jsonl"),
                   str(WORK / "manifest_giant.jsonl")],
     "quarantine_unmapped": True},
    {"path": str(WORK / "nasap_labels.jsonl"),     "kind": "nasap",   "domain": "real"},
    # 【必须用切窗版】整曲版 maestro_amt_labels.jsonl 是几分钟长的不可训行(P8 实测只装出
    # 1,276 条、AMT 全灭);切窗版 23,657 条 12-25s 窗,行带 win=[t0,t1] + split(来自 MAESTRO CSV)。
    {"path": str(WORK / "maestro_amt_windows.jsonl"), "kind": "maestro", "domain": "real"},
]
# 偏移窗(C2 → 二轮数据方案 D53):同录音错开的多组 AMT 窗,按 glob 全量挂载
# (o5/o10/o15…,存在即收编)。只含 train 行(生成器强制),utt_id 带 _oN 后缀不撞名;
# 评测池(val/test)因此不变。
for _of in sorted(WORK.glob("maestro_amt_windows_o*.jsonl")):
    SOURCES.append({"path": str(_of), "kind": "maestro", "domain": "real"})
# C3 音色副本(D50):生成器只写 .staging 名;把 staging 改成本名 = 进池武装,
# 只按 EXECUTOR.md 的书面指令执行(单变量纪律)。行全 train、utt_id 带 _s2。
_S2 = WORK / "pdmx_a2s_labels_s2.jsonl"
if _S2.exists():
    SOURCES.append({"path": str(_S2), "kind": "pdmx", "domain": "synth"})
# pdmxperf 二音色副本(ROUND2_DATA,s5_vn_render --second-timbre):同 staging/武装纪律。
# 行内带 audio_path(pdmx_audio_s2 下),utt_id 尾缀 _s2,仅一轮成功曲 × train。
_PERF_S2 = WORK / "pdmx_perf_labels_s2.jsonl"
if _PERF_S2.exists():
    SOURCES.append({"path": str(_PERF_S2), "kind": "pdmx", "domain": "synth"})
# r3 去重回收波次(D60/D68,官方 VN 批 + s5 消费):同 staging/武装纪律,全 train
# (清单生成即 train-only),行内带 audio_path(pdmx_audio_r3_native 下,flac)。
_PERF_R3 = WORK / "pdmx_perf_labels_r3_native.jsonl"
if _PERF_R3.exists():
    SOURCES.append({
        "path": str(_PERF_R3), "kind": "pdmx", "domain": "synth",
        "manifest": str(WORK / "manifest_pieces_round3_restore_train_vn_ok.jsonl"),
    })

# ---------------------------------------------------------------- 音频时长缓存
# 【D71,用户点名"竞赛早 TLE 了"】进程内 dict 之外加【持久化】层:75 万行逐个
# sf.info 开文件 ≈ 半小时/次装配;持久层以 (size, mtime_ns) 做失效键,命中只花一次
# os.stat(~0.1ms),重复装配从 IO 车祸变秒级读账。缓存是纯优化:任何 IO 失败静默
# 降级为直接探测,绝不让缓存问题变装配问题。追加写(jsonl,后行覆盖前行),中断安全。
_DUR_CACHE: dict[str, float] = {}
_DUR_DB: dict[str, tuple[int, int, float]] = {}      # path -> (size, mtime_ns, dur)
_DUR_DB_LOADED = False
_DUR_DB_FH = None
_DUR_DB_PENDING = 0


def _dur_db_path() -> Path:
    import os as _os
    return Path(_os.environ.get("RUBATO_DUR_CACHE") or (WORK / "audio_dur_cache.jsonl"))


def _dur_db_close() -> None:
    """刷新并关闭持久缓存句柄；Windows 下否则会锁住缓存文件/临时目录。"""
    global _DUR_DB_FH, _DUR_DB_PENDING
    fh, _DUR_DB_FH = _DUR_DB_FH, None
    _DUR_DB_PENDING = 0
    if fh is not None:
        try:
            fh.flush()
        finally:
            fh.close()


import atexit as _atexit
_atexit.register(_dur_db_close)


def _dur_db_load() -> None:
    global _DUR_DB_LOADED
    if _DUR_DB_LOADED:
        return
    _DUR_DB_LOADED = True
    p = _dur_db_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    path, size, mt, d = json.loads(line)
                    _DUR_DB[path] = (int(size), int(mt), float(d))
                except Exception:
                    continue                      # 坏行跳过(中断写残行属预期)
        print(f"  [INFO] 时长缓存加载 {len(_DUR_DB)} 条({p.name})")
    except OSError:
        pass                                      # 无缓存文件 = 首次,静默


def _dur_db_append(path: str, size: int, mt: int, d: float) -> None:
    global _DUR_DB_FH, _DUR_DB_PENDING
    try:
        if _DUR_DB_FH is None:
            _dur_db_path().parent.mkdir(parents=True, exist_ok=True)
            _DUR_DB_FH = open(_dur_db_path(), "a", encoding="utf-8")
        _DUR_DB_FH.write(json.dumps([path, size, mt, d]) + "\n")
        _DUR_DB_PENDING += 1
        if _DUR_DB_PENDING >= 500:                # 批量落盘:中断最多丢 500 条探测
            _DUR_DB_FH.flush()
            _DUR_DB_PENDING = 0
    except OSError:
        pass                                      # 缓存写失败不影响装配


def _flac_dur(path: str) -> float | None:
    if path in _DUR_CACHE:
        return _DUR_CACHE[path]
    _dur_db_load()
    import os as _os
    try:
        st = _os.stat(path)
    except OSError:
        return None                               # 缺文件不缓存(可能后补)
    rec = _DUR_DB.get(path)
    if rec and rec[0] == st.st_size and rec[1] == st.st_mtime_ns:
        _DUR_CACHE[path] = rec[2]
        return rec[2]
    try:
        import soundfile as sf
        info = sf.info(path)
        d = info.frames / info.samplerate
    except Exception:
        return None
    _DUR_CACHE[path] = d
    _DUR_DB[path] = (st.st_size, st.st_mtime_ns, d)
    _dur_db_append(path, st.st_size, st.st_mtime_ns, d)
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


def _load_pdmx_eval_blacklist() -> set[str]:
    """Build the exact external-evaluation work blacklist once per assembly."""
    from scripts.s3_filter_pdmx import get_nasap_test_works, get_beyer_work_keys
    from rubato.data.pdmx import build_blacklist
    blacklist = build_blacklist(
        get_nasap_test_works(WORK),
        get_beyer_work_keys(
            ROOT / "asap-dataset" / "asap-dataset" / "asap_annotations.json"))
    if not blacklist:
        raise RuntimeError("PDMX evaluation blacklist is empty")
    return blacklist


def _load_pdmx_content_quarantine() -> set[str]:
    """Load score-level exclusions proven unsafe by strict content audit."""
    path = REPO_ROOT / "configs" / "pdmx_content_quarantine.jsonl"
    if not path.exists():
        return set()
    quarantined = set()
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                piece_id = str(row["piece_id"])
                reason = str(row["reason"])
            except Exception as e:
                raise ValueError(
                    f"PDMX 内容隔离清单第 {line_no} 行无效:"
                    f"{type(e).__name__}: {e}") from e
            if not piece_id or not reason:
                raise ValueError(
                    f"PDMX 内容隔离清单第 {line_no} 行缺 piece_id/reason")
            if piece_id in quarantined:
                raise ValueError(
                    f"PDMX 内容隔离清单 piece_id 重复:{piece_id}")
            quarantined.add(piece_id)
    return quarantined


def _pdmx_row_fn(manifest_paths=None, quarantine_unmapped: bool = False,
                 blacklist: set[str] | None = None):
    """PDMX 行注入:manifest 的 split/work_key(标签行不带,P8 实测全体默认 train、val/test≈0);
    命中 nASAP-test/Beyer 黑名单的工作【过滤出训练】(问题#14 的装配层强制,P4 曾以空名单跑过)；
    以及审计确认的音频截断 utt(隔离清单在 configs/pdmx_duration_quarantine.jsonl)。"""
    import json as _json
    m = {}
    if manifest_paths is None:
        manifest_paths = [WORK / "manifest_pieces.jsonl"]
    elif isinstance(manifest_paths, (str, Path)):
        manifest_paths = [manifest_paths]
    manifest_paths = [Path(x) for x in manifest_paths]
    for mani in manifest_paths:
        if not mani.exists():
            raise FileNotFoundError(
                f"PDMX manifest 缺失：{mani}。不能把全部样本静默当 train。")
        with open(mani, "r", encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = _json.loads(line)
                except Exception as e:
                    raise ValueError(
                        f"PDMX manifest {mani.name} 第 {n} 行 JSON 损坏:"
                        f"{type(e).__name__}: {e}") from e
                piece_id = r.get("piece_id")
                if not piece_id:
                    raise ValueError(f"PDMX manifest {mani.name} 第 {n} 行缺 piece_id")
                split = r.get("split")
                work_key = r.get("work_key")
                if split not in {"train", "val", "test"}:
                    raise ValueError(
                        f"PDMX manifest {mani.name} 第 {n} 行 split 非法: {split!r}")
                if not isinstance(work_key, str) or not work_key.strip():
                    raise ValueError(
                        f"PDMX manifest {mani.name} 第 {n} 行 work_key 缺失")
                value = (split, work_key)
                if piece_id in m and m[piece_id] != value:
                    raise ValueError(
                        f"PDMX manifest piece_id 重复且元数据冲突:{piece_id} "
                        f"{m[piece_id]} vs {value}")
                m[piece_id] = value
    if not m:
        raise RuntimeError(f"PDMX manifest 为空或没有有效 piece_id：{mani}")
    try:
        bl = set(blacklist) if blacklist is not None else _load_pdmx_eval_blacklist()
    except Exception as e:
        raise RuntimeError(
            f"PDMX 泄漏黑名单构建失败，拒绝在不过滤的情况下训练："
            f"{type(e).__name__}: {e}") from e

    duration_quarantine = set()
    qpath = Path(__file__).resolve().parent.parent / "configs" / "pdmx_duration_quarantine.jsonl"
    if qpath.exists():
        with open(qpath, "r", encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    uid = str(_json.loads(line)["utt_id"])
                except Exception as e:
                    raise ValueError(
                        f"时长隔离清单第 {n} 行无效，拒绝把可能截断样本放回训练:"
                        f"{type(e).__name__}: {e}") from e
                duration_quarantine.add(uid)
        print(f"  [INFO] PDMX duration quarantine utt_ids: {len(duration_quarantine)}")
    content_quarantine = _load_pdmx_content_quarantine()
    if content_quarantine:
        print(f"  [INFO] PDMX content quarantine piece_ids: "
              f"{len(content_quarantine)}")

    audit = {"unmapped_piece_ids": set(),
             "manifests": [str(x) for x in manifest_paths]}

    def row_fn(row):
        uid = str(row.get("utt_id") or "")
        if uid in duration_quarantine:
            return None                # 已证实音频被截断:计 filtered,不进入训练/评测
        piece_id = row.get("piece_id")
        if not piece_id:
            raise ValueError(f"PDMX 标签 {uid or '<unknown>'} 缺 piece_id，无法注入 split/去泄漏")
        info = m.get(piece_id)
        if info is None:
            if quarantine_unmapped:
                audit["unmapped_piece_ids"].add(str(piece_id))
                return None
            raise ValueError(
                f"PDMX 标签 {uid or '<unknown>'} 的 piece_id={piece_id} 不在 manifest；"
                "拒绝按默认 train 静默放行")
        split, wk = info
        if split == "train" and str(piece_id) in content_quarantine:
            return None                # 严格内容审计确认泄漏/不可签名，只隔离 train
        if split == "train" and wk in bl:
            return None                # 外部评测作品只禁止进入 train
        if split and not row.get("split"):
            row["split"] = split
        return row
    row_fn.audit = audit
    return row_fn


def attach_pdmx_row_fns(sources: list[dict]) -> None:
    """按每个 PDMX 波次自己的 manifest 注入 split/work_key/泄漏过滤。"""
    cache = {}
    blacklist = None
    for src in sources:
        if src["kind"] != "pdmx":
            continue
        if blacklist is None:
            blacklist = _load_pdmx_eval_blacklist()
        manifests = tuple(src.get("manifests") or
                          [src.get("manifest") or (WORK / "manifest_pieces.jsonl")])
        quarantine = bool(src.get("quarantine_unmapped", False))
        # 允许隔离 unmapped 的混合历史文件必须各自留 audit，不能共享集合后误报。
        key = (tuple(map(str, manifests)), quarantine,
               str(src["path"]) if quarantine else "")
        if key not in cache:
            cache[key] = _pdmx_row_fn(
                manifests, quarantine_unmapped=quarantine,
                blacklist=blacklist)
        src["row_fn"] = cache[key]


def pdmx_source_manifest_paths(src: dict) -> list[Path]:
    """Resolve the manifest set used by one PDMX label source."""
    manifests = src.get("manifests") or [
        src.get("manifest") or (WORK / "manifest_pieces.jsonl")]
    return [Path(raw).resolve() for raw in manifests]


def active_pdmx_manifest_paths(sources: list[dict]) -> list[Path]:
    """Return the exact manifest set that supplies split metadata this run."""
    paths: dict[str, Path] = {}
    for src in sources:
        if src.get("kind") != "pdmx":
            continue
        for p in pdmx_source_manifest_paths(src):
            paths[str(p).lower()] = p
    return [paths[k] for k in sorted(paths)]


def active_pdmx_label_paths(sources: list[dict]) -> list[Path]:
    """Return the exact PDMX label files armed for this assembly."""
    paths: dict[str, Path] = {}
    for src in sources:
        if src.get("kind") != "pdmx":
            continue
        p = Path(src["path"]).resolve()
        paths[str(p).lower()] = p
    return [paths[k] for k in sorted(paths)]


def active_pdmx_filter_paths() -> list[Path]:
    """Files whose exact bytes alter the certified PDMX train scope."""
    candidates = [
        REPO_ROOT / "configs" / "pdmx_duration_quarantine.jsonl",
        REPO_ROOT / "configs" / "pdmx_content_quarantine.jsonl",
    ]
    return [path.resolve() for path in candidates if path.is_file()]


def _file_fingerprint(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    rows = 0
    with path.open("rb") as handle:
        for line in handle:
            digest.update(line)
            if line.strip():
                rows += 1
    return digest.hexdigest(), rows


def verify_pdmx_leakage_certificate(
        manifest_paths: list[str | Path],
        certificate_path: str | Path = ROOT / "reports" /
        "pdmx_leakage_certificate.json",
        label_sources: list[dict] | None = None,
        filter_paths: list[str | Path] | None = None) -> dict:
    """Verify that the audit covers the exact manifests and armed labels."""
    cp = Path(certificate_path)
    if not cp.is_file():
        raise FileNotFoundError(
            f"PDMX 内容泄漏证书不存在:{cp}；先跑 scripts/certify_pdmx_leakage.py")
    try:
        cert = json.loads(cp.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(
            f"PDMX 内容泄漏证书损坏:{cp} ({type(e).__name__}: {e})") from e
    if cert.get("status") != "pass":
        raise ValueError(
            f"PDMX 内容泄漏证书未通过:status={cert.get('status')!r} "
            f"reason={cert.get('reason')!r}")
    if int(cert.get("leaked_count", -1)) != 0:
        raise ValueError(
            f"PDMX 内容泄漏证书仍含 {cert.get('leaked_count')} 个泄漏 piece")
    records = cert.get("manifests")
    if not isinstance(records, list) or not records:
        raise ValueError("PDMX 内容泄漏证书缺 manifests")
    certified = {
        str(Path(r["path"]).resolve()).lower(): r
        for r in records if isinstance(r, dict) and r.get("path")
    }
    actual = {
        str(Path(p).resolve()).lower(): Path(p).resolve()
        for p in manifest_paths
    }
    if set(certified) != set(actual):
        missing = sorted(set(actual) - set(certified))
        stale = sorted(set(certified) - set(actual))
        raise ValueError(
            f"PDMX 内容泄漏证书清单集合不匹配:未认证={missing} 多余={stale}")
    for key, path in actual.items():
        if not path.is_file():
            raise FileNotFoundError(f"PDMX manifest 不存在:{path}")
        sha, rows = _file_fingerprint(path)
        rec = certified[key]
        if sha != rec.get("sha256") or rows != int(rec.get("rows", -1)):
            raise ValueError(
                f"PDMX 内容泄漏证书过期:{path} "
                f"sha={sha[:12]}/{str(rec.get('sha256'))[:12]} "
                f"rows={rows}/{rec.get('rows')}")
    if label_sources is not None:
        expected_sources = {}
        for src in label_sources:
            if src.get("kind") != "pdmx":
                continue
            path = Path(src["path"]).resolve()
            key = str(path).lower()
            if key in expected_sources:
                raise ValueError(f"重复 PDMX labels source:{path}")
            expected_sources[key] = {
                "path": path,
                "manifests": [
                    str(p).lower() for p in pdmx_source_manifest_paths(src)],
                "quarantine_unmapped": bool(
                    src.get("quarantine_unmapped", False)),
            }
        label_records = cert.get("label_sources")
        if not isinstance(label_records, list) or not label_records:
            raise ValueError("PDMX 内容泄漏证书缺 label_sources")
        certified_sources = {}
        for rec in label_records:
            if not isinstance(rec, dict) or not rec.get("path"):
                continue
            key = str(Path(rec["path"]).resolve()).lower()
            certified_sources[key] = rec
        if set(certified_sources) != set(expected_sources):
            missing = sorted(set(expected_sources) - set(certified_sources))
            stale = sorted(set(certified_sources) - set(expected_sources))
            raise ValueError(
                f"PDMX 内容泄漏证书 labels 集合不匹配:"
                f"未认证={missing} 多余={stale}")
        for key, expected in expected_sources.items():
            path = expected["path"]
            if not path.is_file():
                raise FileNotFoundError(f"PDMX labels 不存在:{path}")
            sha, rows = _file_fingerprint(path)
            rec = certified_sources[key]
            certified_manifests = [
                str(Path(p).resolve()).lower()
                for p in rec.get("manifests", [])]
            if (sha != rec.get("sha256")
                    or rows != int(rec.get("rows", -1))
                    or certified_manifests != expected["manifests"]
                    or bool(rec.get("quarantine_unmapped", False))
                    != expected["quarantine_unmapped"]):
                raise ValueError(
                    f"PDMX 内容泄漏证书 labels/source 过期:{path}")
    if filter_paths is not None:
        expected_filters = {
            str(Path(path).resolve()).lower(): Path(path).resolve()
            for path in filter_paths
        }
        records = cert.get("filter_files")
        if not isinstance(records, list):
            raise ValueError("PDMX 内容泄漏证书缺 filter_files")
        certified_filters = {
            str(Path(rec["path"]).resolve()).lower(): rec
            for rec in records
            if isinstance(rec, dict) and rec.get("path")
        }
        if set(certified_filters) != set(expected_filters):
            raise ValueError("PDMX 内容泄漏证书过滤清单集合不匹配")
        for key, path in expected_filters.items():
            sha, rows = _file_fingerprint(path)
            rec = certified_filters[key]
            if sha != rec.get("sha256") \
                    or rows != int(rec.get("rows", -1)):
                raise ValueError(
                    f"PDMX 内容泄漏证书过滤清单过期:{path}")
    if int(cert.get("target_parse_failed", -1)) != 0 \
            or int(cert.get("reference_parse_failed", -1)) != 0:
        raise ValueError("PDMX 内容泄漏证书存在未解析目标/参考，不能 fail open")
    return cert


def validate_assembly_for_training(stats: dict) -> None:
    """训练装配硬门：任何非空数据源零保留都必须中止，不能只打印警告后继续。"""
    bad = []
    detail = stats.get("per_file") or stats.get("per_source", {})
    for source, s in detail.items():
        if int(s.get("rows", 0)) > 0 and int(s.get("kept", 0)) == 0:
            bad.append(
                f"{source}(kind={s.get('kind', source)}, rows={s.get('rows')}, "
                f"no_audio={s.get('no_audio')}, "
                f"no_dialect={s.get('no_dialect')}, filtered={s.get('filtered')})")
    if bad:
        raise RuntimeError(
            "训练装配失败：以下非空数据源 kept=0，拒绝拿残缺数据集训练："
            + "; ".join(bad))


def validate_cli_args(args) -> None:
    """训练启动前验证所有会进入除法、取模、采样或预算的数值参数。"""
    positive = {
        "max_batch_sec": args.max_batch_sec,
        "clip_norm": args.clip_norm,
        "eval_max": args.eval_max,
        "eval_every": args.eval_every,
        "smoke_steps": args.smoke_steps,
        "probe_n": args.probe_n,
        "abtest_n": args.abtest_n,
        "max_steps": args.max_steps,
    }
    bad = [f"{k}={v}" for k, v in positive.items() if v is None or float(v) <= 0]
    if args.smoke < 0 or args.prefetch < 0 or args.eval_decode_every < 0:
        bad.extend([
            f"smoke={args.smoke}" if args.smoke < 0 else "",
            f"prefetch={args.prefetch}" if args.prefetch < 0 else "",
            (f"eval_decode_every={args.eval_decode_every}"
             if args.eval_decode_every < 0 else ""),
        ])
    if args.pitch_loss_weight <= 0:
        bad.append(f"pitch_loss_weight={args.pitch_loss_weight}")
    if args.amt_aux_weight < 0:
        bad.append(f"amt_aux_weight={args.amt_aux_weight}")
    if args.amt_align_weight < 0:
        bad.append(f"amt_align_weight={args.amt_align_weight}")
    if args.amt_align_margin < 0:
        bad.append(f"amt_align_margin={args.amt_align_margin}")
    if args.lr_enc is not None and args.lr_enc <= 0:
        bad.append(f"lr_enc={args.lr_enc}")
    if args.lr_dec is not None and args.lr_dec <= 0:
        bad.append(f"lr_dec={args.lr_dec}")
    bad = [x for x in bad if x]
    if bad:
        raise ValueError("非法 CLI 数值参数:" + ", ".join(bad))


def load_train_config(path: str | Path) -> dict:
    """Load and validate the runtime training configuration.

    This file used to be documentation-only while the production entrypoint
    silently hard-coded a second set of values.  Keep one source of truth:
    explicit CLI flags override this mapping, everything else comes from it.
    """
    import yaml
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"训练配置不存在:{path}")
    try:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(
            f"训练配置无法解析:{path} ({type(e).__name__}: {e})") from e
    if not isinstance(cfg, dict):
        raise ValueError(f"训练配置根节点必须是 mapping:{path}")
    allowed_top = {
        "tokenizer", "data", "optim", "max_steps", "max_epochs",
        "precision", "loss", "specaugment", "eval", "ckpt", "memory", "seed",
    }
    unknown_top = set(cfg) - allowed_top
    if unknown_top:
        raise ValueError(
            f"训练配置含未消费的顶层键:{sorted(unknown_top)}；"
            "拒绝把拼错/写了未调用的配置静默忽略")
    for section in ("tokenizer", "data", "optim", "loss", "eval", "ckpt", "memory"):
        if not isinstance(cfg.get(section), dict):
            raise ValueError(f"训练配置缺 mapping 节:{section}")
    allowed_sections = {
        "tokenizer": {"vocab", "spm_alpha"},
        "data": {"mix", "max_duration_per_batch_sec"},
        "optim": {
            "name", "lr_decoder", "lr_encoder", "lr_encoder_from_scratch",
            "betas", "wd", "warmup_steps", "schedule", "min_lr_ratio",
            "clip_norm", "grad_accum_to_audio_sec",
        },
        "loss": {"len_weight_pow", "sem_label_smooth", "ts_smooth",
                 "pitch_weight", "acoustic_aux"},
        "eval": {"every_steps", "decode_every_steps",
                 "max_samples_per_source"},
        "ckpt": {"keep", "save_every_steps", "select_by"},
        "memory": {
            "allocator_conf", "check_every_steps", "min_free_mb",
            "min_reclaimable_mb", "cleanup_after_eval",
        },
    }
    for section, allowed in allowed_sections.items():
        unknown = set(cfg[section]) - allowed
        if unknown:
            raise ValueError(
                f"训练配置 {section} 含未消费键:{sorted(unknown)}")
    if str(cfg["optim"].get("name", "")).lower() != "adamw":
        raise ValueError("生产优化器只实现 adamw")
    if str(cfg["optim"].get("schedule", "")).lower() != "cosine":
        raise ValueError("生产 scheduler 只实现 cosine")
    if float(cfg["loss"].get("len_weight_pow", 0.5)) != 0.5:
        raise ValueError(
            "生产 loss 固定使用 1/sqrt(T)，len_weight_pow 必须为 0.5")
    acoustic = cfg["loss"].get("acoustic_aux") or {}
    if not isinstance(acoustic, dict):
        raise ValueError("loss.acoustic_aux 必须是 mapping")
    allowed_acoustic = {
        "weight", "alignment_weight", "alignment_margin",
        "onset_radius", "hidden_dim", "dropout",
    }
    unknown_acoustic = set(acoustic) - allowed_acoustic
    if unknown_acoustic:
        raise ValueError(
            f"训练配置 loss.acoustic_aux 含未消费键:"
            f"{sorted(unknown_acoustic)}")
    for key in ("weight", "alignment_weight", "alignment_margin",
                "onset_radius", "hidden_dim", "dropout"):
        value = float(acoustic.get(key, 0.0))
        if value < 0:
            raise ValueError(f"loss.acoustic_aux.{key} 必须非负")
    if float(acoustic.get("dropout", 0.0)) >= 1:
        raise ValueError("loss.acoustic_aux.dropout 必须 <1")
    if cfg["ckpt"].get("select_by") != "text_ned_proxy":
        raise ValueError(
            "当前训练期 best checkpoint 只支持 text_ned_proxy")
    if str(cfg.get("precision", "")).lower() not in {"bf16", "fp32"}:
        raise ValueError("precision 只支持 bf16/fp32")
    mix = cfg["data"].get("mix")
    expected_dialects = {"A2S", "A2S_lite", "TAST", "AMT"}
    if not isinstance(mix, dict) or set(mix) != expected_dialects:
        raise ValueError(
            f"data.mix 必须且只能含 {sorted(expected_dialects)}")
    if any(float(v) < 0 for v in mix.values()) or abs(
            sum(float(v) for v in mix.values()) - 1.0) > 1e-6:
        raise ValueError("data.mix 权重必须非负且总和为 1")
    positives = {
        "tokenizer.vocab": cfg["tokenizer"].get("vocab"),
        "data.max_duration_per_batch_sec":
            cfg["data"].get("max_duration_per_batch_sec"),
        "optim.lr_decoder": cfg["optim"].get("lr_decoder"),
        "optim.lr_encoder": cfg["optim"].get("lr_encoder"),
        "optim.grad_accum_to_audio_sec":
            cfg["optim"].get("grad_accum_to_audio_sec"),
        "max_steps": cfg.get("max_steps"),
        "max_epochs": cfg.get("max_epochs"),
        "eval.every_steps": cfg["eval"].get("every_steps"),
        "eval.max_samples_per_source":
            cfg["eval"].get("max_samples_per_source"),
        "ckpt.keep": cfg["ckpt"].get("keep"),
        "ckpt.save_every_steps": cfg["ckpt"].get("save_every_steps"),
        "memory.check_every_steps": cfg["memory"].get("check_every_steps"),
        "memory.min_free_mb": cfg["memory"].get("min_free_mb"),
        "memory.min_reclaimable_mb":
            cfg["memory"].get("min_reclaimable_mb"),
    }
    bad = [f"{k}={v}" for k, v in positives.items()
           if v is None or float(v) <= 0]
    if bad:
        raise ValueError("训练配置正数项非法:" + ", ".join(bad))
    if cfg.get("specaugment") not in (False, None):
        raise ValueError(
            "specaugment=true 尚无生产实现；拒绝把写了但未调用的配置当作已生效")
    allocator_conf = str(cfg["memory"].get("allocator_conf", "")).strip()
    if not allocator_conf:
        raise ValueError("memory.allocator_conf 不能为空")
    if not isinstance(cfg["memory"].get("cleanup_after_eval"), bool):
        raise ValueError("memory.cleanup_after_eval 必须是 bool")
    return cfg


def apply_train_config_defaults(args, cfg: dict):
    """Resolve config-controlled CLI values in place; explicit CLI wins."""
    data = cfg["data"]
    optim = cfg["optim"]
    ev = cfg.get("eval") or {}
    loss = cfg["loss"]
    if args.max_batch_sec is None:
        args.max_batch_sec = (
            120.0 if args.smoke
            else float(data.get("max_duration_per_batch_sec", 60.0)))
    if args.clip_norm is None:
        args.clip_norm = float(optim.get("clip_norm", 1.0))
    if args.eval_max is None:
        args.eval_max = int(ev.get("max_samples_per_source", 48))
    if args.eval_every is None:
        args.eval_every = int(
            ev.get("every_steps", cfg.get("eval_every_steps", 1000)))
    if args.eval_decode_every is None:
        args.eval_decode_every = int(ev.get("decode_every_steps", 0))
    if args.pitch_loss_weight is None:
        args.pitch_loss_weight = float(loss.get("pitch_weight", 1.0))
    acoustic = dict(loss.get("acoustic_aux") or {})
    if args.amt_aux_weight is None:
        args.amt_aux_weight = float(acoustic.get("weight", 0.0))
    if args.amt_align_weight is None:
        args.amt_align_weight = float(acoustic.get("alignment_weight", 0.25))
    if args.amt_align_margin is None:
        args.amt_align_margin = float(acoustic.get("alignment_margin", 0.10))
    if args.max_steps is None:
        args.max_steps = int(cfg.get("max_steps") or 100000)
    if args.lr_enc is None:
        if args.from_scratch:
            # 热启动 encoder 的低学习率不能静默套到随机初始化模型上。若没有单列
            # from-scratch 值，就与 decoder 同速；显式 CLI 仍优先。
            args.lr_enc = float(
                optim.get("lr_encoder_from_scratch",
                          optim.get("lr_decoder", 5e-4)))
        else:
            args.lr_enc = float(optim.get("lr_encoder", 1e-4))
    if args.lr_dec is None:
        args.lr_dec = float(optim.get("lr_decoder", 5e-4))
    return args


def select_training_partitions(part: dict) -> tuple[list, list, list, list, list]:
    """返回 train/nASAP-val/MAESTRO-val/nASAP-test/MAESTRO-test。

    test 只供 ``scripts/eval_final.py`` 最终一次评测；训练期 checkpoint 选择、早停、
    探针都只能看 val。旧入口把 val+test 合并，造成不可逆的 test 泄漏。
    """
    train = list(part.get("train", []))
    val = list(part.get("val", []))
    test = list(part.get("test", []))
    nasap_val = [u for u in val if u.get("kind") == "nasap"]
    maestro_val = [u for u in val if u.get("kind") == "maestro"]
    nasap_test = [u for u in test if u.get("kind") == "nasap"]
    maestro_test = [u for u in test if u.get("kind") == "maestro"]
    return train, nasap_val, maestro_val, nasap_test, maestro_test


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-config", default=str(DEFAULT_TRAIN_CONFIG),
                    help="生产训练配置；显式 CLI 参数优先于该文件")
    ap.add_argument("--dry-run", action="store_true", help="只装配 + 打印 stats,不建模型/不训练")
    ap.add_argument("--tokenizer", default=str(WORK / "rubato_spm.model"))
    ap.add_argument("--nemo", default=str(ROOT / "canary-180m-flash.nemo"))
    ap.add_argument("--vocab-spec", default=str(DEFAULT_VOCAB_SPEC))
    ap.add_argument("--from-scratch", action="store_true")
    ap.add_argument("--no-resume", action="store_true",
                    help="不读取已有 last.pt；从 .nemo 当前初始化重新开始，但不随机重置参数。"
                         "--from-scratch 会自动包含此语义。")
    ap.add_argument("--allow-legacy-resume-from-epoch-start", action="store_true",
                    help="仅兼容旧版 last.pt（缺 epoch 内 batch_cursor）：明确接受从该 epoch "
                         "开头重放。新版快照不需要；默认拒绝不精确续跑。")
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
    ap.add_argument("--clip-norm", type=float, default=None,
                    help="梯度裁剪阈值。序列损失量纲 ≈65(非逐 token 平均),若日志 gn 长期"
                         "远大于阈值 = 有效 lr 被裁剪吃掉几十倍 —— 证实后按 gn 中位数上调(如 10)")
    ap.add_argument("--eval-max", type=int, default=None,
                    help="每次 eval 抽的样本数/源。逐 token 生成:快路径 ~10s/样本,128 个≈半小时起;"
                         "监控用 48 足够,论文终评另跑全量")
    ap.add_argument("--eval-every", type=int, default=None,
                    help="每多少优化步跑一次 eval+存滚动 ckpt。这台卡 ~1600 步/epoch、"
                         "每步几十秒 —— 3000 步一评是两天一评,太稀;1000 步≈半天一评")
    ap.add_argument("--eval-decode-every", type=int, default=None,
                    help="解码腿(48×逐 token 生成,~25 分钟)的独立节奏;0=与 --eval-every 同步。"
                         "探针(秒级,试验主判据)仍按 --eval-every 每次跑(D77 双节奏)")
    ap.add_argument("--smoke-steps", type=int, default=800,
                    help="冒烟步数。执行端实测:100 utt × 800 步 sem 8.98→3.83 稳降但没到 0.05"
                         "(全新 embedding+头要背下语料需要更多步);32 utt × 4000 步可达标")
    ap.add_argument("--pitch-loss-weight", type=float, default=None,
                    help="音高 piece 的 CE 权重(D82;均值归一,总量级不变只移内部占比;"
                         "1.0=仅监控 pv= 列)")
    ap.add_argument("--amt-aux-weight", type=float, default=None,
                    help="实验性 encoder AMT 辅助损失权重；0=关闭。使用现有 AMT/TAST "
                         "精确事件目标，不在训练进程运行 TransKun")
    ap.add_argument("--amt-align-weight", type=float, default=None,
                    help="AMT 辅助头的错配目标 margin 权重；无需第二次 forward")
    ap.add_argument("--amt-align-margin", type=float, default=None,
                    help="正确音频事件损失优于批内错配事件损失的目标 margin")
    ap.add_argument("--max-steps", type=int, default=None,
                    help="覆盖训练终止步；短 A/B 实验设为起始 checkpoint step + 实验步数")
    ap.add_argument("--ckpt-dir", default=None,
                    help="覆盖 checkpoint 目录；实验必须使用独立目录，避免覆盖主线")
    ap.add_argument("--augment-acoustic", action="store_true",
                    help="C1a(D58):标签安全声学增广(增益/倾斜/噪声,无混响)。二轮启动配置开;"
                         "生效自证看回显 aug_acoustic= 字段")
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
    train_spec = load_train_config(args.train_config)
    allocator_conf = configure_cuda_allocator(train_spec)
    print(f"CUDA allocator 预配置: PYTORCH_ALLOC_CONF={allocator_conf}", flush=True)
    apply_train_config_defaults(args, train_spec)
    validate_cli_args(args)
    runtime_ckpt_dir = (
        Path(args.ckpt_dir).resolve()
        if args.ckpt_dir else ROOT / "outputs" / "ckpt")
    runtime_eval_autolog = (
        runtime_ckpt_dir / "eval_autolog.md"
        if args.ckpt_dir
        else Path(__file__).resolve().parent.parent
        / "reports" / "eval_autolog.md")

    attach_pdmx_row_fns(SOURCES)
    try:
        utts, labels, stats = assemble(SOURCES, resolve_audio)
    finally:
        # 装配结束后训练阶段不再写时长缓存，立即释放 Windows 文件锁。
        _dur_db_close()
    print("=== 装配统计(每一步丢弃都计数,不静默)===")
    for kind, s in stats["per_source"].items():
        print(f"  {kind:8s} rows={s['rows']:>7} kept={s['kept']:>7} "
              f"no_audio={s['no_audio']:>7} no_dialect={s['no_dialect']:>6} "
              f"bad_schema={s['bad_schema']:>5} dup={s['dup']:>5} "
              f"filtered={s['filtered']:>5}")
    print("  -- per file --")
    for path, s in stats.get("per_file", {}).items():
        print(f"  {Path(path).name:38s} kind={s['kind']:8s} rows={s['rows']:>7} "
              f"kept={s['kept']:>7} no_audio={s['no_audio']:>7} "
              f"no_dialect={s['no_dialect']:>6} dup={s['dup']:>5} "
              f"filtered={s['filtered']:>5}")
    for src in SOURCES:
        audit = getattr(src.get("row_fn"), "audit", {})
        missing = audit.get("unmapped_piece_ids") or set()
        if missing:
            print(f"  ⚠ manifest 无映射隔离: {Path(src['path']).name} "
                  f"{len(missing)} 个 unique piece；样例={sorted(missing)[:5]}")
    print(f"  TOTAL utts={stats['totals']['utts']} by_dialect={stats['totals']['by_dialect']}")
    print(f"        by_kind={stats['totals']['by_kind']} by_split={stats['totals']['by_split']}")
    if stats["dup_utt_ids"]:
        print(f"  ⚠ 撞名 utt_id 样本: {stats['dup_utt_ids']}")

    # 健壮性红线必须真的中止；旧代码只有 print，随后照常进入训练。
    validate_assembly_for_training(stats)

    part = partition_by_split(utts)
    (train_utts, nasap_val, maestro_val,
     nasap_test, maestro_test) = select_training_partitions(part)
    print(f"  train={len(train_utts)} nasap_val={len(nasap_val)} maestro_val={len(maestro_val)} "
          f"nasap_test(保留终评)={len(nasap_test)} "
          f"maestro_test(保留终评)={len(maestro_test)} "
          f"other={len(part.get('other', []))}(隔离/未知split,训练/验证/终评均不进)")
    if not train_utts:
        raise RuntimeError("train split 为空，拒绝启动训练")
    if not nasap_val or not maestro_val:
        raise RuntimeError(
            f"验证集不完整：nasap_val={len(nasap_val)} maestro_val={len(maestro_val)}；"
            "拒绝在缺少关键验证源时训练")

    active_manifests = active_pdmx_manifest_paths(SOURCES)
    try:
        leak_cert = verify_pdmx_leakage_certificate(
            active_manifests, label_sources=SOURCES,
            filter_paths=active_pdmx_filter_paths())
        print("  PDMX 内容泄漏证书: PASS "
              f"(train_unique={leak_cert.get('target_unique_train')} "
              f"refs={leak_cert.get('reference_signatures')})")
    except (OSError, ValueError, KeyError, TypeError) as e:
        if not args.dry_run:
            raise RuntimeError(
                "PDMX 内容级泄漏未获当前 manifest 证书，禁止启动训练。"
                f"{type(e).__name__}: {e}") from e
        print("  ⚠ PDMX 内容泄漏证书: 未通过；dry-run 可完成，但正式训练会被阻止。"
              f"{type(e).__name__}: {e}")

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
        raise RuntimeError("模型词表/位置表体检不过，禁止开训")
    if args.amt_aux_weight > 0:
        from rubato.model.acoustic_aux import attach_amt_aux_head
        _aux_head = attach_amt_aux_head(
            model,
            hidden_dim=int((train_spec["loss"].get("acoustic_aux") or {})
                           .get("hidden_dim", 0)),
            dropout=float((train_spec["loss"].get("acoustic_aux") or {})
                          .get("dropout", 0.0)))
        print(f"AMT 辅助头: input={_aux_head['input_dim']} "
              f"params={_aux_head['n_params']:,}（训练专用）")

    if args.probe_only:
        # 诊断模式,不训练。v2(D27 后):三源探针 —— 对齐审计发现只有 nASAP 对齐故障,
        # 而此前所有探针/评测样本恰好全来自 nASAP。"decoder 全局忽略音频"可能要收窄为
        # "nASAP 分支被污染 + 评测建在污染源上"。本模式对 nasap/maestro/pdmx 各取 2 个
        # 训练对,分别测 真音频 vs 静音 的语义命中率差(Δsem),一分钟分辨全局病与局部病。
        import numpy as np
        import time as _time
        import torch
        last = runtime_ckpt_dir / "last.pt"
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
        autolog = runtime_eval_autolog
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
        last = runtime_ckpt_dir / "last.pt"
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
        autolog = runtime_eval_autolog
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
    tokenizer_cfg = train_spec["tokenizer"]
    configured_vocab = int(tokenizer_cfg.get("vocab", pf["vocab"]))
    if configured_vocab != int(pf["vocab"]):
        raise RuntimeError(
            f"train.yaml tokenizer.vocab={configured_vocab} != 实际 tokenizer={pf['vocab']}")
    configured_mix = dict(train_spec["data"].get("mix") or {})
    if dialect_mix is None:
        dialect_mix = configured_mix
    train_ds = RubatoDataset(train_utts, labels, tok, train=True, max_target_len=max_tgt,
                             augment=not args.smoke, dialect_mix=dialect_mix,
                             acoustic_aug=args.augment_acoustic,
                             acoustic_targets=args.amt_aux_weight > 0,
                             seed=int(train_spec.get("seed", 20260706)),
                             alpha=float(tokenizer_cfg.get("spm_alpha", 0.25)))
    lf = train_ds.len_filter_report
    print(f"  超长过滤: 保留 {lf.get('kept_pairs')} 对,丢弃 {lf.get('dropped_by_dialect') or 0}")
    if args.amt_aux_weight > 0:
        available = train_ds._available()
        n_aux = sum(
            1 for uid in available
            if labels.get(uid, {}).get("AMT")
            or labels.get(uid, {}).get("TAST"))
        print(f"  AMT 辅助目标覆盖: {n_aux}/{len(available)} utt "
              f"({n_aux / max(len(available), 1):.1%});"
              "优先 exact AMT，其次 time-aligned TAST，无时间戳样本不伪造")
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
    optim_cfg = train_spec["optim"]
    loss_spec = train_spec["loss"]
    memory_spec = train_spec["memory"]
    ts_smooth = loss_spec.get("ts_smooth") or {}
    ckpt_cfg = train_spec["ckpt"]
    cfg = {
        "train_config": str(Path(args.train_config).resolve()),
        "lr_encoder": args.lr_enc,
        "lr_decoder": args.lr_dec,
        "betas": tuple(optim_cfg.get("betas", (0.9, 0.98))),
        "wd": float(optim_cfg.get("wd", 0.01)),
        "warmup_steps": int(optim_cfg.get("warmup_steps", 1500)),
        "min_lr_ratio": float(optim_cfg.get("min_lr_ratio", 0.1)),
        "max_steps": int(args.max_steps),
        "max_epochs": int(train_spec.get("max_epochs", 1000)),
        "grad_accum_to_audio_sec": float(
            optim_cfg.get("grad_accum_to_audio_sec", 2000)),
        "precision": str(train_spec.get("precision", "bf16")),
        "ckpt_dir": str(runtime_ckpt_dir),
        "save_every_steps": int(ckpt_cfg.get("save_every_steps", 200)),
        "ckpt_keep": int(ckpt_cfg.get("keep", 6)),
        "selection_metric": str(ckpt_cfg["select_by"]),
        "clip_norm": args.clip_norm,
        "eval_decode_every": args.eval_decode_every,
        "pitch_loss_weight": args.pitch_loss_weight,
        "acoustic_aux": {
            "weight": float(args.amt_aux_weight),
            "alignment_weight": float(args.amt_align_weight),
            "alignment_margin": float(args.amt_align_margin),
            "onset_radius": int((loss_spec.get("acoustic_aux") or {})
                                .get("onset_radius", 1)),
            "hidden_dim": int((loss_spec.get("acoustic_aux") or {})
                              .get("hidden_dim", 0)),
            "dropout": float((loss_spec.get("acoustic_aux") or {})
                             .get("dropout", 0.0)),
            "sample_rate": 16000,
        },
        "dialect_mix": dialect_mix,                # None=D2 纸面;设了 --amt-mix 则为换算后的四元组(回显自证)
        "prefetch_batches": args.prefetch,         # 预取深度;0=串行直迭代(对照)
        "cuda_memory": dict(memory_spec),
        "allow_legacy_resume_from_epoch_start":
            args.allow_legacy_resume_from_epoch_start,
        # --from-scratch 若仍自动读 last.pt，就会把随机初始化和旧 optimizer 全部覆盖。
        "resume": not (args.no_resume or args.from_scratch),
        "eval_max": args.eval_max,                 # 每次 eval 抽的 val 子集(逐 token 生成,大了小时级)
        "eval_time_budget_s": 1200,                # eval 硬时限:超时截断按已评样本出指标,不再"疑似卡死"
        # eval 证据自动落盘到 repo 内(追加式);执行端上报 = git add reports/eval_autolog.md
        # + commit + push,不再人肉摘录(三次摘录事故后收权)
        "eval_autolog": str(runtime_eval_autolog),
        "loss": {
            "sem_label_smooth": float(loss_spec.get("sem_label_smooth", 0.1)),
            "p_center": float(ts_smooth.get("p_center", 0.9)),
            "w": int(ts_smooth.get("w", 5)),
        },
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
