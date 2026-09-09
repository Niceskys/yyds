from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
from statistics import mean
from typing import Mapping

from .dynamic_rule_controller import DynamicRuleController, RuleCandidate
from .model import GameConfig, MatchResult, Team
from .rule_bots import RuleAwareAttackFirstBot, RuleAwareBot, RuleAwareKiteBot
from .rule_experiment import RULE_CANDIDATES


DYNAMIC_EXPERIMENT_CONFIG = GameConfig(initial_hp=5, knife_damage=2)

# V0.2 intermission cadence: keys are the completed round after which the
# player attempts a replacement. Round 1 always resolves without a player rule.
DYNAMIC_SCHEDULE: Mapping[int, RuleCandidate] = {
    1: RULE_CANDIDATES["always_bow_range_plus_1"],
    2: RULE_CANDIDATES["distance_ge_3_bow_hit_half"],
    3: RULE_CANDIDATES["repeat_bow_cooldown"],
    4: RULE_CANDIDATES["low_hp_bow_damage_plus_1"],
    5: RULE_CANDIDATES["always_move_range_plus_1"],
}
STATIC_SCHEDULE: Mapping[int, RuleCandidate] = {
    1: RULE_CANDIDATES["always_bow_range_plus_1"],
}


@dataclass(frozen=True, slots=True)
class DynamicTrace:
    result: str
    rounds: int
    accepted_phases: int
    replacement_phases: int
    carry_phases: int
    round4_actions: tuple[str, str] | None


@dataclass(frozen=True, slots=True)
class DynamicSummary:
    pairing: str
    matches: int
    static_results: dict[str, int]
    dynamic_results: dict[str, int]
    static_timeout_rate: float
    dynamic_timeout_rate: float
    outcome_change_rate: float
    mean_dynamic_replacements: float
    mean_dynamic_carries: float
    round4_comparable_matches: int
    round4_action_change_rate: float | None
    static_mean_rounds: float
    dynamic_mean_rounds: float


def _action_signature(action) -> str:
    path = ",".join(step.value for step in action.move_path) or "STAY"
    attack = action.attack.value if action.attack is not None else "NONE"
    return f"{path}|{attack}"


def play_scheduled_match(
    red_bot: RuleAwareBot,
    blue_bot: RuleAwareBot,
    *,
    schedule: Mapping[int, RuleCandidate],
    match_seed: int,
    config: GameConfig = DYNAMIC_EXPERIMENT_CONFIG,
) -> DynamicTrace:
    controller = DynamicRuleController(config)
    started = controller.start_match()
    state = started.state

    accepted_phases = 0
    replacement_phases = 0
    carry_phases = 0
    rounds = 0
    round4_actions: tuple[str, str] | None = None

    while not state.game_state.is_terminal:
        red_action = red_bot.choose_action(
            state.game_state,
            Team.RED,
            controller.engine,
            rule=state.active_rule,
            histories=state.histories,
            match_seed=match_seed,
        )
        blue_action = blue_bot.choose_action(
            state.game_state,
            Team.BLUE,
            controller.engine,
            rule=state.active_rule,
            histories=state.histories,
            match_seed=match_seed,
        )
        if state.game_state.round_no == 4:
            round4_actions = (_action_signature(red_action), _action_signature(blue_action))

        resolved = controller.resolve_round(
            state,
            {Team.RED: red_action, Team.BLUE: blue_action},
            match_seed=match_seed,
        )
        state = resolved.state
        rounds += 1

        if state.in_intermission:
            after_round = state.pending_intermission_after_round
            candidate = schedule.get(after_round)
            if candidate is None:
                carry_phases += 1
                state = controller.continue_match(state).state
            else:
                submission = controller.submit_rule(state, candidate)
                accepted_phases += int(submission.outcome.accepted)
                replacement_phases += int(submission.outcome.replaced)
                state = controller.continue_match(submission.state).state

    assert state.game_state.result is not None
    return DynamicTrace(
        result=state.game_state.result.value,
        rounds=rounds,
        accepted_phases=accepted_phases,
        replacement_phases=replacement_phases,
        carry_phases=carry_phases,
        round4_actions=round4_actions,
    )


