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
    def __init__(self, plateau_patience: int = 3, plateau_eps: float = 0.2,
                 proxy_plateau_eps: float = 0.002):
        self.omr_history = []  # 向后兼容：指向最近一次使用的指标历史
        self.metric_history = {}
        self.loss_median_window = []
        self.plateau_patience = plateau_patience
        self.plateau_eps = plateau_eps
        self.proxy_plateau_eps = proxy_plateau_eps

    def update(self, step: int, parseable_rate: float, maestro_amt_f1: float | None,
               selection_value: float | None, recent_loss: float | None = None,
               selection_metric: str = "text_ned_proxy") -> dict:
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

        # 4. 连续 3 个完整 eval 的选择指标无改善 → 收敛。
        # 训练选择指标当前只允许明确标名的 text_ned_proxy；接口仍按名称分历史，
        # 防止未来新增代理时把不同量纲混在一起。
        if selection_value is not None:
            history = self.metric_history.setdefault(selection_metric, [])
            history.append(selection_value)
            self.omr_history = history
            eps = (self.proxy_plateau_eps
                   if selection_metric == "text_ned_proxy"
                   else self.plateau_eps)
            if len(history) >= self.plateau_patience + 1:
                recent = history[-(self.plateau_patience + 1):]
                best_old = min(recent[:-self.plateau_patience]) if len(recent) > self.plateau_patience else recent[0]
                improved = any(best_old - v > eps
                               for v in recent[-self.plateau_patience:])
                if not improved:
                    return {"action": "converged",
                            "reason": f"连续{self.plateau_patience}个 eval "
                                      f"{selection_metric} 无改善(<{eps})"}

        return {"action": "continue", "reason": ""}

    def state_dict(self) -> dict:
        """可 JSON 序列化的训练控制状态；断点恢复后收敛判据不能失忆。"""
        return {
            "metric_history": {k: list(v) for k, v in self.metric_history.items()},
            "loss_median_window": list(self.loss_median_window),
            "plateau_patience": self.plateau_patience,
            "plateau_eps": self.plateau_eps,
            "proxy_plateau_eps": self.proxy_plateau_eps,
        }

    def load_state_dict(self, state: dict) -> None:
        """恢复历史观测；阈值沿用当前代码配置。"""
        histories = state.get("metric_history") or {}
        self.metric_history = {
            str(k): [float(x) for x in v] for k, v in histories.items()
            if isinstance(v, list)
        }
        self.loss_median_window = [
            float(x) for x in (state.get("loss_median_window") or [])][-20:]
        self.omr_history = next(iter(self.metric_history.values()), [])
