from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from rules_beyond.api_app import build_app
from rules_beyond.match_application_service import ModelUnavailableMatchFailure
from rules_beyond.match_repository import InMemoryMatchRepository, MatchServiceFactory
from rules_beyond.model_call_log import (
    LoggedModel,
    ModelCallOutcome,
    ModelCallPurpose,
    ModelCallRecorder,
    safe_endpoint_origin,
)


MOVE_RULE_TEXT = "双方移动距离增加1格。"
MOVE_RULE_JSON = json.dumps(
    {
        "decision": "CANDIDATE",
        "candidate": {
            "version": "v0.1",
            "target": "ALL_UNITS",
            "conditions": [],
            "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
            "duration": "UNTIL_REPLACED",
        },
    },
    ensure_ascii=False,
)


class StrategyModel:
    def __init__(self, intent: str, *, fail: bool = False) -> None:
        self.intent = intent
        self.fail = fail

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        del system_prompt, observation
        if self.fail:
            raise RuntimeError("provider unavailable")
        return json.dumps({"intent": self.intent})


class RuleModel:
    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        if "semantic verifier" in system_prompt:
            return '{"decision":"FAITHFUL"}'
        if player_text == MOVE_RULE_TEXT:
            return MOVE_RULE_JSON
        return '{"decision":"NO_CANDIDATE","reason_code":"CANNOT_MAP_SAFELY"}'


def repository(*, fail_red: bool = False) -> InMemoryMatchRepository:
    return InMemoryMatchRepository(
        service_factory=MatchServiceFactory(
            red_strategy_model_factory=lambda: StrategyModel("PRESSURE", fail=fail_red),
            blue_strategy_model_factory=lambda: StrategyModel("KITE"),
            rule_model_factory=RuleModel,
            model_name="glm-5.1",
            endpoint_url=(
                "https://user:password@open.bigmodel.cn:443/api/paas/v4?api_key=secret#x"
            ),
        )
    )


def test_round_records_two_confirmed_strategy_responses_without_state_mutation() -> None:
    repo = repository()
    match = repo.create_match(seed=9)
    repo.advance_match(match.match_id, expected_revision=0, idempotency_key="round-1")
    revision_before = repo.get_match_snapshot(match.match_id).revision

    log = repo.get_model_call_log(match.match_id)

    assert log.attempted_calls == 2
    assert log.confirmed_responses == 2
    assert log.failed_attempts == 0
    assert [entry.purpose.value for entry in log.entries] == [
        "STRATEGY_RED",
        "STRATEGY_BLUE",
    ]
    assert all(entry.outcome.value == "RESPONSE_RECEIVED" for entry in log.entries)
    assert all(entry.model == "glm-5.1" for entry in log.entries)
    assert all(
        entry.endpoint_origin == "https://open.bigmodel.cn:443" for entry in log.entries
    )
    assert repo.get_match_snapshot(match.match_id).revision == revision_before


def test_rule_submission_records_translation_and_faithfulness_separately() -> None:
    repo = repository()
    match = repo.create_match(seed=10)
    advanced = repo.advance_match(
        match.match_id,
        expected_revision=0,
        idempotency_key="round-1",
    )

    result = repo.submit_public_rule(
        match.match_id,
        expected_revision=advanced.match.revision,
        idempotency_key="rule-1",
        player_text=MOVE_RULE_TEXT,
    )
    log = repo.get_model_call_log(match.match_id)

    assert result.accepted
    assert [entry.purpose.value for entry in log.entries[-2:]] == [
        "RULE_TRANSLATION",
        "RULE_FAITHFULNESS",
    ]
    assert log.confirmed_responses == 4


