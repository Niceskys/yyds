from __future__ import annotations

import json
from pathlib import Path

from rules_beyond.api_contract import ErrorEnvelope, MatchSnapshot, RuleSubmissionResult

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "contracts" / "fixtures" / "mvp-v0.1"


def test_checked_in_contract_fixtures_validate() -> None:
    models = {
        "rule_accepted.json": RuleSubmissionResult,
        "rule_rejected.json": RuleSubmissionResult,
        "match_terminal.json": MatchSnapshot,
        "error_revision_conflict.json": ErrorEnvelope,
    }
    assert {path.name for path in FIXTURE_DIR.glob("*.json")} == set(models)

    for filename, model in models.items():
        payload = json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
        model.model_validate(payload)
