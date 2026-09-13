from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from rules_beyond.api_contract import (
    AdvanceResult,
    DirectionPublic,
    ErrorEnvelope,
    MatchLifecycle,
    MatchResultPublic,
    MatchSnapshot,
    ReplaySnapshot,
    RuleConditionTypePublic,
    RuleDurationPublic,
    RuleEffectTypePublic,
    RuleSubmissionResult,
    RuleTargetPublic,
    RuleWeaponPublic,
    SCHEMA_VERSION,
    StrategyDecisionStatusPublic,
    StrategyIntentPublic,
    TeamPublic,
    WeaponPublic,
)
from rules_beyond.contract_fixtures import build_fixtures
from rules_beyond.model import Direction, MatchResult, Team, Weapon
from rules_beyond.openapi_contract import contract_app
from rules_beyond.rule_dsl import (
    RuleConditionType,
    RuleDuration,
    RuleEffectType,
    RuleTarget,
    RuleWeapon,
)
from rules_beyond.strategy_agent import StrategyDecisionStatus, StrategyIntent


def _values(enum_type: type) -> set[str]:
    return {member.value for member in enum_type}


def test_public_enums_match_current_domain_values() -> None:
    assert _values(TeamPublic) == _values(Team)
    assert _values(DirectionPublic) == _values(Direction)
    assert _values(WeaponPublic) == _values(Weapon)
    assert _values(MatchResultPublic) == _values(MatchResult)
    assert _values(RuleTargetPublic) == _values(RuleTarget)
    assert _values(RuleDurationPublic) == _values(RuleDuration)
    assert _values(RuleConditionTypePublic) == _values(RuleConditionType)
    assert _values(RuleEffectTypePublic) == _values(RuleEffectType)
    assert _values(RuleWeaponPublic) == _values(RuleWeapon)
    assert _values(StrategyIntentPublic) == _values(StrategyIntent)
    assert _values(StrategyDecisionStatusPublic) == _values(StrategyDecisionStatus)


def test_v02_lifecycle_removes_old_rule_phase_states() -> None:
    assert _values(MatchLifecycle) == {
        "RUNNING",
        "PLAYER_DECISION",
        "TERMINAL",
        "FAILED_RECOVERABLE",
    }
    assert "AWAITING_INITIAL_RULE" not in _values(MatchLifecycle)
    assert "AWAITING_RULE" not in _values(MatchLifecycle)


def test_openapi_contains_exactly_the_five_mvp_routes() -> None:
    schema = contract_app.openapi()
    assert set(schema["paths"]) == {
        "/api/v1/matches",
        "/api/v1/matches/{match_id}",
        "/api/v1/matches/{match_id}/rules",
        "/api/v1/matches/{match_id}/advance",
        "/api/v1/matches/{match_id}/replay",
    }
    assert "post" in schema["paths"]["/api/v1/matches"]
    assert "get" in schema["paths"]["/api/v1/matches/{match_id}"]
    assert "post" in schema["paths"]["/api/v1/matches/{match_id}/rules"]
    assert "post" in schema["paths"]["/api/v1/matches/{match_id}/advance"]
    assert "get" in schema["paths"]["/api/v1/matches/{match_id}/replay"]


def test_write_routes_require_idempotency_header() -> None:
    schema = contract_app.openapi()
    for path in (
        "/api/v1/matches/{match_id}/rules",
        "/api/v1/matches/{match_id}/advance",
    ):
        params = schema["paths"][path]["post"]["parameters"]
        header = next(item for item in params if item["name"] == "Idempotency-Key")
        assert header["in"] == "header"
        assert header["required"] is True


def test_generated_fixture_shapes_validate() -> None:
    models = {
        "match_initial.json": MatchSnapshot,
        "match_player_decision.json": MatchSnapshot,
        "rule_accepted.json": RuleSubmissionResult,
        "rule_rejected.json": RuleSubmissionResult,
        "match_terminal.json": MatchSnapshot,
        "error_revision_conflict.json": ErrorEnvelope,
        "advance_round.json": AdvanceResult,
        "replay_terminal.json": ReplaySnapshot,
    }
    for filename, model_instance in build_fixtures().items():
        payload = model_instance.model_dump(mode="json")
        assert payload["schema_version"] == SCHEMA_VERSION
        models[filename].model_validate(payload)


def test_initial_match_forbids_rule_before_round_one() -> None:
    match = build_fixtures()["match_initial.json"]
    assert match.completed_rounds == 0
    assert match.rule_change_count == 0
    assert match.active_rule is None
    assert match.lifecycle is MatchLifecycle.RUNNING
    assert match.player_decision.after_round is None
    assert match.player_decision.can_submit_rule is False
    assert match.player_decision.can_advance is True


def test_each_completed_round_enters_player_decision_state() -> None:
    match = build_fixtures()["match_player_decision.json"]
    assert match.completed_rounds == 1
    assert match.score_rounds == 1
    assert match.lifecycle is MatchLifecycle.PLAYER_DECISION
    assert match.player_decision.after_round == 1
    assert match.player_decision.can_submit_rule is True
    assert match.player_decision.can_advance is True


def test_successful_rule_change_locks_further_change_until_next_round() -> None:
    result = build_fixtures()["rule_accepted.json"]
    assert result.accepted is True
    assert result.match.rule_change_count == 1
    assert result.match.player_decision.rule_changed_this_intermission is True
    assert result.match.player_decision.can_submit_rule is False
    assert result.match.player_decision.can_advance is True


def test_rejected_rule_does_not_consume_rule_change_count() -> None:
    result = build_fixtures()["rule_rejected.json"]
    assert result.accepted is False
    assert result.match.rule_change_count == 0
    assert result.match.player_decision.can_submit_rule is True


def test_battle_escalation_is_public_and_explainable() -> None:
    match = build_fixtures()["match_player_decision.json"]
    escalation = match.battle_escalation
    assert escalation.level == 0
    assert escalation.next_level_at_no_damage == 3
    assert escalation.rounds_until_next_level == 3


def test_contract_models_fail_closed_on_private_extra_fields() -> None:
    payload = build_fixtures()["match_player_decision.json"].model_dump(mode="json")
    payload["private_memory"] = [{"intent": "PRESSURE"}]
    with pytest.raises(ValidationError):
        MatchSnapshot.model_validate(payload)


def test_public_schema_and_fixtures_do_not_expose_private_fields() -> None:
    forbidden = {
        "private_memory",
        "raw_model_output",
        "system_prompt",
        "api_key",
        "chain_of_thought",
        "hidden_reasoning",
        "stack_trace",
        "provider_body",
    }
    material = [json.dumps(contract_app.openapi(), sort_keys=True).lower()]
    material.extend(
        json.dumps(model.model_dump(mode="json"), sort_keys=True).lower()
        for model in build_fixtures().values()
    )
    combined = "\n".join(material)
    for token in forbidden:
        assert token not in combined


def test_replay_fixture_starts_with_round_one_without_pregame_rule_phase() -> None:
    replay = build_fixtures()["replay_terminal.json"]
    parsed = ReplaySnapshot.model_validate(replay.model_dump(mode="json"))
    assert parsed.terminal_result is MatchResultPublic.RED_WIN
    assert parsed.score_rounds == 2
    assert parsed.rule_change_count == 1
    assert len(parsed.timeline) >= 3
    assert parsed.timeline[0].entry_type == "ROUND"
    assert parsed.timeline[0].round_no == 1
    assert parsed.timeline[1].entry_type == "INTERMISSION"
    assert parsed.timeline[1].after_round == 1
