from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json

from .liveness_experiment import scenarios
from .model import GameConfig, MatchResult
from .rule_experiment import play_rule_match, validated_rules


@dataclass(frozen=True, slots=True)
class Round24RegressionSummary:
    scenario: str
    matches: int
    results: dict[str, int]
    timeout_rate: float
    mean_rounds: float


REGRESSION_CONFIG = GameConfig(
    initial_hp=5,
    knife_damage=2,
    late_game_hard_round=24,
)


def regression_suite(matches_per_cell: int = 1000) -> list[Round24RegressionSummary]:
    if matches_per_cell <= 0:
        raise ValueError("matches_per_cell must be positive")

    rules = validated_rules(REGRESSION_CONFIG)
    exploit_scenarios = [scenario for scenario in scenarios() if scenario.expected_class == "exploit"]
    output: list[Round24RegressionSummary] = []

    for index, scenario in enumerate(exploit_scenarios):
        assert scenario.rule_name is not None
        rule = rules[scenario.rule_name]
        start = 900_000 + index * matches_per_cell
        traces = [
            play_rule_match(
                scenario.red_bot,
                scenario.blue_bot,
                rule=rule,
                match_seed=seed,
                config=REGRESSION_CONFIG,
            )
            for seed in range(start, start + matches_per_cell)
        ]
        timeout_count = sum(trace.result == MatchResult.TIMEOUT.value for trace in traces)
        output.append(
            Round24RegressionSummary(
                scenario=scenario.name,
                matches=matches_per_cell,
                results=dict(Counter(trace.result for trace in traces)),
                timeout_rate=timeout_count / matches_per_cell,
                mean_rounds=sum(trace.rounds for trace in traces) / matches_per_cell,
            )
        )

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Regression for normative Round-24 Hard Liveness")
    parser.add_argument("--matches-per-cell", type=int, default=1000)
    args = parser.parse_args()

    rows = regression_suite(args.matches_per_cell)
    print(json.dumps([asdict(row) for row in rows], indent=2, ensure_ascii=False))

    if any(row.timeout_rate > 0 for row in rows):
        raise SystemExit("Round-24 regression failed: exploit TIMEOUT detected")


if __name__ == "__main__":
    main()
