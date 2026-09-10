"""A3 HTTP coverage: the real V0.2 five-route vertical slice.

Every provider is a deterministic fake and every match is served by a real A2
``InMemoryMatchRepository`` built from those fakes, so no test touches the real MiMo
network. The primary vertical-flow test additionally patches
``OpenerDirector.open`` to fail, proving the whole HTTP slice never opens a
connection.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from rules_beyond.api_app import build_app
from rules_beyond.api_contract import SCHEMA_VERSION, ErrorCode
from rules_beyond.match_application_service import (
    MatchApplicationService,
    MatchTerminalError,
)
from rules_beyond.match_repository import InMemoryMatchRepository, MatchServiceFactory
from rules_beyond.model import GameConfig, Team
from rules_beyond.natural_language_dynamic_controller import (
    VerifiedNaturalLanguageDynamicController,
)
from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.openapi_contract import contract_app
from rules_beyond.rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from rules_beyond.rule_validator import RuleValidator
from rules_beyond.strategy_agent import IsolatedStrategyAgent
from rules_beyond.verified_natural_language_rule_adapter import (
    VerifiedNaturalLanguageRuleAdapter,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_SNAPSHOT = REPOSITORY_ROOT / "contracts" / "openapi" / "mvp-v0.2.json"

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
NO_CANDIDATE_JSON = '{"decision":"NO_CANDIDATE","reason_code":"CANNOT_MAP_SAFELY"}'

_FORBIDDEN_TOKENS = (
    "private_memory",
    "raw_model_output",
    "system_prompt",
    "api-key",
    "api_key",
    "chain_of_thought",
    "traceback",
    "provider down",
    "stack",
)
_ENTRY_TIMEOUT = 5.0
_JOIN_TIMEOUT = 5.0


class CountingRuleModel:
    """Deterministic translator + faithfulness double with call counters."""

    def __init__(self, responses: dict[str, str] | None = None, *, faithful: bool = True) -> None:
        self.responses = dict(responses or {})
        self.faithful = faithful
        self.translation_calls = 0
        self.faithfulness_calls = 0

    @property
    def calls(self) -> int:
        return self.translation_calls + self.faithfulness_calls

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        if "semantic verifier" in system_prompt:
            self.faithfulness_calls += 1
            if self.faithful:
                return '{"decision":"FAITHFUL"}'
            return '{"decision":"REJECT","reason_code":"DROPPED_INTENT"}'
        self.translation_calls += 1
        return self.responses.get(player_text, NO_CANDIDATE_JSON)


class CountingStrategyModel:
    """Strategy double that counts calls and can block or fail deterministically."""

    def __init__(
        self,
        intent: str,
        *,
        fail: bool = False,
        entered: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.intent = intent
        self.fail = fail
        self.calls = 0
        self._entered = entered
        self._release = release

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:  # noqa: ARG002
        self.calls += 1
        if self._entered is not None:
            self._entered.set()
        if self._release is not None and not self._release.wait(timeout=_ENTRY_TIMEOUT):
            raise RuntimeError("blocking strategy model was never released")
        if self.fail:
            raise RuntimeError("provider down")
        return json.dumps({"intent": self.intent})


def _build_repository(
    *,
    responses: dict[str, str] | None = None,
    fail_red: bool = False,
    entered: threading.Event | None = None,
    release: threading.Event | None = None,
):
    """Real A2 repository over deterministic fake providers (no network)."""

    red_models: list[CountingStrategyModel] = []
    blue_models: list[CountingStrategyModel] = []
    rule_models: list[CountingRuleModel] = []
    config = GameConfig()

    def red_make() -> CountingStrategyModel:
        model = CountingStrategyModel("PRESSURE", fail=fail_red, entered=entered, release=release)
        red_models.append(model)
        return model

    def blue_make() -> CountingStrategyModel:
        model = CountingStrategyModel("KITE")
        blue_models.append(model)
        return model

    def rule_make() -> CountingRuleModel:
        model = CountingRuleModel(responses)
        rule_models.append(model)
        return model

    factory = MatchServiceFactory(
        config=config,
        red_strategy_model_factory=red_make,
        blue_strategy_model_factory=blue_make,
        rule_model_factory=rule_make,
    )
    return InMemoryMatchRepository(service_factory=factory), red_models, blue_models, rule_models


class ErrorRepository:
    """Route-layer double: every A2 entry point raises one configured error."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def create_match(self, *, seed: int | None = None):  # noqa: ANN201
        raise self.error

    def get_match_snapshot(self, match_id: str):  # noqa: ANN201
        raise self.error

    def submit_public_rule(self, match_id: str, *, expected_revision: int, idempotency_key: str, player_text: str):  # noqa: ANN201, E501
        raise self.error

    def advance_match(self, match_id: str, *, expected_revision: int, idempotency_key: str):  # noqa: ANN201
        raise self.error

    def get_replay(self, match_id: str):  # noqa: ANN201
        raise self.error


