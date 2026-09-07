from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Protocol

from .engine import GameEngine
from .model import Action, Direction, GameState, Position, Team, Weapon


class Bot(Protocol):
    name: str

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: GameEngine,
        *,
        match_seed: int,
    ) -> Action: ...


_MOVE_ORDER: tuple[Direction | None, ...] = (
    None,
    Direction.UP,
    Direction.DOWN,
    Direction.LEFT,
    Direction.RIGHT,
)


def _stats_for_state(state: GameState, engine: GameEngine):
    """Simulation-only access to the exact effective stats used by Engine."""
    return engine._effective_stats(
        state.no_damage_streak,
        hard_liveness_active=state.hard_liveness_active,
    )


def _candidate_moves(
    state: GameState,
    team: Team,
    engine: GameEngine,
) -> list[tuple[tuple[Direction, ...], Position]]:
    current = state.unit(team).position
    result: list[tuple[tuple[Direction, ...], Position]] = [((), current)]
    for direction in _MOVE_ORDER[1:]:
        assert direction is not None
        destination = current.moved(direction)
        if engine.config.contains(destination):
            result.append(((direction,), destination))
    return result


def _weapon_for_distance(
    distance: int,
    *,
    knife_range: int,
    bow_range: int,
) -> Weapon | None:
    if distance <= knife_range:
        return Weapon.KNIFE
    if distance <= bow_range:
        return Weapon.BOW
    return None


@dataclass(frozen=True, slots=True)
class AggressiveBot:
    name: str = "aggressive"

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: GameEngine,
        *,
        match_seed: int,
    ) -> Action:
        del match_seed
        opponent = state.unit(team.opponent).position
        stats = _stats_for_state(state, engine)
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


@dataclass(frozen=True, slots=True)
class KiteBot:
    name: str = "kite"
    preferred_distance: int = 3

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: GameEngine,
        *,
        match_seed: int,
    ) -> Action:
        del match_seed
        opponent = state.unit(team.opponent).position
        stats = _stats_for_state(state, engine)
        candidates = _candidate_moves(state, team, engine)

        def score(item: tuple[tuple[Direction, ...], Position]) -> tuple[float, int, int, tuple[str, ...]]:
            path, destination = item
            distance = destination.manhattan_distance(opponent)
            attackable_penalty = 0 if distance <= stats.bow_range else 1
            return (
                attackable_penalty,
                abs(distance - self.preferred_distance),
                len(path),
                tuple(step.value for step in path),
            )

        path, destination = min(candidates, key=score)
        distance = destination.manhattan_distance(opponent)
        weapon = _weapon_for_distance(
            distance,
            knife_range=stats.knife_range,
            bow_range=stats.bow_range,
        )
        if weapon is Weapon.KNIFE and distance < self.preferred_distance:
            farther = [
                item
                for item in candidates
                if item[1].manhattan_distance(opponent) > distance
            ]
            if farther:
                path, destination = max(
                    farther,
                    key=lambda item: item[1].manhattan_distance(opponent),
                )
                distance = destination.manhattan_distance(opponent)
                weapon = _weapon_for_distance(
                    distance,
                    knife_range=stats.knife_range,
                    bow_range=stats.bow_range,
                )
        return Action(path, weapon)


@dataclass(frozen=True, slots=True)
class PassiveBot:
    name: str = "passive"

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: GameEngine,
        *,
        match_seed: int,
    ) -> Action:
        del state, team, engine, match_seed
        return Action()


@dataclass(frozen=True, slots=True)
class RandomBot:
    name: str = "random"

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: GameEngine,
        *,
        match_seed: int,
    ) -> Action:
        stats = _stats_for_state(state, engine)
        opponent = state.unit(team.opponent).position
        rng = random.Random(f"{match_seed}:{state.round_no}:{team.value}:{self.name}")
        candidates = _candidate_moves(state, team, engine)
        path, destination = rng.choice(candidates)
        distance = destination.manhattan_distance(opponent)

        legal_weapons: list[Weapon | None] = [None]
        if distance <= stats.knife_range:
            legal_weapons.append(Weapon.KNIFE)
        if distance <= stats.bow_range:
            legal_weapons.append(Weapon.BOW)

        return Action(path, rng.choice(legal_weapons))
