"""S8 装配层测试(补齐 labels→RubatoDataset 的缺失胶水)。运行: python tests_assemble.py"""
import json
import sys
from pathlib import Path
sys.path.insert(0, ".")
from rubato.data.assemble import normalize_row, assemble, partition_by_split, DIALECT_KEYS

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

TMP = Path("/tmp/claude-0/-home-user-Rubato/979b20cc-3d21-57cb-a889-5c21bf922d99/scratchpad")
TMP.mkdir(parents=True, exist_ok=True)

def write_jsonl(name, rows):
    p = TMP / name
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return str(p)


print("[1] schema 归一:三份来源键名不同,都要归到统一 schema")
# pdmx / nasap: utt_id + 四方言键
n1 = normalize_row({"utt_id": "pdmx_1_000", "A2S": "|4/4k0C4 1/4c4", "A2S_lite": "|4/4k0N60 1/4n60",
                    "TAST": None, "AMT": None}, "pdmx")
check("pdmx_uid", n1[0] == "pdmx_1_000")
check("pdmx_dialects", set(n1[1]) == {"A2S", "A2S_lite"}, n1[1])   # null 的被剔
# maestro: midi_file + amt_text(键名都不同!)
n2 = normalize_row({"midi_file": "2004/MIDI-Unprocessed_01.midi", "amt_text": "N60 <|0.50|>", "split": "train"}, "maestro")
check("maestro_uid_from_midi", n2[0].startswith("maestro_"), n2[0])
check("maestro_amt_mapped", n2[1].get("AMT") == "N60 <|0.50|>", n2[1])   # amt_text→AMT
check("maestro_split", n2[2] == "train")
# 不认识的行
check("bad_schema_none", normalize_row({"foo": "bar"}, "pdmx") is None)

print("[2] assemble:合并三源 + 音频配对 + dialect 推导 + 不静默计数")
pdmx = write_jsonl("pdmx.jsonl", [
    {"utt_id": "pdmx_1_000", "A2S": "|4/4k0C4 1/4c4", "A2S_lite": "|4/4k0N60 1/4n60", "TAST": None, "AMT": None},
    {"utt_id": "pdmx_2_000", "A2S": None, "A2S_lite": None, "TAST": None, "AMT": None},   # 无 dialect → 丢+计数
])
nasap = write_jsonl("nasap.jsonl", [
    {"utt_id": "nasap_x_000", "A2S": "|4/4k0C4 1/4c4", "A2S_lite": "|4/4k0N60 1/4n60", "TAST": "|4/4k0C4 <|0.00|> 1/4c4 <|0.50|>"},
])
maestro = write_jsonl("maestro.jsonl", [
    {"midi_file": "2004/a.midi", "amt_text": "N60 <|0.50|>", "split": "train"},
    {"midi_file": "2004/b.midi", "amt_text": "N62 <|0.30|>", "split": "test"},
    {"midi_file": "2004/c.midi", "amt_text": "N64 <|0.10|>", "split": "train"},   # 无音频 → 丢+计数
])

# fake resolver:pdmx_2 没标签就到不了这;maestro c 没音频
NO_AUDIO = {"maestro_2004_c_midi"}
def resolver(uid, kind, row):
    if uid in NO_AUDIO:
        return None
    return (f"/audio/{uid}.flac", 20.0)

sources = [
    {"path": pdmx, "kind": "pdmx", "domain": "synth"},
    {"path": nasap, "kind": "nasap", "domain": "real"},
    {"path": maestro, "kind": "maestro", "domain": "real"},
]
utts, labels, stats = assemble(sources, resolver)

# kept = pdmx_1, nasap_x, maestro_a, maestro_b(test 也保留,后面按 split 分区);
# pdmx_2 无 dialect、maestro_c 无音频 → 各丢 1(计数不静默)
check("kept_is_4", len(utts) == 4, [u["utt_id"] for u in utts])
check("no_dialect_counted", stats["per_source"]["pdmx"]["no_dialect"] == 1, stats["per_source"]["pdmx"])
check("no_audio_counted", stats["per_source"]["maestro"]["no_audio"] == 1, stats["per_source"]["maestro"])
check("labels_aligned", set(labels) == {u["utt_id"] for u in utts}, (set(labels), [u["utt_id"] for u in utts]))
check("dialects_on_utt", sorted(next(u for u in utts if u["utt_id"]=="nasap_x_000")["dialects"]) == ["A2S","A2S_lite","TAST"])
check("domain_carried", next(u for u in utts if u["kind"]=="pdmx")["domain"] == "synth")
check("audio_paired", all(u["audio_path"] and u["dur_s"] == 20.0 for u in utts))

print("[3] 不静默:每一步丢弃都进 stats,加总守恒")
for kind in ("pdmx", "nasap", "maestro"):
    s = stats["per_source"][kind]
    check(f"{kind}_conserves", s["rows"] == s["kept"] + s["bad_schema"] + s["no_dialect"] + s["no_audio"] + s["dup"], s)

print("[4] split 分区(maestro 的 test 不进 train)")
part = partition_by_split(utts)
check("train_has_pdmx_nasap", any(u["kind"]=="pdmx" for u in part["train"]) and any(u["kind"]=="nasap" for u in part["train"]))
check("test_isolated", [u["utt_id"] for u in part["test"]] == ["maestro_2004_b_midi"], part["test"])

