"""
r3 收尾第 1 步:失败清单清洗(把"已补回/已成功"的曲从隔离集释放,只留真失败)。

判定口径(存在性,与交接文档下一步①一致):
  释放 = 该曲【已有标签行】(其实成功了) 或 【官方 MIDI+CSV 产物在盘】(补跑救回,待消费);
  保留 = 两样都没有(终败,含卡死隔离)。
产物:失败清单原地重写(.bak 备份)+ 打印下一步消费命令(自动发现本地文件名)。

用法(人手直接跑,无参数):
  python scripts/r3_failures_release.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout, read_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("RUBATO_WORK")
            or (ROOT.parent / "work" if (ROOT.parent / "work").exists()
                else r"D:\vscode_projects\ee_download\work"))

FAILURES = WORK / "pdmx_vn_failures_r3_native.jsonl"
STAGING = WORK / "pdmx_perf_labels_r3_native.staging.jsonl"
NATIVE_ROOT = WORK / "vn_native_r3_train"


def _labeled(path: Path) -> set:
    ids = set()
    if path.exists():
        for r in read_jsonl(path):
            pid = r.get("piece_id")
            if pid:
                ids.add(pid)
    return ids


def _has_product(pid: str, native_root: Path) -> bool:
    """官方产物在盘 = 任一叶目录下存在 {leaf}_{pid}_by_isgn_*.mid 及其 CSV。
    (消费后产物被清理,但那种曲必已有标签,走"已标注"分支,不会来查这里。)"""
    hits = list(native_root.glob(f"*/*/*_{pid}_by_isgn_*.mid"))
    for m in hits:
        if Path(str(m) + "_midi_notes.csv").exists():
            return True
    return False


def main(argv=None):
    harden_stdout()
    if not FAILURES.exists():
        print(f"✗ 失败清单不存在: {FAILURES}")
        return 1
    labeled = _labeled(STAGING)
    rows = list(read_jsonl(FAILURES))
    keep, rel_labeled, rel_product = [], 0, 0
    seen = set()
    for r in rows:
        pid = r.get("piece_id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        if pid in labeled:
            rel_labeled += 1
            continue
        if NATIVE_ROOT.exists() and _has_product(pid, NATIVE_ROOT):
            rel_product += 1
            continue
        keep.append(r)
    bak = FAILURES.with_suffix(FAILURES.suffix + ".pre_release.bak")
    if not bak.exists():                       # 首跑留底;重跑幂等不覆盖首证
        bak.write_text(FAILURES.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = FAILURES.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(FAILURES)
    print(f"清单 {len(rows)} 行(去重 {len(seen)} 曲)→ 保留终败 {len(keep)}"
          f" | 释放:已有标签 {rel_labeled} + 有产物待消费 {rel_product}")
    print(f"备份: {bak}")
    manis = sorted(WORK.glob("manifest_pieces_r3*.jsonl"))
    if manis:
        print("\n下一步(复制运行,补消费释放的曲;可反复跑直到 DONE 行 fail=0 附近):")
        print(f"python scripts/s5_vn_render.py --native-vn-root {NATIVE_ROOT} "
              f"--manifest {manis[0]} --out-labels {STAGING} "
              f"--out-audio-dir {WORK / 'pdmx_audio_r3_native'} --out-corpus \"\" "
              f"--out-failures {FAILURES}")
    else:
        print(f"\n⚠ 没找到 {WORK}/manifest_pieces_r3*.jsonl —— 把 work 下 r3 清单文件名发回来")
    return 0


if __name__ == "__main__":
    sys.exit(main())
