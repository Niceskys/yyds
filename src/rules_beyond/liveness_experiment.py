from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass, replace
from enum import Enum
import argparse
import json
from statistics import mean
from typing import Iterable

from .model import MatchResult, Team, initial_state
from .rule_bots import RuleAwareAttackFirstBot, RuleAwareBot, RuleAwareKiteBot
from .rule_dsl import RuleAST
from .rule_engine import RuleAwareGameEngine
from .rule_experiment import EXPERIMENT_CONFIG, validated_rules
from .rule_runtime import initial_public_rule_histories


class LivenessPolicy(str, Enum):
    CURRENT = "current"
    PRESSURE_12 = "pressure_12"
    ROLLING_10_LOW_DAMAGE = "rolling_10_low_damage"
    HARD_AT_ROUND_24 = "hard_at_round_24"


@dataclass(frozen=True, slots=True)
class LivenessScenario:
    name: str
    rule_name: str | None
    red_bot: RuleAwareBot
    blue_bot: RuleAwareBot
    expected_class: str  # exploit | healthy


@dataclass(frozen=True, slots=True)
class LivenessTrace:
    result: str
    rounds: int
    policy_triggered: bool
    policy_trigger_round: int | None
    any_hard_liveness: bool
    total_damage: int
    forced_bows: int


@dataclass(frozen=True, slots=True)
class LivenessSummary:
    scenario: str
    expected_class: str
    policy: str
    matches: int
    current_results: dict[str, int]
    policy_results: dict[str, int]
    current_timeout_rate: float
    policy_timeout_rate: float
    timeout_rate_delta: float
    current_mean_rounds: float
    policy_mean_rounds: float
    mean_round_delta: float
    outcome_change_rate_vs_current: float
    policy_trigger_rate: float
    mean_policy_trigger_round: float | None
    any_hard_liveness_rate: float
    mean_forced_bows: float


POLICIES: tuple[LivenessPolicy, ...] = (
    LivenessPolicy.CURRENT,
    LivenessPolicy.PRESSURE_12,
    LivenessPolicy.ROLLING_10_LOW_DAMAGE,
    LivenessPolicy.HARD_AT_ROUND_24,
)


def scenarios() -> tuple[LivenessScenario, ...]:
    attack = RuleAwareAttackFirstBot()
    kite = RuleAwareKiteBot()
    return (
        LivenessScenario("exploit_bow_range_attack_mirror", "always_bow_range_plus_1", attack, attack, "exploit"),
        LivenessScenario("exploit_hit_half_attack_kite", "distance_ge_3_bow_hit_half", attack, kite, "exploit"),
        LivenessScenario("exploit_hit_half_kite_attack", "distance_ge_3_bow_hit_half", kite, attack, "exploit"),
        LivenessScenario("exploit_hit_half_kite_mirror", "distance_ge_3_bow_hit_half", kite, kite, "exploit"),
        LivenessScenario("healthy_no_rule_attack_mirror", None, attack, attack, "healthy"),
        LivenessScenario("healthy_no_rule_attack_kite", None, attack, kite, "healthy"),
        LivenessScenario("healthy_low_hp_damage_attack_kite", "low_hp_bow_damage_plus_1", attack, kite, "healthy"),
        LivenessScenario("healthy_cooldown_attack_kite", "repeat_bow_cooldown", attack, kite, "healthy"),
    )


def _should_force_hard(
    policy: LivenessPolicy,
    *,
    round_no: int,
    pressure: int,
    damage_window: deque[int],
) -> bool:
    if policy is LivenessPolicy.CURRENT:
        return False
    if policy is LivenessPolicy.PRESSURE_12:
        return pressure >= 12
    if policy is LivenessPolicy.ROLLING_10_LOW_DAMAGE:
        return len(damage_window) == 10 and sum(damage_window) <= 1
    if policy is LivenessPolicy.HARD_AT_ROUND_24:
        return round_no >= 24
    raise ValueError(f"Unsupported liveness policy: {policy}")


