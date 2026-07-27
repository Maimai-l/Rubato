"""
O4 旋钮(--amt-mix → mix_with_amt → dialect_sampler)的判决性测试。
混比错了是整轮训练报废,这里把换算、恒等、越界、配额落地四件事钉死。
"""
import math

from rubato.model.sampling import DIALECT_MIX, dialect_sampler, mix_with_amt


def test_mix_with_amt_022_proportions():
    m = mix_with_amt(0.22)
    assert math.isclose(sum(m.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(m["AMT"], 0.22, abs_tol=1e-9)
    # 其余三方言维持 35:15:20 的内部比例
    assert math.isclose(m["A2S"] / m["A2S_lite"], 35 / 15, rel_tol=1e-9)
    assert math.isclose(m["A2S"] / m["TAST"], 35 / 20, rel_tol=1e-9)
    # 数值本身:0.35×0.78/0.70 = 0.39
    assert math.isclose(m["A2S"], 0.39, abs_tol=1e-9)


def test_mix_with_amt_030_is_identity():
    m = mix_with_amt(0.30)
    for d, v in DIALECT_MIX.items():
        assert math.isclose(m[d], v, abs_tol=1e-9), (d, m[d], v)


def test_mix_with_amt_rejects_out_of_band():
    for bad in (0.0, 0.04, 0.51, 1.0, -0.1):
        try:
            mix_with_amt(bad)
        except ValueError:
            continue
        raise AssertionError(f"amt={bad} 应当抛 ValueError")


def test_sampler_honors_injected_mix():
    # 1000 utt,四方言全可用 → 配额应贴合注入 mix,而不是缺省 D2
    av = {f"u{i:04d}": ["A2S", "A2S_lite", "TAST", "AMT"] for i in range(1000)}
    mix = mix_with_amt(0.22)
    report: dict = {}
    plan = dialect_sampler(av, seed=7, epoch=0, mix=mix, report=report)
    counts: dict = {}
    for _, d in plan:
        counts[d] = counts.get(d, 0) + 1
    total = sum(counts.values())
    for d, w in mix.items():
        got = counts[d] / total
        assert abs(got - w) < 0.02, (d, got, w)
    # report 的 quota 与实际计数一致(验收看的就是这行数)
    for d, r in report.items():
        assert r["quota"] == counts[d], (d, r, counts[d])


def test_sampler_default_still_d2_when_mix_none():
    av = {f"u{i:04d}": ["A2S", "A2S_lite", "TAST", "AMT"] for i in range(1000)}
    plan = dialect_sampler(av, seed=7, epoch=0, mix=None)
    counts: dict = {}
    for _, d in plan:
        counts[d] = counts.get(d, 0) + 1
    total = sum(counts.values())
    for d, w in DIALECT_MIX.items():
        assert abs(counts[d] / total - w) < 0.02, (d, counts[d] / total, w)


def test_sampler_quota_is_exact_even_for_tiny_pool():
    av = {"only": ["A2S", "A2S_lite", "TAST", "AMT"]}
    plan = dialect_sampler(av, seed=7, epoch=0)
    assert len(plan) == 1, plan
    av3 = {f"u{i}": ["A2S", "A2S_lite", "TAST", "AMT"] for i in range(3)}
    assert len(dialect_sampler(av3, seed=7, epoch=0)) == 3


def test_sampler_rejects_incomplete_or_invalid_mix():
    for bad in ({"AMT": 1.0}, {**DIALECT_MIX, "AMT": -0.1}):
        try:
            dialect_sampler({"u": ["AMT"]}, seed=1, epoch=0, mix=bad)
            raise AssertionError(f"bad mix accepted: {bad}")
        except ValueError:
            pass


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok {name}")
            except Exception as e:
                fails += 1
                print(f"  FAIL {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if fails else 0)
