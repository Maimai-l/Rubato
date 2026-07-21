"""
C3 音色副本生成器(EXPERIMENT_ACOUSTIC,O5 已拍板 M 档 12,000 曲,D50)。

给选中的 train 曲渲【第二音色】副本:整曲渲染(强制换源换预设)→ 按原窗切段 →
标签行复制(utt_id 加 _s2)。三阶段一条命令,断点续跑,CPU 与训练并行(召回战役同款作业面)。

安全设计:
  - 只选全 train 行的曲(val/test 不渲:评测冻结 + 不浪费);
  - 第二源 = 确定性哈希在【其余 4 源】中加权选(绝不与原音色重复);
  - 标签写 STAGING 名(pdmx_a2s_labels_s2.staging.jsonl)—— 装配只认正式名,
    【改名 = 进池武装,只按 EXECUTOR.md 的书面指令执行,严禁自行改名】(单变量纪律);
  - 范围 v1 = S4 直渲线(A2S/A2S_lite);pdmxperf(VN/TAST)不在本期。

用法(执行端):
  python scripts/c3_timbre_copies.py --n 12000            # 全量(断了重跑即续)
  python scripts/c3_timbre_copies.py --n 20 --workers 2   # 冒烟
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rubato.platform import harden_stdout, read_jsonl          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get("RUBATO_BASE")
            or (ROOT.parent if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download"))
WORK = BASE / "work"


# ---------------------------------------------------------------- 纯逻辑(沙盒可测)

def pick_subset(pieces_rows: dict, n: int) -> list[str]:
    """确定性选曲:全 train 行 + 有 midi(调用方保证音频存在性另查)。
    按 sha256(pid) 排序取前 n —— 可复现、断点续跑同名单。"""
    ok = []
    for pid, rows in pieces_rows.items():
        if not rows:
            continue
        if all((r.get("split") or "train") == "train" for r in rows):
            ok.append(pid)
    ok.sort(key=lambda p: hashlib.sha256(p.encode()).hexdigest())
    return ok[:n]


def choose_second(pid: str, sources_cfg: dict, presets_cfg: dict):
    """第二音色 = 其余源中确定性加权选;预设独立重选。绝不返回原源。"""
    from rubato.render.core import assign_source_and_preset, _pick, _unit
    orig_src, _ = assign_source_and_preset(f"pdmx_{pid}", sources_cfg, presets_cfg)
    weights = {sid: s["ratio"] for sid, s in sources_cfg["sources"].items()
               if sid != orig_src}
    if not weights:
        raise ValueError("只有一个音源,无从选第二音色")
    seed = presets_cfg.get("seed", 0)
    src2 = _pick(weights, _unit(seed, f"c3:{pid}", "src"))
    preset2 = _pick(presets_cfg["weights"], _unit(seed, f"c3:{pid}", "preset"))
    return orig_src, src2, preset2


def transform_rows(rows: list[dict]) -> list[dict]:
    """标签行副本:utt_id += '_s2',其余字段原样(resolve_audio 按 utt_id 找 <utt_id>.flac,
    后缀自然落到 _s2 段文件,零解析器改动)。"""
    out = []
    for r in rows:
        r2 = dict(r)
        r2["utt_id"] = f"{r['utt_id']}_s2"
        out.append(r2)
    return out


# ---------------------------------------------------------------- 渲染(镜像 s4 render_one)

def _render_s2_task(t) -> dict:
    midi_path, pid, out_dir, src2, preset2 = t
    from rubato.render.core import render_midi_to_wav44, finalize
    import yaml
    scfg = yaml.safe_load(open(str(ROOT / "configs" / "sources.yaml"), encoding="utf-8"))
    pcfg = yaml.safe_load(open(str(ROOT / "configs" / "recording_presets.yaml"), encoding="utf-8"))
    utt = f"pdmx_{pid}_s2"
    opus_path = str(Path(out_dir) / f"{utt}.opus")
    if os.path.isfile(opus_path) and os.path.getsize(opus_path) > 0:
        return {"ok": True, "skipped": True}
    wav_path = str(Path(out_dir) / f"{utt}.wav")
    t0 = time.time()
    last_err = None
    for attempt in range(3):              # PermissionError(杀毒/索引器瞬时锁)退避重试
        try:
            render_midi_to_wav44(midi_path, scfg["sources"][src2], scfg, wav_path, utt_id=utt,
                                 timeout_s=float(scfg["render"].get("timeout_s", 600)))
            finalize(wav_path, pcfg["presets"][preset2], scfg, pcfg, utt, opus_path)
            return {"ok": True, "elapsed_s": round(time.time() - t0, 1),
                    "source": src2, "preset": preset2}
        except PermissionError as e:
            last_err = e
            time.sleep(1.0 + attempt)
        except Exception as e:
            last_err = e
            break
        finally:
            if os.path.exists(wav_path):
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass
    return {"ok": False, "error": f"{type(last_err).__name__}: {str(last_err)[:120]}"}


def main() -> int:
    harden_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12000, help="选曲数(O5 拍板 M 档 12000)")
    ap.add_argument("--labels", default=str(WORK / "pdmx_a2s_labels.jsonl"))
    ap.add_argument("--manifest", default=str(WORK / "manifest_pieces.jsonl"))
    ap.add_argument("--audio-dir", default=str(WORK / "pdmx_audio"),
                    help="原渲染目录(只读:查原整曲存在性)")
    ap.add_argument("--audio-out", default=str(WORK / "pdmx_audio_s2"),
                    help="C3 专属输出目录(D51:与训练读取目录隔离,根治 Windows 文件锁争抢)")
    ap.add_argument("--staging-out", default=str(WORK / "pdmx_a2s_labels_s2.staging.jsonl"))
    ap.add_argument("--min-sec", type=float, default=2.0)
    ap.add_argument("--max-sec", type=float, default=41.0)
    ap.add_argument("--workers", type=int, default=4, help="渲染并行度(内存紧张降 2)")
    args = ap.parse_args()
    import yaml
    from rubato.ops import auto_map
    from scripts.s4_slice_segments import slice_piece_task, _find_whole

    scfg = yaml.safe_load(open(str(ROOT / "configs" / "sources.yaml"), encoding="utf-8"))
    pcfg = yaml.safe_load(open(str(ROOT / "configs" / "recording_presets.yaml"), encoding="utf-8"))
    audio_dir = Path(args.audio_dir)
    out_dir = Path(args.audio_out)
    out_dir.mkdir(parents=True, exist_ok=True)
    # 迁移:早期版本(D50 首发)把 _s2 产物写进了训练读取目录,与训练争抢(99/700 PermissionError,
    # @86a5706)。把已渲的搬进专属目录,已花的 CPU 不浪费;搬完老目录零 _s2 残留。
    n_mig = 0
    for f in list(audio_dir.glob("*_s2.*")):
        try:
            f.rename(out_dir / f.name)
            n_mig += 1
        except OSError:
            pass                          # 被占用的留待下轮(训练重启后自然可搬)
    if n_mig:
        print(f"C3: 迁移旧产物 {n_mig} 个 → {out_dir}")

    # 曲 → 标签行 / midi
    pieces_rows: dict = defaultdict(list)
    for r in read_jsonl(args.labels):
        pid = r.get("piece_id")                    # 与 recall_explain 同口径
        if pid:
            pieces_rows[pid].append(r)
    midi_of: dict = {}
    for m in read_jsonl(args.manifest):
        if m.get("midi_path"):
            midi_of[str(m.get("piece_id") or m.get("id"))] = str(m["midi_path"])

    picked = [p for p in pick_subset(pieces_rows, args.n * 2)
              if p in midi_of and _find_whole(audio_dir, p) is not None][: args.n]
    st: Counter = Counter(picked=len(picked))
    print(f"C3: 选曲 {len(picked)}(确定性名单,断点续跑同名单)")

    # 阶段 1:渲染(断点续跑)
    tasks = []
    for pid in picked:
        mp = midi_of[pid]
        mp = mp if Path(mp).is_absolute() else str(WORK / mp)
        try:
            _, src2, preset2 = choose_second(pid, scfg, pcfg)
        except Exception:
            st["choose_fail"] += 1
            continue
        tasks.append((mp, pid, str(out_dir), src2, preset2))

    def _on_render(_t, res):
        st["render_ok" if res.get("ok") else "render_fail"] += 1
        if res.get("skipped"):
            st["render_skipped"] += 1
        if not res.get("ok"):
            st.setdefault  # noqa —— 失败样例最多记 5 条
            if st["render_fail"] <= 5:
                print(f"  渲染失败样例: {res.get('error')}", flush=True)

    auto_map(tasks, _render_s2_task, workers=args.workers, on_result=_on_render, log_every=100)

    # 阶段 2:切段(复用 s4 切割器:pid 传 _s2 名,行传 _s2 后缀 → 找 _s2 整曲、写 _s2 段)
    n_sliced = 0
    for pid in picked:
        rows2 = transform_rows(pieces_rows[pid])
        mp = midi_of[pid]
        mp = mp if Path(mp).is_absolute() else str(WORK / mp)
        r = slice_piece_task((f"{pid}_s2", rows2, mp, str(out_dir), str(out_dir),
                              args.min_sec, args.max_sec))
        for k, v in r.items():
            st[f"slice_{k}"] += v
        n_sliced += r.get("sliced", 0)

    # 阶段 3:标签落 STAGING(改名=武装,严禁自行执行 —— 见 EXECUTOR.md)
    with open(args.staging_out, "w", encoding="utf-8") as fo:
        n_rows = 0
        for pid in picked:
            for r2 in transform_rows(pieces_rows[pid]):
                fo.write(json.dumps(r2, ensure_ascii=False) + "\n")
                n_rows += 1
    st["staging_rows"] = n_rows

    lines = [f"\n## C3 渲染 @ {time.strftime('%Y-%m-%d %H:%M:%S')} (n={args.n})",
             "  " + " ".join(f"{k}={v}" for k, v in sorted(st.items()))]
    out = ROOT / "reports" / "C3_RENDER.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n已追加 {out};标签在 STAGING({args.staging_out}),改名武装只按 EXECUTOR.md 指令。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
