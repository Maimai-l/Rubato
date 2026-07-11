# SOP:数据重跑作战手册(2026-07-11 定稿)

> **给执行端:不要手工跑本文件里的命令。你的全部工作只有三条命令:**
> ```
> python scripts/sop_next.py --status     # 看进度(状态存盘,忘了就跑这条)
> python scripts/sop_next.py --go         # 执行下一步(自动推进,遇 GATE/失败自动停)
> python scripts/sop_next.py --approve XX # 仅当用户明确说"批准 XX"(P1 / P2FULL / P7)
> ```
> 驱动器自动:找到下一步→执行→解析判据→存档(work/sop_state.json)→打印【贴回给用户】块。
> 你只需要:跑 `--go`,把打印的贴回块发给用户;看到 🚫GATE 就停下等用户批准。
> 中断/断电/OOM 后直接再跑 `--go`,自动从断点继续,永不重复已完成的步骤。
> 任何失败:贴回块已含日志尾部,整段发给用户,【不要自己修、不要重试别的命令】。
> RUN.md 五条死规定继续有效。下面的分步说明是背景参考,以驱动器实际执行为准。

## 进度表(每完成一步打勾并填数)

| 步骤 | 状态 | 关键数字(做完填) |
|------|------|--------------------|
| P0 准备 | ☐ | commit=____ |
| P1 S4 速度钳制 | ☐ | outlier_pieces=____ clamped=____ |
| P2 S5 VN 全量重渲 | ☐ | vn_ok=____ utts=____ TAST=____ 回收=____次 |
| P3 S4 补渲 | ☐ | ok=____ fail=____ |
| P4 文本标签重生成 | ☐ | processed=____ labels=____ tempo_fallback=____ |
| P5 MAESTRO AMT 切窗 | ☐ | windows=____ labels=____ win_fail=____ |
| P6 S4 段切割 | ☐ | sliced=____ structure_mismatch=____ |
| P7 tokenizer 重训 | ☐ | vocab=____ split_rate=____ |

依赖关系:P1→P3→P4→P6 严格串行;P2 独立(P1 后即可开);P5 独立随时;P7 要等 P2+P4 都完。
**并行规则:P2(GPU 重)期间只允许同时跑 P5(轻)。P3/P4(CPU 重)不许与 P2 同时跑。**

---

## P0 准备(5 分钟)

```
git pull
git log --oneline -1
```
旧语料与旧文本标签**改名留档**(防新旧混杂,这步不做后面全白跑):
```
cd /d D:\vscode_projects\ee_download\work
ren a2s_corpus.txt a2s_corpus.old.txt
ren pdmx_a2s_labels.jsonl pdmx_a2s_labels.old.jsonl
```
文件不存在就跳过该条。**贴回**:git log 那一行 + 两个 ren 的结果。

## P1 S4 速度钳制(约 10 分钟)✋GATE

```
python scripts/s4_fix_tempo.py            # 干跑
```
**贴回**:整段报告(重点 outlier_pieces 数和例子)。等确认后:
```
python scripts/s4_fix_tempo.py --apply
```
**贴回**:events_clamped / audio_deleted。

## P2 S5 VN 全量重渲(最长,天级;P1 完成后即可开,可跨夜)

```
python scripts/s5_repair_segments.py --all --apply
```
**贴回**:rows_dropped / audio_deleted / done_deleted。然后冒烟:
```
python scripts/s5_vn_render.py --limit 20 --out-corpus work/a2s_corpus_vn.txt
```
判据:vn_ok ≥ 15、TAST > 0、无 traceback。**贴回 DONE 行**。冒烟过了直接全量:
```
python scripts/s5_vn_render.py --out-corpus work/a2s_corpus_vn.txt      # 终端1
python scripts/memtrace.py --interval 10                               # 终端2
```
> 注意 `--out-corpus` 必须是 **a2s_corpus_vn.txt**(独立文件)——P4 的合并会重写 a2s_corpus.txt,
> VN 语料写同一文件会被互相污染。
判据:跑完不 OOM;memtrace 无单进程无界爬升(VN 子进程 ≤4GB 锯齿)。
**贴回**:DONE 行(全部计数)+ memtrace 最后 10 行。

## P3 S4 补渲(P1 后,且不与 P2 同时;小时级)

```
python scripts/s4_parallel.py
```
判据:只重渲 P1 删掉的曲(skipped ≈ 其余全部)。**贴回**:DONE 行。

## P4 文本标签重生成(P3 后;CPU 重,约数小时)

```
python scripts/s5_parallel.py
```
判据:processed 与上次同量级(~48k);合并产出全新 work/a2s_corpus.txt 与 pdmx_a2s_labels.jsonl。
**贴回**:processed / segments / labels / chars + 报告里 tempo_fallback 的占比。

## P5 MAESTRO AMT 切窗(轻,<1 小时;随时可跑,允许与 P2 并行)

```
python scripts/s6_amt_windows.py --limit 5      # 冒烟
python scripts/s6_amt_windows.py                # 全量
```
判据:win_fail 占比 < 5%。**贴回**:两次 DONE 计数。

## P6 S4 段切割(P4 后;小时级)

```
python scripts/s4_slice_segments.py --limit 20   # 冒烟
python scripts/s4_slice_segments.py              # 全量
```
判据:sliced 为主;**structure_mismatch 占比重点贴回**(高=MIDI 展开反复,要报我处理)。
**贴回**:全量计数表 + 随手抽听 2 段(边界应在小节线、速度自然)。

## P7 tokenizer 重训(P2 和 P4 都完成后;<1 小时)✋GATE

```
python -c "from rubato.data.tokenizer import train_unigram; print(train_unigram(['work/a2s_corpus.txt','work/a2s_corpus_vn.txt'],'work/rubato_spm',vocab_size=8000,spec_path='configs/vocab_spec.json'))"
python -c "from rubato.data.tokenizer import check_glyph_coverage as c; print(c('work/rubato_spm.model'))"
```
判据:vocab_size=8000、fell_back=False;split_rate<0.30。**贴回**:两条输出原文。

---

## 明确不做的事
- 不重渲 S4 速度正常的 ~48k 整曲(本来就按真速度渲的)。
- 不碰 MAESTRO FLAC(s6_convert_all)、nASAP(s7)——审计干净。
- **不运行** s4_retry.py / s4_batch_render.py / s4_retry_worker.py(已截断为守卫)。
- 旧模型 checkpoint 一律作废,P7 完成前不开训练。
