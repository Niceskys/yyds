from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
from statistics import mean
from typing import Mapping

from .model import GameConfig, MatchResult, Team, initial_state
from .rule_bots import RuleAwareAttackFirstBot, RuleAwareBot, RuleAwareKiteBot
from .rule_dsl import RuleAST
from .rule_engine import RuleAwareGameEngine
from .rule_runtime import initial_public_rule_histories
from .rule_validator import RuleValidator


@dataclass(frozen=True, slots=True)
class MatchTrace:
    result: str
    rounds: int
    move_distance: int
    knife_attacks: int
    bow_attacks: int
    forced_bows: int
    invalid_attacks: int
    rule_activations: int
    first_red_action: str
    first_blue_action: str


@dataclass(frozen=True, slots=True)
class PairedRuleSummary:
    scenario: str
    red_bot: str
    blue_bot: str
    matches: int
    baseline_results: dict[str, int]
    ruled_results: dict[str, int]
    baseline_mean_rounds: float
    ruled_mean_rounds: float
    mean_round_delta: float
    outcome_changed: int
    outcome_change_rate: float
    first_action_changed: int
    first_action_change_rate: float
    baseline_mean_move_distance: float
    ruled_mean_move_distance: float
    baseline_mean_bow_attacks: float
    ruled_mean_bow_attacks: float
    baseline_mean_knife_attacks: float
    ruled_mean_knife_attacks: float
    ruled_mean_rule_activations: float
    baseline_timeout_rate: float
    ruled_timeout_rate: float


# Historical experiment configuration deliberately disables the new product
# Round-24 fallback so previous paired-seed reports remain reproducible.
EXPERIMENT_CONFIG = GameConfig(initial_hp=5, knife_damage=2, late_game_hard_round=31)


RULE_CANDIDATES: Mapping[str, dict[str, object]] = {
    "always_bow_range_plus_1": {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    "always_move_range_plus_1": {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    "distance_ge_3_bow_hit_half": {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "DISTANCE_GTE", "value": 3}],
        "effect": {"type": "BOW_HIT_MULTIPLIER", "multiplier": 0.5},
        "duration": "UNTIL_REPLACED",
    },
    "low_hp_bow_damage_plus_1": {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "SELF_HP_LTE", "value": 2}],
        "effect": {"type": "BOW_DAMAGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    "repeat_bow_cooldown": {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "CONSECUTIVE_SAME_WEAPON_USE_GTE", "value": 2}],
        "effect": {"type": "WEAPON_COOLDOWN", "weapon": "BOW", "rounds": 1},
        "duration": "UNTIL_REPLACED",
    },
}


def validated_rules(config: GameConfig = EXPERIMENT_CONFIG) -> dict[str, RuleAST]:
    validator = RuleValidator(config)
    result: dict[str, RuleAST] = {}
    for name, candidate in RULE_CANDIDATES.items():
        validation = validator.validate(candidate)
        if not validation.accepted or validation.rule is None:
            codes = ", ".join(issue.code for issue in validation.issues)
            raise RuntimeError(f"Experiment rule {name} is invalid: {codes}")
        result[name] = validation.rule
    return result


def _action_signature(action) -> str:
    path = ",".join(step.value for step in action.move_path) or "STAY"
    attack = action.attack.value if action.attack is not None else "NONE"
    return f"{path}|{attack}"


def play_rule_match(
    red_bot: RuleAwareBot,
    blue_bot: RuleAwareBot,
    *,
    rule: RuleAST | None,
    match_seed: int,
    config: GameConfig = EXPERIMENT_CONFIG,
) -> MatchTrace:
    engine = RuleAwareGameEngine(config)
    state = initial_state(config)
    histories = initial_public_rule_histories()

    rounds = 0
    move_distance = 0
    knife_attacks = 0
    bow_attacks = 0
    forced_bows = 0
    invalid_attacks = 0
    rule_activations = 0
    first_red_action = ""
    first_blue_action = ""

    while not state.is_terminal:
        red_action = red_bot.choose_action(
            state,
            Team.RED,
            engine,
            rule=rule,
            histories=histories,
            match_seed=match_seed,
        )
        blue_action = blue_bot.choose_action(
            state,
            Team.BLUE,
            engine,
            rule=rule,
            histories=histories,
            match_seed=match_seed,
        )
        if rounds == 0:
            first_red_action = _action_signature(red_action)
            first_blue_action = _action_signature(blue_action)

        before = state
        resolution = engine.resolve_rule_round(
            state,
            {Team.RED: red_action, Team.BLUE: blue_action},
            rule=rule,
            histories=histories,
            match_seed=match_seed,
        )
        state = resolution.state
        histories = resolution.histories
        rounds += 1

        for team in (Team.RED, Team.BLUE):
            move_distance += before.unit(team).position.manhattan_distance(state.unit(team).position)

        for event in resolution.events:
            if event.kind == "RULE_MODIFIER_APPLIED":
                rule_activations += 1
            elif event.kind == "INVALID_ATTACK":
                invalid_attacks += 1
            elif event.kind == "FORCED_BOW":
                forced_bows += 1
            elif event.kind == "ATTACK_RESOLVED":
                weapon = event.details.get("weapon")
                if weapon == "KNIFE":
                    knife_attacks += 1
                elif weapon == "BOW":
                    bow_attacks += 1

    assert state.result is not None
    return MatchTrace(
        result=state.result.value,
        rounds=rounds,
        move_distance=move_distance,
        knife_attacks=knife_attacks,
        bow_attacks=bow_attacks,
        forced_bows=forced_bows,
        invalid_attacks=invalid_attacks,
        rule_activations=rule_activations,
        first_red_action=first_red_action,
        first_blue_action=first_blue_action,
    )


