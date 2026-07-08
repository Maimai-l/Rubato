"""
S8/S11 dataset —— 音频↔标签配对 + collate(修复问题#4/#5)。

这是 train.py 训练循环缺的那一环:把 labels.jsonl 的文本标签 tokenize、拼 prompt、
做 teacher-forcing 右移、标 token_types/ts_bins/loss_mask,和 FLAC/Opus 音频配对成
`training_step_logic` 需要的 batch 契约。不依赖 lhotse —— 普通 PyTorch Dataset + collate。

batch 契约(与 rubato/model/train.py:training_step_logic 一致):
  audio (B,S) / audio_lens (B,) / input_ids (B,L) / input_lens (B,) /
  labels (B,L) / token_types (B,L) / loss_mask (B,L) / ts_bins (B,L)

┌─ 沙盒可测(本文件配套 tests_dataset.py 用 mock tokenizer 验证):
│    encode_target 的 token_types/ts_bins/loss_mask、teacher-forcing 右移、tiling、
│    collate 的 padding 与契约键。
└─ 需本地真实数据验证(标 TODO/LOCAL):FLAC/Opus 解码、labels.jsonl 真实路径、
     spm 真实模型、tiling 的音频补零×预设链次序(R-S4.5)。见 LOCAL_VERIFICATION.md D 步。
"""
from __future__ import annotations
import re
from pathlib import Path

from rubato.model.build import DIALECT_PROMPT
from rubato.model.sampling import dialect_sampler, tiling_offset
from rubato.model.train import bucket_batches

_TS_RE = re.compile(r"^<\|t(\d+)\|>$")
_TS_INLINE_RE = re.compile(r"<\|t(\d+)\|>")
TS_MS = 10
N_BINS = 4000


# ---------------------------------------------------------------- tiling(R-S11.3,文本级)

def apply_tiling_text(text: str, t0_bins: int) -> str:
    """
    TAST/AMT 的时间戳整体 +t0(R-S11.3)。在【文本级】平移 <|tN|> → <|t(N+t0)|>,
    钳到 N_BINS-1。音频侧对应补 t0 秒前导(在 collate/加载时做)。
    t0_bins==0 → 原样返回(A2S/A2S_lite 不 tiling)。
    """
    if t0_bins == 0:
        return text

    def _shift(m):
        return f"<|t{min(int(m.group(1)) + t0_bins, N_BINS - 1)}|>"
    return _TS_INLINE_RE.sub(_shift, text)


# ---------------------------------------------------------------- 目标序列编码(R-S10.4)

def encode_target(tokenizer, dialect: str, label_text: str,
                  sample: bool = True, alpha: float = 0.25,
                  domain: str | None = None) -> dict:
    """
    label_text(InterMo 序列化文本)→ 完整目标序列的张量元数据。
    步骤:
      1. spm 切分 label_text → label 子词 pieces(训练期 alpha 采样,R-S9.4);
         user_defined(时间戳/prompt/MIDI)在 spm 内恒原子,不被采样切碎。
      2. 拼 [prompt] + [label pieces] + [eot],prompt 位置 loss_mask=False(R-S10.4)。
      3. 逐 token 标 token_type(0 语义 / 1 时间戳)与 ts_bin。
      4. teacher-forcing 右移:input_ids=seq[:-1],labels=seq[1:],各元数据同步右移。
    返回 {input_ids, labels, token_types, loss_mask, ts_bins}(均为 list[int/bool])。
    """
    # 1. label 文本 → piece 字符串序列
    if sample and hasattr(tokenizer, "encode") and _supports_sampling(tokenizer):
        label_pieces = tokenizer.encode(label_text, out_type=str,
                                        enable_sampling=True, alpha=alpha, nbest_size=-1)
    else:
        label_pieces = tokenizer.encode(label_text, out_type=str)

    # 2. 拼 prompt + eot(与 build.build_target_sequence 同布局,但这里要保留 piece 串)
    prompt = list(DIALECT_PROMPT[dialect])
    if domain in ("real", "synth"):
        prompt.append(f"<|{domain}|>")
    pieces = prompt + list(label_pieces) + ["<|eot|>"]
    loss_mask_full = [False] * len(prompt) + [True] * (len(label_pieces) + 1)

    # 3. piece → id + token_type + ts_bin
    ids, types, bins = [], [], []
    for p in pieces:
        ids.append(tokenizer.piece_to_id(p))
        m = _TS_RE.match(p)
        if m:
            types.append(1)
            bins.append(min(int(m.group(1)), N_BINS - 1))
        else:
            types.append(0)
            bins.append(0)

    # 4. teacher-forcing 右移:预测 seq[1:],输入 seq[:-1]
    return {
        "input_ids": ids[:-1],
        "labels": ids[1:],
        "token_types": types[1:],       # 与 labels 对齐(标的是"要预测的那个 token")
        "loss_mask": loss_mask_full[1:],
        "ts_bins": bins[1:],
    }


