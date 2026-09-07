from dataclasses import dataclass

from .cases import Challenge


@dataclass
class Simulation:
    baseline_score: int
    strategy_score: int
    advantage: int
    trace: list[str]


class DeterministicEngine:
    """受控微型模拟器：用固定状态验证“策略标签是否确有收益”。"""
    _advantages = {
        "maintain_low_hp": 24, "trade_for_extra_action": 18, "block_center_route": 20,
        "feed_strongest_unit": 22, "preserve_weakest_unit": 16, "rush_then_block": 19,
    }

    def simulate(self, case: Challenge, strategy_id: str, repaired: bool = False) -> Simulation:
        baseline = 50
        expected = case.expected_strategy
        raw_gain = self._advantages.get(strategy_id, 0) if strategy_id == expected else 0
        gain = max(0, raw_gain - 16) if repaired else raw_gain
        trace = ["第1回合：双方进入受限棋盘。", f"公共规则生效：{case.public_rule}"]
        if strategy_id == expected:
            trace.append("蓝方执行候选策略，触发规则中的可利用边界。")
        else:
            trace.append("候选策略未触发可验证的规则收益。")
        if repaired:
            trace.append(f"玩家追加修正规则：{case.repair_rule}")
        trace.append(f"确定性结算：蓝方策略收益 {gain} 分。")
        return Simulation(baseline, baseline + gain, gain, trace)
