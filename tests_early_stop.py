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
r = c.update(step=1000, parseable_rate=0.5, maestro_amt_f1=None, val_omr_ned=None)
check("pause_low_parseable", r["action"] == "pause_unparseable", r)
# 高可解析率不触发
r2 = c.update(step=1000, parseable_rate=0.95, maestro_amt_f1=None, val_omr_ned=50.0)
check("no_pause_high_parseable", r2["action"] != "pause_unparseable")

print("[2] 步数门控的 AMT F1 止损")
c = StopController()
# 步<8000 不触发,即使 F1 低
r = c.update(step=5000, parseable_rate=0.95, maestro_amt_f1=50, val_omr_ned=50.0)
check("no_stop_before_8000", r["action"] != "stop_bad_labels", r)
# 步≥8000 且 F1<70 触发
r = c.update(step=8000, parseable_rate=0.95, maestro_amt_f1=50, val_omr_ned=50.0)
check("stop_after_8000_low_f1", r["action"] == "stop_bad_labels", r)
# 步≥8000 但 F1 好 → 继续
c2 = StopController()
r = c2.update(step=9000, parseable_rate=0.95, maestro_amt_f1=90, val_omr_ned=50.0)
check("continue_good_f1", r["action"] == "continue", r)

print("[3] loss 尖峰 → 回滚")
c = StopController()
# 喂正常 loss 建立中位数
for i in range(6):
    c.update(step=i*100, parseable_rate=0.95, maestro_amt_f1=90, val_omr_ned=50.0, recent_loss=1.0)
# 尖峰
r = c.update(step=700, parseable_rate=0.95, maestro_amt_f1=90, val_omr_ned=50.0, recent_loss=5.0)
check("rollback_on_spike", r["action"] == "rollback_lr", r)

print("[4] OMR-NED 平台 → 收敛")
c = StopController(plateau_patience=3, plateau_eps=0.2)
# OMR-NED 持续下降 → 不收敛
for v in [50, 48, 46, 44]:
    r = c.update(step=1000, parseable_rate=0.95, maestro_amt_f1=90, val_omr_ned=v)
check("no_converge_improving", r["action"] != "converged", r)
# 之后平台(无改善)
for v in [43.95, 43.9, 43.88]:
    r = c.update(step=1000, parseable_rate=0.95, maestro_amt_f1=90, val_omr_ned=v)
check("converge_on_plateau", r["action"] == "converged", r)

print("[5] 优先级:严重问题先触发")
c = StopController()
# 可解析率低 + F1 低 同时 → 应先报可解析率(更基础的问题)
r = c.update(step=9000, parseable_rate=0.5, maestro_amt_f1=50, val_omr_ned=50.0)
check("parseable_priority", r["action"] == "pause_unparseable", r)

print(f"\n全部通过: {PASS} 项")
