from __future__ import annotations

import json
from pathlib import Path

from rules_beyond.api_contract import (
    AdvanceResult,
    ErrorEnvelope,
    MatchSnapshot,
    ReplaySnapshot,
    RuleSubmissionResult,
)
from rules_beyond.contract_fixtures import build_fixtures

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "contracts" / "fixtures" / "mvp-v0.2"

MODELS = {
    "match_initial.json": MatchSnapshot,
    "match_player_decision.json": MatchSnapshot,
    "rule_accepted.json": RuleSubmissionResult,
    "rule_rejected.json": RuleSubmissionResult,
    "match_terminal.json": MatchSnapshot,
    "error_revision_conflict.json": ErrorEnvelope,
    "advance_round.json": AdvanceResult,
    "replay_terminal.json": ReplaySnapshot,
}

CURRENT_ENGINE_EVENT_KINDS = {
    "INVALID_MOVE_PATH",
    "SAME_DESTINATION_CONFLICT",
    "SWAP_CONFLICT",
    "INVALID_ATTACK",
    "FORCED_BOW",
    "ATTACK_RESOLVED",
    "DAMAGE_APPLIED",
    "MATCH_TIMEOUT",
    "MATCH_TERMINAL",
}


def test_checked_in_contract_fixtures_validate() -> None:
    assert {path.name for path in FIXTURE_DIR.glob("*.json")} == set(MODELS)

    for filename, model in MODELS.items():
        payload = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
        model.model_validate(payload)


def test_checked_in_contract_fixtures_match_generator() -> None:
    generated = build_fixtures()
    assert set(generated) == set(MODELS)

    for filename, model_instance in generated.items():
        actual = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
        expected = model_instance.model_dump(mode="json")
        assert actual == expected, f"{filename} drifted from contract_fixtures.py"


def test_fixture_events_use_current_engine_vocabulary() -> None:
    generated = build_fixtures()
    kinds = {event.kind for event in generated["advance_round.json"].round.events}
    replay = generated["replay_terminal.json"]
    for entry in replay.timeline:
        if entry.entry_type == "ROUND":
            kinds.update(event.kind for event in entry.events)

    assert kinds <= CURRENT_ENGINE_EVENT_KINDS
