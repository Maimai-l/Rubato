"""
钳制 TAST 定点重渲 —— 找回被 _shift_tmap 秒轴 bug 毁掉的 13k 段 TAST(用户拍板:必须重渲)。

责任说明:旧 _shift_tmap(规划端写的)秒轴不归零,段落在整曲 40s 后的 TAST 全被钳到
39.99(多对一,文本不可逆)。P2e 已把这批置 null 下架;本脚本把受影响的【整曲】清场,
交给 S5 续跑机制用【修好的代码】重渲重打戳 —— TAST 全量找回,不是凑合。

圈定(证据来自备份,不猜):
  受影响曲 = pdmx_perf_labels.bak(P2e 修复前的原件)里 TAST 被判 clamped/nonmonotone
  的行所属 piece_id;无 .bak 时退化为扫当前标签文件。
清场(粒度必须是整曲 —— S5 续跑按"该曲有无标签行"判断做没做完,留半曲的行会被跳过):
  该曲全部标签行(purge_label_rows,首份 .bak 不覆盖)+ 全部 VN 段音频 pdmxperf_{pid}_*
  + {pid}.done。该曲本来正常的段会被一并重渲,产出等价(同曲同哈希同预设)。
注意:重渲走 apply_preset 当前默认 = 能量归一混音(D15:用户实听"修了听着差不多",
  故新旧混音并存可接受,不为此单独回退 legacy)。

用法(执行端):
  python scripts/rerender_tast_clamped.py            # 干跑:曲数/段数/预估时长
  python scripts/rerender_tast_clamped.py --apply    # 清场 + 残留全 0 验证表
  然后: python scripts/sop_next.py --reset-step P2c,P2e,P6c,P7,P8 && python scripts/sop_next.py --go
  (P2c 续跑只补被清的曲;P2e 复扫即验证 —— 修好后应报 0 shift/0 clamped。)
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl
from rubato.data.cleanup import purge_label_rows
from scripts.rerender_presets import _files_s5
from scripts.repair_tast_labels import classify

ROOT = Path(r"D:\vscode_projects\ee_download")


def find_affected(labels: Path) -> tuple[set, dict]:
    """返回 (受影响 piece_id 集, 统计)。证据源:.bak(修复前原件)优先。"""
    src = labels.with_suffix(".bak") if labels.with_suffix(".bak").exists() else labels
    pids: set = set()
    st = {"source": src.name, "rows": 0, "bad_rows": 0}
    for r in read_jsonl(str(src)):
        st["rows"] += 1
        t = r.get("TAST")
        if isinstance(t, str) and t.strip() and classify(t) in ("clamped", "nonmonotone"):
            st["bad_rows"] += 1
            if r.get("piece_id"):
                pids.add(r["piece_id"])
    return pids, st


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="钳制 TAST 的整曲清场重渲(默认干跑)")
    ap.add_argument("--labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--audio-dir", default=str(ROOT / "work" / "pdmx_audio"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    labels = Path(args.labels)
    audio_dir = Path(args.audio_dir)
    if not labels.exists():
        print(f"✗ 标签文件不存在: {labels}")
        return 1
    pids, st = find_affected(labels)
    cur_rows = [r for r in read_jsonl(str(labels)) if r.get("piece_id") in pids]
    n_files = sum(len(_files_s5(audio_dir, p)) for p in pids)
    print(f"证据源: {st['source']}(共 {st['rows']} 行,钳制/非单调 {st['bad_rows']} 行)")
    print(f"受影响: {len(pids)} 曲(整曲清场)→ 现有标签行 {len(cur_rows)},VN 段音频/.done 文件 {n_files}")
    print(f"预估重渲: 每曲 VN ~0.4s(GPU)+ 渲染切片 ~5-20s(CPU,受影响曲偏长)"
          f" → 约 {len(pids) * 10 / 3600:.1f} 小时量级(续跑式,可中断)")
    if not pids:
        print("没有受影响曲 —— 无事可做(可能已重渲完成)。")
        return 0
    if not args.apply:
        print("\n干跑结束(未改任何文件)。加 --apply 实施。")
        return 0

    deleted = 0
    for p in pids:
        for f in _files_s5(audio_dir, p):
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
    kept, dropped = purge_label_rows(labels, pids, ("pdmxperf_",))
    print(f"已清:文件 {deleted},标签行剔除 {dropped}(保留 {kept})")

    # 残留验证(D10:全 0 才算干净)
    resid_files = sum(len(_files_s5(audio_dir, p)) for p in pids)
    resid_rows = sum(1 for r in read_jsonl(str(labels)) if r.get("piece_id") in pids)
    clean = resid_files == 0 and resid_rows == 0
    print("===== 清场验证 =====")
    print(f"  {'✓' if resid_files == 0 else '✗'} 残留文件 = {resid_files}")
    print(f"  {'✓' if resid_rows == 0 else '✗'} 残留标签行 = {resid_rows}")
    print("  结论: " + ("【干净】" if clean else "【没清干净,贴回给规划端】"))
    print("\n下一步(一条龙,S5 续跑只补被清的曲,P2e 复扫即验证):")
    print("  python scripts/sop_next.py --reset-step P2c,P2e,P6c,P7,P8")
    print("  python scripts/sop_next.py --go")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
