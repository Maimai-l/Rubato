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
import random
import re
from pathlib import Path

from rubato.model.build import DIALECT_PROMPT
from rubato.model.sampling import dialect_sampler, tiling_offset
from rubato.model.train import bucket_batches

from rubato.intermo.core import ts_glyph, ts_bin_from_glyph

_TS_RE = re.compile(r"^<\|(\d+\.\d{2})\|>$")
_TS_INLINE_RE = re.compile(r"<\|(\d+\.\d{2})\|>")
TS_MS = 10
N_BINS = 4000


# ---------------------------------------------------------------- tiling(R-S11.3,文本级)

def apply_tiling_text(text: str, t0_bins: int) -> str:
    """
    TAST/AMT 的时间戳整体 +t0(R-S11.3)。在【文本级】平移时间戳字形(秒·两位小数),
    钳到 N_BINS-1。音频侧对应补 t0 秒前导(在 collate/加载时做)。
    t0_bins==0 → 原样返回(A2S/A2S_lite 不 tiling)。
    """
    if t0_bins == 0:
        return text

    def _shift(m):
        return ts_glyph(min(ts_bin_from_glyph(m.group(1)) + t0_bins, N_BINS - 1))
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
            bins.append(min(ts_bin_from_glyph(m.group(1)), N_BINS - 1))
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

def online_room_augment(audio, utt_id: str, epoch: int, presets_cfg: dict,
                        seed: int = 20260706, sr: int = 16000,
                        irs_dir: str = "assets/irs/real"):
    """
    在线房间增广(R-S4.5 apply_online):对【干声】每 epoch 施加一个 hash 选中的录音预设
    (真实 IR 优先,见 irgen.resolve_ir)。同 (utt, epoch) 确定,不同 epoch 变→白拿的房间多样性。

    这补上论文的增广乘数中"房间/环境"那一维,且【无额外磁盘】(不预渲多份)。
    前提:S4 应渲【干声】(源音色,不烘焙预设),预设在此在线施加;若 S4 已烘焙预设,
    此步会二次加混响,需在 S4 关闭预设烘焙(见 EXECUTOR 指引)。
    音色维度另需在渲染期用多个源(见 sources.yaml),在线只能变房间不能变音色。
    """
    import hashlib
    from rubato.render.irgen import apply_preset
    presets = presets_cfg["presets"]
    weights = presets_cfg.get("weights", {pid: 1.0 for pid in presets})
    ids = list(presets)
    h = hashlib.sha256(f"{seed}:{epoch}:{utt_id}:preset".encode()).hexdigest()
    u = int(h[:15], 16) / float(16 ** 15)
    # 加权选一个预设
    tot = sum(weights.get(pid, 0.0) for pid in ids) or 1.0
    acc, chosen = 0.0, ids[-1]
    for pid in ids:
        acc += weights.get(pid, 0.0) / tot
        if u < acc:
            chosen = pid
            break
    ps_seed = int(int(h[15:30], 16) % 1_000_000)
    return apply_preset(audio, presets[chosen], sr=sr, seed=ps_seed,
                        preset_id=chosen, irs_dir=irs_dir)


def acoustic_augment(audio, utt_id: str, epoch: int, seed: int = 20260706):
    """
    C1a 标签安全在线增广(D58,二轮默认开):增益 ±6dB + 一阶谱倾斜 + 加性噪声(SNR 25-45dB)。
    三者都不动音高/时间戳标签,湿声上可安全叠加;【不含混响】——房间维度被"烘焙预设"
    卡死(C1b,D45 半成品考古),在此加混响 = 双重房间,禁止。
    确定性:(utt_id, epoch) 哈希 → 同 epoch 同样本恒同,跨 epoch 变(与 tiling 同纪律)。
    """
    import hashlib
    import numpy as np
    h = hashlib.sha256(f"{seed}:{epoch}:{utt_id}:c1a".encode()).digest()
    r = [int.from_bytes(h[i:i + 4], "big") / 2 ** 32 for i in (0, 4, 8)]
    x = np.asarray(audio, dtype=np.float32).copy()
    if x.size < 2:
        return x
    x *= np.float32(10 ** ((r[0] * 12.0 - 6.0) / 20.0))            # 增益 ±6dB
    a = np.float32(r[1] * 0.6 - 0.3)                                # 倾斜 ∈[-0.3,0.3]
    x = x - a * np.concatenate((np.zeros(1, dtype=np.float32), x[:-1]))
    rms = float(np.sqrt(np.mean(np.square(x))))
    if rms > 1e-5:                                                  # 静音段不加噪
        snr_db = 25.0 + 20.0 * r[2]
        rng = np.random.default_rng(int.from_bytes(h[16:24], "big"))
        x = x + rng.standard_normal(x.size).astype(np.float32) * np.float32(rms / 10 ** (snr_db / 20.0))
    peak = float(np.max(np.abs(x)))
    if peak > 0.99:                                                 # 防削顶
        x *= np.float32(0.99 / peak)
    return x


