"""
TAST 时间戳修复 —— 把已产出标签里的【绝对演奏秒】戳归零为【段内相对秒】,不重渲。

背景(训练前代码审计抓出的数据毒药):_shift_tmap 旧版只平移乐谱轴、秒轴保持绝对
演奏时间,导致 S5(pdmx_perf_labels.jsonl)里凡是段起点 >0 的 TAST:
  ① 全部戳整体偏移 +t_lo(音频切片从 t_lo 起、戳却从 t_lo 计)——模型学不到一致映射;
  ② 段落在整曲 40s 之后的,戳被 stamp_units 钳到末 bin 39.99 —— 全段常数戳,
     过 validate(单调非降)不报错,纯静默毒药。
77.9% 单段曲的 t_lo≈0 基本无感,多段曲的后续段全部中招。

修复原理(精确、无需 tmap/重渲):TAST 首单元恒为段首小节线,其戳 = round(t_lo/10ms)。
  未钳制的行(max bin < 3999):所有戳减首戳 —— 与"秒轴归零后重打戳"至多差 ±1 bin(10ms,
    远小于 50ms 评测容差);单调性减常数后保持。
  已钳制的行(max bin == 3999):信息已丢,不可逆 → TAST 置 null(A2S/A2S_lite/音频保留,
    该 utt 退出 TAST 池但不退出训练)。想找回这部分 TAST 只能删该曲标签走 S5 续跑重渲。

用法(执行端,改 s7/nasap 无需本脚本 —— nasap 整个重跑):
  python scripts/repair_tast_labels.py            # 干跑:分类计数,不写文件
  python scripts/repair_tast_labels.py --apply    # 实施(留 .bak)+ 复扫验证表(残留必须 0)
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rubato.platform import harden_stdout

ROOT = Path(r"D:\vscode_projects\ee_download")
_TS_RE = re.compile(r"<\|(\d+)\.(\d{2})\|>")
CLAMP_BIN = 3999


def _bins(text: str) -> list[int]:
    return [int(m.group(1)) * 100 + int(m.group(2)) for m in _TS_RE.finditer(text)]


def _shift_text(text: str, delta: int) -> str:
    def sub(m):
        b = int(m.group(1)) * 100 + int(m.group(2)) - delta
        return f"<|{b // 100}.{b % 100:02d}|>"
    return _TS_RE.sub(sub, text)


def classify(text: str) -> str:
    """行分类:ok(首戳 0)/ shift(可精确平移)/ clamped(钳到末 bin,不可逆)/ no_stamp。"""
    bs = _bins(text)
    if not bs:
        return "no_stamp"
    if max(bs) >= CLAMP_BIN:
        return "clamped"
    if bs[0] == 0:
        return "ok"
    if any(b2 < b1 for b1, b2 in zip(bs, bs[1:])):
        return "nonmonotone"          # stamp_units 保单调,出现即上游异常 —— 同 clamped 处置
    return "shift"


def repair_row(row: dict) -> tuple[dict, str]:
    t = row.get("TAST")
    if not isinstance(t, str) or not t.strip():
        return row, "no_tast"
    kind = classify(t)
    if kind == "shift":
        row["TAST"] = _shift_text(t, _bins(t)[0])
    elif kind in ("clamped", "nonmonotone"):
        row["TAST"] = None            # 不可逆:退出 TAST 池,A2S/A2S_lite/音频保留
    return row, kind


def scan_or_apply(path: Path, apply: bool) -> dict:
    counts = {"rows": 0, "no_tast": 0, "no_stamp": 0, "ok": 0,
              "shift": 0, "clamped": 0, "nonmonotone": 0}
    out_lines = [] if apply else None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            counts["rows"] += 1
            row = json.loads(line)
            row, kind = repair_row(row)
            counts[kind] += 1
            if apply:
                out_lines.append(json.dumps(row, ensure_ascii=False))
    if apply:
        bak = path.with_suffix(".bak")
        if not bak.exists():          # 首次留原件;重复跑不覆盖首份备份
            shutil.copy2(path, bak)
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        tmp.replace(path)
    return counts


def main(argv=None):
    harden_stdout()
    ap = argparse.ArgumentParser(description="TAST 绝对戳→段内相对戳修复(默认干跑)")
    ap.add_argument("--labels", default=str(ROOT / "work" / "pdmx_perf_labels.jsonl"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.labels)
    if not path.exists():
        print(f"✗ 标签文件不存在: {path}")
        return 1
    c = scan_or_apply(path, apply=False)
    print(f"扫描 {path.name}:{c['rows']} 行")
    print(f"  首戳=0(本就对齐,单段曲)      : {c['ok']}")
    print(f"  可精确平移修复(整体减首戳)    : {c['shift']}")
    print(f"  已钳制/非单调 → TAST 置 null   : {c['clamped'] + c['nonmonotone']}"
          f"(clamped={c['clamped']} nonmono={c['nonmonotone']})")
    print(f"  无 TAST / 无戳                 : {c['no_tast']} / {c['no_stamp']}")
    if not args.apply:
        print("\n干跑结束(未改文件)。加 --apply 实施(留 .bak)。")
        return 0

    c2 = scan_or_apply(path, apply=True)
    # 复扫验证(D10 章程:清理/修复后必须贴全 0 残留表)
    resid = {"shift": 0, "clamped": 0, "nonmonotone": 0}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            t = json.loads(line).get("TAST")
            if isinstance(t, str) and t.strip():
                k = classify(t)
                if k in resid:
                    resid[k] += 1
    clean = all(v == 0 for v in resid.values())
    print("\n===== 修复验证(复扫)=====")
    for k, v in resid.items():
        print(f"  {'✓' if v == 0 else '✗'} 残留 {k} = {v}")
    print("  结论: " + ("【干净】" if clean else "【没修干净,贴回给规划端】"))
    print(f"\n已修 {c2['shift']} 行,置 null {c2['clamped'] + c2['nonmonotone']} 行(备份 {path.with_suffix('.bak').name})")
    print("下一步:sop_next --reset-step P6c(语料重建)→ P7(tokenizer)→ P8(装配)")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
