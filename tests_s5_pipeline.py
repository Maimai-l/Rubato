"""s5_vn_render 流水线接线的 mock 测试(不需真 VN/sfizz/partitura)。

真实进程池由 tests_ops.py 覆盖；这里把 pipeline_map 换成同进程调度器，专门验证
VN → MIDI/CSV → 渲染 → 切片 → 标签/续跑的生产接线。这样 Windows spawn 也会真正
执行测试，不再因为 monkeypatch 无法跨进程继承而整段跳过。
运行: python tests_s5_pipeline.py
"""
import sys, os, json, types, tempfile
sys.path.insert(0, ".")

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

import scripts.s5_vn_render as s5
import rubato.ops as ops
from fractions import Fraction as F


def inline_pipeline_map(items, gpu_stage, cpu_stage, *, n_cpu, on_result=None,
                        done_fn=None, key_fn=None, max_inflight=None,
                        weight_fn=None, budget_gb=None, initializer=None, initargs=(),
                        max_tasks_per_child=None, log=print, log_every=50):
    """Production-compatible sequential harness for wiring tests.

    It deliberately exercises the real gpu_stage/cpu_stage/on_result/done_fn
    callbacks. Process scheduling, memory admission and worker recycling are
    tested separately in tests_ops.py.
    """
    del n_cpu, key_fn, max_inflight, budget_gb, max_tasks_per_child, log, log_every
    items = list(items)
    stats = {"total": len(items), "done_skipped": 0, "dropped": 0,
             "ok": 0, "failed": 0, "peak_gb_est": 0.0}
    if initializer:
        initializer(*initargs)
    for item in items:
        if done_fn and done_fn(item):
            stats["done_skipped"] += 1
            continue
        mid = gpu_stage(item)
        if mid is None:
            stats["dropped"] += 1
            continue
        if weight_fn:
            stats["peak_gb_est"] = max(stats["peak_gb_est"], float(weight_fn(mid)))
        try:
            result = cpu_stage(mid)
            if on_result:
                on_result(item, result)
            stats["ok"] += 1
        except Exception:
            stats["failed"] += 1
    return stats


ops.pipeline_map = inline_pipeline_map

# 假 partitura:load_musicxml 返回带 .parts 的对象
fake_part = types.SimpleNamespace(notes=[], notes_tied=[])
fake_score = types.SimpleNamespace(parts=[fake_part])
sys.modules["partitura"] = types.SimpleNamespace(load_musicxml=lambda p: fake_score)

# 假 IR:两小节,便于 segment/make_labels 出一个段
from rubato.intermo.core import SPitch, Note, Measure, ScoreIR, TimeMap
FAKE_IR = ScoreIR([Note("PR", SPitch("C",0,4), F(0), F(1))],
                  [Measure(F(0),4,4,0), Measure(F(1),4,4,0),
                   Measure(F(2),4,4,0), Measure(F(3),4,4,0)], F(4))   # 4 小节:满足 R-S8.1 min=4

# [0] 先用【真函数】回归 _slice_audio 的 NameError(拆函数时 import soundfile 曾漏掉,执行端实测全崩)
print("[0] _slice_audio 真函数不再 NameError(注入假 soundfile)")
_writes = []
sys.modules["soundfile"] = types.SimpleNamespace(
    write=lambda p, a, s, **kw: _writes.append(p),   # format=FLAC 等关键字随真代码演进
    read=lambda p, dtype=None: ([0.0], 16000))
_tmp0 = tempfile.mkdtemp()
_out = s5._slice_audio([0.0] * (4 * 16000), 16000, 0.0, 3.0, os.path.join(_tmp0, "seg.opus"))
check("slice_audio_no_nameerror", _out is not None and _out.endswith(".flac"), _out)
check("slice_audio_wrote", len(_writes) == 1, _writes)
# 【2s 下限回归】用户定:<2s 即退化样本 —— 1 秒切片必须被拒(旧版 0.2s 保底是漏洞)
check("slice_under_2s_rejected",
      s5._slice_audio([0.0] * (4 * 16000), 16000, 0.0, 1.0, os.path.join(_tmp0, "s2.opus")) is None)

