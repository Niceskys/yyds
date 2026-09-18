"""Exercise production wiring without sending requests to a model provider."""

import pytest
from fastapi.testclient import TestClient

from rules_beyond import api_runtime
from rules_beyond.api_app import build_app


class PressureModel:
    def __init__(self, *args, **kwargs):
        pass

    def generate_strategy(self, **kwargs):
        return '{"intent":"PRESSURE"}'

    def generate_candidate(self, **kwargs):
        pytest.fail("Skipping rules must not invoke the rule model")

    def check_connection(self):
        return None


@pytest.mark.parametrize("custom", [False, True])
@pytest.mark.parametrize("seed", [0, 1, 7])
def test_runtime_no_rule_match_leaves_multiple_rule_windows(monkeypatch, custom, seed):
    for name in tuple(api_runtime.os.environ):
        if name.startswith(("MODEL_API_", "MIMO_")):
            monkeypatch.delenv(name)
    if custom:
        monkeypatch.setenv("MODEL_API_KEY", "test")
        monkeypatch.setenv("MODEL_API_MODEL", "test")
        monkeypatch.setenv("MODEL_API_BASE_URL", "https://example.com/v1")
    else:
        monkeypatch.setenv("MIMO_API_KEY", "test")
    monkeypatch.setattr(api_runtime, "OpenAICompatibleModel", PressureModel)
    monkeypatch.setattr(api_runtime, "MimoStrategyModel", PressureModel)
    monkeypatch.setattr(api_runtime, "MimoRuleCandidateModel", PressureModel)

    with TestClient(build_app(repository=api_runtime.build_runtime_repository_from_env())) as client:
        created = client.post("/api/v1/matches", json={"seed": seed})
        assert created.status_code == 201
        snapshot = created.json()
        match_id = snapshot["match_id"]
        assert snapshot["units"]["RED"]["hp"] == 4
        assert snapshot["units"]["BLUE"]["hp"] == 4
        for round_no in range(1, 31):
            response = client.post(
                f"/api/v1/matches/{match_id}/advance",
                json={"expected_revision": snapshot["revision"]},
                headers={"Idempotency-Key": f"round-{round_no}"},
            )
            assert response.status_code == 200
            snapshot = response.json()["match"]
            assert snapshot["completed_rounds"] == round_no
            assert snapshot["active_rule"] is None
            assert snapshot["rule_change_count"] == 0
            if round_no <= 3:
                assert snapshot["result"] is None
                assert snapshot["player_decision"]["can_submit_rule"]
                assert snapshot["player_decision"]["can_advance"]
            if snapshot["result"] is not None:
                break
        assert 4 <= snapshot["completed_rounds"] < 30
        assert snapshot["result"] != "TIMEOUT"
        assert not snapshot["player_decision"]["can_advance"]
        replay_response = client.get(f"/api/v1/matches/{match_id}/replay")
        assert replay_response.status_code == 200
        rounds = [e for e in replay_response.json()["timeline"] if e["entry_type"] == "ROUND"]
        assert len(rounds) == snapshot["completed_rounds"]
