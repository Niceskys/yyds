from rules_beyond.bots import AggressiveBot, PassiveBot
from rules_beyond.model import MatchResult
from rules_beyond.simulation import play_match, run_batch


def test_passive_vs_passive_proves_hard_liveness_latch() -> None:
    metrics = play_match(PassiveBot(), PassiveBot(), seed=1)

    assert metrics.result is MatchResult.DRAW_MUTUAL_DEATH
    assert metrics.terminal_round == 16
    assert metrics.hard_liveness_triggered is True
    assert metrics.forced_bow_count == 8


def test_batch_summary_counts_all_matches() -> None:
    summary = run_batch(AggressiveBot(), AggressiveBot(), range(10))

    assert summary.matches == 10
    assert sum(summary.results.values()) == 10
    assert summary.mean_rounds > 0
    assert summary.max_rounds_observed <= 30