def play_liveness_match(
    scenario: LivenessScenario,
    *,
    rule: RuleAST | None,
    policy: LivenessPolicy,
    match_seed: int,
) -> LivenessTrace:
    engine = RuleAwareGameEngine(EXPERIMENT_CONFIG)
    state = initial_state(EXPERIMENT_CONFIG)
    histories = initial_public_rule_histories()

    pressure = 0
    damage_window: deque[int] = deque(maxlen=10)
    policy_triggered = False
    policy_trigger_round: int | None = None
    any_hard_liveness = False
    total_damage = 0
    forced_bows = 0
    rounds = 0

    while not state.is_terminal:
        if (
            not state.hard_liveness_active
            and _should_force_hard(
                policy,
                round_no=state.round_no,
                pressure=pressure,
                damage_window=damage_window,
            )
        ):
            state = replace(state, hard_liveness_active=True)
            policy_triggered = True
            policy_trigger_round = state.round_no

        any_hard_liveness = any_hard_liveness or state.hard_liveness_active

        red_action = scenario.red_bot.choose_action(
            state,
            Team.RED,
            engine,
            rule=rule,
            histories=histories,
            match_seed=match_seed,
        )
        blue_action = scenario.blue_bot.choose_action(
            state,
            Team.BLUE,
            engine,
            rule=rule,
            histories=histories,
            match_seed=match_seed,
        )

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

        round_damage = sum(
            max(0, before.unit(team).hp - state.unit(team).hp)
            for team in (Team.RED, Team.BLUE)
        )
        total_damage += round_damage
        damage_window.append(round_damage)
        if round_damage == 0:
            pressure += 1
        else:
            pressure = max(0, pressure - 1)

        forced_bows += sum(event.kind == "FORCED_BOW" for event in resolution.events)
        any_hard_liveness = any_hard_liveness or state.hard_liveness_active

    assert state.result is not None
    return LivenessTrace(
        result=state.result.value,
        rounds=rounds,
        policy_triggered=policy_triggered,
        policy_trigger_round=policy_trigger_round,
        any_hard_liveness=any_hard_liveness,
        total_damage=total_damage,
        forced_bows=forced_bows,
    )


def summarize_policy(
    scenario: LivenessScenario,
    *,
    rule: RuleAST | None,
    policy: LivenessPolicy,
    seeds: Iterable[int],
) -> LivenessSummary:
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("seeds must not be empty")

    current_traces = [
        play_liveness_match(
            scenario,
            rule=rule,
            policy=LivenessPolicy.CURRENT,
            match_seed=seed,
        )
        for seed in seed_list
    ]
    if policy is LivenessPolicy.CURRENT:
        policy_traces = current_traces
    else:
        policy_traces = [
            play_liveness_match(scenario, rule=rule, policy=policy, match_seed=seed)
            for seed in seed_list
        ]

    matches = len(seed_list)
    current_timeouts = sum(t.result == MatchResult.TIMEOUT.value for t in current_traces)
    policy_timeouts = sum(t.result == MatchResult.TIMEOUT.value for t in policy_traces)
    changed = sum(a.result != b.result for a, b in zip(current_traces, policy_traces))
    trigger_rounds = [t.policy_trigger_round for t in policy_traces if t.policy_trigger_round is not None]

    current_timeout_rate = current_timeouts / matches
    policy_timeout_rate = policy_timeouts / matches
    current_mean_rounds = mean(t.rounds for t in current_traces)
    policy_mean_rounds = mean(t.rounds for t in policy_traces)

    return LivenessSummary(
        scenario=scenario.name,
        expected_class=scenario.expected_class,
        policy=policy.value,
        matches=matches,
        current_results=dict(Counter(t.result for t in current_traces)),
        policy_results=dict(Counter(t.result for t in policy_traces)),
        current_timeout_rate=current_timeout_rate,
        policy_timeout_rate=policy_timeout_rate,
        timeout_rate_delta=policy_timeout_rate - current_timeout_rate,
        current_mean_rounds=current_mean_rounds,
        policy_mean_rounds=policy_mean_rounds,
        mean_round_delta=policy_mean_rounds - current_mean_rounds,
        outcome_change_rate_vs_current=changed / matches,
        policy_trigger_rate=sum(t.policy_triggered for t in policy_traces) / matches,
        mean_policy_trigger_round=mean(trigger_rounds) if trigger_rounds else None,
        any_hard_liveness_rate=sum(t.any_hard_liveness for t in policy_traces) / matches,
        mean_forced_bows=mean(t.forced_bows for t in policy_traces),
    )


def experiment_suite(matches_per_cell: int = 500) -> list[LivenessSummary]:
    if matches_per_cell <= 0:
        raise ValueError("matches_per_cell must be positive")

    rules = validated_rules(EXPERIMENT_CONFIG)
    output: list[LivenessSummary] = []
    for scenario_index, scenario in enumerate(scenarios()):
        rule = rules[scenario.rule_name] if scenario.rule_name is not None else None
        start = 900_000 + scenario_index * matches_per_cell
        seeds = range(start, start + matches_per_cell)
        for policy in POLICIES:
            output.append(
                summarize_policy(
                    scenario,
                    rule=rule,
                    policy=policy,
                    seeds=seeds,
                )
            )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare adversarial anti-stall candidates")
    parser.add_argument("--matches-per-cell", type=int, default=500)
    args = parser.parse_args()
    print(json.dumps([asdict(row) for row in experiment_suite(args.matches_per_cell)], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
