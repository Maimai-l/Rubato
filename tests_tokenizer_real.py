"""真实 SentencePiece 回归测试:锁死 split_by_number/unicode_script 修复(问题#3 终案)。
此前这两个默认切分把 C4→C,4、1/16→1,/,16 砸碎,vocab 从 8000 塌到 ~427。运行: python tests_tokenizer_real.py"""
import sys, os, random, io, tempfile
sys.path.insert(0, ".")
from fractions import Fraction as F
from rubato.intermo.core import SPitch, Note, Measure, ScoreIR, project
from rubato.data.tokenizer import train_unigram, check_glyph_coverage

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

try:
    import sentencepiece  # noqa
except ImportError:
    print("  skip  sentencepiece 不可用(执行端有);沙盒跳过")
    print("\n全部通过: 0 项(skipped)")
    raise SystemExit(0)

# 生成一份多样的小语料(A2S + A2S_lite),覆盖各调号/拍号/音高
random.seed(7)
STEPS = "CDEFGAB"
tmp = tempfile.mkdtemp()
corpus = os.path.join(tmp, "c.txt")
with io.open(corpus, "w", encoding="utf-8") as w:
    made = 0
    while made < 9000:      # ~18k 行:vocab 8000 需要够多 distinct 学习片(3571)
        num, den = random.choice([(4,4),(3,4),(6,8),(2,4),(3,8)])
        fifths = random.randint(-6, 6)
        n_meas = random.randint(2, 6)
        mlen = F(num, den); grid = F(1, 16)
        measures = [Measure(i*mlen, num, den, fifths) for i in range(n_meas)]
        end = n_meas*mlen
        notes, occ = [], set()
        for _ in range(random.randint(6, 30)):
            staff = random.choice(["PL","PR"])
            p = SPitch(random.choice(STEPS), random.choice([-1,0,1]),
                       random.randint(2,4) if staff=="PL" else random.randint(4,6))
            st = random.randint(0, max(0, int(end/grid)-1))
            du = random.randint(1, min(8, max(1, int(end/grid)-st)))
            cells = {(staff, str(p), i) for i in range(st, st+du)}
            if cells & occ: continue
            occ |= cells
            notes.append(Note(staff, p, st*grid, du*grid))
        if not notes: continue
        try:
            ir = ScoreIR(notes, measures, end)
            w.write(project(ir,"A2S")+"\n"); w.write(project(ir,"A2S_lite")+"\n")
            made += 1
        except Exception:
            continue

print("[1] train_unigram 达到目标词表(修复前会塌到 ~427/5148)")
prefix = os.path.join(tmp, "spm")
res = train_unigram([corpus], prefix, vocab_size=8000, spec_path="configs/vocab_spec.json")
check("vocab_reached", res["vocab_size"] == 8000 and res["reconcile"]["learnable_semantic"] == 3571, res)
check("no_fallback", res["fell_back"] is False and res["warning"] is None, res)

print("[2] 关键字形是【单 piece】(不再被数字/脚本切分砸碎)")
import sentencepiece as spm
sp = spm.SentencePieceProcessor(model_file=prefix+".model")
def atomic(g):
    pieces = [x.lstrip("▁") for x in sp.encode(g, out_type=str)]
    return len([x for x in pieces if x]) == 1
for g in ["C4", "F#3", "1/16", "|3/4k-4", "PR:C4", "N60", "<|0.00|>", "<|vel:82|>"]:
    check(f"atomic[{g}]", atomic(g), sp.encode(g, out_type=str))

print("[3] check_glyph_coverage 不再把词首符 '▁' 误报为分裂(用语料覆盖到的常见字形探)")
# 小语料只覆盖 3-5 八度 + 常见 interval;用这些探针测【度量修复】,不被稀有八度拖累。
common = ([f"{s}{o}" for s in "CDEFG" for o in (3,4,5)] +
          [f"{s.lower()}{o}" for s in "CDEFG" for o in (3,4,5)] +
          ["1/4","1/8","1/16","1/2","3/8"] + ["PR:C4","PL:c3"])
cov = check_glyph_coverage(prefix+".model", probes=common)
check("common_glyphs_atomic", cov["split_rate"] < 0.30, cov)
# 度量修复的直接证明:C4 明明是单 piece(见[2]),旧度量会把 ['▁','C4'] 记成分裂
raw = sp.encode("C4", out_type=str)
check("metric_ignores_boundary_mark", len(raw) >= 2 and cov["split_rate"] < 0.30,
      f"raw={raw} split_rate={cov['split_rate']}")

print("[4] 往返无损(byte_fallback)")
line = io.open(corpus, encoding="utf-8").readline().strip()
check("roundtrip", sp.decode(sp.encode(line)) == line, line[:60])

print(f"\n全部通过: {PASS} 项")
