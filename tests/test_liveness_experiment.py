from collections import deque

from rules_beyond.liveness_experiment import (
    LivenessPolicy,
    _should_force_hard,
    play_liveness_match,
    scenarios,
)
from rules_beyond.rule_experiment import EXPERIMENT_CONFIG, validated_rules


def test_pressure_policy_requires_accumulated_pressure() -> None:
    assert not _should_force_hard(
        LivenessPolicy.PRESSURE_12,
        round_no=20,
        pressure=11,
        damage_window=deque(maxlen=10),
    )
    assert _should_force_hard(
        LivenessPolicy.PRESSURE_12,
        round_no=20,
        pressure=12,
        damage_window=deque(maxlen=10),
    )


def test_rolling_window_requires_ten_rounds_and_at_most_one_damage() -> None:
    short = deque([0] * 9, maxlen=10)
    low = deque([0] * 9 + [1], maxlen=10)
    enough = deque([0] * 8 + [1, 1], maxlen=10)
    assert not _should_force_hard(
        LivenessPolicy.ROLLING_10_LOW_DAMAGE,
        round_no=10,
        pressure=0,
        damage_window=short,
    )
    assert _should_force_hard(
        LivenessPolicy.ROLLING_10_LOW_DAMAGE,
        round_no=11,
        pressure=0,
        damage_window=low,
    )
    assert not _should_force_hard(
        LivenessPolicy.ROLLING_10_LOW_DAMAGE,
        round_no=11,
        pressure=0,
        damage_window=enough,
    )


def test_absolute_late_game_fallback_starts_at_round_24() -> None:
    window = deque(maxlen=10)
    assert not _should_force_hard(
        LivenessPolicy.HARD_AT_ROUND_24,
        round_no=23,
        pressure=0,
        damage_window=window,
    )
    assert _should_force_hard(
        LivenessPolicy.HARD_AT_ROUND_24,
        round_no=24,
        pressure=0,
        damage_window=window,
    )


def test_hybrid_triggers_on_pressure_or_round_24() -> None:
    window = deque(maxlen=10)
    assert not _should_force_hard(
        LivenessPolicy.HYBRID_PRESSURE_12_ROUND_24,
        round_no=23,
        pressure=11,
        damage_window=window,
    )
    assert _should_force_hard(
        LivenessPolicy.HYBRID_PRESSURE_12_ROUND_24,
        round_no=20,
        pressure=12,
        damage_window=window,
    )
    assert _should_force_hard(
        LivenessPolicy.HYBRID_PRESSURE_12_ROUND_24,
        round_no=24,
        pressure=0,
        damage_window=window,
    )


def test_experimental_policy_does_not_modify_default_game_config() -> None:
    from rules_beyond.model import GameConfig

    assert EXPERIMENT_CONFIG.initial_hp == 5
    assert GameConfig().initial_hp == 4


def test_late_game_policy_can_force_known_stall_case_before_timeout() -> None:
    scenario = scenarios()[0]
    rule = validated_rules(EXPERIMENT_CONFIG)["always_bow_range_plus_1"]
    traces = [
        play_liveness_match(
            scenario,
            rule=rule,
            policy=LivenessPolicy.HARD_AT_ROUND_24,
            match_seed=seed,
        )
        for seed in range(910_000, 910_020)
    ]
    assert all(trace.result != "TIMEOUT" for trace in traces)
    assert all(trace.rounds <= EXPERIMENT_CONFIG.max_rounds for trace in traces)


def test_hybrid_can_force_known_stall_case_before_timeout() -> None:
    scenario = scenarios()[0]
    rule = validated_rules(EXPERIMENT_CONFIG)["always_bow_range_plus_1"]
    traces = [
        play_liveness_match(
            scenario,
            rule=rule,
            policy=LivenessPolicy.HYBRID_PRESSURE_12_ROUND_24,
            match_seed=seed,
        )
        for seed in range(920_000, 920_020)
    ]
    assert all(trace.result != "TIMEOUT" for trace in traces)
    assert all(trace.rounds <= EXPERIMENT_CONFIG.max_rounds for trace in traces)