def load_audio(path: str, sr_target: int = 16000, tile_pad_s: float = 0.0,
               win: list | tuple | None = None):
    """
    FLAC/Opus → 16k mono float32 numpy。tile_pad_s>0 时前导补零(R-S11.3 tiling)。
    win=[t0,t1](秒,整曲坐标):窗内 utt(MAESTRO AMT 切窗)只读整曲的该窗 ——
    用 soundfile 的 start/stop 帧级读取,不把几分钟的整曲载进内存、不切文件占双倍磁盘。
    LOCAL:需 soundfile(+soxr 重采样),沙盒不跑真实音频。
    R-S4.5【不变量】:预设链在线增强时须"先 tile-pad、后预设链",使噪底覆盖补零区;
    此处只补零,预设链若在线做需在补零【之后】作用(dataloader 装配处保证次序)。
    """
    import numpy as np
    import soundfile as sf
    if win is not None and len(win) == 2:
        info = sf.info(path)
        a = max(0, int(float(win[0]) * info.samplerate))
        b = min(info.frames, int(float(win[1]) * info.samplerate))
        audio, sr = sf.read(path, dtype="float32", start=a, stop=b)
    else:
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
            "loss_mask": loss_mask, "ts_bins": ts_bins,
            # 逐条 dialect(list,非张量):训练步据此聚合出 A2S/A2S_lite/TAST/AMT 各自曲线
            "dialects": [it.get("dialect") for it in items]}


# ---------------------------------------------------------------- Dataset / DataModule

