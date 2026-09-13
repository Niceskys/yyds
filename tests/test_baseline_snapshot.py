from dataclasses import asdict
import json
from pathlib import Path

from rules_beyond.simulation import baseline_suite


def test_12000_match_baseline_snapshot_is_reproducible() -> None:
    snapshot_path = Path("docs/baseline/BASELINE_12000_2026-09-13.json")
    expected = json.loads(snapshot_path.read_text(encoding="utf-8"))

    actual = [asdict(summary) for summary in baseline_suite(2000)]

    assert actual == expected
