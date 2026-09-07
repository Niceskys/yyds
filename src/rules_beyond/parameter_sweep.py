from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
from statistics import mean, median

from .bots import AggressiveBot, Bot, KiteBot
from .diagnostics import AttackFirstAggressiveBot
from .engine import GameEngine
from .model import GameConfig, MatchResult
from .simulation import play_match


@dataclass(frozen=True, slots=True)
class PaceVariant:
    name: str
    initial_hp: int
    knife_damage: int

    def config(self) -> GameConfig:
        return GameConfig(initial_hp=self.initial_hp, knife_damage=self.knife_damage)


@dataclass(frozen=True, slots=True)
class PaceSweepRow:
    variant: str
    initial_hp: int
    knife_damage: int
    red_bot: str
    blue_bot: str
    matches: int
    results: dict[str, int]
    mean_rounds: float
    median_rounds: float
    short_matches_le_6: int
    short_rate_le_6: float
    long_matches_ge_12: int
    long_rate_ge_12: float
    timeouts: int
    timeout_rate: float
    draws: int
    draw_rate: float
    hard_liveness_matches: int
    hard_liveness_rate: float


VARIANTS: tuple[PaceVariant, ...] = (
    PaceVariant("hp4_knife2_baseline", 4, 2),
    PaceVariant("hp5_knife2", 5, 2),
    PaceVariant("hp6_knife2", 6, 2),
    PaceVariant("hp4_knife1", 4, 1),
    PaceVariant("hp5_knife1", 5, 1),
    PaceVariant("hp6_knife1", 6, 1),
)


def representative_pairings() -> list[tuple[Bot, Bot]]:
    aggressive = AggressiveBot()
    attack_first = AttackFirstAggressiveBot()
    kite = KiteBot()
    return [
        (attack_first, attack_first),
        (aggressive, attack_first),
        (attack_first, aggressive),
        (attack_first, kite),
        (kite, attack_first),
        (kite, kite),
    ]


def run_pace_sweep(matches_per_cell: int = 1000) -> list[PaceSweepRow]:
    if matches_per_cell <= 0:
        raise ValueError("matches_per_cell must be positive")

    rows: list[PaceSweepRow] = []
    pairings = representative_pairings()

    for variant_index, variant in enumerate(VARIANTS):
        engine = GameEngine(variant.config())
        for pair_index, (red_bot, blue_bot) in enumerate(pairings):
            seed_start = 1_000_000 + variant_index * 100_000 + pair_index * matches_per_cell
            metrics = [
                play_match(
                    red_bot,
                    blue_bot,
                    seed=seed,
                    engine=engine,
                )
                for seed in range(seed_start, seed_start + matches_per_cell)
            ]

            results = Counter(metric.result.value for metric in metrics)
            rounds = [metric.terminal_round for metric in metrics]
            short = sum(round_no <= 6 for round_no in rounds)
            long = sum(round_no >= 12 for round_no in rounds)
            timeouts = results.get(MatchResult.TIMEOUT.value, 0)
            draws = results.get(MatchResult.DRAW_MUTUAL_DEATH.value, 0)
            hard = sum(metric.hard_liveness_triggered for metric in metrics)

            rows.append(
                PaceSweepRow(
                    variant=variant.name,
                    initial_hp=variant.initial_hp,
                    knife_damage=variant.knife_damage,
                    red_bot=red_bot.name,
                    blue_bot=blue_bot.name,
                    matches=matches_per_cell,
                    results=dict(sorted(results.items())),
                    mean_rounds=mean(rounds),
                    median_rounds=median(rounds),
                    short_matches_le_6=short,
                    short_rate_le_6=short / matches_per_cell,
                    long_matches_ge_12=long,
                    long_rate_ge_12=long / matches_per_cell,
                    timeouts=timeouts,
                    timeout_rate=timeouts / matches_per_cell,
                    draws=draws,
                    draw_rate=draws / matches_per_cell,
                    hard_liveness_matches=hard,
                    hard_liveness_rate=hard / matches_per_cell,
                )
            )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep HP and knife damage for combat pace")
    parser.add_argument("--matches-per-cell", type=int, default=1000)
    args = parser.parse_args()
    rows = run_pace_sweep(args.matches_per_cell)
    print(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