class ExplodingStrategyAgent:
    """Agent double: forwards to a real isolated agent but raises once on decide()."""

    def __init__(self, team: Team, agent: IsolatedStrategyAgent, *, fail_on_call: int = 1) -> None:
        self.team = team
        self._agent = agent
        self._fail_on_call = fail_on_call
        self.calls = 0

    def decide(self, state, engine, *, rule, histories, remember: bool = True):  # noqa: ANN001
        self.calls += 1
        if self.calls == self._fail_on_call:
            raise RuntimeError("agent exploded")
        return self._agent.decide(
            state,
            engine,
            rule=rule,
            histories=histories,
            remember=remember,
        )

    def commit_decision_memory(self, decision, *, round_no, rule):  # noqa: ANN001
        self._agent.commit_decision_memory(decision, round_no=round_no, rule=rule)


def _breaking_repository() -> InMemoryMatchRepository:
    """Repository whose very first advance fails mid-round -> RecoverableMatchFailure."""

    config = GameConfig()
    rule_model = CountingRuleModel({MOVE_RULE_TEXT: MOVE_RULE_JSON})
    validator = RuleValidator(config)
    base = NaturalLanguageRuleAdapter(rule_model, validator)
    verified = VerifiedNaturalLanguageRuleAdapter(
        base,
        NaturalLanguageRuleFaithfulnessVerifier(rule_model),
    )
    rules = VerifiedNaturalLanguageDynamicController(verified, config)
    service = MatchApplicationService(
        red_agent=ExplodingStrategyAgent(
            Team.RED, IsolatedStrategyAgent(Team.RED, CountingStrategyModel("PRESSURE"))
        ),
        blue_agent=IsolatedStrategyAgent(Team.BLUE, CountingStrategyModel("KITE")),
        rule_pipeline=rules,
    )
    return InMemoryMatchRepository(service_factory=lambda: service)


def _app(**kwargs):
    repository, red_models, blue_models, rule_models = _build_repository(**kwargs)
    return build_app(repository), repository, red_models, blue_models, rule_models


def _create_match(client: TestClient, *, seed: int = 1_270_000) -> dict:
    response = client.post("/api/v1/matches", json={"seed": seed})
    assert response.status_code == 201, response.text
    return response.json()


def _advance(client: TestClient, match_id: str, revision: int, key: str):
    return client.post(
        f"/api/v1/matches/{match_id}/advance",
        json={"expected_revision": revision},
        headers={"Idempotency-Key": key},
    )


def _submit_rule(client: TestClient, match_id: str, revision: int, key: str, text: str = MOVE_RULE_TEXT):
    return client.post(
        f"/api/v1/matches/{match_id}/rules",
        json={"expected_revision": revision, "player_text": text},
        headers={"Idempotency-Key": key},
    )


def _round_entries(replay_payload: dict) -> list[dict]:
    return [entry for entry in replay_payload["timeline"] if entry["entry_type"] == "ROUND"]


