from __future__ import annotations

import json
from pathlib import Path

from rules_beyond.openapi_contract import contract_app


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_SNAPSHOT = REPOSITORY_ROOT / "contracts" / "openapi" / "mvp-v0.2.json"


def test_checked_in_openapi_snapshot_matches_canonical_generator() -> None:
    """The checked-in JSON is a derived artifact, never a second canonical schema."""

    checked_in = json.loads(OPENAPI_SNAPSHOT.read_text(encoding="utf-8"))
    generated = contract_app.openapi()

    assert checked_in == generated