s5.part_to_ir = lambda part: FAKE_IR
s5.vn_infer = lambda xml, comp, mid: mid + "_midi_notes.csv"      # 假装 VN 成功产 CSV
s5.csv_to_tmap = lambda csv, part: (TimeMap([(F(0),0.0),(F(4),16.0)]), {})
s5.render_midi = lambda mid, utt, sc, pr, out, pick=None: open(out, "w").close() or out   # 假渲染:touch 文件(pick=二音色缝隙)
s5._read_audio = lambda path: ([0.1] * (17 * 16000), 16000)                    # 假整曲17s(≥tmap末端、非静音)
s5._slice_audio = lambda audio, sr, t0, t1, out, min_sec=2.0: (
    open(str(out).replace(".opus",".wav"),"w").close() or str(out).replace(".opus",".wav"))

tmp = tempfile.mkdtemp()
manifest = os.path.join(tmp, "m.jsonl")
with open(manifest, "w") as f:
    for pid in ("a", "b"):
        f.write(json.dumps({"piece_id": pid, "xml_raw": f"/fake/{pid}.xml"}) + "\n")
out_labels = os.path.join(tmp, "labels.jsonl")
out_corpus = os.path.join(tmp, "corpus.txt")
out_audio = os.path.join(tmp, "audio")

print("[1] 流水线跑通:两曲 → VN(gpu)→ 渲染(cpu 池)→ 标签落盘")
rep = s5.run(manifest, {"sources":{},"render":{}}, {"presets":{}}, out_labels, out_corpus,
             out_audio, n_cpu=2)
check("vn_ok_2", rep["vn_ok"] == 2, rep)
check("utts_written", rep["utts"] >= 2, rep)
rows = [json.loads(l) for l in open(out_labels) if l.strip()]
check("labels_have_tast", all(r.get("TAST") for r in rows), rows[:1])
check("labels_have_audio", all(r.get("audio_path", "").endswith(".wav") for r in rows), rows[:1])
check("corpus_written", os.path.getsize(out_corpus) > 0)
check("done_markers", os.path.exists(os.path.join(out_audio,"a.done")) and
                      os.path.exists(os.path.join(out_audio,"b.done")))
check("intermediates_cleaned",
      not os.path.exists(os.path.join(out_audio,"a_whole.opus")) and
      not os.path.exists(os.path.join(out_audio,"a_perf.mid")), os.listdir(out_audio))

print("[2] 续跑:.done 存在 → 全跳过,不重复写标签")
n_before = len(open(out_labels).readlines())
rep2 = s5.run(manifest, {"sources":{},"render":{}}, {"presets":{}}, out_labels, out_corpus,
              out_audio, n_cpu=2)
check("resume_no_new_utts", rep2["utts"] == 0, rep2)
check("labels_not_duplicated", len(open(out_labels).readlines()) == n_before)

print("[3] InferenceModel 只加载一次:引擎构造一次,每曲只前向(不重载)")
loads = {"n": 0}; infers = {"n": 0}
class FakeVNEngine:
    def __init__(self, ckpt, out_dir, device=None):
        loads["n"] += 1                                   # 构造(载模型)只应发生一次
    def infer(self, xml, composer):
        infers["n"] += 1
        mid = os.path.join(out_audio, "e.mid"); open(mid, "w").close()
        csv = mid + "_midi_notes.csv"; open(csv, "w").close()
        return mid, csv
s5.VNEngine = FakeVNEngine
os.environ["S5_VN_INPROCESS"] = "1"     # 走主进程内联(mock 的 VNEngine);子进程模式 spawn 收不到 monkeypatch
out2 = os.path.join(tmp, "audio2")
rep3 = s5.run(manifest, {"sources":{},"render":{}}, {"presets":{}},
              os.path.join(tmp,"l3.jsonl"), os.path.join(tmp,"c3.txt"),
              out2, n_cpu=2, vn_checkpoint="fake.pt")
check("engine_loaded_once", loads["n"] == 1, loads)          # 关键:模型只加载 1 次
check("inferred_per_piece", infers["n"] == 2, infers)        # 2 曲各前向 1 次(复用模型)
check("engine_vn_ok", rep3["vn_ok"] == 2, rep3)

print(f"\n全部通过: {PASS} 项")
