"""
S8 装配层:把三份 labels.jsonl(+ 音频)合成 RubatoDataset 需要的 (utts, labels)。

【为什么需要它 —— 一个此前缺失的关键胶水】
s5(PDMX)、s7(nASAP)、gen_amt(MAESTRO)各自把标签落盘,但三份文件:
  - schema 不一致:pdmx/nasap 用 {utt_id, A2S, A2S_lite, TAST, AMT};
    maestro(gen_amt)用 {midi_file, amt_text, split} —— 键名都不同(midi_file≠utt_id,
    amt_text≠AMT)。直接 load 合并会漏掉整份 MAESTRO 的 AMT。
  - 都不带 audio_path / dur_s,而 RubatoDataset 需要它们做 bucketing / tiling / 采样。
本模块把三份归一到统一 schema、按注入的 audio_resolver 配上音频、按非空标签推导可用 dialect,
任何配不上音频/无可用 dialect 的样本都【计数不静默丢】,产出 (utts, labels, stats)。

分层:
  纯逻辑(沙盒可测):schema 归一、dialect 推导、split 分区、stats 记账。
  执行端注入:audio_resolver(真实渲染产物/FLAC 路径 + 时长),见 scripts/build_dataset.py。
"""
from __future__ import annotations
import re

from rubato.platform import read_jsonl

DIALECT_KEYS = ("A2S", "A2S_lite", "TAST", "AMT")
_SLUG_RE = re.compile(r"[^0-9A-Za-z]+")


def _slug(s: str) -> str:
    return _SLUG_RE.sub("_", str(s)).strip("_")


def normalize_row(row: dict, kind: str) -> tuple[str, dict, str | None] | None:
    """
    一行 labels.jsonl → (utt_id, {A2S,A2S_lite,TAST,AMT}, split|None)。无法识别返回 None。
      - pdmx/nasap:已有 utt_id + 四方言键(TAST/AMT 可能为 null)。
      - maestro(gen_amt):无 utt_id(用 midi_file 造),AMT 存在 amt_text 里。
    """
    if row.get("utt_id"):
        uid = str(row["utt_id"])
        labels = {k: row.get(k) for k in DIALECT_KEYS}
    elif row.get("midi_file"):                       # maestro amt schema
        uid = "maestro_" + _slug(row["midi_file"])
        labels = {"A2S": None, "A2S_lite": None, "TAST": None,
                  "AMT": row.get("amt_text") or row.get("AMT")}
    else:
        return None
    # 只保留非空字符串标签
    labels = {k: v for k, v in labels.items() if isinstance(v, str) and v.strip()}
    return uid, labels, row.get("split")


def assemble(sources: list[dict], audio_resolver, default_split: str = "train") -> tuple:
    """
    sources: [{"path": <labels.jsonl>, "kind": "pdmx"|"nasap"|"maestro",
               "domain": "synth"|"real"}]
    audio_resolver(utt_id, kind, row) -> (audio_path: str, dur_s: float) | None
        返回 None = 该 utt 没有可用音频(如 PDMX 段未渲染 / FLAC 缺失)→ 计入 no_audio,【不静默】。
    返回 (utts, labels, stats)。
      utts:  [{utt_id, kind, audio_path, dur_s, dialects, split, domain}]
      labels:{utt_id: {A2S?,A2S_lite?,TAST?,AMT?}}
      stats: {per_source: {kind: {...计数}}, totals: {...}, dup_utt_ids: [...]}
    """
    utts: list[dict] = []
    labels: dict[str, dict] = {}
    per_source: dict[str, dict] = {}
    dup_ids: list[str] = []

    for src in sources:
        kind = src["kind"]
        domain = src.get("domain")
        st = per_source.setdefault(kind, {"rows": 0, "kept": 0, "bad_schema": 0,
                                          "no_dialect": 0, "no_audio": 0, "dup": 0})
        for row in read_jsonl(src["path"]):
            st["rows"] += 1
            norm = normalize_row(row, kind)
            if norm is None:
                st["bad_schema"] += 1
                continue
            uid, lab, split = norm
            dialects = [k for k in DIALECT_KEYS if lab.get(k)]
            if not dialects:
                st["no_dialect"] += 1
                continue
            if uid in labels:                        # 重复 utt_id(跨源撞名或重跑追加)
                st["dup"] += 1
                dup_ids.append(uid)
                continue
            res = audio_resolver(uid, kind, row)
            if res is None:
                st["no_audio"] += 1
                continue
            audio_path, dur_s = res
            u = {"utt_id": uid, "kind": kind, "audio_path": audio_path,
                 "dur_s": float(dur_s), "dialects": dialects,
                 "split": split or default_split, "domain": domain}
            # 【窗内 utt】行带 win=[t0,t1](秒,整曲坐标)= 该 utt 只用整曲音频的一个窗
            # (MAESTRO AMT 切窗:整曲 FLAC 不切文件,加载时按窗读)。dur_s 必须按窗长,
            # 否则 bucketing/tiling 拿整曲时长会全错。
            win = row.get("win")
            if isinstance(win, (list, tuple)) and len(win) == 2:
                u["win"] = [float(win[0]), float(win[1])]
                u["dur_s"] = float(win[1]) - float(win[0])
            utts.append(u)
            labels[uid] = lab
            st["kept"] += 1

    totals = {"utts": len(utts), "labels": len(labels),
              "by_dialect": {d: sum(1 for u in utts if d in u["dialects"])
                             for d in DIALECT_KEYS},
              "by_split": _count(u["split"] for u in utts),
              "by_kind": _count(u["kind"] for u in utts)}
    stats = {"per_source": per_source, "totals": totals, "dup_utt_ids": dup_ids[:20]}
    return utts, labels, stats


def partition_by_split(utts: list[dict]) -> dict:
    """按 split 字段分区。返回 {train:[...], val:[...], test:[...], other:[...]}。"""
    out = {"train": [], "val": [], "test": [], "other": []}
    for u in utts:
        s = (u.get("split") or "train").lower()
        key = s if s in out else ("val" if s in ("valid", "validation", "dev") else
                                  "test" if s in ("test", "eval") else "other")
        out[key].append(u)
    return out


def _count(it) -> dict:
    d: dict = {}
    for x in it:
        d[x] = d.get(x, 0) + 1
    return d