def _clean_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("MIMO_")}
    env["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
    return env


# 1. create ----------------------------------------------------------------


def test_create_match_is_201_revision_zero_and_calls_no_provider() -> None:
    app, repository, red_models, blue_models, rule_models = _app()
    client = TestClient(app)

    body = _create_match(client)

    assert body["schema_version"] == SCHEMA_VERSION
    assert body["revision"] == 0
    assert body["completed_rounds"] == 0
    assert body["rule_change_count"] == 0
    assert body["active_rule"] is None
    assert body["lifecycle"] == "RUNNING"
    assert body["player_decision"]["after_round"] is None
    assert body["player_decision"]["can_submit_rule"] is False
    assert body["player_decision"]["can_advance"] is True
    assert red_models[0].calls == 0
    assert blue_models[0].calls == 0
    assert rule_models[0].calls == 0
    assert repository.get_replay(body["match_id"]).timeline == []


# 2. read ------------------------------------------------------------------


def test_get_match_returns_the_public_snapshot() -> None:
    app, _, _, _, _ = _app()
    client = TestClient(app)
    created = _create_match(client)

    response = client.get(f"/api/v1/matches/{created['match_id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_unknown_match_is_404_match_not_found() -> None:
    app, _, _, _, _ = _app()
    client = TestClient(app)

    for response in (
        client.get("/api/v1/matches/missing"),
        client.get("/api/v1/matches/missing/replay"),
        _advance(client, "missing", 0, "k"),
        _submit_rule(client, "missing", 0, "k"),
    ):
        assert response.status_code == 404
        payload = response.json()
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["error"]["code"] == "MATCH_NOT_FOUND"
        assert payload["error"]["retryable"] is False


# 3. advance ---------------------------------------------------------------


def test_first_advance_runs_round_one_and_increments_revision() -> None:
    app, repository, red_models, blue_models, _ = _app()
    client = TestClient(app)
    created = _create_match(client)

    response = _advance(client, created["match_id"], 0, "adv-1")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["round"]["round_no"] == 1
    assert body["match"]["revision"] == 1
    assert body["match"]["completed_rounds"] == 1
    assert body["match"]["score_rounds"] == 1
    assert body["match"]["lifecycle"] == "PLAYER_DECISION"
    assert body["match"]["player_decision"]["after_round"] == 1
    assert body["match"]["player_decision"]["can_submit_rule"] is True
    assert red_models[0].calls == 1
    assert blue_models[0].calls == 1
    assert len(_round_entries(repository.get_replay(created["match_id"]).model_dump(mode="json"))) == 1


# 4. rules -----------------------------------------------------------------


def test_accepted_rule_stays_in_player_decision_and_does_not_advance() -> None:
    app, _, red_models, blue_models, rule_models = _app(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    client = TestClient(app)
    created = _create_match(client)
    _advance(client, created["match_id"], 0, "adv-1")

    response = _submit_rule(client, created["match_id"], 1, "rule-1")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert body["accepted"] is True
    assert body["public_code"] == "ACCEPTED"
    assert body["rule_id"]
    match = body["match"]
    assert match["revision"] == 2
    assert match["rule_change_count"] == 1
    assert match["completed_rounds"] == 1
    assert match["lifecycle"] == "PLAYER_DECISION"
    assert match["player_decision"]["rule_changed_this_intermission"] is True
    assert match["player_decision"]["can_submit_rule"] is False
    assert match["player_decision"]["can_advance"] is True
    assert match["active_rule"]["player_text"] == MOVE_RULE_TEXT
    assert red_models[0].calls == 1
    assert blue_models[0].calls == 1
    assert rule_models[0].calls == 2


def test_safely_rejected_rule_is_a_normal_rule_submission_result() -> None:
    app, _, red_models, blue_models, rule_models = _app()
    client = TestClient(app)
    created = _create_match(client)
    _advance(client, created["match_id"], 0, "adv-1")

    response = _submit_rule(client, created["match_id"], 1, "rule-1", text="这句话无法表达")

    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert body["accepted"] is False
    assert body["public_code"] == "NO_CANDIDATE"
    assert body["match"]["rule_change_count"] == 0
    assert body["match"]["player_decision"]["can_submit_rule"] is True
    assert body["match"]["revision"] == 1
    assert red_models[0].calls == 1
    assert blue_models[0].calls == 1
    assert rule_models[0].calls == 1


# 5. idempotency -----------------------------------------------------------


def test_same_advance_idempotency_key_replays_the_first_result() -> None:
    app, repository, red_models, blue_models, _ = _app()
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]

    first = _advance(client, match_id, 0, "adv-key")
    second = _advance(client, match_id, 0, "adv-key")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert red_models[0].calls == 1
    assert blue_models[0].calls == 1
    assert len(_round_entries(repository.get_replay(match_id).model_dump(mode="json"))) == 1


def test_same_rule_idempotency_key_replays_without_extra_model_calls() -> None:
    app, repository, _, _, rule_models = _app(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]
    _advance(client, match_id, 0, "adv-1")

    first = _submit_rule(client, match_id, 1, "rule-key")
    calls_after_first = rule_models[0].calls
    second = _submit_rule(client, match_id, 1, "rule-key")

    assert first.status_code == 200
    assert first.json() == second.json()
    assert rule_models[0].calls == calls_after_first == 2
    replay = repository.get_replay(match_id).model_dump(mode="json")
    assert [entry["entry_type"] for entry in replay["timeline"]] == ["ROUND", "INTERMISSION"]
    assert replay["rule_change_count"] == 1


def test_wrong_expected_revision_is_409_revision_conflict() -> None:
    app, repository, red_models, blue_models, rule_models = _app(
        responses={MOVE_RULE_TEXT: MOVE_RULE_JSON}
    )
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]

    advance_response = _advance(client, match_id, 5, "adv-bad")
    rule_response = _submit_rule(client, match_id, 5, "rule-bad")

    for response in (advance_response, rule_response):
        assert response.status_code == 409
        payload = response.json()
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["error"]["code"] == "REVISION_CONFLICT"
        assert payload["error"]["retryable"] is True
    assert red_models[0].calls == 0
    assert blue_models[0].calls == 0
    assert rule_models[0].calls == 0
    assert repository.get_replay(match_id).timeline == []


def test_reused_key_with_a_changed_payload_is_400_invalid_request() -> None:
    app, _, _, _, rule_models = _app(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]
    _advance(client, match_id, 0, "adv-1")
    _submit_rule(client, match_id, 1, "shared")
    calls_after_first = rule_models[0].calls

    response = _submit_rule(client, match_id, 1, "shared", text="换一句完全不同的话")

    assert response.status_code == 400
    payload = response.json()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["error"]["code"] == "INVALID_REQUEST"
    assert payload["error"]["retryable"] is False
    assert rule_models[0].calls == calls_after_first


# 6. Idempotency-Key header ------------------------------------------------


def test_missing_idempotency_key_header_is_400_idempotency_key_required() -> None:
    app, _, _, _, _ = _app()
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]

    for path, body in (
        (f"/api/v1/matches/{match_id}/advance", {"expected_revision": 0}),
        (f"/api/v1/matches/{match_id}/rules", {"expected_revision": 0, "player_text": MOVE_RULE_TEXT}),
    ):
        response = client.post(path, json=body)
        assert response.status_code == 400
        payload = response.json()
        assert "detail" not in payload
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
        assert payload["error"]["retryable"] is True