def _supports_sampling(tokenizer) -> bool:
    """SentencePieceProcessor.encode 支持 enable_sampling;mock/其他不一定。"""
    try:
        import sentencepiece as spm
        return isinstance(tokenizer, spm.SentencePieceProcessor)
    except Exception:
        return False


# ---------------------------------------------------------------- 音频加载(本地,LOCAL)

def load_audio(path: str, sr_target: int = 16000, tile_pad_s: float = 0.0):
    """
    FLAC/Opus → 16k mono float32 numpy。tile_pad_s>0 时前导补零(R-S11.3 tiling)。
    LOCAL:需 soundfile(+soxr 重采样),沙盒不跑真实音频。
    R-S4.5【不变量】:预设链在线增强时须"先 tile-pad、后预设链",使噪底覆盖补零区;
    此处只补零,预设链若在线做需在补零【之后】作用(dataloader 装配处保证次序)。
    """
    import numpy as np
    import soundfile as sf
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != sr_target:
        try:
            import soxr
            audio = soxr.resample(audio, sr, sr_target)
        except Exception:
            import scipy.signal as ss
            audio = ss.resample(audio, int(round(len(audio) * sr_target / sr))).astype("float32")
    if tile_pad_s > 0:
        pad = np.zeros(int(round(tile_pad_s * sr_target)), dtype="float32")
        audio = np.concatenate([pad, audio])
    return audio.astype("float32")


# ---------------------------------------------------------------- collate(batch 契约)

def collate_batch(items: list[dict], pad_id: int = 0) -> dict:
    """
    右填充成 batch。items: [{audio(np), input_ids, labels, token_types, loss_mask, ts_bins}]。
    返回 training_step_logic 的 batch 契约(torch 张量)。
    """
    import torch
    import numpy as np

    B = len(items)
    Lmax = max(len(it["input_ids"]) for it in items)
    Smax = max(len(it["audio"]) for it in items)

    audio = torch.zeros(B, Smax, dtype=torch.float32)
    audio_lens = torch.zeros(B, dtype=torch.long)
    input_ids = torch.full((B, Lmax), pad_id, dtype=torch.long)
    input_lens = torch.zeros(B, dtype=torch.long)
    labels = torch.full((B, Lmax), pad_id, dtype=torch.long)
    token_types = torch.zeros(B, Lmax, dtype=torch.long)
    loss_mask = torch.zeros(B, Lmax, dtype=torch.bool)
    ts_bins = torch.zeros(B, Lmax, dtype=torch.long)

    for i, it in enumerate(items):
        a = torch.from_numpy(np.asarray(it["audio"], dtype="float32"))
        audio[i, :len(a)] = a
        audio_lens[i] = len(a)
        L = len(it["input_ids"])
        input_lens[i] = L
        input_ids[i, :L] = torch.tensor(it["input_ids"], dtype=torch.long)
        labels[i, :L] = torch.tensor(it["labels"], dtype=torch.long)
        token_types[i, :L] = torch.tensor(it["token_types"], dtype=torch.long)
        loss_mask[i, :L] = torch.tensor(it["loss_mask"], dtype=torch.bool)
        ts_bins[i, :L] = torch.tensor(it["ts_bins"], dtype=torch.long)
        # 填充位 loss_mask 已是 False,不计入 loss

    return {"audio": audio, "audio_lens": audio_lens,
            "input_ids": input_ids, "input_lens": input_lens,
            "labels": labels, "token_types": token_types,
            "loss_mask": loss_mask, "ts_bins": ts_bins}


