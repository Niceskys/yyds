from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class Team(str, Enum):
    RED = "RED"
    BLUE = "BLUE"

    @property
    def opponent(self) -> "Team":
        return Team.BLUE if self is Team.RED else Team.RED


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class Weapon(str, Enum):
    KNIFE = "KNIFE"
    BOW = "BOW"


class MatchResult(str, Enum):
    RED_WIN = "RED_WIN"
    BLUE_WIN = "BLUE_WIN"
    DRAW_MUTUAL_DEATH = "DRAW_MUTUAL_DEATH"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True, slots=True)
class Position:
    row: int
    col: int

    def moved(self, direction: Direction) -> "Position":
        if direction is Direction.UP:
            return Position(self.row - 1, self.col)
        if direction is Direction.DOWN:
            return Position(self.row + 1, self.col)
        if direction is Direction.LEFT:
            return Position(self.row, self.col - 1)
        if direction is Direction.RIGHT:
            return Position(self.row, self.col + 1)
        raise ValueError(f"Unsupported direction: {direction!r}")

    def manhattan_distance(self, other: "Position") -> int:
        return abs(self.row - other.row) + abs(self.col - other.col)


@dataclass(frozen=True, slots=True)
class UnitState:
    team: Team
    position: Position
    hp: int


@dataclass(frozen=True, slots=True)
class Action:
    move_path: tuple[Direction, ...] = ()
    attack: Weapon | None = None


@dataclass(frozen=True, slots=True)
class GameConfig:
    rows: int = 5
    cols: int = 5
    initial_hp: int = 4
    max_rounds: int = 30
    late_game_hard_round: int = 24
    base_move_range: int = 1
    base_knife_range: int = 1
    base_bow_range: int = 3
    knife_damage: int = 2
    bow_damage: int = 1

    @property
    def max_manhattan_distance(self) -> int:
        return (self.rows - 1) + (self.cols - 1)

    def contains(self, position: Position) -> bool:
        return 1 <= position.row <= self.rows and 1 <= position.col <= self.cols


@dataclass(frozen=True, slots=True)
class GameState:
    round_no: int
    units: Mapping[Team, UnitState]
    no_damage_streak: int = 0
    hard_liveness_active: bool = False
    result: MatchResult | None = None

    def unit(self, team: Team) -> UnitState:
        return self.units[team]

    @property
    def is_terminal(self) -> bool:
        return self.result is not None


@dataclass(frozen=True, slots=True)
class Event:
    kind: str
    actor: Team | None = None
    details: Mapping[str, object] = field(default_factory=dict)


def initial_state(config: GameConfig | None = None) -> GameState:
    config = config or GameConfig()
    return GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(3, 1), config.initial_hp),
            Team.BLUE: UnitState(Team.BLUE, Position(3, config.cols), config.initial_hp),
        },
        no_damage_streak=0,
        hard_liveness_active=False,
        result=None,
    )


def terminal_utility(
    result: MatchResult,
    perspective: Team,
    *,
    terminal_round: int,
    own_hp: int,
) -> tuple[float, float, float, float, float]:
    """Return the V0.1 frozen lexicographic terminal utility vector.

    Tuple order:
      (P_WIN, P_DRAW, -P_TIMEOUT, -E_WIN_ROUND, E_OWN_HP)

    For a deterministic terminal state, probabilities are 0/1. Non-win states use
    0 for the win-round component because E_WIN_ROUND is undefined when P_WIN=0.
    """

    is_win = (
        result is MatchResult.RED_WIN and perspective is Team.RED
    ) or (
        result is MatchResult.BLUE_WIN and perspective is Team.BLUE
    )

    if is_win:
        return (1.0, 0.0, 0.0, float(-terminal_round), float(own_hp))
    if result is MatchResult.DRAW_MUTUAL_DEATH:
        return (0.0, 1.0, 0.0, 0.0, float(own_hp))
    if result is MatchResult.TIMEOUT:
        return (0.0, 0.0, -1.0, 0.0, float(own_hp))
    return (0.0, 0.0, 0.0, 0.0, float(own_hp))
