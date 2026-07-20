"""
prefetch_batches 的判决性测试:预取只许改变"何时装批",不许改变"装什么"。
(它包在训练主循环外面,错了会毒化每一步 —— 五个场景钉死。)
"""
import time

from rubato.model.train import prefetch_batches


def test_identical_stream():
    src = [{"i": i, "x": [i] * 3} for i in range(50)]
    got = list(prefetch_batches(iter(src), depth=3))
    assert got == src                      # 逐元素、逐序相同
    assert got[7] is src[7]                # 同一对象,零拷贝


def test_depth_zero_is_passthrough():
    src = [1, 2, 3]
    g = prefetch_batches(iter(src), depth=0)
    assert list(g) == src


def test_empty_generator():
    assert list(prefetch_batches(iter([]), depth=3)) == []


def test_producer_exception_propagates():
    def bad():
        yield 1
        yield 2
        raise RuntimeError("装批炸了")
    got = []
    try:
        for b in prefetch_batches(bad(), depth=2):
            got.append(b)
    except RuntimeError as e:
        assert "装批炸了" in str(e)
        assert got == [1, 2]               # 炸之前的批一个不丢
    else:
        raise AssertionError("生产者异常被吞了")


def test_slow_consumer_bounded_queue():
    # 消费者比生产者慢:队列有界不爆内存,数据仍完整有序
    produced = []
    def src():
        for i in range(20):
            produced.append(i)
            yield i
    out = []
    for b in prefetch_batches(src(), depth=2):
        time.sleep(0.005)                  # 慢消费
        out.append(b)
        # 有界队列:生产者最多领先 depth+1(队列 depth + put 在手 1)
        assert len(produced) - len(out) <= 2 + 1 + 1
    assert out == list(range(20))


def test_overlap_actually_happens():
    # 生产一批 20ms、消费一批 20ms × 10 批:串行 ≈400ms,重叠后应明显更快
    def src():
        for i in range(10):
            time.sleep(0.02)
            yield i
    t0 = time.time()
    n = 0
    for _ in prefetch_batches(src(), depth=3):
        time.sleep(0.02)
        n += 1
    wall = time.time() - t0
    assert n == 10
    assert wall < 0.34, f"无重叠迹象:{wall:.3f}s(串行 ≈0.40s,重叠应 ≈0.22s)"


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