class RubatoDataset:
    """
    一个 split 的样本集。每 epoch 调 set_epoch(e) 按混比重采样 (utt, dialect) 并重算 tiling。
    utts: [{utt_id, kind, audio_path, dur_s, dialects, split, domain?}]。
    labels: {utt_id: {A2S, A2S_lite, TAST, AMT}}(文本,可含 None)。
    """
    def __init__(self, utts: list[dict], labels: dict, tokenizer,
                 seed: int = 20260706, sr: int = 16000,
                 alpha: float = 0.25, train: bool = True,
                 dialect_mix: dict | None = None,
                 max_target_len: int | None = None,
                 augment: bool | None = None,
                 acoustic_aug: bool = False):
        self.utts = {u["utt_id"]: u for u in utts}
        self.labels = labels
        self.acoustic_aug = bool(acoustic_aug)   # C1a(D58):声学增广旗,与 alpha/tiling 增广独立
        self.tok = tokenizer
        self.seed = seed
        self.sr = sr
        self.alpha = alpha
        self.train = train
        self.dialect_mix = dialect_mix          # None → sampling.DIALECT_MIX 缺省;可从配置注入
        self.max_target_len = max_target_len    # decoder 位置表上限(canary=512);None=不过滤
        # 增强开关(缺省跟随 train):alpha 子词重采样 + tiling 时间戳平移。过拟合冒烟必须关 ——
        # 两者每 epoch 换答案,sem 被切分熵钉在 ~1.1、ts 被 t0 随机钉在 ~6.4(执行端 4000 步实测),
        # "背不下来"是增强的设计属性,不是收敛失败。全量训练保持开启(论文 R-S9.4/R-S11.3)。
        self.augment = bool(train) if augment is None else bool(augment)
        self.len_filter_report: dict = {}
        self._tok_len: dict = {}
        self.last_mix_report: dict = {}         # 每 epoch 的池大小/配额/过采样倍数,给日志看
        self._len_ok = self._build_len_filter() if max_target_len else None
        self._plan: list[tuple[str, str]] = []
        self.set_epoch(0)

    def _build_len_filter(self) -> set:
        """(utt_id, dialect) 白名单:目标序列(prompt+标签+eot,确定性切分)≤ max_target_len。
        为什么必须有(执行端冒烟实测):canary decoder 位置编码表只有 512 行,AMT 密集窗
        (25s 炫技段几百音符)能编出 1000+ token → position_ids 越界 = CUDA device assert,
        整个训练进程报废。超长样本【丢弃并记账】—— 截断会破坏 InterMo 的 Dyck 闭合,不可取。
        长度按确定性切分量;训练期 alpha 采样可能更长,__getitem__ 有确定性回退兜底。"""
        ok: set = set()
        drop: dict = {}
        self._tok_len: dict = {}
        for uid, u in self.utts.items():
            lab = self.labels.get(uid, {})
            for d in u.get("dialects", []):
                t = lab.get(d)
                if not t:
                    continue
                n = len(self.tok.encode(t, out_type=str)) + len(DIALECT_PROMPT[d]) + 2  # +domain+eot
                if n <= self.max_target_len:
                    ok.add((uid, d))
                    self._tok_len[(uid, d)] = n
                else:
                    drop[d] = drop.get(d, 0) + 1
        self.len_filter_report = {"max_target_len": self.max_target_len,
                                  "dropped_by_dialect": drop,
                                  "kept_pairs": len(ok)}
        return ok

    def tok_len(self, uid: str, dialect: str) -> int:
        """(utt, dialect) 的确定性目标 token 数(_build_len_filter 顺带记的);未知返回 0。
        供 bucketing 的 B×Lmax² 显存预算用。"""
        return self._tok_len.get((uid, dialect), 0)

    def _available(self) -> dict:
        """{utt_id: [有标签的 dialect]}(标签为 None / 超长的 dialect 不可用)。"""
        av = {}
        for uid, u in self.utts.items():
            lab = self.labels.get(uid, {})
            ds = [d for d in u.get("dialects", []) if lab.get(d)
                  and (self._len_ok is None or (uid, d) in self._len_ok)]
            if ds:
                av[uid] = ds
        return av

    def set_epoch(self, epoch: int):
        self.epoch = epoch
        av = self._available()
        if self.train:
            self.last_mix_report = {}
            self._plan = dialect_sampler(av, self.seed, epoch,
                                         mix=self.dialect_mix,
                                         report=self.last_mix_report)
            # 混比生效自证(O4 验收即看此行):配额来自注入 mix 还是缺省,日志可查,不靠信任
            print(f"  epoch{epoch} 混比报告: " + " ".join(
                f"{d}[池{r['pool_size']} 额{r['quota']} 过采x{r['oversample_ratio']}]"
                for d, r in sorted(self.last_mix_report.items())), flush=True)
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

        # tiling(R-S11.3):TAST/AMT 每 epoch 每样本 t0~U[0, 40-dur](augment=False 时恒 0)
        t0_s = tiling_offset(dialect, u.get("dur_s", 0.0), uid, self.epoch, self.seed) \
            if (self.train and self.augment) else 0.0
        t0_bins = int(round(t0_s / (TS_MS / 1000.0)))
        text = apply_tiling_text(text, t0_bins)

        enc = encode_target(self.tok, dialect, text,
                            sample=self.train and self.augment,
                            alpha=self.alpha, domain=u.get("domain"))
        # alpha 采样切分可能比确定性切分更长 → 超上限就退回确定性切分(预过滤保证它必然合规)
        if self.max_target_len and len(enc["input_ids"]) + 1 > self.max_target_len:
            enc = encode_target(self.tok, dialect, text, sample=False, domain=u.get("domain"))
            if len(enc["input_ids"]) + 1 > self.max_target_len:
                raise ValueError(f"目标序列超长(预过滤应已拦下):{uid}/{dialect} "
                                 f"{len(enc['input_ids']) + 1} > {self.max_target_len}")
        enc["audio"] = load_audio(u["audio_path"], self.sr, tile_pad_s=t0_s,
                                  win=u.get("win"))  # LOCAL;win=窗内 utt 只读整曲的 [t0,t1]
        if self.train and self.acoustic_aug:
            # C1a(D58):标签安全声学增广,旗子门控(--augment-acoustic),二轮启动配置开
            enc["audio"] = acoustic_augment(enc["audio"], uid, self.epoch, self.seed)
        enc["utt_id"] = uid
        enc["dialect"] = dialect
        return enc