def test_whitespace_idempotency_key_is_400_idempotency_key_required() -> None:
    app, repository, red_models, blue_models, _ = _app()
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]

    for key in ("   ", "\t"):
        response = _advance(client, match_id, 0, key)
        assert response.status_code == 400
        payload = response.json()
        assert payload["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
        assert payload["error"]["retryable"] is True
    assert red_models[0].calls == 0
    assert blue_models[0].calls == 0
    assert repository.get_match_snapshot(match_id).revision == 0


# 7. terminal / not-allowed / recoverable ----------------------------------


def test_terminal_advance_is_409_match_terminal() -> None:
    client = TestClient(build_app(ErrorRepository(MatchTerminalError("terminal"))))

    response = _advance(client, "match_x", 3, "adv")

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"]["code"] == "MATCH_TERMINAL"
    assert payload["schema_version"] == SCHEMA_VERSION


def test_rule_submission_before_round_one_is_409_rule_submission_not_allowed() -> None:
    app, _, red_models, blue_models, rule_models = _app()
    client = TestClient(app)
    created = _create_match(client)

    response = _submit_rule(client, created["match_id"], 0, "rule-1")

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"]["code"] == "RULE_SUBMISSION_NOT_ALLOWED"
    assert red_models[0].calls == 0
    assert blue_models[0].calls == 0
    assert rule_models[0].calls == 0


def test_recoverable_advance_failure_is_a_clean_503() -> None:
    repository = _breaking_repository()
    client = TestClient(build_app(repository))
    created = _create_match(client)

    response = _advance(client, created["match_id"], 0, "adv-1")

    assert response.status_code == 503
    payload = response.json()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert payload["error"]["retryable"] is True
    body_text = json.dumps(payload, ensure_ascii=False)
    assert "agent exploded" not in body_text
    assert "RuntimeError" not in body_text
    assert repository.get_match_snapshot(created["match_id"]).revision == 0
    assert repository.get_replay(created["match_id"]).timeline == []


# 8. replay ----------------------------------------------------------------


def test_replay_get_is_side_effect_free() -> None:
    app, repository, red_models, blue_models, rule_models = _app(
        responses={MOVE_RULE_TEXT: MOVE_RULE_JSON}
    )
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]
    _advance(client, match_id, 0, "adv-1")
    _submit_rule(client, match_id, 1, "rule-1")

    counts_before = (red_models[0].calls, blue_models[0].calls, rule_models[0].calls)
    snapshot_before = client.get(f"/api/v1/matches/{match_id}").json()

    first = client.get(f"/api/v1/matches/{match_id}/replay")
    second = client.get(f"/api/v1/matches/{match_id}/replay")

    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["schema_version"] == SCHEMA_VERSION
    assert first.json()["replay_version"] == "replay-v0.2"
    assert first.json()["timeline"][0]["entry_type"] == "ROUND"
    assert (red_models[0].calls, blue_models[0].calls, rule_models[0].calls) == counts_before
    assert client.get(f"/api/v1/matches/{match_id}").json() == snapshot_before
    assert repository.get_match_snapshot(match_id).revision == snapshot_before["revision"]


