"""
钳制 TAST 定点重渲 —— 找回被 _shift_tmap 秒轴 bug 毁掉的 13k 段 TAST(用户拍板:必须重渲)。

责任说明:旧 _shift_tmap(规划端写的)秒轴不归零,段落在整曲 40s 后的 TAST 全被钳到
39.99(多对一,文本不可逆)。P2e 已把这批置 null 下架;本脚本把受影响的【整曲】清场,
交给 S5 续跑机制用【修好的代码】重渲重打戳 —— TAST 全量找回,不是凑合。

圈定(证据 = 活文件,不再信 .bak 的身份 —— 执行端实测翻车:.bak 路径有三个写者、
"首份保留"语义,盘上那份是更早世代的备份,按它扫出 affected=0,重渲空转):
  受影响曲 = 当前标签文件里【A2S 非空 ∧ TAST=null】的行所属 piece_id。这正是 P2e 置 null
  的集合:本世代 TAST 覆盖率 34,859/34,859(P2c 实测),不存在"天然无 TAST"的行,
  故该判据恰好圈住毒药段、重渲后自动收敛为空(修好代码后 TAST 不再置 null)。
  另并【待渲侧车】pdmx_perf_labels_rerender_pending.json:清场前先写意向,防"清完就崩"
  的窗口把已清的曲弄丢;曲重渲回来(有 TAST 行)即自动消账,全消则删侧车。
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

ROOT = Path(r"D:\vscode_projects\ee_download")


def _sidecar(labels: Path) -> Path:
    return labels.with_name(labels.stem + "_rerender_pending.json")


def find_affected(labels: Path) -> tuple[set, dict]:
    """返回 (受影响 piece_id 集, 统计)。证据 = 活文件的【A2S 非空 ∧ TAST=null】行
    ∪ 待渲侧车(清场意向,防清完就崩的窗口)。侧车里已重渲回来的曲(现有非空 TAST 行)
    自动消账;全消则删侧车。不读 .bak —— 它的身份不可靠(多写者、首份保留)。"""
    pids: set = set()
    healthy: set = set()                    # 有非空 TAST 行的曲(已健康)
    st = {"rows": 0, "live_null_rows": 0, "pending": 0}
    for r in read_jsonl(str(labels)):
        st["rows"] += 1
        pid = r.get("piece_id")
        if not pid:
            continue
        a2s, t = r.get("A2S"), r.get("TAST")
        if isinstance(t, str) and t.strip():
            healthy.add(pid)
        elif isinstance(a2s, str) and a2s.strip():
            st["live_null_rows"] += 1
            pids.add(pid)
    sc = _sidecar(labels)
    if sc.exists():
        try:
            pending = set(json.loads(sc.read_text(encoding="utf-8")).get("pieces", []))
        except Exception:
            pending = set()
        still = pending - healthy           # 还没渲回来的才算账
        st["pending"] = len(still)
        pids |= still
        if not still:
            sc.unlink(missing_ok=True)      # 全部渲回 → 侧车消账
        elif still != pending:
            sc.write_text(json.dumps({"pieces": sorted(still)}, ensure_ascii=False),
                          encoding="utf-8")
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
        # 本脚本现在是常驻 SOP 步骤(P2c0):全新管线跑到这一步时标签还没生成,无事可做
        print(f"标签文件不存在({labels})→ 受影响: 0 曲,无事可做。")
        return 0
    pids, st = find_affected(labels)
    cur_rows = [r for r in read_jsonl(str(labels)) if r.get("piece_id") in pids]
    n_files = sum(len(_files_s5(audio_dir, p)) for p in pids)
    print(f"证据: 活文件 {st['rows']} 行,其中 TAST=null 行 {st['live_null_rows']}"
          f"(+侧车待渲 {st['pending']} 曲)")
    print(f"受影响: {len(pids)} 曲(整曲清场)→ 现有标签行 {len(cur_rows)},VN 段音频/.done 文件 {n_files}")
    print(f"预估重渲: 每曲 VN ~0.4s(GPU)+ 渲染切片 ~5-20s(CPU,受影响曲偏长)"
          f" → 约 {len(pids) * 10 / 3600:.1f} 小时量级(续跑式,可中断)")
    if not pids:
        print("没有受影响曲 —— 无事可做(可能已重渲完成)。")
        return 0
    if not args.apply:
        print("\n干跑结束(未改任何文件)。加 --apply 实施。")
        return 0

    # 清场【前】先写意向侧车:清完标签行后活文件就没证据了,中途崩溃会把这批曲弄丢
    sc = _sidecar(labels)
    old = set()
    if sc.exists():
        try:
            old = set(json.loads(sc.read_text(encoding="utf-8")).get("pieces", []))
        except Exception:
            pass
    sc.write_text(json.dumps({"pieces": sorted(old | pids)}, ensure_ascii=False),
                  encoding="utf-8")
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
