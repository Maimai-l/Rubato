"""
C1a 声学增广(D58)判决性测试:确定性、跨 epoch 变化、标签安全(长度/静音)、防削顶、旗子门控。
"""
import time

import numpy as np

from rubato.data.dataset import acoustic_augment


def _tone(n=16000):
    t = np.arange(n, dtype=np.float32) / 16000.0
    return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_deterministic_same_epoch_and_varies_across_epochs():
    x = _tone()
    a1 = acoustic_augment(x, "u1", epoch=3)
    a2 = acoustic_augment(x, "u1", epoch=3)
    b = acoustic_augment(x, "u1", epoch=4)
    c = acoustic_augment(x, "u2", epoch=3)
    assert np.array_equal(a1, a2), "同 (utt,epoch) 必须逐位相同"
    assert not np.array_equal(a1, b), "跨 epoch 必须变化"
    assert not np.array_equal(a1, c), "跨样本必须变化"


def test_label_safety_length_and_silence():
    x = _tone(12345)
    y = acoustic_augment(x, "u1", epoch=0)
    assert y.shape == x.shape and y.dtype == np.float32   # 长度不变 = 时间戳安全
    z = acoustic_augment(np.zeros(8000, dtype=np.float32), "u1", epoch=0)
    assert float(np.max(np.abs(z))) == 0.0                # 静音段不加噪(探针静音对照不被污染)


def test_no_clipping_and_energy_sane():
    x = (_tone() * 3.0).astype(np.float32)                # 故意大信号
    y = acoustic_augment(x, "u9", epoch=1)
    assert float(np.max(np.abs(y))) <= 0.99 + 1e-6
    # 增益带 ±6dB + 噪声:能量不应偏出一个数量级
    rx, ry = np.sqrt(np.mean(x ** 2)), np.sqrt(np.mean(y ** 2))
    assert 0.2 < ry / rx < 5.0


def test_flag_gating_in_dataset():
    from rubato.data.dataset import RubatoDataset
    class Tok:
        def encode(self, t, out_type=str, **k):
            return t.split()
        def piece_to_id(self, p):
            import zlib
            return zlib.crc32(p.encode()) % 5000
    import soundfile as sf
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp(prefix="c1a_"))
    p = tmp / "a.flac"
    sf.write(str(p), _tone(24000), 16000)
    utts = [{"utt_id": "x1", "audio_path": str(p), "dur_s": 1.5, "dialects": ["TAST"],
             "split": "train", "domain": "synth"}]
    labels = {"x1": {"TAST": "|4/4k0 PL:C4 <|0.50|>"}}
    d_off = RubatoDataset(utts, labels, Tok(), train=True, augment=False, acoustic_aug=False)
    d_on = RubatoDataset(utts, labels, Tok(), train=True, augment=False, acoustic_aug=True)
    d_off.set_epoch(0); d_on.set_epoch(0)
    a_off = d_off[0]["audio"]; a_on = d_on[0]["audio"]
    assert not np.array_equal(np.asarray(a_off), np.asarray(a_on)), "旗子开必须改变音频"
    d_off.set_epoch(1)
    assert np.array_equal(np.asarray(a_off), np.asarray(d_off[0]["audio"])), "旗子关必须恒原样"


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
