"""HTTP regressions for provider failures that are normal business fallbacks.

These tests intentionally exercise the real A2 repository + A1 application service
through the A3 FastAPI app. Provider doubles fail deterministically; no real network
request is made.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from rules_beyond.api_app import build_app
from rules_beyond.match_repository import InMemoryMatchRepository, MatchServiceFactory


RAW_STRATEGY_FAILURE = "raw strategy provider secret failure"
RAW_RULE_FAILURE = "raw rule provider secret failure"


class StableStrategyModel:
    def __init__(self, intent: str) -> None:
        self.intent = intent

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:  # noqa: ARG002
        return json.dumps({"intent": self.intent})


class FailingStrategyModel:
    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:  # noqa: ARG002
        raise RuntimeError(RAW_STRATEGY_FAILURE)


class StableRuleModel:
    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:  # noqa: ARG002
        return '{"decision":"NO_CANDIDATE","reason_code":"CANNOT_MAP_SAFELY"}'


class FailingRuleModel:
    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:  # noqa: ARG002
        raise RuntimeError(RAW_RULE_FAILURE)


def _client(*, fail_strategy: bool = False, fail_rule: bool = False) -> TestClient:
    def red_factory():
        if fail_strategy:
            return FailingStrategyModel()
        return StableStrategyModel("PRESSURE")

    def blue_factory():
        return StableStrategyModel("KITE")

    def rule_factory():
        if fail_rule:
            return FailingRuleModel()
        return StableRuleModel()

    repository = InMemoryMatchRepository(
        service_factory=MatchServiceFactory(
            red_strategy_model_factory=red_factory,
            blue_strategy_model_factory=blue_factory,
            rule_model_factory=rule_factory,
        )
    )
    return TestClient(build_app(repository))


def _create(client: TestClient) -> dict:
    response = client.post("/api/v1/matches", json={"seed": 1_270_000})
    assert response.status_code == 201
    return response.json()


def _advance(client: TestClient, match_id: str, revision: int, key: str):
    return client.post(
        f"/api/v1/matches/{match_id}/advance",
        json={"expected_revision": revision},
        headers={"Idempotency-Key": key},
    )


def test_strategy_provider_failure_is_200_degraded_fallback() -> None:
    client = _client(fail_strategy=True)
    created = _create(client)

    response = _advance(client, created["match_id"], 0, "adv-fallback")

    assert response.status_code == 200
    payload = response.json()
    assert payload["round"]["round_no"] == 1
    assert payload["match"]["revision"] == 1
    assert payload["match"]["completed_rounds"] == 1
    assert payload["match"]["lifecycle"] == "PLAYER_DECISION"

    red = payload["round"]["strategies"]["RED"]
    assert red["status"] == "FALLBACK_MODEL_ERROR"
    assert red["degraded"] is True
    assert payload["match"]["latest_strategy"]["RED"]["status"] == "FALLBACK_MODEL_ERROR"
    assert payload["match"]["latest_strategy"]["RED"]["degraded"] is True

    response_text = response.text.lower()
    assert RAW_STRATEGY_FAILURE.lower() not in response_text
    assert "runtimeerror" not in response_text


def test_rule_provider_failure_is_200_model_unavailable_and_retryable_in_intermission() -> None:
    client = _client(fail_rule=True)
    created = _create(client)
    match_id = created["match_id"]

    first_round = _advance(client, match_id, 0, "adv-1")
    assert first_round.status_code == 200
    assert first_round.json()["match"]["revision"] == 1

    first = client.post(
        f"/api/v1/matches/{match_id}/rules",
        json={"expected_revision": 1, "player_text": "双方移动距离增加1格。"},
        headers={"Idempotency-Key": "rule-model-down-1"},
    )

    assert first.status_code == 200
    payload = first.json()
    assert payload["accepted"] is False
    assert payload["public_code"] == "MODEL_UNAVAILABLE"
    assert payload["match"]["revision"] == 1
    assert payload["match"]["rule_change_count"] == 0
    assert payload["match"]["lifecycle"] == "PLAYER_DECISION"
    assert payload["match"]["player_decision"]["can_submit_rule"] is True
    assert RAW_RULE_FAILURE.lower() not in first.text.lower()
    assert "runtimeerror" not in first.text.lower()

    # A new user attempt in the same intermission remains allowed after MODEL_UNAVAILABLE.
    second = client.post(
        f"/api/v1/matches/{match_id}/rules",
        json={"expected_revision": 1, "player_text": "双方弓箭距离增加1格。"},
        headers={"Idempotency-Key": "rule-model-down-2"},
    )
    assert second.status_code == 200
    assert second.json()["public_code"] == "MODEL_UNAVAILABLE"
    assert second.json()["match"]["revision"] == 1
    assert second.json()["match"]["rule_change_count"] == 0
