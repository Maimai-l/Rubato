"""
外科手术重渲 —— 按【坏预设名单】精确圈出受影响的曲,只清只渲那部分,不动其余语料。

原理:音源/预设分配是确定性哈希(assign_source_and_preset),给定坏预设名单即可精确重算
每首曲的归属。注意两条管线的哈希键不同(搞错=白手术,已核对代码):
  S4 整曲直渲:按 "pdmx_{pid}" 分配 → 受影响者删【整曲 opus + 段 flac】,标签不动
              (文本/score_range 与混响无关,重渲重切后文件名相同,自动重新配对)。
  S5 VN 渲染:按裸 "pid" 分配 → 受影响者删【VN 段音频 + .done + VN 标签行(留 .bak)】,
              续跑机制按标签自动只重做这些曲(VN 推理 GPU ~0.4s/曲,可承受)。

工作流(在用户听完 preset_audition 并由规划端改好 presets yaml 之后):
  python scripts/rerender_presets.py --list                       # 各预设的受影响曲数成本表
  python scripts/rerender_presets.py --bad p09_church,p12_dome    # 干跑:圈出范围,报数
  python scripts/rerender_presets.py --bad ... --apply            # 清场 + 验证表
  然后依次: python scripts/s4_parallel.py → s4_slice_segments.py → s5_vn_render.py(全部续跑式)
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl
from rubato.data.cleanup import purge_label_rows

ROOT = Path(r"D:\vscode_projects\ee_download")


def _load_cfgs(sources_path, presets_path):
    import yaml
    with open(sources_path, "r", encoding="utf-8") as f:
        sources_cfg = yaml.safe_load(f)
    with open(presets_path, "r", encoding="utf-8") as f:
        presets_cfg = yaml.safe_load(f)
    return sources_cfg, presets_cfg


def compute_affected(pids, sources_cfg, presets_cfg, bad: set):
    """返回 (s4_pids, s5_pids, per_preset_counts)。哈希键:S4 用 pdmx_{pid},S5 用裸 pid。"""
    from rubato.render.core import assign_source_and_preset
    s4, s5 = set(), set()
    counts: dict = {}
    for pid in pids:
        _, p4 = assign_source_and_preset(f"pdmx_{pid}", sources_cfg, presets_cfg)
        _, p5 = assign_source_and_preset(pid, sources_cfg, presets_cfg)
        c4 = counts.setdefault(p4, {"s4": 0, "s5": 0}); c4["s4"] += 1
        c5 = counts.setdefault(p5, {"s4": 0, "s5": 0}); c5["s5"] += 1
        if p4 in bad:
            s4.add(pid)
        if p5 in bad:
            s5.add(pid)
    return s4, s5, counts


def _files_s4(audio_dir: Path, pid: str) -> list[Path]:
    out = [p for e in (".opus", ".flac", ".wav") if (p := audio_dir / f"pdmx_{pid}{e}").exists()]
    out += list(audio_dir.glob(f"pdmx_{pid}_*"))          # 段 flac
    return out


def _files_s5(audio_dir: Path, pid: str) -> list[Path]:
    out = list(audio_dir.glob(f"pdmxperf_{pid}_*"))       # VN 段音频
    dm = audio_dir / f"{pid}.done"
    if dm.exists():
        out.append(dm)
    return out


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="按坏预设名单外科手术式清场重渲(默认干跑)")
    ap.add_argument("--bad", default="", help="坏预设 id 逗号表,如 p09_church,p12_dome,p13_cave")
    ap.add_argument("--list", action="store_true", help="只打各预设受影响曲数成本表")
    ap.add_argument("--manifest", default=str(ROOT / "work" / "manifest_pieces.jsonl"))
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--vn-labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--sources", default="configs/sources.yaml")
    ap.add_argument("--presets", default="configs/recording_presets.yaml")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    sources_cfg, presets_cfg = _load_cfgs(args.sources, args.presets)
    pids = [p["piece_id"] for p in read_jsonl(args.manifest) if p.get("piece_id")]
    bad = {b.strip() for b in args.bad.split(",") if b.strip()}
    s4p, s5p, counts = compute_affected(pids, sources_cfg, presets_cfg, bad)

    if args.list or not bad:
        print(f"预设 → 受影响曲数(全库 {len(pids)} 曲;S4/S5 哈希键不同,故两列):")
        for pid_, c in sorted(counts.items(), key=lambda kv: -(kv[1]['s4'] + kv[1]['s5'])):
            mark = " ←坏" if pid_ in bad else ""
            print(f"  {pid_:<20} S4={c['s4']:>6}({100*c['s4']/max(len(pids),1):.1f}%) "
                  f"S5={c['s5']:>6}({100*c['s5']/max(len(pids),1):.1f}%){mark}")
        if not bad:
            print("\n用 --bad p09_church,... 圈定名单后重跑(先干跑看范围)。")
            return 0

    audio_dir = Path(args.audio_dir)
    n_s4_files = sum(len(_files_s4(audio_dir, p)) for p in s4p)
    n_s5_files = sum(len(_files_s5(audio_dir, p)) for p in s5p)
    print(f"\n坏预设 {sorted(bad)}:")
    print(f"  S4 受影响 {len(s4p)} 曲({100*len(s4p)/max(len(pids),1):.1f}%)→ 删整曲+段文件 {n_s4_files} 个,标签不动")
    print(f"  S5 受影响 {len(s5p)} 曲({100*len(s5p)/max(len(pids),1):.1f}%)→ 删 VN 段/.done {n_s5_files} 个 + VN 标签行(留 .bak)")
    if not args.apply:
        print("\n干跑结束(未改任何文件)。确认预设 yaml 已按用户裁决改好后,加 --apply 实施。")
        return 0

    deleted = {"s4": 0, "s5": 0}
    for p in s4p:
        for f in _files_s4(audio_dir, p):
            try:
                f.unlink(); deleted["s4"] += 1
            except OSError:
                pass
    for p in s5p:
        for f in _files_s5(audio_dir, p):
            try:
                f.unlink(); deleted["s5"] += 1
            except OSError:
                pass
    kept, dropped = purge_label_rows(Path(args.vn_labels), s5p, ("pdmxperf_",))
    print(f"已清:S4 文件 {deleted['s4']},S5 文件 {deleted['s5']},VN 标签行剔除 {dropped}(保留 {kept},备份 .bak)")

    # 验证(残留全 0 才算清干净 —— 贴回给用户)
    resid_s4 = sum(len(_files_s4(audio_dir, p)) for p in s4p)
    resid_s5 = sum(len(_files_s5(audio_dir, p)) for p in s5p)
    clean = resid_s4 == 0 and resid_s5 == 0
    print("===== 清理验证 =====")
    print(f"  {'✓' if resid_s4 == 0 else '✗'} S4 残留文件 = {resid_s4}")
    print(f"  {'✓' if resid_s5 == 0 else '✗'} S5 残留文件 = {resid_s5}")
    print("  结论: " + ("【干净】" if clean else "【没清干净,贴回给用户】"))
    print("\n下一步(全部续跑式,只补被清的曲):")
    print("  python scripts/s4_parallel.py")
    print("  python scripts/s4_slice_segments.py")
    print("  python scripts/s5_vn_render.py")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
