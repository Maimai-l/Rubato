"""训练前审计三修复的回归:_shift_tmap 秒轴归零、s7 win、eval hook 契约、TAST 修复脚本。
运行: python tests_tast_repair.py"""
import json
import sys
import tempfile
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, ".")
import numpy as np

from rubato.intermo.core import Note, Measure, ScoreIR, SPitch, TimeMap
from rubato.data.segment import make_labels, _slice_ir, _shift_tmap
import scripts.repair_tast_labels as rt

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


def make_ir(n_measures):
    mlen = F(4, 4)
    measures = [Measure(i * mlen, 4, 4, 0) for i in range(n_measures)]
    notes = []
    for i in range(n_measures):
        for j in range(2):
            notes.append(Note("PR", SPitch("CDEFGAB"[(i + j) % 7], 0, 4),
                              i * mlen + j * mlen / 2, mlen / 2))
    return ScoreIR(notes, measures, n_measures * mlen)


_TSRE = rt._TS_RE


def bins_of(text):
    return [int(m.group(1)) * 100 + int(m.group(2)) for m in _TSRE.finditer(text)]


print("[1] _shift_tmap 秒轴归零:段起点 >0 的 TAST 首戳必须是 0.00(旧版=绝对演奏秒)")
ir = make_ir(20)
# 演奏:前 60s 弹前 10 小节,后 20s 弹后 10 小节(变速);段 [10,20) 在绝对 60s 起
tmap = TimeMap([(F(0), 0.0), (F(10), 60.0), (F(20), 80.0)])
sub, off = _slice_ir(ir, 10, 20)
check("slice_offset", off == F(10))
local = _shift_tmap(sub, tmap, off)
check("local_zero", abs(float(local(F(0)))) < 1e-9, float(local(F(0))))
check("local_end", abs(float(local(sub.score_end)) - 20.0) < 1e-6, float(local(sub.score_end)))
labels, fails = make_labels(sub, "nasap", tmap=tmap, score_offset=off)
tb = bins_of(labels["TAST"])
check("tast_first_stamp_zero", tb and tb[0] == 0, tb[:3])
check("tast_within_window", max(tb) <= 2000 + 1, max(tb))   # 段长 20s → 全部 ≤2000 bin
check("tast_not_clamped", max(tb) < 3999, max(tb))          # 旧版:绝对 60-80s 全钳 3999

print("[2] 开头留白(nASAP 常见):offset=0 但 tmap(0)=2.5s,戳仍从 0 起(相对窗读音频)")
tmap2 = TimeMap([(F(0), 2.5), (F(20), 42.5)])
local2 = _shift_tmap(ir, tmap2, F(0))
check("lead_silence_rebased", abs(float(local2(F(0)))) < 1e-9, float(local2(F(0))))
labels2, _ = make_labels(ir, "nasap", tmap=tmap2, score_offset=F(0))
tb2 = bins_of(labels2["TAST"])
check("lead_first_zero", tb2 and tb2[0] == 0, tb2[:3])

print("[3] 修复脚本:平移/钳制/本就对齐 三类行的精确处置")
tmp = Path(tempfile.mkdtemp())
lab = tmp / "pdmx_perf_labels.jsonl"
rows = [
    {"utt_id": "u_ok",    "TAST": "<|0.00|>x <|1.50|>y", "A2S": "a"},
    {"utt_id": "u_shift", "TAST": "<|10.00|>x <|25.25|>y", "A2S": "a"},
    {"utt_id": "u_clamp", "TAST": "<|55.00|>x <|39.99|>y <|39.99|>z", "A2S": "a"},
    {"utt_id": "u_none",  "TAST": None, "A2S": "a"},
]
# u_clamp 首戳 55>39.99?造更真实的:首戳已在 40s 后 → 单调钳制使全部=3999
rows[2]["TAST"] = "<|39.99|>x <|39.99|>y <|39.99|>z"
lab.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
check("dry_rc0", rt.main(["--labels", str(lab)]) == 0)
check("dry_untouched", json.loads(lab.read_text().splitlines()[1])["TAST"].startswith("<|10.00|>"))
check("apply_rc0", rt.main(["--labels", str(lab), "--apply"]) == 0)
got = {json.loads(l)["utt_id"]: json.loads(l) for l in lab.read_text().splitlines() if l.strip()}
check("ok_untouched", got["u_ok"]["TAST"] == "<|0.00|>x <|1.50|>y")
check("shift_exact", got["u_shift"]["TAST"] == "<|0.00|>x <|15.25|>y", got["u_shift"]["TAST"])
check("clamped_nulled", got["u_clamp"]["TAST"] is None)
check("a2s_kept", all(got[u]["A2S"] == "a" for u in got))
check("bak_exists", lab.with_suffix(".bak").exists())

print("[4] eval hook 契约:assemble 的 utt dict(audio_path/win)直接可用,无参照不打 0 分")
import soundfile as sf
from rubato.model.train import run_eval_hooks, _eval_subset, _sample_audio

