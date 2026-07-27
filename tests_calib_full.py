"""校准全量四件套的沙盒测试(配对枚举 / 转写驱动 / 批量推理入口 / 打分驱动)。

真 transkun/M2ST/LEGATO 都不在沙盒 —— 测的是我们这层的全部逻辑:
split 过滤与单元聚合、缺失检测、断点续跑、自检门、口径换算、预登记判决、报告落盘。
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def _mkworld(tmp: Path):
    """假 WORK + 假 ASAP:2 个 test 单元(1 个缺参考谱)+ train/quarantine 干扰行。"""
    work = tmp / "work"
    (work / "maestro_audio").mkdir(parents=True)
    asap = tmp / "asap"
    (asap / "Bach" / "P1").mkdir(parents=True)
    (asap / "Bach" / "P1" / "xml_score.musicxml").write_text("<score>A</score>", encoding="utf-8")
    (work / "maestro_audio" / "perfA.flac").write_bytes(b"x" * 8)
    (work / "maestro_audio" / "perfB.flac").write_bytes(b"y" * 8)
    rows = [
        # 单元1:两段(聚合成一对)
        {"utt_id": "nasap_pA_s1_000", "split": "test", "audio_path": "{maestro}/2006/perfA.wav",
         "xml_score": "Bach/P1/xml_score.musicxml"},
        {"utt_id": "nasap_pA_s1_001", "split": "test", "audio_path": "{maestro}/2006/perfA.wav",
         "xml_score": "Bach/P1/xml_score.musicxml"},
        # 单元2:参考谱不存在 → 缺参考谱
        {"utt_id": "nasap_pB_s1_000", "split": "test", "audio_path": "{maestro}/2006/perfB.wav",
         "xml_score": "Bach/P9/xml_score.musicxml"},
        # 干扰:train 与 quarantine_leak 都必须被无视
        {"utt_id": "nasap_pC_s1_000", "split": "train", "audio_path": "{maestro}/2006/perfA.wav",
         "xml_score": "Bach/P1/xml_score.musicxml"},
        {"utt_id": "nasap_pD_s1_000", "split": "quarantine_leak",
         "audio_path": "{maestro}/2006/perfA.wav", "xml_score": "Bach/P1/xml_score.musicxml"},
    ]
    with open(work / "nasap_labels.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return work, asap


def _run(script: str, extra, env_add):
    env = dict(os.environ)
    env.update(env_add)
    return subprocess.run([PY, str(ROOT / "scripts" / script), *extra],
                          capture_output=True, text=True, env=env, cwd=str(ROOT))


def test_pairs_enumeration():
    with tempfile.TemporaryDirectory() as td:
        work, asap = _mkworld(Path(td))
        r = _run("calib_pairs.py", [], {"RUBATO_WORK": str(work), "RUBATO_ASAP": str(asap)})
        assert r.returncode == 0, r.stdout + r.stderr
        assert "配对成功 1" in r.stdout and "缺参考谱 1" in r.stdout, r.stdout
        assert "单元 2" in r.stdout, r.stdout          # train/quarantine 行没混进来
        pairs = [json.loads(l) for l in open(work / "calib_pairs.jsonl", encoding="utf-8")]
        assert len(pairs) == 1 and pairs[0]["perf_id"] == "nasap_pA_s1"
        assert pairs[0]["n_segments"] == 2
        assert pairs[0]["flac"].endswith("perfA.flac")


def test_transkun_resume_and_fail():
    with tempfile.TemporaryDirectory() as td:
        work, asap = _mkworld(Path(td))
        # 两对:pA 已有产物(应跳过);pB 由假 transkun 生成
        (asap / "Bach" / "P9").mkdir(parents=True)
        (asap / "Bach" / "P9" / "xml_score.musicxml").write_text("<score>B</score>", encoding="utf-8")
        pairs = [
            {"perf_id": "nasap_pA_s1", "flac": str(work / "maestro_audio" / "perfA.flac"),
             "ref_xml": str(asap / "Bach" / "P1" / "xml_score.musicxml"), "n_segments": 2},
            {"perf_id": "nasap_pB_s1", "flac": str(work / "maestro_audio" / "perfB.flac"),
             "ref_xml": str(asap / "Bach" / "P9" / "xml_score.musicxml"), "n_segments": 1},
        ]
        with open(work / "calib_pairs.jsonl", "w", encoding="utf-8") as f:
            for p in pairs:
                f.write(json.dumps(p) + "\n")
        out_dir = work / "calib_full"
        out_dir.mkdir()
        (out_dir / "nasap_pA_s1.mid").write_bytes(b"MThd")      # 已完成 → 跳过
        stub = Path(td) / "fake_transkun.py"
        stub.write_text("import sys;open(sys.argv[2],'wb').write(b'MThd');print('ok')",
                        encoding="utf-8")
        sh = Path(td) / ("transkun.cmd" if os.name == "nt" else "transkun")
        if os.name == "nt":
            sh.write_text(f'@"{PY}" "{stub}" %*\n', encoding="utf-8")
        else:
            sh.write_text(f"#!/bin/sh\nexec {PY} {stub} \"$@\"\n",
                          encoding="utf-8")
        sh.chmod(sh.stat().st_mode | stat.S_IEXEC)
        r = _run("calib_transkun.py", ["--transkun", str(sh)], {"RUBATO_WORK": str(work)})
        assert r.returncode == 0, r.stdout + r.stderr
        assert "新 1 / 跳过 1 / 失败 0" in r.stdout, r.stdout
        assert (out_dir / "nasap_pB_s1.mid").stat().st_size > 0


def test_m2st_all_mids_arg_guard():
    with tempfile.TemporaryDirectory() as td:
        empty = Path(td) / "mids"
        empty.mkdir()
        m2st = Path(td) / "m2st"
        (m2st / "midi2scoretransformer").mkdir(parents=True)
        r = subprocess.run([PY, str(ROOT / "scripts" / "calib_m2st_infer.py"),
                            "--m2st-dir", str(m2st), "--ckpt", "x.ckpt",
                            "--in-dir", str(empty), "--out-dir", str(empty), "--all-mids"],
                           capture_output=True, text=True)
        assert r.returncode == 2 and "没有 *.mid" in r.stdout, r.stdout + r.stderr
        r2 = subprocess.run([PY, str(ROOT / "scripts" / "calib_m2st_infer.py"),
                             "--m2st-dir", str(m2st), "--ckpt", "x.ckpt",
                             "--in-dir", str(empty), "--out-dir", str(empty)],
                            capture_output=True, text=True)
        assert r2.returncode == 2 and "二选一" in r2.stdout, r2.stdout + r2.stderr


def _score_world(td: Path, stub_body: str):
    """搭打分现场:1 对配对 + est xml + 假 LEGATO 脚本。返回 (work, report, legato)。"""
    work = td / "work"
    (work / "calib_full_xml").mkdir(parents=True)
    ref = td / "ref.xml"
    ref.write_text("<score>REF</score>", encoding="utf-8")
    est = work / "calib_full_xml" / "nasap_pA_s1.xml"
    est.write_text("<score>EST</score>", encoding="utf-8")
    with open(work / "calib_pairs.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"perf_id": "nasap_pA_s1", "flac": "无关",
                            "ref_xml": str(ref), "n_segments": 1}) + "\n")
    legato = td / "compute_OMR-NED.py"
    legato.write_text(stub_body, encoding="utf-8")
    return work, td / "CALIB_FULL.txt", legato


# 仿真 LEGATO 官方 compute_OMR-NED.py 的真实接口(执行端适配后的口径,D59 追认):
# --prediction_file/--ground_truth 各是一个 JSON 列表(XML 文本内容),脚本把结果写到
# <prediction_file 同目录>/ref_preds/<prediction_file 词干>/output/output.csv,
# 列名精确为 "OMR-NED (OMR-ED / total numsyms)",汇总行首格 "Total:"。
_STUB_100 = """import argparse, csv, json
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("--prediction_file", required=True)
ap.add_argument("--ground_truth", required=True)
ap.add_argument("--prediction_type", required=True)
a = ap.parse_args()
pred = json.loads(Path(a.prediction_file).read_text(encoding="utf-8"))
ref = json.loads(Path(a.ground_truth).read_text(encoding="utf-8"))
score = 0.0 if pred == ref else 68.5
outdir = Path(a.prediction_file).parent / "ref_preds" / Path(a.prediction_file).stem / "output"
outdir.mkdir(parents=True)
with open(outdir / "output.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["name", "OMR-NED (OMR-ED / total numsyms)"])
    w.writerow(["item0", str(score)])
    w.writerow(["Total:", str(score)])
print("done")
"""
_STUB_01 = _STUB_100.replace("68.5", "0.685")
_STUB_BAD = "import sys; sys.exit(3)\n"


def test_score_pass_verdict_and_report():
    with tempfile.TemporaryDirectory() as td:
        work, rp, legato = _score_world(Path(td), _STUB_100)
        r = _run("calib_score.py", ["--legato-script", str(legato), "--report", str(rp)],
                 {"RUBATO_WORK": str(work)})
        assert r.returncode == 0, r.stdout + r.stderr
        assert "自检通过" in r.stdout, r.stdout
        txt = rp.read_text(encoding="utf-8")
        assert "均值 68.50" in txt and "判决" in txt and "通过" in txt, txt
        assert "预登记" in txt


def test_score_scale_01_and_selfcheck_gate():
    with tempfile.TemporaryDirectory() as td:
        work, rp, legato = _score_world(Path(td), _STUB_01)
        r = _run("calib_score.py", ["--legato-script", str(legato), "--report", str(rp)],
                 {"RUBATO_WORK": str(work)})
        assert r.returncode == 0, r.stdout + r.stderr
        txt = rp.read_text(encoding="utf-8")
        assert "均值 68.50" in txt and "×100" in txt, txt        # 0-1 口径换算生效
    with tempfile.TemporaryDirectory() as td:
        work, rp, legato = _score_world(Path(td), _STUB_BAD)
        r = _run("calib_score.py", ["--legato-script", str(legato), "--report", str(rp)],
                 {"RUBATO_WORK": str(work)})
        assert r.returncode == 1 and "自检失败" in r.stdout, r.stdout
        assert not rp.exists()                                    # 自检不过 → 不产报告


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        t0 = time.time()
        try:
            fn()
            print(f"  ok {fn.__name__} ({time.time()-t0:.1f}s)")
        except Exception as e:
            bad += 1
            import traceback
            print(f"  FAIL {fn.__name__}: {e}")
            traceback.print_exc(limit=4)
    print(("PASS" if not bad else "FAIL") + f" {len(fns)-bad}/{len(fns)}")
    sys.exit(1 if bad else 0)
