from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from rules_beyond.api_contract import (
    AdvanceResult,
    ErrorEnvelope,
    MatchResultPublic,
    MatchSnapshot,
    ReplaySnapshot,
    RuleSubmissionResult,
    TeamPublic,
    DirectionPublic,
    WeaponPublic,
    RuleTargetPublic,
    RuleDurationPublic,
    RuleConditionTypePublic,
    RuleEffectTypePublic,
    RuleWeaponPublic,
    StrategyIntentPublic,
    StrategyDecisionStatusPublic,
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
        "match_running.json": MatchSnapshot,
        "rule_accepted.json": RuleSubmissionResult,
        "rule_rejected.json": RuleSubmissionResult,
        "match_terminal.json": MatchSnapshot,
        "error_revision_conflict.json": ErrorEnvelope,
        "advance_round.json": AdvanceResult,
        "replay_terminal.json": ReplaySnapshot,
    }
    for filename, model_instance in build_fixtures().items():
        payload = model_instance.model_dump(mode="json")
        models[filename].model_validate(payload)


def test_contract_models_fail_closed_on_private_extra_fields() -> None:
    payload = build_fixtures()["match_running.json"].model_dump(mode="json")
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


def test_replay_fixture_is_self_contained_public_data() -> None:
    replay = build_fixtures()["replay_terminal.json"]
    parsed = ReplaySnapshot.model_validate(replay.model_dump(mode="json"))
    assert parsed.terminal_result is MatchResultPublic.RED_WIN
    assert len(parsed.timeline) >= 2
    assert parsed.timeline[0].entry_type == "RULE_PHASE"
    assert parsed.timeline[1].entry_type == "ROUND"