wav = tmp / "full.flac"
sr = 16000
sf.write(str(wav), np.zeros(sr * 10, dtype="float32"), sr)   # 10s 整曲
n_utt = {"utt_id": "nasap_x_000", "kind": "nasap", "audio_path": str(wav),
         "win": [2.0, 6.0], "dur_s": 4.0, "dialects": ["A2S", "TAST"], "split": "val"}
m_utt = {"utt_id": "maestro_y_000", "kind": "maestro", "audio_path": str(wav),
         "win": [0.0, 5.0], "dur_s": 5.0, "dialects": ["AMT"], "split": "test"}
a = _sample_audio(n_utt)
check("win_read_len", a is not None and abs(len(a) - 4 * sr) <= 2, None if a is None else len(a))

# model=None:infer 全兜底 → 不崩、可解析率 0、empty_rate=1;maestro 无 AMT 参照 → F1 None(不是 0)
m = run_eval_hooks(None, [n_utt], [m_utt], tokenizer=None, labels={"nasap_x_000": {"A2S": "|4/4k0"}})
check("no_keyerror", isinstance(m, dict))
check("empty_rate_1", m["empty_rate"] == 1.0, m)
check("no_ref_no_zero_poison", m["maestro_amt_f1"] is None, m)   # 旧版会算 0 分触发 8000 步停训
check("n_eval_counted", m["n_eval_nasap"] == 1 and m["n_eval_maestro"] == 0, m)

# 有 AMT 参照:model=None 预测为空 → F1=0.0 是【正确】的差成绩(有参照就该记分)
from rubato.intermo.core import perf_to_amt
from rubato.model.evaluate import amt_text_to_notes
ref_amt, _st = perf_to_amt([{"pitch": 60, "on": 0.5, "off": 1.5, "vel": 70}], [])
check("ref_amt_parses", len(amt_text_to_notes(ref_amt)) == 1, ref_amt)
m2 = run_eval_hooks(None, [], [m_utt], tokenizer=None, labels={"maestro_y_000": {"AMT": ref_amt}})
check("ref_scored", m2["maestro_amt_f1"] == 0.0 and m2["n_eval_maestro"] == 1, m2)

print("[5] eval 子集:确定性 + 截断")
samples = [{"utt_id": f"u{i}"} for i in range(50)]
s1 = _eval_subset(samples, 8)
s2 = _eval_subset(list(reversed(samples)), 8)
check("subset_cap", len(s1) == 8)
check("subset_deterministic", [s["utt_id"] for s in s1] == [s["utt_id"] for s in s2])
check("subset_passthrough", _eval_subset(samples, 0) is samples)

print("[6] nASAP split 后置分配:val/test 非空、work_key 隔离、幂等")
import scripts.s7_assign_split as sp

nl = tmp / "nasap_labels.jsonl"
rows_n = []
for w in range(12):                       # 12 个作品,每作品 2 演奏 × 4 段
    for perf in ("PerfA", "PerfB"):
        for si in range(4):
            rows_n.append({"utt_id": f"nasap_{perf}{w:02d}_piece{w:02d}_{si:03d}",
                           "work_key": f"comp{w}|title{w}", "A2S": "|4/4k0",
                           "win": [si * 10.0, si * 10.0 + 8.0]})
nl.write_text("\n".join(json.dumps(r) for r in rows_n) + "\n", encoding="utf-8")
mani = tmp / "nasap_split.json"
check("sp_dry_rc0", sp.main(["--labels", str(nl), "--val-target", "16"]) == 0)
check("sp_dry_untouched", "split" not in json.loads(nl.read_text().splitlines()[0]))
check("sp_apply_rc0", sp.main(["--labels", str(nl), "--val-target", "16",
                               "--manifest-out", str(mani), "--apply"]) == 0)
got_n = [json.loads(l) for l in nl.read_text().splitlines() if l.strip()]
splits = {}
wk_splits = {}
for r in got_n:
    splits[r["split"]] = splits.get(r["split"], 0) + 1
    wk_splits.setdefault(r["work_key"], set()).add(r["split"])
check("sp_all_assigned", sum(splits.values()) == len(rows_n), splits)
check("sp_val_nonempty", splits.get("val", 0) >= 16, splits)
check("sp_test_nonempty", splits.get("test", 0) > 0, splits)
check("sp_isolation", all(len(s) == 1 for s in wk_splits.values()),
      {k: v for k, v in wk_splits.items() if len(v) > 1})
check("sp_manifest", json.loads(mani.read_text())["val_segments"] >= 16)
# 幂等:重跑 --apply,分配不变(确定性 hash)
first = {r["utt_id"]: r["split"] for r in got_n}
sp.main(["--labels", str(nl), "--val-target", "16", "--manifest-out", str(mani), "--apply"])
second = {json.loads(l)["utt_id"]: json.loads(l)["split"]
          for l in nl.read_text().splitlines() if l.strip()}
check("sp_idempotent", first == second)

print(f"\n全部通过: {PASS} 项")