def run_paired_rule_batch(
    scenario: str,
    rule: RuleAST,
    red_bot: RuleAwareBot,
    blue_bot: RuleAwareBot,
    seeds,
    *,
    config: GameConfig = EXPERIMENT_CONFIG,
) -> PairedRuleSummary:
    baseline: list[MatchTrace] = []
    ruled: list[MatchTrace] = []

    for seed in seeds:
        baseline.append(
            play_rule_match(red_bot, blue_bot, rule=None, match_seed=seed, config=config)
        )
        ruled.append(
            play_rule_match(red_bot, blue_bot, rule=rule, match_seed=seed, config=config)
        )

    matches = len(baseline)
    if matches == 0:
        raise ValueError("seeds must not be empty")

    outcome_changed = sum(a.result != b.result for a, b in zip(baseline, ruled))
    first_action_changed = sum(
        (a.first_red_action, a.first_blue_action) != (b.first_red_action, b.first_blue_action)
        for a, b in zip(baseline, ruled)
    )

    baseline_timeouts = sum(trace.result == MatchResult.TIMEOUT.value for trace in baseline)
    ruled_timeouts = sum(trace.result == MatchResult.TIMEOUT.value for trace in ruled)

    return PairedRuleSummary(
        scenario=scenario,
        red_bot=red_bot.name,
        blue_bot=blue_bot.name,
        matches=matches,
        baseline_results=dict(Counter(trace.result for trace in baseline)),
        ruled_results=dict(Counter(trace.result for trace in ruled)),
        baseline_mean_rounds=mean(trace.rounds for trace in baseline),
        ruled_mean_rounds=mean(trace.rounds for trace in ruled),
        mean_round_delta=mean(b.rounds - a.rounds for a, b in zip(baseline, ruled)),
        outcome_changed=outcome_changed,
        outcome_change_rate=outcome_changed / matches,
        first_action_changed=first_action_changed,
        first_action_change_rate=first_action_changed / matches,
        baseline_mean_move_distance=mean(trace.move_distance for trace in baseline),
        ruled_mean_move_distance=mean(trace.move_distance for trace in ruled),
        baseline_mean_bow_attacks=mean(trace.bow_attacks for trace in baseline),
        ruled_mean_bow_attacks=mean(trace.bow_attacks for trace in ruled),
        baseline_mean_knife_attacks=mean(trace.knife_attacks for trace in baseline),
        ruled_mean_knife_attacks=mean(trace.knife_attacks for trace in ruled),
        ruled_mean_rule_activations=mean(trace.rule_activations for trace in ruled),
        baseline_timeout_rate=baseline_timeouts / matches,
        ruled_timeout_rate=ruled_timeouts / matches,
    )


def experiment_suite(matches_per_cell: int = 1000) -> list[PairedRuleSummary]:
    if matches_per_cell <= 0:
        raise ValueError("matches_per_cell must be positive")

    rules = validated_rules(EXPERIMENT_CONFIG)
    attack_first = RuleAwareAttackFirstBot()
    kite = RuleAwareKiteBot()
    pairings: tuple[tuple[RuleAwareBot, RuleAwareBot], ...] = (
        (attack_first, attack_first),
        (attack_first, kite),
        (kite, attack_first),
        (kite, kite),
    )

    summaries: list[PairedRuleSummary] = []
    for rule_index, (scenario, rule) in enumerate(rules.items()):
        for pair_index, (red_bot, blue_bot) in enumerate(pairings):
            start = 500_000 + (rule_index * len(pairings) + pair_index) * matches_per_cell
            seeds = range(start, start + matches_per_cell)
            summaries.append(
                run_paired_rule_batch(
                    scenario,
                    rule,
                    red_bot,
                    blue_bot,
                    seeds,
                    config=EXPERIMENT_CONFIG,
                )
            )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired-seed public-rule core-signal experiment")
    parser.add_argument("--matches-per-cell", type=int, default=1000)
    args = parser.parse_args()
    summaries = experiment_suite(args.matches_per_cell)
    print(json.dumps([asdict(summary) for summary in summaries], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
