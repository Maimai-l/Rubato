"""
D91 形式语言语料判决性测试:同种子确定性 / 每条过生产验证器 / 真嵌套(shuffle-Dyck)
占比 / TAST 时间戳单调 / 拍号与调号多样性 / 超长控制。
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, ".")

from rubato.intermo.core import text_to_units, units_to_ir, validate_units
from scripts.gen_formal_corpus import main as gen_main


def _gen(tmp: str, n=120, seed=11) -> list[dict]:
    out = str(Path(tmp) / f"c_{seed}.jsonl")
    assert gen_main(["--n", str(n), "--out", out, "--seed", str(seed)]) == 0
    return [json.loads(x) for x in open(out, encoding="utf-8")]


def test_deterministic_same_seed():
    with tempfile.TemporaryDirectory() as td:
        a = _gen(td, n=40, seed=5)
        b = [json.loads(x) for x in open(str(Path(td) / "c2.jsonl"), encoding="utf-8")] \
            if gen_main(["--n", "40", "--out", str(Path(td) / "c2.jsonl"),
                         "--seed", "5"]) == 0 else None
        assert [r["text"] for r in a] == [r["text"] for r in b], "同种子必须逐字节确定"


def test_every_line_validates_and_ts_monotone():
    with tempfile.TemporaryDirectory() as td:
        rows = _gen(td)
        assert len(rows) == 120
        for r in rows:
            units = text_to_units(r["text"])
            viol = validate_units(units)
            assert not viol, f"{r['utt_id']}: {viol[:3]}"
            if r["dialect"] == "TAST":
                bins = [u.ts_bin for u in units if u.ts_bin is not None]
                assert bins and bins == sorted(bins), "TAST 时间戳必须非降"


def test_shuffle_dyck_nesting_present():
    with tempfile.TemporaryDirectory() as td:
        rows = _gen(td)
        nested = 0
        for r in rows:
            ir = units_to_ir(text_to_units(r["text"]))
            by_staff: dict = {}
            for n in ir.notes:
                by_staff.setdefault(n.staff, []).append(n)
            found = False
            for ns in by_staff.values():
                ns = sorted(ns, key=lambda n: n.onset)
                for i, a in enumerate(ns):
                    for b in ns[i + 1:]:
                        if a.onset < b.onset < a.offset:   # 长音跨越他音起点 = 真嵌套
                            found = True
                            break
                    if found:
                        break
                if found:
                    break
            nested += int(found)
        assert nested / len(rows) > 0.30, \
            f"嵌套占比过低({nested}/{len(rows)})—— 语料退化成平铺,练不出 Dyck"


def test_signature_and_key_variety():
    with tempfile.TemporaryDirectory() as td:
        rows = _gen(td)
        sigs, keys = set(), set()
        for r in rows:
            for u in text_to_units(r["text"]):
                if u.bar is not None:
                    sigs.add((u.bar[0], u.bar[1]))
                    keys.add(u.bar[2])
        assert len(sigs) >= 4, f"拍号多样性不足: {sigs}"
        assert len(keys) >= 6, f"调号多样性不足: {keys}"
        assert all(r["n_atoms"] <= 700 for r in rows), "超长控制失效"


def test_existing_output_is_not_overwritten_without_flag():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "corpus.jsonl"
        out.write_text("sentinel\n", encoding="utf-8")
        try:
            gen_main(["--n", "1", "--out", str(out)])
            raised = False
        except FileExistsError:
            raised = True
        assert raised, "已有 corpus 必须缺省拒绝覆盖"
        assert out.read_text(encoding="utf-8") == "sentinel\n"


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