def test_provider_failure_is_an_attempt_not_a_confirmed_response() -> None:
    repo = repository(fail_red=True)
    match = repo.create_match(seed=11)

    with pytest.raises(ModelUnavailableMatchFailure):
        repo.advance_match(
            match.match_id,
            expected_revision=0,
            idempotency_key="round-1",
        )
    log = repo.get_model_call_log(match.match_id)

    assert repo.get_match_snapshot(match.match_id).completed_rounds == 0
    assert log.attempted_calls == 2
    assert log.confirmed_responses == 1
    assert log.failed_attempts == 1
    assert log.entries[0].purpose.value == "STRATEGY_RED"
    assert log.entries[0].outcome.value == "CALL_FAILED"


def test_different_matches_have_isolated_logs() -> None:
    repo = repository()
    first = repo.create_match(seed=1)
    second = repo.create_match(seed=2)

    repo.advance_match(first.match_id, expected_revision=0, idempotency_key="first")

    assert repo.get_model_call_log(first.match_id).attempted_calls == 2
    assert repo.get_model_call_log(second.match_id).attempted_calls == 0


def test_bounded_recorder_keeps_totals_and_reports_truncation() -> None:
    recorder = ModelCallRecorder(max_entries=2)
    for index in range(3):
        recorder.record(
            time=f"2026-09-15T00:00:0{index}Z",
            purpose=ModelCallPurpose.STRATEGY_RED,
            model="glm-5.1",
            endpoint_origin="https://example.test",
            outcome=ModelCallOutcome.RESPONSE_RECEIVED,
            duration_ms=index,
        )

    snapshot = recorder.snapshot()

    assert snapshot.attempted_calls == 3
    assert snapshot.confirmed_responses == 3
    assert snapshot.truncated
    assert [entry.sequence for entry in snapshot.entries] == [2, 3]


def test_logging_failure_never_changes_result_or_original_exception() -> None:
    class ExplodingRecorder:
        def record(self, **kwargs) -> None:  # noqa: ANN003
            del kwargs
            raise RuntimeError("log storage failed")

    successful = LoggedModel(
        StrategyModel("HOLD"),
        ExplodingRecorder(),  # type: ignore[arg-type]
        purpose=ModelCallPurpose.STRATEGY_RED,
        model_name="glm-5.1",
        endpoint_url="https://example.test/v1",
    )
    assert json.loads(successful.generate_strategy(system_prompt="s", observation="o")) == {
        "intent": "HOLD"
    }

    provider_error = RuntimeError("original provider failure")

    class FailingModel:
        def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
            del system_prompt, observation
            raise provider_error

    failing = LoggedModel(
        FailingModel(),
        ExplodingRecorder(),  # type: ignore[arg-type]
        purpose=ModelCallPurpose.STRATEGY_BLUE,
        model_name="glm-5.1",
        endpoint_url="https://example.test/v1",
    )
    with pytest.raises(RuntimeError) as caught:
        failing.generate_strategy(system_prompt="s", observation="o")
    assert caught.value is provider_error


def test_endpoint_origin_removes_path_query_fragment_and_credentials() -> None:
    assert safe_endpoint_origin(
        "https://user:pass@Example.COM:8443/v1/chat/completions?key=secret#fragment"
    ) == "https://example.com:8443"
    assert safe_endpoint_origin("not a url") is None


def test_http_export_contains_only_safe_receipts_and_unknown_match_is_404() -> None:
    secret = "secret-must-not-appear"
    repo = repository()
    client = TestClient(build_app(repo))
    created = client.post("/api/v1/matches", json={"seed": 12}).json()
    client.post(
        f"/api/v1/matches/{created['match_id']}/advance",
        json={"expected_revision": 0},
        headers={"Idempotency-Key": secret},
    )

    response = client.get(f"/api/v1/matches/{created['match_id']}/model-calls")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "mvp-v0.2"
    assert payload["log_version"] == "model-call-log-v1"
    assert payload["confirmed_responses"] == 2
    serialized = response.text.lower()
    assert secret not in serialized
    assert "authorization" not in serialized
    assert "system_prompt" not in serialized
    assert "raw_model_output" not in serialized
    assert client.get("/api/v1/matches/missing/model-calls").status_code == 404