# ---------------------------------------------------------------- Dataset / DataModule

class RubatoDataset:
    """
    一个 split 的样本集。每 epoch 调 set_epoch(e) 按混比重采样 (utt, dialect) 并重算 tiling。
    utts: [{utt_id, kind, audio_path, dur_s, dialects, split, domain?}]。
    labels: {utt_id: {A2S, A2S_lite, TAST, AMT}}(文本,可含 None)。
    """
    def __init__(self, utts: list[dict], labels: dict, tokenizer,
                 seed: int = 20260706, sr: int = 16000,
                 alpha: float = 0.25, train: bool = True):
        self.utts = {u["utt_id"]: u for u in utts}
        self.labels = labels
        self.tok = tokenizer
        self.seed = seed
        self.sr = sr
        self.alpha = alpha
        self.train = train
        self._plan: list[tuple[str, str]] = []
        self.set_epoch(0)

    def _available(self) -> dict:
        """{utt_id: [有标签的 dialect]}(标签为 None 的 dialect 不可用)。"""
        av = {}
        for uid, u in self.utts.items():
            lab = self.labels.get(uid, {})
            ds = [d for d in u.get("dialects", []) if lab.get(d)]
            if ds:
                av[uid] = ds
        return av

    def set_epoch(self, epoch: int):
        self.epoch = epoch
        av = self._available()
        if self.train:
            self._plan = dialect_sampler(av, self.seed, epoch)
        else:
            # eval:每 utt 每可用 dialect 各一次(确定性,不采样)
            self._plan = [(u, d) for u, ds in sorted(av.items()) for d in ds]

    def __len__(self):
        return len(self._plan)

    def sample_meta(self):
        """返回 [(utt_id, dialect, dur_s)],供 bucketing 排程。"""
        return [(u, d, self.utts[u].get("dur_s", 0.0)) for u, d in self._plan]

    def __getitem__(self, idx: int) -> dict:
        uid, dialect = self._plan[idx]
        u = self.utts[uid]
        text = self.labels[uid][dialect]

        # tiling(R-S11.3):TAST/AMT 每 epoch 每样本 t0~U[0, 40-dur]
        t0_s = tiling_offset(dialect, u.get("dur_s", 0.0), uid, self.epoch, self.seed) \
            if self.train else 0.0
        t0_bins = int(round(t0_s / (TS_MS / 1000.0)))
        text = apply_tiling_text(text, t0_bins)

        enc = encode_target(self.tok, dialect, text,
                            sample=self.train, alpha=self.alpha, domain=u.get("domain"))
        enc["audio"] = load_audio(u["audio_path"], self.sr, tile_pad_s=t0_s)  # LOCAL
        enc["utt_id"] = uid
        enc["dialect"] = dialect
        return enc


class RubatoDataModule:
    """
    train.py:train() 依赖的接口:train_batches(epoch) 生成器 + nasap_val + maestro_val。
    train_batches 每 epoch 按混比重采样、bucketing(≤max_batch_sec)、collate。
    """
    def __init__(self, train_ds: RubatoDataset, nasap_val: list[dict],
                 maestro_val: list[dict], pad_id: int = 0,
                 max_batch_sec: float = 560.0):
        self.train_ds = train_ds
        self.nasap_val = nasap_val          # [{audio, ref_xml?}](infer_a2s 用)
        self.maestro_val = maestro_val      # [{audio, ref_notes}](infer_amt/note_f1 用)
        self.pad_id = pad_id
        self.max_batch_sec = max_batch_sec

    def train_batches(self, epoch: int):
        self.train_ds.set_epoch(epoch)
        meta = self.train_ds.sample_meta()
        idx_of = {(u, d): i for i, (u, d) in enumerate(self.train_ds._plan)}
        samples = [{"utt_id": u, "dialect": d, "dur_s": s} for u, d, s in meta]
        for batch_samples in bucket_batches(samples, self.max_batch_sec):
            items = []
            for s in batch_samples:
                i = idx_of[(s["utt_id"], s["dialect"])]
                items.append(self.train_ds[i])
            yield collate_batch(items, self.pad_id)
