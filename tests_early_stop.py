"""S11 止损状态机测试。运行: python tests_early_stop.py"""
import sys
sys.path.insert(0, ".")
from rubato.model.early_stop import StopController

PASS = 0
def check(name, cond, detail=""):
    global PASS
    if cond: PASS += 1; print(f"  ok  {name}")
    else: print(f"  FAIL {name}  {detail}"); raise SystemExit(1)

print("[1] 可解析率过低 → 暂停")
c = StopController()
r = c.update(step=1000, parseable_rate=0.5, maestro_amt_f1=None, selection_value=None)
check("pause_low_parseable", r["action"] == "pause_unparseable", r)
# 高可解析率不触发
r2 = c.update(step=1000, parseable_rate=0.95, maestro_amt_f1=None, selection_value=0.5)
check("no_pause_high_parseable", r2["action"] != "pause_unparseable")

print("[2] 步数门控的 AMT F1 止损")
c = StopController()
# 步<8000 不触发,即使 F1 低
r = c.update(step=5000, parseable_rate=0.95, maestro_amt_f1=50, selection_value=0.5)
check("no_stop_before_8000", r["action"] != "stop_bad_labels", r)
# 步≥8000 且 F1<70 触发
r = c.update(step=8000, parseable_rate=0.95, maestro_amt_f1=50, selection_value=0.5)
check("stop_after_8000_low_f1", r["action"] == "stop_bad_labels", r)
# 步≥8000 但 F1 好 → 继续
c2 = StopController()
r = c2.update(step=9000, parseable_rate=0.95, maestro_amt_f1=90, selection_value=0.5)
check("continue_good_f1", r["action"] == "continue", r)

print("[3] loss 尖峰 → 回滚")
c = StopController()
# 喂正常 loss 建立中位数
for i in range(6):
    c.update(step=i*100, parseable_rate=0.95, maestro_amt_f1=90, selection_value=0.5, recent_loss=1.0)
# 尖峰
r = c.update(step=700, parseable_rate=0.95, maestro_amt_f1=90, selection_value=0.5, recent_loss=5.0)
check("rollback_on_spike", r["action"] == "rollback_lr", r)

print("[4] text NED 代理平台 → 收敛")
c = StopController(plateau_patience=3, proxy_plateau_eps=0.002)
# 文本 NED 持续下降 → 不收敛
for v in [.50, .48, .46, .44]:
    r = c.update(step=1000, parseable_rate=0.95, maestro_amt_f1=90,
                 selection_value=v)
check("no_converge_improving", r["action"] != "converged", r)
# 之后平台(无改善)
for v in [.4395, .439, .4388]:
    r = c.update(step=1000, parseable_rate=0.95, maestro_amt_f1=90,
                 selection_value=v)
check("converge_on_plateau", r["action"] == "converged", r)

print("[5] 不同训练代理的历史/量纲必须隔离")
c = StopController(plateau_patience=3, plateau_eps=0.2, proxy_plateau_eps=0.002)
for v in [0.90, 0.89, 0.88, 0.87]:
    r = c.update(step=1000, parseable_rate=0.95, maestro_amt_f1=90,
                 selection_value=v, selection_metric="text_ned_proxy")
check("proxy_small_improvement_counts", r["action"] != "converged", r)
r = c.update(step=1000, parseable_rate=0.95, maestro_amt_f1=90,
             selection_value=50.0, selection_metric="other_metric")
check("metric_histories_separate",
      len(c.metric_history["text_ned_proxy"]) == 4
      and len(c.metric_history["other_metric"]) == 1,
      c.metric_history)
state = c.state_dict()
c_restored = StopController()
c_restored.load_state_dict(state)
check("stopper_state_roundtrip",
      c_restored.metric_history == c.metric_history
      and c_restored.loss_median_window == c.loss_median_window)

print("[6] 优先级:严重问题先触发")
c = StopController()
# 可解析率低 + F1 低 同时 → 应先报可解析率(更基础的问题)
r = c.update(step=9000, parseable_rate=0.5, maestro_amt_f1=50, selection_value=0.5)
check("parseable_priority", r["action"] == "pause_unparseable", r)

print(f"\n全部通过: {PASS} 项")
