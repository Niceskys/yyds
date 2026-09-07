from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json

from .bots import AggressiveBot, Bot, KiteBot, _candidate_moves, _stats_for_state, _weapon_for_distance
from .engine import GameEngine
from .model import Action, GameState, Team
from .simulation import BatchSummary, run_batch


@dataclass(frozen=True, slots=True)
class AttackFirstAggressiveBot:
    """A deliberately simple diagnostic bot.

    Difference from AggressiveBot:
    - if it can already attack from its current square, it stays and attacks;
    - it only moves closer when no legal attack is currently available.

    This is not a production planner. It exists to test whether the baseline
    AggressiveBot's repeated center collisions are caused by its heuristic rather
    than by the game rules themselves.
    """

    name: str = "attack_first_aggressive"

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: GameEngine,
        *,
        match_seed: int,
    ) -> Action:
        del match_seed
        me = state.unit(team).position
        opponent = state.unit(team.opponent).position
        stats = _stats_for_state(state, engine)
        current_distance = me.manhattan_distance(opponent)

        current_weapon = _weapon_for_distance(
            current_distance,
            knife_range=stats.knife_range,
            bow_range=stats.bow_range,
        )
        if current_weapon is not None:
            return Action((), current_weapon)

        candidates = _candidate_moves(state, team, engine)
        path, destination = min(
            candidates,
            key=lambda item: (
                item[1].manhattan_distance(opponent),
                len(item[0]),
                tuple(step.value for step in item[0]),
            ),
        )
        distance = destination.manhattan_distance(opponent)
        weapon = _weapon_for_distance(
            distance,
            knife_range=stats.knife_range,
            bow_range=stats.bow_range,
        )
        return Action(path, weapon)


def diagnostic_suite(matches_per_pair: int = 2000) -> list[BatchSummary]:
    if matches_per_pair <= 0:
        raise ValueError("matches_per_pair must be positive")

    naive = AggressiveBot()
    attack_first = AttackFirstAggressiveBot()
    kite = KiteBot()

    pairings: list[tuple[Bot, Bot]] = [
        (naive, naive),
        (attack_first, attack_first),
        (naive, attack_first),
        (attack_first, naive),
        (attack_first, kite),
        (kite, attack_first),
    ]

    summaries: list[BatchSummary] = []
    for pair_index, (red_bot, blue_bot) in enumerate(pairings):
        start = 100_000 + pair_index * matches_per_pair
        seeds = range(start, start + matches_per_pair)
        summaries.append(run_batch(red_bot, blue_bot, seeds))
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose bot-vs-rule behavior")
    parser.add_argument("--matches-per-pair", type=int, default=2000)
    args = parser.parse_args()

    summaries = diagnostic_suite(args.matches_per_pair)
    print(json.dumps([asdict(summary) for summary in summaries], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
