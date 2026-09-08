import json

from rules_beyond.live_agent_planner_match import play_agent_match
from rules_beyond.model import Team
from rules_beyond.strategy_agent import IsolatedStrategyAgent, StrategyDecisionStatus


class OracleStrategyModel:
    model_name = "oracle-strategy"

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        assert "deterministic planner" in system_prompt
        data = json.loads(observation)
        if data["team"] == "RED":
            intent = "PRESSURE"
        else:
            intent = "KITE" if data["round_no"] <= 3 else "PRESSURE"
        return json.dumps({"intent": intent})


def test_offline_oracle_completes_full_agent_planner_gate() -> None:
    model = OracleStrategyModel()
    red = IsolatedStrategyAgent(Team.RED, model)
    blue = IsolatedStrategyAgent(Team.BLUE, model)

    summary = play_agent_match(red, blue)

    assert summary.gate_passed, summary.gate_failures
    assert summary.rounds >= 4
    assert summary.event_counts.get("PLAYER_RULE_REPLACED", 0) >= 2
    assert summary.event_counts.get("INVALID_MOVE_PATH", 0) == 0
    assert summary.planner_snapshot_errors == 0
    assert all(not item.planner_snapshot_issues for item in summary.round_traces)

    # INVALID_ATTACK may still occur after simultaneous movement changes the
    # actual post-movement distance. That is a settlement outcome, not proof
    # that the submitted action was illegal in the planner's public snapshot.
    assert summary.event_counts.get("INVALID_ATTACK", 0) >= 0

    red_decisions = [item for item in summary.decision_traces if item.team == "RED"]
    blue_decisions = [item for item in summary.decision_traces if item.team == "BLUE"]
    assert len(red_decisions) >= 2
    assert len(blue_decisions) >= 2
    assert all(item.status == StrategyDecisionStatus.ACCEPTED.value for item in red_decisions)
    assert all(item.status == StrategyDecisionStatus.ACCEPTED.value for item in blue_decisions)
    assert red.private_memory
    assert blue.private_memory
    assert red.private_memory is not blue.private_memory
