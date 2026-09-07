from rules_beyond.model import Team, initial_state
from rules_beyond.rule_bots import RuleAwareAttackFirstBot, RuleAwareKiteBot
from rules_beyond.rule_engine import RuleAwareGameEngine
from rules_beyond.rule_experiment import (
    EXPERIMENT_CONFIG,
    play_rule_match,
    run_paired_rule_batch,
    validated_rules,
)
from rules_beyond.rule_runtime import initial_public_rule_histories


def test_all_experiment_rules_are_validator_accepted() -> None:
    rules = validated_rules(EXPERIMENT_CONFIG)
    assert set(rules) == {
        "always_bow_range_plus_1",
        "always_move_range_plus_1",
        "distance_ge_3_bow_hit_half",
        "low_hp_bow_damage_plus_1",
        "repeat_bow_cooldown",
    }


def test_bow_range_rule_changes_attack_first_opening_action() -> None:
    rules = validated_rules(EXPERIMENT_CONFIG)
    rule = rules["always_bow_range_plus_1"]
    bot = RuleAwareAttackFirstBot()
    engine = RuleAwareGameEngine(EXPERIMENT_CONFIG)
    state = initial_state(EXPERIMENT_CONFIG)
    histories = initial_public_rule_histories()

    baseline = bot.choose_action(
        state,
        Team.RED,
        engine,
        rule=None,
        histories=histories,
        match_seed=1,
    )
    ruled = bot.choose_action(
        state,
        Team.RED,
        engine,
        rule=rule,
        histories=histories,
        match_seed=1,
    )

    assert baseline != ruled
    assert baseline.move_path
    assert not ruled.move_path
    assert ruled.attack is not None


def test_small_paired_batch_detects_rule_driven_behavior_change() -> None:
    rules = validated_rules(EXPERIMENT_CONFIG)
    summary = run_paired_rule_batch(
        "always_bow_range_plus_1",
        rules["always_bow_range_plus_1"],
        RuleAwareAttackFirstBot(),
        RuleAwareAttackFirstBot(),
        range(20_000, 20_040),
        config=EXPERIMENT_CONFIG,
    )

    assert summary.matches == 40
    assert summary.first_action_change_rate == 1.0
    assert (
        summary.ruled_mean_rounds != summary.baseline_mean_rounds
        or summary.ruled_mean_bow_attacks != summary.baseline_mean_bow_attacks
        or summary.outcome_change_rate > 0
    )


def test_rule_aware_probe_match_always_reaches_terminal_result() -> None:
    trace = play_rule_match(
        RuleAwareAttackFirstBot(),
        RuleAwareKiteBot(),
        rule=validated_rules(EXPERIMENT_CONFIG)["distance_ge_3_bow_hit_half"],
        match_seed=12345,
        config=EXPERIMENT_CONFIG,
    )
    assert trace.result in {"RED_WIN", "BLUE_WIN", "DRAW_MUTUAL_DEATH", "TIMEOUT"}
    assert 1 <= trace.rounds <= EXPERIMENT_CONFIG.max_rounds