def summarize_pairing(
    red_bot: RuleAwareBot,
    blue_bot: RuleAwareBot,
    seeds,
) -> DynamicSummary:
    seed_list = list(seeds)
    if not seed_list:
        raise ValueError("seeds must not be empty")

    static = [
        play_scheduled_match(red_bot, blue_bot, schedule=STATIC_SCHEDULE, match_seed=seed)
        for seed in seed_list
    ]
    dynamic = [
        play_scheduled_match(red_bot, blue_bot, schedule=DYNAMIC_SCHEDULE, match_seed=seed)
        for seed in seed_list
    ]

    matches = len(seed_list)
    comparable = [
        (a.round4_actions, b.round4_actions)
        for a, b in zip(static, dynamic)
        if a.round4_actions is not None and b.round4_actions is not None
    ]
    round4_changes = sum(a != b for a, b in comparable)

    return DynamicSummary(
        pairing=f"{red_bot.name}_vs_{blue_bot.name}",
        matches=matches,
        static_results=dict(Counter(trace.result for trace in static)),
        dynamic_results=dict(Counter(trace.result for trace in dynamic)),
        static_timeout_rate=sum(trace.result == MatchResult.TIMEOUT.value for trace in static) / matches,
        dynamic_timeout_rate=sum(trace.result == MatchResult.TIMEOUT.value for trace in dynamic) / matches,
        outcome_change_rate=sum(a.result != b.result for a, b in zip(static, dynamic)) / matches,
        mean_dynamic_replacements=mean(trace.replacement_phases for trace in dynamic),
        mean_dynamic_carries=mean(trace.carry_phases for trace in dynamic),
        round4_comparable_matches=len(comparable),
        round4_action_change_rate=(round4_changes / len(comparable)) if comparable else None,
        static_mean_rounds=mean(trace.rounds for trace in static),
        dynamic_mean_rounds=mean(trace.rounds for trace in dynamic),
    )


def experiment_suite(matches_per_pair: int = 500) -> list[DynamicSummary]:
    if matches_per_pair <= 0:
        raise ValueError("matches_per_pair must be positive")

    attack = RuleAwareAttackFirstBot()
    kite = RuleAwareKiteBot()
    pairings = (
        (attack, attack),
        (attack, kite),
        (kite, attack),
        (kite, kite),
    )

    output: list[DynamicSummary] = []
    for index, (red_bot, blue_bot) in enumerate(pairings):
        start = 1_200_000 + index * matches_per_pair
        output.append(summarize_pairing(red_bot, blue_bot, range(start, start + matches_per_pair)))
    return output


def assert_dynamic_gate(summaries: list[DynamicSummary]) -> None:
    if not summaries:
        raise AssertionError("dynamic experiment produced no summaries")
    if any(summary.dynamic_timeout_rate > 0 for summary in summaries):
        raise AssertionError("dynamic schedule reintroduced TIMEOUT")
    if not any(summary.mean_dynamic_replacements > 1.0 for summary in summaries):
        raise AssertionError("matches are not surviving long enough to exercise replacement phases")

    comparable = [summary for summary in summaries if summary.round4_comparable_matches > 0]
    if not comparable:
        raise AssertionError("no paired match reached round 4 in both static and dynamic runs")
    if not any((summary.round4_action_change_rate or 0.0) > 0 for summary in comparable):
        raise AssertionError(
            "scheduled replacement effective on round 4 produced no observable action change"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate deterministic dynamic public-rule replacement")
    parser.add_argument("--matches-per-pair", type=int, default=500)
    args = parser.parse_args()
    summaries = experiment_suite(args.matches_per_pair)
    assert_dynamic_gate(summaries)
    print(json.dumps([asdict(summary) for summary in summaries], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