class RubatoDataModule:
    """
    train.py:train() 依赖的接口:train_batches(epoch) 生成器 + nasap_val + maestro_val + labels。
    train_batches 每 epoch 按混比重采样、bucketing(≤max_batch_sec)、collate。
    val 列表就是 assemble 的 utt dict(audio_path/win/dur_s),eval hook 按需窗读音频;
    labels 是全量 {utt_id: {A2S..AMT}} —— eval 的参照(AMT ref_notes / A2S NED)从这里取,
    缺省退回 train_ds.labels(build_dataset 传的本就是全 split 的标签字典)。
    """
    def __init__(self, train_ds: RubatoDataset, nasap_val: list[dict],
                 maestro_val: list[dict], pad_id: int = 0,
                 max_batch_sec: float = 560.0, labels: dict | None = None,
                 max_attn_sq: int = 8 * 1024 * 1024):
        self.train_ds = train_ds
        self.nasap_val = nasap_val          # [utt dict](infer_a2s 用,audio 按需加载)
        self.maestro_val = maestro_val      # [utt dict](infer_amt/note_f1 用)
        self.labels = labels if labels is not None else getattr(train_ds, "labels", {})
        self.pad_id = pad_id
        self.max_batch_sec = max_batch_sec
        self.max_attn_sq = max_attn_sq      # B×Lmax² 预算(≈8 条满长 1024 文本/批)
        self.last_oversize_report = {}

    def train_batches(self, epoch: int, start_batch: int = 0):
        self.train_ds.set_epoch(epoch)
        meta = self.train_ds.sample_meta()
        idx_of = {(u, d): i for i, (u, d) in enumerate(self.train_ds._plan)}
        # 【显存正确性,执行端 29.5GB OOM 实测】tiling 会把音频前置补零到 t0+dur(最长 40s):
        # 按补零【前】时长记账,2s 样本装 30 个、取样时各自膨胀到 40s → 实际 batch 上千秒。
        # tiling_offset 是 (utt, epoch) 确定性哈希 —— 这里预算用的 t0 与 __getitem__ 取到的
        # 严格同值,预算 = 真实进 GPU 的音频秒数。tok 喂 B×Lmax² 预算(短音频长文本的批)。
        samples = []
        for u, d, dur in meta:
            t0 = tiling_offset(d, dur, u, epoch, self.train_ds.seed) \
                if (self.train_ds.train and self.train_ds.augment) else 0.0
            samples.append({"utt_id": u, "dialect": d, "dur_s": dur + t0,
                            "tok": self.train_ds.tok_len(u, d)})
        # bucket_batches 的“≤max_batch_sec”必须是硬不变量。旧逻辑会把单条超限样本
        # 作为 singleton 放行（现役缓存中确有百秒级段），既会 OOM，也会让日志中
        # audio=131s 这类最后 micro-batch 冒充完整有效步。这里显式隔离并逐 epoch 记账。
        oversized = [s for s in samples if float(s["dur_s"]) > self.max_batch_sec]
        self.last_oversize_report = {
            "epoch": epoch,
            "count": len(oversized),
            "max_sec": max((float(s["dur_s"]) for s in oversized), default=0.0),
            "examples": [
                {"utt_id": s["utt_id"], "dialect": s["dialect"],
                 "dur_s": round(float(s["dur_s"]), 3)}
                for s in sorted(oversized, key=lambda x: float(x["dur_s"]), reverse=True)[:5]
            ],
        }
        if oversized:
            print(f"  epoch{epoch} 超 batch 上限隔离: {len(oversized)} 对 "
                  f"(max={self.last_oversize_report['max_sec']:.1f}s > "
                  f"{self.max_batch_sec:.1f}s; 样例={self.last_oversize_report['examples']})",
                  flush=True)
            samples = [s for s in samples if float(s["dur_s"]) <= self.max_batch_sec]
        batches = bucket_batches(samples, self.max_batch_sec, self.max_attn_sq)
        # bucket_batches 按时长排序装桶,返回顺序恒为短→长。若照此逐 epoch 产出,
        # 等于固定的长度课程且跨 epoch 零随机 —— 会给优化引入方向性偏置。
        # 桶【内部】保持长度同质(算力效率),只把桶的【顺序】按 epoch 确定性打乱。
        rng = random.Random((self.train_ds.seed ^ (epoch * 0x9E3779B1)) & 0xFFFFFFFF)
        rng.shuffle(batches)
        if start_batch < 0 or start_batch > len(batches):
            raise ValueError(f"epoch{epoch} 恢复 batch_cursor={start_batch} 越界；"
                             f"本 epoch 只有 {len(batches)} 批")
        if start_batch:
            print(f"  epoch{epoch} 精确续跑:跳过已完成 {start_batch}/{len(batches)} 批"
                  "(只跳 metadata，不重复读音频)", flush=True)
        for batch_samples in batches[start_batch:]:
            items = []
            for s in batch_samples:
                i = idx_of[(s["utt_id"], s["dialect"])]
                items.append(self.train_ds[i])
            yield collate_batch(items, self.pad_id)
