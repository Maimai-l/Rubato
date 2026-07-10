"""s5_vn_render 流水线接线的 mock 测试(不需真 VN/sfizz/partitura)。
用 fork 让主进程 monkeypatch 的模块函数传到 worker。运行: python tests_s5_pipeline.py"""
import sys, os, json, types, tempfile, multiprocessing
sys.path.insert(0, ".")

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

if sys.platform.startswith("win"):
    print("  skip  Windows spawn 不继承 monkeypatch;此接线测试仅在 fork 平台跑")
    print("\n全部通过: 0 项(skipped)")
    raise SystemExit(0)
try:
    multiprocessing.set_start_method("fork")
except RuntimeError:
    pass

import scripts.s5_vn_render as s5
from fractions import Fraction as F

# 假 partitura:load_musicxml 返回带 .parts 的对象
fake_part = types.SimpleNamespace(notes=[], notes_tied=[])
fake_score = types.SimpleNamespace(parts=[fake_part])
sys.modules["partitura"] = types.SimpleNamespace(load_musicxml=lambda p: fake_score)

# 假 IR:两小节,便于 segment/make_labels 出一个段
from rubato.intermo.core import SPitch, Note, Measure, ScoreIR, TimeMap
FAKE_IR = ScoreIR([Note("PR", SPitch("C",0,4), F(0), F(1))],
                  [Measure(F(0),4,4,0), Measure(F(1),4,4,0)], F(2))

s5.part_to_ir = lambda part: FAKE_IR
s5.vn_infer = lambda xml, comp, mid: mid + "_midi_notes.csv"      # 假装 VN 成功产 CSV
s5.csv_to_tmap = lambda csv, part: (TimeMap([(F(0),0.0),(F(2),16.0)]), {})
s5.render_midi = lambda mid, utt, sc, pr, out: open(out, "w").close() or out   # 假渲染:touch 文件
s5._slice_audio = lambda whole, t0, t1, out: (open(str(out).replace(".opus",".wav"),"w").close()
                                              or str(out).replace(".opus",".wav"))

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
out2 = os.path.join(tmp, "audio2")
rep3 = s5.run(manifest, {"sources":{},"render":{}}, {"presets":{}},
              os.path.join(tmp,"l3.jsonl"), os.path.join(tmp,"c3.txt"),
              out2, n_cpu=2, vn_checkpoint="fake.pt")
check("engine_loaded_once", loads["n"] == 1, loads)          # 关键:模型只加载 1 次
check("inferred_per_piece", infers["n"] == 2, infers)        # 2 曲各前向 1 次(复用模型)
check("engine_vn_ok", rep3["vn_ok"] == 2, rep3)

print(f"\n全部通过: {PASS} 项")
