"""
pdmxperf 二音色(s5_vn_render --second-timbre)纯逻辑判决性测试:
第二源绝不撞原源(原源键=裸 pid,与 C3 的 f"pdmx_{pid}" 区分)/ pick 缝隙真正生效
且绕过哈希 / 入选圈 = 一轮成功曲 × train / CLI 默认切换与 staging 红线。
(VN 推理与渲染本体在执行端环境,沙盒不在此测。)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from scripts import s5_vn_render as s5

SCFG = {"sources": {"S1": {"ratio": 0.4}, "S2": {"ratio": 0.3},
                    "S3": {"ratio": 0.2}, "S4": {"ratio": 0.1}}}
PCFG = {"seed": 7, "weights": {"p1": 0.5, "p2": 0.3, "p3": 0.2},
        "presets": {"p1": {"tag": 1}, "p2": {"tag": 2}, "p3": {"tag": 3}}}


def test_choose_second_bare_pid_key_and_deterministic():
    from rubato.render.core import assign_source_and_preset
    seen_src2 = set()
    for pid in (f"Qm{i}" for i in range(60)):
        orig, src2, preset2 = s5._choose_second_s5(pid, SCFG, PCFG)
        assert orig == assign_source_and_preset(pid, SCFG, PCFG)[0], "原源键必须是裸 pid(S5 线约定)"
        assert src2 != orig, f"{pid}: 第二源撞回原源 {src2}"
        assert src2 in SCFG["sources"] and preset2 in PCFG["weights"]
        assert (orig, src2, preset2) == s5._choose_second_s5(pid, SCFG, PCFG)  # 确定性
        seen_src2.add(src2)
    assert len(seen_src2) >= 3, "60 曲第二源应覆盖多个源(加权抽签在工作)"


def test_render_midi_pick_bypasses_hash():
    calls = {}
    orig_render, orig_final, orig_assign = (
        s5.render_midi_to_wav44, s5.finalize, s5.assign_source_and_preset)
    try:
        s5.render_midi_to_wav44 = lambda mp, source, scfg, wav, utt_id=None: \
            calls.setdefault("source", source)
        s5.finalize = lambda wav, preset, scfg, pcfg, utt_id, out: \
            calls.setdefault("preset", preset)
        s5.assign_source_and_preset = \
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("pick 模式不应咨询哈希"))
        s5.render_midi("x.mid", "PIDX", SCFG, PCFG, "out.opus", pick=("S3", "p2"))
    finally:
        s5.render_midi_to_wav44, s5.finalize, s5.assign_source_and_preset = (
            orig_render, orig_final, orig_assign)
    assert calls["source"] is SCFG["sources"]["S3"]
    assert calls["preset"] == {"tag": 2}


def test_s2_filter_base_and_train_only():
    pieces = [
        {"piece_id": "a", "split": "train"},   # 基线有 + train → 入
        {"piece_id": "b"},                     # 基线有 + 缺 split(装配器同约定=train)→ 入
        {"piece_id": "c", "split": "test"},    # 基线有 + test → 冻结,出局
        {"piece_id": "d", "split": "train"},   # 基线没有(一轮失败曲)→ 出局
    ]
    got = s5._s2_filter(pieces, {"a", "b", "c"})
    assert [p["piece_id"] for p in got] == ["a", "b"]


def test_main_s2_defaults_and_staging_guard():
    captured = {}
    orig_run = s5.run
    try:
        s5.run = lambda *a, **k: captured.update(k, _pos=a) or {"utts": 0}
        rc = s5.main(["--second-timbre"])
        assert rc == 0
        labels, corpus, audio_dir = captured["_pos"][3], captured["_pos"][4], captured["_pos"][5]
        assert str(labels).endswith("pdmx_perf_labels_s2.staging.jsonl"), labels
        assert corpus == "", "二音色不写语料(分词器已冻结)"
        assert str(audio_dir).endswith("pdmx_audio_s2"), audio_dir
        assert captured["second_timbre"] is True
        assert str(captured["base_labels"]).endswith("pdmx_perf_labels.jsonl")
        # staging 红线:显式给非 staging 名必须拒绝,且不进 run
        captured.clear()
        rc2 = s5.main(["--second-timbre", "--out-labels", "D:/x/pdmx_perf_labels_s2.jsonl"])
        assert rc2 == 2 and not captured, "非 staging 名必须被拒"
        # 普通模式回归:默认输出不变、模式关闭
        captured.clear()
        rc3 = s5.main([])
        assert rc3 == 0 and captured["second_timbre"] is False
        assert str(captured["_pos"][3]).endswith("pdmx_perf_labels.jsonl")
        assert captured["base_labels"] is None
    finally:
        s5.run = orig_run


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
