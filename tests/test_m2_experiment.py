from __future__ import annotations

import json

import pytest

import rules_beyond.m2_experiment as m2
from rules_beyond.m2_experiment import (
    Arm, BudgetMeter, BudgetStop, FALLBACK_PLAN, MeteredModel, RichPlanner, SCENARIOS,
    arm_order, parse_rich_plan, play_match, replay_reconstructable, rich_decide,
    run_experiment,
)
from rules_beyond.model import Team


class FakeModel:
    model_name = "fake"
    def __init__(self, output='{"intent":"HOLD"}'):
        self.output = output
    def generate_strategy(self, *, system_prompt, observation):
        return self.output


RICH = json.dumps({
    "mode": "KITE", "target_distance": 3, "weapon_preference": "BOW",
    "risk_budget": "LOW", "short_term_goal": "CONTROL_DISTANCE",
    "horizon_rounds": 2, "contingency": "SEPARATE",
})


def test_rich_protocol_is_closed_and_falls_back_whole_plan():
    assert parse_rich_plan(RICH).target_distance == 3
    bad = json.loads(RICH)
    bad["extra"] = True
    assert rich_decide(FakeModel(json.dumps(bad)), "{}").plan == FALLBACK_PLAN


@pytest.mark.parametrize("field,value", [("target_distance", 0), ("horizon_rounds", 4)])
def test_rich_protocol_rejects_bounds(field, value):
    bad = json.loads(RICH)
    bad[field] = value
    with pytest.raises(ValueError):
        parse_rich_plan(json.dumps(bad))


def test_assignment_rotation_is_deterministic():
    assert arm_order(1_280_000) == (Arm.A, Arm.B, Arm.C)
    assert arm_order(1_280_001) == (Arm.B, Arm.C, Arm.A)
    assert arm_order(1_280_002) == (Arm.C, Arm.A, Arm.B)


def test_budget_stops_before_excess_call():
    meter = BudgetMeter(max_calls=1, max_cost_usd=5)
    wrapped = MeteredModel(FakeModel(), meter)
    wrapped.generate_strategy(system_prompt="x", observation="y")
    with pytest.raises(BudgetStop, match="BUDGET_STOP"):
        wrapped.generate_strategy(system_prompt="x", observation="y")


def test_budget_stop_is_not_converted_to_model_fallback():
    meter = BudgetMeter(max_calls=1, max_cost_usd=5)
    def factory(shared):
        return MeteredModel(FakeModel(), shared)
    with pytest.raises(BudgetStop):
        play_match(Arm.B, "S0_control", 1_280_000, factory, meter)


def test_all_arms_run_offline_without_integrity_errors():
    meter = BudgetMeter(max_calls=500, max_cost_usd=5)
    def factory(shared):
        # B and C require different closed outputs.
        return MeteredModel(FakeModel(), shared)
    a = play_match(Arm.A, "S1_mobility", 1_280_000, factory, meter)
    b = play_match(Arm.B, "S1_mobility", 1_280_000, factory, meter)
    def rich_factory(shared):
        return MeteredModel(FakeModel(RICH), shared)
    c = play_match(Arm.C, "S1_mobility", 1_280_000, rich_factory, meter)
    assert {a.arm, b.arm, c.arm} == {"A", "B", "C"}
    assert a.planner_snapshot_issues == b.planner_snapshot_issues == c.planner_snapshot_issues == 0
    assert all(record.result for record in (a, b, c))


def test_scenario_matrix_is_frozen():
    assert tuple(SCENARIOS) == ("S0_control", "S1_mobility", "S2_range", "S3_replacement")


def test_experiment_writes_required_safe_artifacts(monkeypatch, tmp_path):
    class PromptAwareFake(FakeModel):
        def __init__(self, *args, **kwargs):
            super().__init__()
        def generate_strategy(self, *, system_prompt, observation):
            return RICH if "target_distance" in system_prompt else '{"intent":"KITE"}'

    monkeypatch.setattr(m2, "MimoStrategyModel", PromptAwareFake)
    summary = run_experiment([1_280_000], tmp_path, api_key="secret-value", model="fake")
    assert summary["matches"] == 12
    assert summary["planner_snapshot_issues"] == 0
    assert summary["replay_reconstructability"] == 1.0
    assert {path.name for path in tmp_path.iterdir()} == {
        "manifest.json", "matches.jsonl", "decisions.jsonl", "rounds.jsonl",
        "summary.json", "report.md",
    }
    combined = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.iterdir())
    assert "secret-value" not in combined
    assert "raw_model_output" not in combined
