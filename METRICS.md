# METRICS.md —— 训练指标手册(看日志自查版)

日志就两处:**训练行**(train_full.log,每步一行)和 **eval 块**(每 1000 步,
代码自动追加进 reports/eval_autolog.md,执行端只负责 commit)。
本手册逐字段解释,给当前参考值和出处;行为以代码为准:
训练行 train.py:698、eval 块 train.py:337-518、止损 early_stop.py。

## 一、训练行(每步)

    step N loss=… avg50=… sem=… ts=… gn=…/avg… enc=… dec=… lrE=… lrD=… audio=…s | A2S=… A2S_lite=… AMT=… TAST=…

| 字段 | 是什么 | 怎么读 |
|---|---|---|
| loss / avg50 | 论文序列损失 ΣCE×T^(-1/2),当步 / 近50步均值 | 量纲 ≈60(**不是**常见的逐 token ≈3,别跨项目比);看 avg50 趋势,单步抖动是常态 |
| sem / ts | 语义 token / 时间戳 token 两部分损失 | sem 是主项;ts 带序数平滑,数值小得多 |
| gn=x/avgY | 裁剪前梯度总范数,当步 / 近50步 | 经验带 ~17-38(8k-12k 实测,EXPERIMENT_H1);**数量级跳变**才是事件,带内波动不用报 |
| enc= dec= | 编码器 / 解码器分组范数 | 校验关系 gn²≈enc²+dec²;哪端在学一眼可见 |
| lrE / lrD | 两参数组当前学习率 | cosine + warmup1500:enc 自 1e-4、dec 自 3e-4 缓降 |
| audio= | 本步累积音频秒(梯度累积) | 目标 ≈2000s/步;长期显著偏低 = 数据供给有问题 |
| A2S= 等四项 | 【训练批】逐方言 sem 滚动均值(近200条,按字母序 A2S/A2S_lite/AMT/TAST) | 四条学习曲线,A2S 是主线;注意这是**训练侧**数字,不是 val |

sem(A2S)参考线:地板 ≈1.2(label smoothing 0.1 的代价,到不了 0,估算);
**2.0 = 里程碑**(止损器"模型未熟"豁免以它为界,train.py:743);
1.5-1.9 = "真学会"经验区(估算)。现状 2.70 @ step 40750(monitor.md)。

## 二、eval 块(每 1000 步,autolog)

**多源探针**(固定 4 样本池:nasap_Shi05M、maestro_MIDI-Unprocessed_11、pdmx 两条;
build_dataset.py:462,逐 eval 可比):

    eval 多源探针 nasap/TAST[utt]: Δsem=+0.04 Δts=+0.12 真sem=0.66 静sem=0.62 acc=0.54 n=704

- 真sem / 静sem:给对前文时**语义 token 的下一步命中率**(教师强制 accuracy,0-1),
  分别用真音频和全零静音。
- **Δsem = 真sem − 静sem = 该源上模型读没读音频**。≥+0.10 明确在读;≈0.00 = 只靠文本惯性。
  当前:pdmx 强样本 +0.16~0.27,nasap +0.04~0.09,**maestro/AMT ≈0.00(连续 16+ 次 eval,
  O4 挂账,step 50000 决策)**。
- acc = 全 token 命中率;n = 计分 token 数。

**样本预测[0]/[1] + 解码现场**:确定性前两个 val 样本的自由解码。
`'|4/4k0'` **不是模型输出**,是校验拒绝后的兜底常量(infer.py:24);
出现兜底时"解码现场"打出被拒的真实输出(raw)和违规项(viol)——看真实水平看这里。
**样本预测[首个通过 utt]**:当轮第一条真正过校验的预测 + 同样本参照(防"只看失败样本"偏差)。

**汇总行**:

    eval 汇总: parseable=0.08 empty=0.92 n=48 样本0='|4/4k0' 探针acc=0.54/前缀0.59 eotP0=0.0000

- **parseable:日常最重要的单一进度数** —— 48 个固定 val 样本里自由解码通过全部校验的比例。
  当前 0.02-0.10 缓升(autolog 36000-40000 区间);终态要 →0.80+(止损器成熟线)。
- empty:兜底比例(与 parseable 大致互补,中间还有"有输出但违规"的样本)。
- 探针acc/前缀:池中第一条(nasap_Shi05M)教师强制命中率 / 前 32 token 命中率。
- eotP0:第一位就想吐终止符的概率 = **塌缩报警器**。一直 0.000x = 健康;>0.5 才报警。

**指标行**:

    eval 指标: parseable=… amt_f1=0.0 omr_ned=0.918 n_nasap=48 n_maestro=48

- amt_f1:MAESTRO 上音符级 F1(×100)。论文终点 97.0;**当前 0.0 = AMT 病**(与 Δsem≈0 同源)。
- omr_ned:通过校验样本的文本差异代理(difflib,0=全同,**越低越好**;evaluate.py:147)。
  只用于挑 best.pt 与收敛判定;**不是论文的 OMR-NED**(那个终评才用 LEGATO 官方脚本算,
  口径不同不能直接比)。当前 ~0.86-0.92 = 通过的样本也还粗糙。
- n_nasap / n_maestro:实际评到的样本数(时限 1200s 可能截断,截断另有明示行)。

## 三、止损器现在停在哪条(early_stop.py + train.py:740-766)

规则按优先级串联,前一条命中就不看后面:
1. parseable<0.80 → 暂停 —— **但有双闸豁免**:step<4000 或训练 sem>2.0("模型未熟")。
   现状 sem≈2.7,长期豁免中(日志逢 eval 打一行"(不停训:…)")。
   sem 降破 2.0 后豁免撤销,parseable 必须真达标 —— 这就是 2.0 里程碑的由来。
2. step≥8000 且 amt_f1<70 → 停训查标签(被规则 1 挡着,当前不可达)。
3. loss 尖峰 >3× 近 20 步中位数 → 自动回滚上一 ckpt + lr×0.5。
4. omr_ned 连续 3 eval 无改善 → 判收敛(同被规则 1 挡着)。

## 四、终点线(论文数,evaluate.py:213;终评对照用,平时别拿日常数硬比)

- AMT @ MAESTRO note F1 = 97.0;TAST note F1:ASAP 91.0 / MAESTRO 87.1
- OMR-NED @ ASAP = 64.3(LEGATO 官方脚本口径,越低越好)

## 五、样本名怎么读

- `nasap_Bult-ItoS02M_171360e0_004` = nasap 源 + ASAP 演奏文件名
  (钢琴家姓 Bult-Ito、名缩写 S、第 02 个演奏、M=MIDI)+ 消歧哈希 + 段号
  (s7_full_nasap.py:281;同名演奏文件可属不同曲,哈希消歧)。
- `maestro_MIDI-Unprocessed_…_000` = MAESTRO 原始文件名 + 段号。
- `pdmxperf_Qm…_000` = PDMX 曲目内容哈希(Qm 开头)+ 段号。

## 六、日常三眼 + 报警清单

三眼:① 训练行 A2S 缓降、gn 在带内;② eval 汇总 parseable 趋势向上;
③ maestro/AMT 的 Δsem 是否离开 0.00(O4)。

要喊规划端的:gn 数量级跳变(如 30→300)、loss avg50 连续上翘、eotP0>0.5、
parseable 从爬升区掉回 0 且无解码现场行、autolog 停止追加、audio= 长期远低于 2000。
其余带内波动、empty 高企(现阶段常态)不用报,复盘节点统一看。
