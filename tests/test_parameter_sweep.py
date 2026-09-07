from rules_beyond.parameter_sweep import VARIANTS, representative_pairings, run_pace_sweep


def test_pace_sweep_runs_all_variants_and_pairings() -> None:
    rows = run_pace_sweep(matches_per_cell=5)

    assert len(rows) == len(VARIANTS) * len(representative_pairings())
    assert all(row.matches == 5 for row in rows)
    assert all(1 <= row.mean_rounds <= 30 for row in rows)
    assert all(0.0 <= row.short_rate_le_6 <= 1.0 for row in rows)
    assert all(0.0 <= row.timeout_rate <= 1.0 for row in rows)
