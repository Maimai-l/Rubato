"""
r3 收尾第 2 步:遗留 WAV 逐件转 FLAC + 标签路径原子改写 + 全量存在性核验。

三相,全部幂等可断点(交接文档下一步②③的机械化):
  相1 转换:标签引用的每个 .wav → 同名 .flac(soundfile 无损)→ 复读校验 → 删 .wav。
        逐件进行,盘上瞬时只多一件,不会撑爆 D:。
  相2 改写:所有 audio_path 以 .wav 结尾且 .flac 孪生在盘的标签行 → 改指 .flac
        (整文件 tmp+替换,.bak 留底)。中断重跑自愈(相1 跳过已转,相2 幂等)。
  相3 核验:逐行 audio 存在 + soundfile 可读,打印 flac/wav/缺失/不可读 四账。

用法(人手直接跑,无参数;可反复跑):
  python scripts/wav2flac_labels.py
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


def convert_one(wav: Path) -> tuple[bool, str]:
    """wav → 同名 flac(校验后删 wav)。已有 flac 则只删残留 wav。返回 (成功, 说明)。"""
    import soundfile as sf
    flac = wav.with_suffix(".flac")
    if not flac.exists():
        try:
            audio, sr = sf.read(str(wav), dtype="float32")
            sf.write(str(flac), audio, sr, format="FLAC")
            info = sf.info(str(flac))            # 复读校验:帧数一致才算成
            if info.frames != len(audio):
                flac.unlink(missing_ok=True)
                return False, "frames_mismatch"
        except Exception as e:
            flac.unlink(missing_ok=True)
            return False, f"{type(e).__name__}"
    try:
        wav.unlink()
    except OSError as e:
        return True, f"flac_ok_wav_undeleted:{type(e).__name__}"
    return True, "ok"


def main(argv=None):
    harden_stdout()
    import argparse
    ap = argparse.ArgumentParser(description="r3 遗留 WAV→FLAC + 标签改写 + 核验(幂等)")
    ap.add_argument("--labels", default=str(WORK / "pdmx_perf_labels_r3_native.staging.jsonl"))
    args = ap.parse_args(argv)
    lp = Path(args.labels)
    if not lp.exists():
        print(f"✗ 标签不存在: {lp}")
        return 1
    rows = list(read_jsonl(lp))

    # 相1 转换(只碰标签引用的 wav —— 不误伤别的目录)
    conv = fail = 0
    fails: list[str] = []
    for r in rows:
        apath = str(r.get("audio_path") or "")
        if not apath.lower().endswith(".wav"):
            continue
        wav = Path(apath)
        if not wav.exists():
            if wav.with_suffix(".flac").exists():
                continue                       # 已转(中断后重跑)
            continue                           # 真缺失 → 相3 记账
        ok, why = convert_one(wav)
        if ok:
            conv += 1
        else:
            fail += 1
            if len(fails) < 8:
                fails.append(f"{wav.name}:{why}")
    print(f"相1 转换: 新转 {conv} | 失败 {fail}" + (f" 例:{fails}" if fails else ""))

    # 相2 标签改写(整文件原子)
    changed = 0
    for r in rows:
        apath = str(r.get("audio_path") or "")
        if apath.lower().endswith(".wav") and Path(apath).with_suffix(".flac").exists():
            r["audio_path"] = str(Path(apath).with_suffix(".flac"))
            changed += 1
    if changed:
        bak = lp.with_suffix(lp.suffix + ".pre_flac.bak")
        if not bak.exists():
            bak.write_text(lp.read_text(encoding="utf-8"), encoding="utf-8")
        tmp = lp.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(lp)
    print(f"相2 改写: {changed} 行 → .flac" + (f"(备份 {lp.name}.pre_flac.bak)" if changed else ""))

    # 相3 核验
    import soundfile as sf
    n_flac = n_wav = n_missing = n_unreadable = 0
    for r in rows:
        apath = str(r.get("audio_path") or "")
        p = Path(apath)
        if not p.exists():
            n_missing += 1
            continue
        try:
            sf.info(str(p))
        except Exception:
            n_unreadable += 1
            continue
        if apath.lower().endswith(".flac"):
            n_flac += 1
        else:
            n_wav += 1
    print(f"相3 核验: 行 {len(rows)} | flac {n_flac} | 仍 wav {n_wav} | "
          f"缺失 {n_missing} | 不可读 {n_unreadable}")
    print("目标态: 仍wav=0 且 缺失/不可读 只剩真失败对应行(把这三行数字发回)")
    return 0 if (fail == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