print("[5] 产物能直接构造 RubatoDataset(接口对齐)")
from rubato.data.dataset import RubatoDataset
class MockTok:
    def encode(self, text, out_type=str, enable_sampling=False, alpha=0.1, nbest_size=-1):
        return text.split()
    def piece_to_id(self, p): return 7
ds = RubatoDataset(utts, labels, MockTok(), train=True)
check("dataset_builds", len(ds) > 0, len(ds))
check("dataset_available_dialects", all(any(d in labels[u] for d in DIALECT_KEYS) for u in labels))

print("[6] 重复 utt_id 被计数不覆盖")
dup_src = write_jsonl("dup.jsonl", [
    {"utt_id": "dup_1", "A2S": "|4/4k0C4 1/4c4"},
    {"utt_id": "dup_1", "A2S": "|4/4k0D4 1/4d4"},   # 撞名
])
u2, l2, s2 = assemble([{"path": dup_src, "kind": "pdmx", "domain": "synth"}], resolver)
check("dup_counted", s2["per_source"]["pdmx"]["dup"] == 1, s2["per_source"]["pdmx"])
check("dup_kept_first", len(u2) == 1 and l2["dup_1"]["A2S"] == "|4/4k0C4 1/4c4", l2)

print("[X] row_fn:行级注入 split + 黑名单过滤(filtered 计数,不静默)")
import json as _json, tempfile as _tf, os as _os
_d = _tf.mkdtemp()
_lp = _os.path.join(_d, "rf.jsonl")
with open(_lp, "w", encoding="utf-8") as f:
    f.write(_json.dumps({"utt_id": "pdmx_A_000", "piece_id": "A", "A2S": "x"}) + "\n")
    f.write(_json.dumps({"utt_id": "pdmx_B_000", "piece_id": "B", "A2S": "y"}) + "\n")
def _rf(row):
    if row.get("piece_id") == "B":
        return None                      # 黑名单
    row["split"] = "val"                 # manifest 注入
    return row
_u, _l, _st = assemble([{"path": _lp, "kind": "pdmx", "domain": "synth", "row_fn": _rf}],
                       lambda uid, kind, row: ("a.flac", 3.0))
check("rowfn_filtered", _st["per_source"]["pdmx"]["filtered"] == 1, _st)
check("rowfn_split_injected", _u[0]["split"] == "val" and len(_u) == 1, _u)

print("[7] 训练入口只可使用 val；test 必须完整保留给正式终评")
from scripts.build_dataset import (
    select_training_partitions, validate_assembly_for_training, validate_cli_args)
_parts = {
    "train": [{"utt_id": "tr", "kind": "pdmx"}],
    "val": [{"utt_id": "nv", "kind": "nasap"},
            {"utt_id": "mv", "kind": "maestro"}],
    "test": [{"utt_id": "nt", "kind": "nasap"},
             {"utt_id": "mt", "kind": "maestro"}],
}
_tr, _nv, _mv, _nt, _mt = select_training_partitions(_parts)
check("val_test_not_merged",
      [u["utt_id"] for u in _nv] == ["nv"]
      and [u["utt_id"] for u in _mv] == ["mv"])
check("test_reserved_for_final",
      [u["utt_id"] for u in _nt] == ["nt"]
      and [u["utt_id"] for u in _mt] == ["mt"])

print("[8] 非空源 kept=0 是硬错误，不是打印后继续")
try:
    validate_assembly_for_training({
        "per_source": {"nasap": {"rows": 10, "kept": 0, "no_audio": 10,
                                  "no_dialect": 0, "filtered": 0}}})
    _hard_gate = False
except RuntimeError:
    _hard_gate = True
check("zero_kept_aborts", _hard_gate)
validate_assembly_for_training({
    "per_source": {"nasap": {"rows": 10, "kept": 9, "no_audio": 1}}})
check("nonzero_kept_passes", True)
try:
    validate_assembly_for_training({
        "per_source": {"pdmx": {"rows": 20, "kept": 10}},
        "per_file": {
            "good.jsonl": {"kind": "pdmx", "rows": 10, "kept": 10},
            "dead.jsonl": {"kind": "pdmx", "rows": 10, "kept": 0,
                           "no_audio": 10},
        }})
    _file_gate = False
except RuntimeError:
    _file_gate = True
check("per_file_zero_not_hidden_by_same_kind", _file_gate)

print("[9] CLI 数值参数启动前校验")
from types import SimpleNamespace
_cli = SimpleNamespace(
    max_batch_sec=60, clip_norm=1, eval_max=48, eval_every=1000,
    smoke_steps=800, probe_n=8, abtest_n=48, smoke=0, prefetch=0,
    eval_decode_every=0, pitch_loss_weight=1, lr_enc=None, lr_dec=None)
validate_cli_args(_cli)
check("valid_cli_passes", True)
try:
    validate_cli_args(SimpleNamespace(**{**vars(_cli), "eval_every": 0}))
    _cli_gate = False
except ValueError:
    _cli_gate = True
check("zero_eval_every_rejected", _cli_gate)

print(f"\n全部通过: {PASS} 项")
