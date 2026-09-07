from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from .model import Action, Direction, GameState, Position, Team, Weapon
from .rule_dsl import RuleAST
from .rule_engine import RuleAwareGameEngine, RuleEffectiveStats
from .rule_runtime import PublicRuleHistory


class RuleAwareBot(Protocol):
    name: str

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: RuleAwareGameEngine,
        *,
        rule: RuleAST | None,
        histories: Mapping[Team, PublicRuleHistory],
        match_seed: int,
    ) -> Action: ...


_MOVE_ORDER: tuple[Direction, ...] = (
    Direction.UP,
    Direction.DOWN,
    Direction.LEFT,
    Direction.RIGHT,
)


def _candidate_moves(
    state: GameState,
    team: Team,
    engine: RuleAwareGameEngine,
    move_range: int,
) -> list[tuple[tuple[Direction, ...], Position]]:
    """Return one shortest legal path to each reachable destination, including STAY."""
    start = state.unit(team).position
    best: dict[Position, tuple[Direction, ...]] = {start: ()}
    frontier: list[tuple[tuple[Direction, ...], Position]] = [((), start)]

    for _ in range(move_range):
        next_frontier: list[tuple[tuple[Direction, ...], Position]] = []
        for path, position in frontier:
            for direction in _MOVE_ORDER:
                destination = position.moved(direction)
                if not engine.config.contains(destination):
                    continue
                new_path = path + (direction,)
                if destination not in best or len(new_path) < len(best[destination]):
                    best[destination] = new_path
                    next_frontier.append((new_path, destination))
        frontier = next_frontier

    return [(path, destination) for destination, path in best.items()]


def _weapon_for_distance(distance: int, stats: RuleEffectiveStats) -> Weapon | None:
    # Prefer knife when available because it is deterministic and normally higher damage.
    if Weapon.KNIFE not in stats.cooldown_weapons and distance <= stats.knife_range:
        return Weapon.KNIFE
    if Weapon.BOW not in stats.cooldown_weapons and distance <= stats.bow_range:
        return Weapon.BOW
    return None


@dataclass(frozen=True, slots=True)
class RuleAwareAttackFirstBot:
    name: str = "rule_attack_first"

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: RuleAwareGameEngine,
        *,
        rule: RuleAST | None,
        histories: Mapping[Team, PublicRuleHistory],
        match_seed: int,
    ) -> Action:
        del match_seed
        stats = engine.effective_stats_for_team(
            state,
            team,
            rule=rule,
            histories=histories,
        )
        me = state.unit(team).position
        opponent = state.unit(team.opponent).position
        current_distance = me.manhattan_distance(opponent)
        current_weapon = _weapon_for_distance(current_distance, stats)
        if current_weapon is not None:
            return Action((), current_weapon)

        candidates = _candidate_moves(state, team, engine, stats.move_range)
        path, destination = min(
            candidates,
            key=lambda item: (
                item[1].manhattan_distance(opponent),
                len(item[0]),
                tuple(step.value for step in item[0]),
            ),
        )
        distance = destination.manhattan_distance(opponent)
        return Action(path, _weapon_for_distance(distance, stats))


@dataclass(frozen=True, slots=True)
class RuleAwareKiteBot:
    name: str = "rule_kite"
    preferred_distance: int = 3

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: RuleAwareGameEngine,
        *,
        rule: RuleAST | None,
        histories: Mapping[Team, PublicRuleHistory],
        match_seed: int,
    ) -> Action:
        del match_seed
        stats = engine.effective_stats_for_team(
            state,
            team,
            rule=rule,
            histories=histories,
        )
        opponent = state.unit(team.opponent).position
        candidates = _candidate_moves(state, team, engine, stats.move_range)

        def score(item: tuple[tuple[Direction, ...], Position]):
            path, destination = item
            distance = destination.manhattan_distance(opponent)
            attackable = _weapon_for_distance(distance, stats) is not None
            return (
                0 if attackable else 1,
                abs(distance - self.preferred_distance),
                len(path),
                tuple(step.value for step in path),
            )

        path, destination = min(candidates, key=score)
        distance = destination.manhattan_distance(opponent)
        return Action(path, _weapon_for_distance(distance, stats))