# 9. validation / privacy --------------------------------------------------


def test_malformed_body_is_400_invalid_request_envelope() -> None:
    app, _, _, _, _ = _app()
    client = TestClient(app)
    created = _create_match(client)

    response = client.post(
        f"/api/v1/matches/{created['match_id']}/advance",
        content="{not-json",
        headers={"Idempotency-Key": "adv-1", "Content-Type": "application/json"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert "detail" not in payload
    assert payload["error"]["code"] == "INVALID_REQUEST"
    assert payload["error"]["retryable"] is False


def test_every_error_envelope_carries_the_frozen_schema_version() -> None:
    app, _, _, _, _ = _app()
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]

    responses = [
        client.get("/api/v1/matches/missing"),
        _advance(client, match_id, 9, "adv-bad"),
        client.post(f"/api/v1/matches/{match_id}/advance", json={"expected_revision": 0}),
        client.post(
            f"/api/v1/matches/{match_id}/advance",
            content="{not-json",
            headers={"Idempotency-Key": "adv-1", "Content-Type": "application/json"},
        ),
        _submit_rule(client, match_id, 0, "rule-1"),
    ]

    breaking_client = TestClient(build_app(_breaking_repository()))
    breaking_created = _create_match(breaking_client)
    responses.append(_advance(breaking_client, breaking_created["match_id"], 0, "adv-1"))

    assert [response.status_code for response in responses] == [404, 409, 400, 400, 409, 503]
    for response in responses:
        payload = response.json()
        assert payload["schema_version"] == SCHEMA_VERSION
        assert set(payload) == {"schema_version", "error"}
        assert set(payload["error"]) == {"code", "message", "retryable"}
        assert payload["error"]["code"] in {code.value for code in ErrorCode}


def test_http_responses_never_expose_private_or_secret_material() -> None:
    app, _, _, _, _ = _app(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    client = TestClient(app)
    created = _create_match(client)
    match_id = created["match_id"]

    payloads = [
        created,
        client.get(f"/api/v1/matches/{match_id}").json(),
        _advance(client, match_id, 0, "adv-1").json(),
        _submit_rule(client, match_id, 1, "rule-1").json(),
        _advance(client, match_id, 2, "adv-2").json(),
        client.get(f"/api/v1/matches/{match_id}/replay").json(),
        _advance(client, match_id, 99, "adv-bad").json(),
        client.post(f"/api/v1/matches/{match_id}/advance", json={"expected_revision": 0}).json(),
    ]

    blob = json.dumps(payloads, ensure_ascii=False).lower()
    for token in _FORBIDDEN_TOKENS:
        assert token not in blob


# 10. contract surface -----------------------------------------------------


def test_runtime_app_openapi_matches_the_frozen_snapshot() -> None:
    repository, _, _, _ = _build_repository()
    snapshot = json.loads(OPENAPI_SNAPSHOT.read_text(encoding="utf-8"))

    assert build_app(repository).openapi() == snapshot
    assert contract_app.openapi() == snapshot
    assert set(snapshot["paths"]) == {
        "/api/v1/matches",
        "/api/v1/matches/{match_id}",
        "/api/v1/matches/{match_id}/rules",
        "/api/v1/matches/{match_id}/advance",
        "/api/v1/matches/{match_id}/replay",
    }
    for path in ("/api/v1/matches/{match_id}/rules", "/api/v1/matches/{match_id}/advance"):
        parameters = snapshot["paths"][path]["post"]["parameters"]
        header = next(item for item in parameters if item["name"] == "Idempotency-Key")
        assert header["in"] == "header"
        assert header["required"] is True


def test_import_and_openapi_export_do_not_require_mimo_api_key(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from rules_beyond.openapi_contract import export_openapi\n"
        "export_openapi(Path(sys.argv[1]))\n"
        "print('exported')\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code, str(target)],
        cwd=REPOSITORY_ROOT,
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr
    assert "exported" in result.stdout
    assert json.loads(target.read_text(encoding="utf-8")) == json.loads(
        OPENAPI_SNAPSHOT.read_text(encoding="utf-8")
    )


def test_runtime_app_builds_providers_only_at_startup() -> None:
    code = (
        "import rules_beyond.api_server as server\n"
        "print('import-ok')\n"
        "try:\n"
        "    server.create_runtime_app()\n"
        "except RuntimeError as exc:\n"
        "    print('runtime-error:', exc)\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPOSITORY_ROOT,
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout
    assert "MIMO_API_KEY is not set" in result.stdout


def test_runtime_app_serves_the_offline_safe_routes_with_a_real_key(monkeypatch) -> None:
    """The production wiring is a real, importable ASGI app for Developer B B4.

    ``POST /matches``, ``GET /matches/{id}`` and ``GET /replay`` never call a
    provider, so this exercises the true runtime app without any network access.
    """

    monkeypatch.setenv("MIMO_API_KEY", "tp-dummy-runtime-wiring")
    monkeypatch.delenv("MIMO_BASE_URL", raising=False)
    from rules_beyond.api_server import create_runtime_app

    client = TestClient(create_runtime_app())
    created = client.post("/api/v1/matches", json={"seed": 7})
    assert created.status_code == 201
    match_id = created.json()["match_id"]

    assert client.get(f"/api/v1/matches/{match_id}").status_code == 200
    assert client.get(f"/api/v1/matches/{match_id}/replay").status_code == 200
    assert client.get("/api/v1/matches/missing").status_code == 404


def test_contract_only_app_without_a_repository_returns_a_clean_envelope() -> None:
    client = TestClient(build_app(), raise_server_exceptions=False)

    response = client.get("/api/v1/matches/match_x")

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert "Traceback" not in response.text
    assert "RuntimeNotConfigured" not in response.text


# 11. sync/async boundary --------------------------------------------------


def test_all_five_endpoints_are_synchronous() -> None:
    app = build_app(None)
    endpoints = [
        route.endpoint
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/v1/matches")
    ]

    assert len(endpoints) == 5
    assert not any(inspect.iscoroutinefunction(endpoint) for endpoint in endpoints)


def test_blocking_repository_calls_do_not_block_the_asgi_event_loop() -> None:
    entered = threading.Event()
    release = threading.Event()
    app, repository, _, _, _ = _app(entered=entered, release=release)
    slow = repository.create_match(seed=1_270_000)
    other = repository.create_match(seed=1_270_001)

    async def scenario() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            blocked = asyncio.create_task(
                client.post(
                    f"/api/v1/matches/{slow.match_id}/advance",
                    json={"expected_revision": 0},
                    headers={"Idempotency-Key": "adv-slow"},
                )
            )
            # The blocked advance is inside the sync endpoint's worker thread.
            assert await asyncio.to_thread(entered.wait, _ENTRY_TIMEOUT)
            # A second request still completes: the event loop was never blocked.
            other_match = await client.get(f"/api/v1/matches/{other.match_id}")
            assert other_match.status_code == 200
            release.set()
            return await blocked

    response = asyncio.run(asyncio.wait_for(scenario(), timeout=30))

    assert response.status_code == 200
    assert response.json()["round"]["round_no"] == 1


# 12. HTTP vertical flow ---------------------------------------------------


def test_http_vertical_flow_matches_the_frozen_contract(monkeypatch) -> None:
    def _no_network(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("A3 HTTP tests must never open a real network connection")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _no_network)

    app, repository, red_models, blue_models, rule_models = _app(
        responses={MOVE_RULE_TEXT: MOVE_RULE_JSON}
    )
    client = TestClient(app)

    created = _create_match(client)
    match_id = created["match_id"]
    assert created["revision"] == 0

    round_one = _advance(client, match_id, 0, "adv-1")
    assert round_one.status_code == 200
    assert round_one.json()["round"]["round_no"] == 1
    assert round_one.json()["match"]["revision"] == 1
    assert round_one.json()["match"]["completed_rounds"] == 1

    accepted = _submit_rule(client, match_id, 1, "rule-1")
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True
    assert accepted.json()["match"]["revision"] == 2
    assert accepted.json()["match"]["rule_change_count"] == 1
    assert accepted.json()["match"]["completed_rounds"] == 1
    assert accepted.json()["match"]["lifecycle"] == "PLAYER_DECISION"

    round_two = _advance(client, match_id, 2, "adv-2")
    assert round_two.status_code == 200
    assert round_two.json()["round"]["round_no"] == 2
    assert round_two.json()["match"]["revision"] == 3
    assert round_two.json()["match"]["completed_rounds"] == 2
    assert round_two.json()["match"]["rule_change_count"] == 1

    snapshot = client.get(f"/api/v1/matches/{match_id}").json()
    assert snapshot["revision"] == 3
    assert snapshot["completed_rounds"] == 2
    assert snapshot["score_rounds"] == 2
    assert snapshot["rule_change_count"] == 1
    assert snapshot["active_rule"]["player_text"] == MOVE_RULE_TEXT

    replay = client.get(f"/api/v1/matches/{match_id}/replay").json()
    # One accepted RULE_ATTEMPT during the intermission after round 1, plus the
    # implicit CONTINUE that /advance records when it starts round 2.
    assert [entry["entry_type"] for entry in replay["timeline"]] == [
        "ROUND",
        "INTERMISSION",
        "INTERMISSION",
        "ROUND",
    ]
    assert replay["timeline"][0]["round_no"] == 1
    assert replay["timeline"][1]["after_round"] == 1
    assert replay["timeline"][1]["choice"] == "RULE_ATTEMPT"
    assert replay["timeline"][1]["accepted_rule_id"] == accepted.json()["rule_id"]
    assert replay["timeline"][2]["after_round"] == 1
    assert replay["timeline"][2]["choice"] == "CONTINUE"
    assert replay["timeline"][3]["round_no"] == 2
    assert replay["score_rounds"] == 2
    assert replay["rule_change_count"] == 1

    assert red_models[0].calls == 2
    assert blue_models[0].calls == 2
    assert rule_models[0].calls == 2
    assert repository.get_match_snapshot(match_id).revision == 3


def test_vertical_flow_does_not_require_a_real_provider() -> None:
    # Guard for the shared fakes: the whole slice is deterministic and offline.
    app, _, _, _, _ = _app(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    client = TestClient(app)
    created = _create_match(client)

    assert _advance(client, created["match_id"], 0, "adv-1").status_code == 200
    assert _submit_rule(client, created["match_id"], 1, "rule-1").status_code == 200
    assert _advance(client, created["match_id"], 2, "adv-2").status_code == 200
    assert client.get(f"/api/v1/matches/{created['match_id']}/replay").status_code == 200
