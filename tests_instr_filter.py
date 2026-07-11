"""乐器过滤 + 可验证清理 + 语料重建 回归测试。运行: python tests_instr_filter.py"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, ".")
import mido

from rubato.data.pdmx import classify_musicxml_text, classify_score_file, classify_midi_file
from rubato.data.cleanup import piece_files, purge_pieces, verify_pieces, format_verify
import scripts.s3_instrument_audit as audit
import scripts.cleanup_pieces as clp
import scripts.rebuild_corpus as rbc

PASS = 0


def check(name, cond, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        raise SystemExit(1)


tmp = Path(tempfile.mkdtemp())

PIANO_XML = """<score-partwise><part-list><score-part id="P1"><part-name>Piano</part-name>
<midi-instrument><midi-channel>1</midi-channel><midi-program>1</midi-program></midi-instrument>
</score-part></part-list><part id="P1"><measure number="1">
<attributes><clef><sign>G</sign></clef></attributes>
<note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note>
</measure></part></score-partwise>"""

DRUM_XML = PIANO_XML.replace("<pitch><step>C</step><octave>4</octave></pitch>",
                             "<unpitched><display-step>E</display-step></unpitched>")

print("[1] 谱面判定:钢琴过、鼓/打击谱号/TAB/10通道/非键盘音色/乐器名全拦")
check("piano_ok", classify_musicxml_text(PIANO_XML) == (True, "ok"))
check("unpitched", classify_musicxml_text(DRUM_XML)[1] == "percussion_unpitched")
check("perc_clef", classify_musicxml_text(
    PIANO_XML.replace("<sign>G</sign>", "<sign>percussion</sign>"))[1] == "percussion_clef")
check("tab_clef", classify_musicxml_text(
    PIANO_XML.replace("<sign>G</sign>", "<sign>TAB</sign>"))[1] == "tab_clef")
check("chan10", classify_musicxml_text(
    PIANO_XML.replace("<midi-channel>1<", "<midi-channel>10<"))[1] == "midi_channel_10")
check("guitar_prog", classify_musicxml_text(
    PIANO_XML.replace("<midi-program>1<", "<midi-program>25<"))[1] == "midi_program_25")
check("name_drum", classify_musicxml_text(
    PIANO_XML.replace(">Piano<", ">Drum Set<"))[1].startswith("name:"))
check("name_harpsichord_ok", classify_musicxml_text(
    PIANO_XML.replace(">Piano<", ">Harpsichord<"))[0], "harpsichord 不应误杀")

print("[2] .mxl(zip)读取判定")
mxl = tmp / "drum.mxl"
with zipfile.ZipFile(mxl, "w") as z:
    z.writestr("META-INF/container.xml", "<container/>")
    z.writestr("score.xml", DRUM_XML)
check("mxl_drum", classify_score_file(mxl)[1] == "percussion_unpitched")
xmlp = tmp / "piano.musicxml"
xmlp.write_text(PIANO_XML, encoding="utf-8")
check("plain_xml_ok", classify_score_file(xmlp) == (True, "ok"))

print("[3] MIDI 判定:10通道(channel=9)与非键盘 program 拦,纯钢琴过")


def _mk_midi(path, channel=0, program=None):
    m = mido.MidiFile(); tr = mido.MidiTrack(); m.tracks.append(tr)
    if program is not None:
        tr.append(mido.Message("program_change", program=program, channel=channel, time=0))
    tr.append(mido.Message("note_on", note=60, velocity=64, channel=channel, time=0))
    tr.append(mido.Message("note_off", note=60, velocity=0, channel=channel, time=480))
    m.save(str(path)); return path


check("midi_piano_ok", classify_midi_file(_mk_midi(tmp / "p.mid", 0, 0)) == (True, "ok"))
check("midi_drums", classify_midi_file(_mk_midi(tmp / "d.mid", 9))[1] == "midi_channel_10")
check("midi_guitar", classify_midi_file(_mk_midi(tmp / "g.mid", 0, 24))[1] == "midi_program_25")

print("[4] 清理:穷举产物(含上次漏掉的 _vn mid+csv)→ purge → 验证表全 0")
aud = tmp / "audio"; (aud / "_vn").mkdir(parents=True)
for f in ("pdmx_X.opus", "pdmx_X_000.flac", "pdmxperf_X_000.wav", "X_whole.opus",
          "X_perf.mid", "X.done", "_vn/2018_X_by_isgn_Chopin.mid", "_vn/2018_X_by_isgn_Chopin.mid_midi_notes.csv"):
    (aud / f).write_bytes(b"x")
labels = tmp / "l.jsonl"
labels.write_text(json.dumps({"utt_id": "pdmx_X_000", "piece_id": "X", "A2S": "a"}) + "\n"
                  + json.dumps({"utt_id": "pdmx_K_000", "piece_id": "K", "A2S": "keepme"}) + "\n",
                  encoding="utf-8")
vnl = tmp / "v.jsonl"
vnl.write_text(json.dumps({"utt_id": "pdmxperf_X_000", "piece_id": "X", "TAST": "t"}) + "\n",
               encoding="utf-8")
pf = piece_files(aud, "X")
check("artifacts_enumerated", sum(len(v) for v in pf.values()) == 8, pf)
check("vn_csv_seen", len(pf["vn_mid_csv"]) == 2, pf["vn_mid_csv"])
lf = [(labels, ("pdmx_",)), (vnl, ("pdmxperf_",))]
st = purge_pieces({"X"}, aud, lf)
clean, counts = verify_pieces({"X"}, aud, lf)
print(format_verify(clean, counts))
check("purged_clean", clean, counts)
kept = [json.loads(l) for l in open(labels, encoding="utf-8")]
check("other_piece_kept", kept and kept[0]["piece_id"] == "K", kept)
check("backup_exists", labels.with_suffix(".bak").exists())

print("[5] 审计脚本端到端:manifest 剔除 + 清理 + 验证(exit 0)")
mani = tmp / "mani.jsonl"
drum_mid = _mk_midi(tmp / "dr.mid", 9)
with open(mani, "w", encoding="utf-8") as f:
    f.write(json.dumps({"piece_id": "PA", "xml_raw": str(xmlp), "midi_path": str(_mk_midi(tmp/"pa.mid", 0, 0))}) + "\n")
    f.write(json.dumps({"piece_id": "DR", "xml_raw": str(mxl), "midi_path": str(drum_mid)}) + "\n")
(aud / "pdmx_DR.opus").write_bytes(b"x")
labels2 = tmp / "l2.jsonl"
labels2.write_text(json.dumps({"utt_id": "pdmx_DR_000", "piece_id": "DR", "A2S": "a"}) + "\n",
                   encoding="utf-8")
rc = audit.main(["--manifest", str(mani), "--xml-root", str(tmp), "--audio-dir", str(aud),
                 "--text-labels", str(labels2), "--vn-labels", str(tmp / "none.jsonl"),
                 "--out-ids", str(tmp / "bad.txt"), "--apply"])
check("audit_rc0", rc == 0, rc)
mani_rows = [json.loads(l) for l in open(mani, encoding="utf-8")]
check("manifest_pruned", [r["piece_id"] for r in mani_rows] == ["PA"], mani_rows)
check("drum_audio_gone", not (aud / "pdmx_DR.opus").exists())
check("ids_file", "DR" in (tmp / "bad.txt").read_text(encoding="utf-8"))

print("[6] cleanup_pieces CLI:--verify-only 能当'清没清干净'的凭证")
rc = clp.main(["--pids", "DR", "--audio-dir", str(aud),
               "--text-labels", str(labels2), "--vn-labels", str(tmp / "none.jsonl"),
               "--verify-only"])
check("verify_only_clean_rc0", rc == 0, rc)

print("[7] 语料重建:从标签确定性重建,行数与标签一致")
lb3 = tmp / "l3.jsonl"
with open(lb3, "w", encoding="utf-8") as f:
    f.write(json.dumps({"utt_id": "u1", "A2S": "aaa", "A2S_lite": "bbb"}) + "\n")
    f.write(json.dumps({"utt_id": "u2", "A2S": "ccc", "A2S_lite": None}) + "\n")
out_c = tmp / "corpus.txt"
rc = rbc.main(["--labels", str(lb3), str(tmp / "missing.jsonl"), "--out", str(out_c)])
check("rebuild_rc0", rc == 0, rc)
lines = out_c.read_text(encoding="utf-8").splitlines()
check("corpus_lines", lines == ["aaa", "bbb", "ccc"], lines)

print("[8] 并行路径实测:12 曲 > seq_threshold → 真进程池跑审计(结果与顺序一致)")
mani_p = tmp / "mani_p.jsonl"
with open(mani_p, "w", encoding="utf-8") as f:
    for i in range(11):
        f.write(json.dumps({"piece_id": f"PP{i}", "xml_raw": str(xmlp),
                            "midi_path": str(tmp / "pa.mid")}) + "\n")
    f.write(json.dumps({"piece_id": "DRUM_P", "xml_raw": str(mxl),
                        "midi_path": str(tmp / "dr.mid")}) + "\n")
rc = audit.main(["--manifest", str(mani_p), "--xml-root", str(tmp), "--audio-dir", str(aud),
                 "--text-labels", str(tmp / "no1.jsonl"), "--vn-labels", str(tmp / "no2.jsonl"),
                 "--out-ids", str(tmp / "bad_p.txt"), "--workers", "2"])
check("pool_audit_rc0", rc == 0, rc)
ids_p = (tmp / "bad_p.txt").read_text(encoding="utf-8")
check("pool_found_only_drum", ids_p.strip().startswith("DRUM_P") and "PP" not in ids_p, ids_p)

print(f"\n全部通过: {PASS} 项")
