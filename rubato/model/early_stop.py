"""
S11 条件触发止损(R-S11.7)。纯状态机,沙盒可验证。
替代原时间制 Gate——按步数与指标触发,不按 wall-clock。
"""
from __future__ import annotations


class StopController:
    """
    维护训练状态,每个 eval 周期调 update() 返回动作。
    动作: continue | pause_unparseable | stop_bad_labels | rollback_lr | converged
    """
    def __init__(self, plateau_patience: int = 3, plateau_eps: float = 0.2):
        self.omr_history = []
        self.loss_median_window = []
        self.plateau_patience = plateau_patience
        self.plateau_eps = plateau_eps

    def update(self, step: int, parseable_rate: float, maestro_amt_f1: float | None,
               val_omr_ned: float | None, recent_loss: float | None = None) -> dict:
        """返回 {action, reason}。"""
        # 1. 可解析率 <80% → 暂停(任何时候)
        if parseable_rate < 0.80:
            return {"action": "pause_unparseable",
                    "reason": f"可解析率 {parseable_rate:.2f}<0.80,查 prompt/EOS/投影"}

        # 2. 步 ≥8000 后 AMT F1 <70 → 停训查标签
        if step >= 8000 and maestro_amt_f1 is not None and maestro_amt_f1 < 70:
            return {"action": "stop_bad_labels",
                    "reason": f"step{step} AMT F1 {maestro_amt_f1:.1f}<70,标签管线有 bug"}

        # 3. loss 尖峰 >3×滑动中位数 → 回滚 + lr×0.5
        if recent_loss is not None:
            self.loss_median_window.append(recent_loss)
            if len(self.loss_median_window) > 20:
                self.loss_median_window.pop(0)
            if len(self.loss_median_window) >= 5:
                srt = sorted(self.loss_median_window[:-1])
                median = srt[len(srt) // 2]
                if recent_loss > 3 * median:
                    return {"action": "rollback_lr",
                            "reason": f"loss {recent_loss:.3f}>3×median {median:.3f}"}

        # 4. 连续 3 个 eval OMR-NED 无改善 → 收敛
        if val_omr_ned is not None:
            self.omr_history.append(val_omr_ned)
            if len(self.omr_history) >= self.plateau_patience + 1:
                recent = self.omr_history[-(self.plateau_patience + 1):]
                best_old = min(recent[:-self.plateau_patience]) if len(recent) > self.plateau_patience else recent[0]
                improved = any(best_old - v > self.plateau_eps
                               for v in recent[-self.plateau_patience:])
                if not improved:
                    return {"action": "converged",
                            "reason": f"连续{self.plateau_patience}个 eval OMR-NED 无改善(<{self.plateau_eps})"}

        return {"action": "continue", "reason": ""}
