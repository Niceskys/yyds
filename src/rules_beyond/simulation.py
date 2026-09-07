from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
from statistics import mean, median
from typing import Iterable

from .bots import AggressiveBot, Bot, KiteBot, PassiveBot, RandomBot
from .engine import GameEngine
from .model import GameConfig, MatchResult, Team, initial_state


# Historical 2026-09-07 baseline predates the normative Round-24 fallback.
# Keep it explicit so the committed snapshot remains reproducible after product
# defaults evolve.
BASELINE_CONFIG = GameConfig(late_game_hard_round=31)


@dataclass(frozen=True, slots=True)
class MatchMetrics:
    seed: int
    result: MatchResult
    terminal_round: int
    max_no_damage_streak: int
    hard_liveness_triggered: bool
    same_destination_conflicts: int
    swap_conflicts: int
    attack_count: int
    knife_attack_count: int
    bow_attack_count: int
    forced_bow_count: int
    damage_events: int


@dataclass(frozen=True, slots=True)
class BatchSummary:
    red_bot: str
    blue_bot: str
    matches: int
    results: dict[str, int]
    mean_rounds: float
    median_rounds: float
    max_rounds_observed: int
    hard_liveness_matches: int
    hard_liveness_rate: float
    mean_max_no_damage_streak: float
    total_same_destination_conflicts: int
    total_swap_conflicts: int
    total_attacks: int
    total_knife_attacks: int
    total_bow_attacks: int
    total_forced_bows: int


def play_match(
    red_bot: Bot,
    blue_bot: Bot,
    *,
    seed: int,
    engine: GameEngine | None = None,
) -> MatchMetrics:
    engine = engine or GameEngine()
    state = initial_state(engine.config)

    max_streak = state.no_damage_streak
    hard = False
    same_destination = 0
    swap = 0
    attacks = 0
    knife_attacks = 0
    bow_attacks = 0
    forced_bows = 0
    damage_events = 0

    while not state.is_terminal:
        actions = {
            Team.RED: red_bot.choose_action(
                state,
                Team.RED,
                engine,
                match_seed=seed,
            ),
            Team.BLUE: blue_bot.choose_action(
                state,
                Team.BLUE,
                engine,
                match_seed=seed,
            ),
        }
        resolution = engine.resolve_round(state, actions, match_seed=seed)
        hard = hard or resolution.state.hard_liveness_active

        for event in resolution.events:
            if event.kind == "SAME_DESTINATION_CONFLICT":
                same_destination += 1
            elif event.kind == "SWAP_CONFLICT":
                swap += 1
            elif event.kind == "FORCED_BOW":
                forced_bows += 1
            elif event.kind == "ATTACK_RESOLVED":
                attacks += 1
                if event.details["weapon"] == "KNIFE":
                    knife_attacks += 1
                elif event.details["weapon"] == "BOW":
                    bow_attacks += 1
            elif event.kind == "DAMAGE_APPLIED":
                damage_events += 1

        state = resolution.state
        max_streak = max(max_streak, state.no_damage_streak)

    assert state.result is not None
    return MatchMetrics(
        seed=seed,
        result=state.result,
        terminal_round=state.round_no,
        max_no_damage_streak=max_streak,
        hard_liveness_triggered=hard,
        same_destination_conflicts=same_destination,
        swap_conflicts=swap,
        attack_count=attacks,
        knife_attack_count=knife_attacks,
        bow_attack_count=bow_attacks,
        forced_bow_count=forced_bows,
        damage_events=damage_events,
    )


def run_batch(
    red_bot: Bot,
    blue_bot: Bot,
    seeds: Iterable[int],
    *,
    engine: GameEngine | None = None,
) -> BatchSummary:
    engine = engine or GameEngine()
    metrics = [
        play_match(red_bot, blue_bot, seed=seed, engine=engine)
        for seed in seeds
    ]
    if not metrics:
        raise ValueError("At least one seed is required")

    result_counts = Counter(metric.result.value for metric in metrics)
    rounds = [metric.terminal_round for metric in metrics]
    hard_count = sum(metric.hard_liveness_triggered for metric in metrics)

    return BatchSummary(
        red_bot=red_bot.name,
        blue_bot=blue_bot.name,
        matches=len(metrics),
        results=dict(sorted(result_counts.items())),
        mean_rounds=mean(rounds),
        median_rounds=median(rounds),
        max_rounds_observed=max(rounds),
        hard_liveness_matches=hard_count,
        hard_liveness_rate=hard_count / len(metrics),
        mean_max_no_damage_streak=mean(
            metric.max_no_damage_streak for metric in metrics
        ),
        total_same_destination_conflicts=sum(
            metric.same_destination_conflicts for metric in metrics
        ),
        total_swap_conflicts=sum(metric.swap_conflicts for metric in metrics),
        total_attacks=sum(metric.attack_count for metric in metrics),
        total_knife_attacks=sum(metric.knife_attack_count for metric in metrics),
        total_bow_attacks=sum(metric.bow_attack_count for metric in metrics),
        total_forced_bows=sum(metric.forced_bow_count for metric in metrics),
    )


def baseline_suite(matches_per_pair: int) -> list[BatchSummary]:
    if matches_per_pair <= 0:
        raise ValueError("matches_per_pair must be positive")

    pairings: list[tuple[Bot, Bot]] = [
        (AggressiveBot(), AggressiveBot()),
        (AggressiveBot(), KiteBot()),
        (KiteBot(), AggressiveBot()),
        (KiteBot(), KiteBot()),
        (PassiveBot(), PassiveBot()),
        (RandomBot(), RandomBot()),
    ]

    historical_engine = GameEngine(BASELINE_CONFIG)
    summaries: list[BatchSummary] = []
    for pair_index, (red_bot, blue_bot) in enumerate(pairings):
        start = pair_index * matches_per_pair
        seeds = range(start, start + matches_per_pair)
        summaries.append(run_batch(red_bot, blue_bot, seeds, engine=historical_engine))
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Rules Beyond baseline simulations")
    parser.add_argument(
        "--matches-per-pair",
        type=int,
        default=1000,
        help="Number of matches for each baseline bot pairing",
    )
    args = parser.parse_args()

    summaries = baseline_suite(args.matches_per_pair)
    print(json.dumps([asdict(summary) for summary in summaries], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
