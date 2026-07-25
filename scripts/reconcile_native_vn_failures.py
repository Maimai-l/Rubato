"""
Native VN R3 失败重算。
按 handoff 2026-07-25 第一步：
以 native_vn_full.*.batches.jsonl、逐首隔离审计和标签/音频实际存在性重建最终 failure 清单；
输出可重消费的 piece 列表（已补回但仍在隔离集合中的 native_missing_*）。
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\vscode_projects\ee_download")
WORK = ROOT / "work"
REPORTS = ROOT / "Rubato" / "reports"

manifest_path = WORK / "manifest_pieces_round3_restore_train_ms4.jsonl"
batch_glob = WORK / "native_vn_full.*.batches.jsonl"
isolated_path = WORK / "leaf15_57_isolated.jsonl"
failures_path = WORK / "pdmx_vn_failures_r3_native.jsonl"
labels_path = WORK / "pdmx_perf_labels_r3_native.staging.jsonl"
audio_dir = WORK / "pdmx_audio_r3_native"
vn_root = WORK / "vn_native_r3_train"


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def main():
    # 1. manifest: piece_id -> leaf
    print("[1/6] 读取 manifest...")
    piece_to_leaf = {}
    leaf_pieces = defaultdict(set)
    xml_norm_root = WORK / "xml_norm_r3_train"
    skipped_non_r3 = 0
    for row in read_jsonl(manifest_path):
        pid = row.get("piece_id")
        xml = row.get("xml_norm") or row.get("xml_raw") or ""
        if not pid or not xml:
            continue
        xml_path = Path(xml)
        if not xml_path.is_absolute():
            xml_path = WORK / xml_path
        try:
            leaf = str(xml_path.parent.relative_to(xml_norm_root)).replace("/", "\\")
        except ValueError:
            skipped_non_r3 += 1
            continue
        piece_to_leaf[pid] = leaf
        leaf_pieces[leaf].add(pid)
    print(f"  manifest pieces: {len(piece_to_leaf)}, leaves: {len(leaf_pieces)}, skipped non-R3: {skipped_non_r3}")

    # 2. batches: 每个 leaf 的最终状态（按 finished_utc 最晚）
    print("[2/6] 读取 batches 账本...")
    batch_files = sorted(WORK.glob("native_vn_full.*.batches.jsonl"))
    leaf_state = {}
    for bf in batch_files:
        for row in read_jsonl(bf):
            leaf = row.get("leaf", "")
            if not leaf:
                continue
            # 保留每个 leaf 最新状态
            key = (bf.name, leaf)
            ts = row.get("finished_utc") or row.get("started_utc") or ""
            if key not in leaf_state or ts > leaf_state[key][0]:
                leaf_state[key] = (ts, row)
    # 合并同名 leaf 跨文件最新
    leaf_latest = {}
    for (fn, leaf), (ts, row) in leaf_state.items():
        if leaf not in leaf_latest or ts > leaf_latest[leaf][0]:
            leaf_latest[leaf] = (ts, row)
    print(f"  batch files: {len(batch_files)}, leaf states: {len(leaf_latest)}")

    # 3. isolated 审计
    print("[3/6] 读取 leaf15_57 逐首审计...")
    isolated_ok = set()
    isolated_fail = {}
    for row in read_jsonl(isolated_path):
        xml = row.get("xml", "")
        pid = Path(xml).stem
        if row.get("ok"):
            isolated_ok.add(pid)
        else:
            isolated_fail[pid] = row
    print(f"  isolated ok: {len(isolated_ok)}, fail: {len(isolated_fail)}")

    # 4. 已消费 piece（有标签）
    print("[4/6] 读取 staging 标签...")
    labeled_pids = set()
    for row in read_jsonl(labels_path):
        pid = row.get("piece_id")
        if pid:
            labeled_pids.add(pid)
    print(f"  labeled pieces: {len(labeled_pids)}")

    # 5. 扫描实际存在的 MIDI/CSV（vn_native_r3_train）
    print("[5/6] 扫描官方 VN 产物...")
    vn_has_midi_csv = set()
    if vn_root.exists():
        for mid in vn_root.rglob("*_by_isgn_Bach.mid"):
            pid = mid.stem.split("_")[1] if "_" in mid.stem else mid.stem
            csv = Path(str(mid) + "_midi_notes.csv")
            if csv.exists():
                vn_has_midi_csv.add(pid)
    print(f"  pieces with MIDI+CSV: {len(vn_has_midi_csv)}")

    # 6. 扫描实际存在的音频（pdmx_audio_r3_native）
    print("[6/6] 扫描 S5 输出音频...")
    audio_pids = set()
    if audio_dir.exists():
        for p in audio_dir.iterdir():
            if p.suffix in (".flac", ".wav"):
                # pdmxperf_<pid>_<seg>.wav/flac
                parts = p.stem.split("_")
                if len(parts) >= 2 and parts[0] == "pdmxperf":
                    audio_pids.add(parts[1])
    print(f"  pieces with audio: {len(audio_pids)}")

    # 7. 重建失败清单
    print("\n[RECONCILE] 重建最终 failure 清单...")
    current_failures = {}
    for row in read_jsonl(failures_path):
        pid = row.get("piece_id")
        if pid:
            current_failures[pid] = row

    all_pids = set(piece_to_leaf.keys())
    success_pids = labeled_pids | audio_pids
    recoverable_pids = vn_has_midi_csv - success_pids   # 有产物但尚未消费
    final_failures = {}
    recovered = {}
    stale_failures = {}

    for pid in all_pids - success_pids - recoverable_pids:
        # 无产物、无标签、无音频 = 确认失败
        leaf = piece_to_leaf.get(pid)
        detail = "native_missing_midi_or_csv"
        if pid in isolated_fail:
            detail = f"isolated_fail:{isolated_fail[pid].get('exit_code')}"
        elif pid in isolated_ok:
            detail = "isolated_ok_but_no_output"
        final_failures[pid] = {
            "piece_id": pid,
            "leaf": leaf,
            "reason": f"vn_infer:{detail}",
            "vn_detail": detail,
        }

    for pid in recoverable_pids:
        if pid in current_failures:
            # 已补回但仍在隔离清单：释放并只重消费这些
            recovered[pid] = {
                "piece_id": pid,
                "leaf": piece_to_leaf.get(pid),
                "old_reason": current_failures[pid].get("reason"),
                "status": "recovered_needs_reconsume",
            }

    for pid in current_failures:
        if pid in success_pids:
            # 已成功消费但仍在 failures 中：应释放
            stale_failures[pid] = {
                "piece_id": pid,
                "leaf": piece_to_leaf.get(pid),
                "old_reason": current_failures[pid].get("reason"),
                "status": "stale_success_needs_release",
            }

    # 输出报告
    report_path = REPORTS / "NATIVE_VN_FAILURE_RECONCILE_2026-07-25.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Native VN R3 失败重算报告\n")
        f.write(f"生成时间: 2026-07-25\n\n")
        f.write("## 输入口径\n")
        f.write(f"- manifest pieces: {len(piece_to_leaf)}\n")
        f.write(f"- leaf states (batches): {len(leaf_latest)}\n")
        f.write(f"- isolated ok: {len(isolated_ok)}\n")
        f.write(f"- isolated fail: {len(isolated_fail)}\n")
        f.write(f"- labeled pieces: {len(labeled_pids)}\n")
        f.write(f"- MIDI+CSV pieces: {len(vn_has_midi_csv)}\n")
        f.write(f"- audio pieces: {len(audio_pids)}\n")
        f.write(f"- current failures.jsonl rows: {len(current_failures)}\n\n")

        f.write("## 汇总\n")
        f.write(f"| 类别 | 数量 |\n")
        f.write(f"| --- | ---: |\n")
        f.write(f"| 所有 R3 piece | {len(all_pids)} |\n")
        f.write(f"| 已成功消费（有标签/音频） | {len(success_pids)} |\n")
        f.write(f"| 有产物待消费（MIDI+CSV） | {len(recoverable_pids)} |\n")
        f.write(f"| 最终确认失败 | {len(final_failures)} |\n")
        f.write(f"| 已补回需重消费 | {len(recovered)} |\n")
        f.write(f"| 成功但仍在 failures 中（需释放） | {len(stale_failures)} |\n\n")

        f.write("## 已补回需重消费的 piece 列表（前 50）\n")
        for pid in sorted(recovered)[:50]:
            r = recovered[pid]
            f.write(f"{pid}\t{r['leaf']}\t{r['old_reason']}\n")
        if len(recovered) > 50:
            f.write(f"... 共 {len(recovered)} 条，完整列表见 recovered_pids.jsonl\n")
        f.write("\n")

        f.write("## 最终确认失败的 piece 列表（前 50）\n")
        for pid in sorted(final_failures)[:50]:
            r = final_failures[pid]
            f.write(f"{pid}\t{r.get('leaf')}\t{r.get('reason')}\n")
        if len(final_failures) > 50:
            f.write(f"... 共 {len(final_failures)} 条，完整列表见 final_failures.jsonl\n")
        f.write("\n")

        f.write("## 成功但仍在 failures 中需释放的 piece 列表（前 50）\n")
        for pid in sorted(stale_failures)[:50]:
            r = stale_failures[pid]
            f.write(f"{pid}\t{r.get('leaf')}\t{r['old_reason']}\n")
        if len(stale_failures) > 50:
            f.write(f"... 共 {len(stale_failures)} 条，完整列表见 stale_failures.jsonl\n")
        f.write("\n")

    # 写完整 JSONL 便于后续消费
    recovered_path = WORK / "native_vn_recovered_pids.jsonl"
    final_fail_path = WORK / "native_vn_final_failures.jsonl"
    stale_path = WORK / "native_vn_stale_failures.jsonl"
    with open(recovered_path, "w", encoding="utf-8") as f:
        for pid in sorted(recovered):
            f.write(json.dumps(recovered[pid]) + "\n")
    with open(final_fail_path, "w", encoding="utf-8") as f:
        for pid in sorted(final_failures):
            f.write(json.dumps(final_failures[pid]) + "\n")
    with open(stale_path, "w", encoding="utf-8") as f:
        for pid in sorted(stale_failures):
            f.write(json.dumps(stale_failures[pid]) + "\n")

    print(f"\n报告: {report_path}")
    print(f"最终确认失败: {len(final_failures)}")
    print(f"已补回需重消费: {len(recovered)}")
    print(f"成功但仍在 failures 中: {len(stale_failures)}")
    print(f"输出文件:\n  {recovered_path}\n  {final_fail_path}\n  {stale_path}")


if __name__ == "__main__":
    main()
