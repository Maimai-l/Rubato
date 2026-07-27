"""
进程级 prefetch_batches 的判决性测试(D40)。
铁则:预取只许改变"何时装批",不许改变"装什么";任何故障必须自动退回串行,绝不停训。
子进程用 spawn(与执行端 Windows 同语义);故障注入靠"子进程会设 CUDA_VISIBLE_DEVICES=''"
这一事实区分父子环境。
"""
import os
import time

import torch

from rubato.model.train import prefetch_batches


def _in_child() -> bool:
    return os.environ.get("CUDA_VISIBLE_DEVICES") == ""


class FakeDM:
    """可 pickle 的最小数据模块:12 批,每批含张量+字符串(走真实的跨进程张量传输)。"""
    def __init__(self, n=12):
        self.n = n

    def train_batches(self, epoch: int, start_batch: int = 0):
        for i in range(start_batch, self.n):
            yield {"i": torch.tensor([epoch, i]),
                   "audio": torch.full((100,), float(i)),
                   "utt": f"u{i:03d}"}


class CrashDM(FakeDM):
    """只在子进程里第 3 批抛异常(父进程串行重放时正常)——模拟 pickle 后环境类故障。"""
    def train_batches(self, epoch: int, start_batch: int = 0):
        for i in range(start_batch, self.n):
            if _in_child() and i == 3:
                raise RuntimeError("子进程专属炸弹")
            yield {"i": torch.tensor([epoch, i]),
                   "audio": torch.full((100,), float(i)),
                   "utt": f"u{i:03d}"}


class ExitDM(FakeDM):
    """只在子进程里第 2 批直接 os._exit —— 模拟静默死亡(无异常可传回)。"""
    def train_batches(self, epoch: int, start_batch: int = 0):
        for i in range(start_batch, self.n):
            if _in_child() and i == 2:
                os._exit(3)
            yield {"i": torch.tensor([epoch, i]),
                   "audio": torch.full((100,), float(i)),
                   "utt": f"u{i:03d}"}


def _collect(gen):
    return list(gen)


def _key(b):
    return (tuple(b["i"].tolist()), float(b["audio"][0]), b["utt"])


def test_identical_stream():
    dm = FakeDM()
    want = [_key(b) for b in dm.train_batches(7)]
    got = [_key(b) for b in _collect(prefetch_batches(dm, 7, depth=3))]
    assert got == want, f"预取流与串行不同:{got[:3]} vs {want[:3]}"


def test_depth_zero_is_serial():
    dm = FakeDM()
    got = [_key(b) for b in _collect(prefetch_batches(dm, 0, depth=0))]
    assert got == [_key(b) for b in dm.train_batches(0)]


def test_child_exception_falls_back_to_serial():
    dm = CrashDM()
    got = [_key(b) for b in _collect(prefetch_batches(dm, 1, depth=2))]
    want = [_key(b) for b in dm.train_batches(1)]        # 父进程环境:完整 12 批
    assert got == want, "子进程异常回退不得重复已消费批"


def test_silent_child_death_falls_back_fast():
    dm = ExitDM()
    t0 = time.time()
    got = [_key(b) for b in _collect(prefetch_batches(dm, 2, depth=2))]
    wall = time.time() - t0
    want = [_key(b) for b in dm.train_batches(2)]
    assert got == want, "子进程静默死亡回退不得重复已消费批"
    assert wall < 90, f"静默死亡检测太慢:{wall:.0f}s(应秒级,不许等到超时)"


class UnpicklableDM(FakeDM):
    def __init__(self):
        super().__init__()
        self.bad = lambda: 1                              # lambda 不可 pickle → 启动期失败


def test_unpicklable_dm_falls_back():
    dm = UnpicklableDM()
    got = [_key(b) for b in _collect(prefetch_batches(dm, 3, depth=2))]
    assert got == [_key(b) for b in FakeDM().train_batches(3)]


def test_start_batch_cursor():
    dm = FakeDM()
    got = [_key(b) for b in _collect(prefetch_batches(dm, 5, depth=0, start_batch=7))]
    assert got == [_key(b) for b in dm.train_batches(5, start_batch=7)]


class TinyTok:
    """顶层可 pickle 的最小分词器(encode/piece_to_id 即 encode_target 的全部依赖)。
    id 用 crc32:hash() 每进程随机盐,跨进程必须用确定性映射,否则父子两边编码不同。"""
    def encode(self, text, out_type=str, **kw):
        return text.split()

    def piece_to_id(self, p):
        import zlib
        return zlib.crc32(p.encode("utf-8")) % 5000


def test_real_classes_end_to_end():
    """真 RubatoDataset + RubatoDataModule + 真 flac 文件过 spawn 子进程:流与串行逐字节同。"""
    import tempfile
    import numpy as np
    import soundfile as sf
    from rubato.data.dataset import RubatoDataset, RubatoDataModule

    tmp = tempfile.mkdtemp(prefix="prefetch_e2e_")
    utts, labels = [], {}
    for i in range(3):
        path = os.path.join(tmp, f"u{i}.flac")
        t = np.linspace(0, 1.5, int(1.5 * 16000), dtype=np.float32)
        sf.write(path, 0.1 * np.sin(2 * np.pi * (220 + 110 * i) * t), 16000)
        uid = f"e2e_{i:03d}"
        utts.append({"utt_id": uid, "audio_path": path, "dur_s": 1.5,
                     "dialects": ["TAST"], "kind": "pdmx", "split": "train",
                     "domain": "synth"})
        labels[uid] = {"TAST": f"|4/4k0 PL:C4 <|0.5{i}|> 1/4PL:d4 <|1.0{i}|>"}
    ds = RubatoDataset(utts, labels, TinyTok(), train=True, augment=False,
                       max_target_len=None)
    dm = RubatoDataModule(ds, nasap_val=[], maestro_val=[], labels=labels,
                          max_batch_sec=4.0)
    want = list(dm.train_batches(0))
    got = list(prefetch_batches(dm, 0, depth=2))
    assert len(got) == len(want) and len(want) > 0
    for gb, wb in zip(got, want):
        assert sorted(gb.keys()) == sorted(wb.keys())
        for k in wb:
            if torch.is_tensor(wb[k]):
                assert torch.equal(gb[k], wb[k]), f"批字段 {k} 不同"
            else:
                assert gb[k] == wb[k], f"批字段 {k} 不同"




def test_timed_iter_accounting():
    """timed_iter 的分账要对得上真实睡眠:装批 ~20ms/批,计算 ~30ms/批。"""
    from rubato.model.train import timed_iter

    def slow_gen():
        for i in range(8):
            time.sleep(0.02)              # 装批
            yield i

    stat = {"data": 0.0, "comp": 0.0}
    got = []
    for b in timed_iter(slow_gen(), stat):
        time.sleep(0.03)                  # 计算
        got.append(b)
    assert got == list(range(8))
    assert 0.12 <= stat["data"] <= 0.30, f"data 分账失真: {stat['data']:.3f}(应 ≈0.16)"
    assert 0.16 <= stat["comp"] <= 0.40, f"comp 分账失真: {stat['comp']:.3f}(应 ≈0.21,7 个间隔)"


def test_timed_iter_empty():
    from rubato.model.train import timed_iter
    stat = {"data": 0.0, "comp": 0.0}
    assert list(timed_iter(iter([]), stat)) == []


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            t0 = time.time()
            try:
                fn()
                print(f"  ok {name} ({time.time() - t0:.1f}s)")
            except Exception as e:
                fails += 1
                print(f"  FAIL {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if fails else 0)
