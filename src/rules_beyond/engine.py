from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Mapping

from .model import (
    Action,
    Event,
    GameConfig,
    GameState,
    MatchResult,
    Position,
    Team,
    UnitState,
    Weapon,
)


@dataclass(frozen=True, slots=True)
class EffectiveStats:
    move_range: int
    knife_range: int
    bow_range: int
    knife_damage: int
    bow_damage: int
    bow_hit_floor: float
    conflict_level: int
    hard_liveness: bool


@dataclass(frozen=True, slots=True)
class RoundResolution:
    state: GameState
    events: tuple[Event, ...]


class GameEngine:
    """Authoritative V0.1 deterministic state resolver.

    This class deliberately contains no AI/planning logic. Given the same state,
    actions and match seed, it produces the same result.
    """

    def __init__(self, config: GameConfig | None = None) -> None:
        self.config = config or GameConfig()

    def resolve_round(
        self,
        state: GameState,
        actions: Mapping[Team, Action],
        *,
        match_seed: int,
    ) -> RoundResolution:
        if state.is_terminal:
            raise ValueError("Cannot resolve a terminal game state")

        events: list[Event] = []
        late_game_hard = state.round_no >= self.config.late_game_hard_round
        stats = self._effective_stats(
            state.no_damage_streak,
            hard_liveness_active=state.hard_liveness_active or late_game_hard,
        )

        normalized_actions: dict[Team, Action] = {}
        for team in (Team.RED, Team.BLUE):
            action = actions.get(team, Action())
            move_path = self._validate_move_path(
                state.unit(team).position,
                action.move_path,
                stats.move_range,
            )
            if move_path is None:
                events.append(
                    Event(
                        "INVALID_MOVE_PATH",
                        actor=team,
                        details={"submitted_path": tuple(step.value for step in action.move_path)},
                    )
                )
                normalized_actions[team] = Action((), action.attack)
            else:
                normalized_actions[team] = Action(move_path, action.attack)

        positions, movement_events = self._resolve_joint_movement(
            state,
            normalized_actions,
        )
        events.extend(movement_events)

        moved_units = {
            team: UnitState(
                team=team,
                position=positions[team],
                hp=state.unit(team).hp,
            )
            for team in (Team.RED, Team.BLUE)
        }

        attack_events, damages = self._resolve_attacks(
            round_no=state.round_no,
            units=moved_units,
            actions=normalized_actions,
            stats=stats,
            match_seed=match_seed,
        )
        events.extend(attack_events)

        total_applied_damage = 0
        final_units: dict[Team, UnitState] = {}
        for team in (Team.RED, Team.BLUE):
            incoming = damages[team]
            previous = moved_units[team]
            applied = min(max(previous.hp, 0), incoming)
            total_applied_damage += applied
            final_hp = max(0, previous.hp - incoming)
            final_units[team] = UnitState(team, previous.position, final_hp)
            if applied > 0:
                events.append(
                    Event(
                        "DAMAGE_APPLIED",
                        actor=team.opponent,
                        details={
                            "target": team.value,
                            "amount": applied,
                            "hp_before": previous.hp,
                            "hp_after": final_hp,
                        },
                    )
                )

        result = self._terminal_result(final_units)
        next_streak = 0 if total_applied_damage > 0 else state.no_damage_streak + 1
        next_hard_liveness = state.hard_liveness_active or stats.hard_liveness

        if result is None and state.round_no >= self.config.max_rounds:
            result = MatchResult.TIMEOUT
            events.append(Event("MATCH_TIMEOUT", details={"round": state.round_no}))

        if result is not None:
            events.append(Event("MATCH_TERMINAL", details={"result": result.value}))

        next_state = GameState(
            round_no=state.round_no if result is not None else state.round_no + 1,
            units=final_units,
            no_damage_streak=next_streak,
            hard_liveness_active=next_hard_liveness,
            result=result,
        )
        return RoundResolution(next_state, tuple(events))

    def _effective_stats(
        self,
        no_damage_streak: int,
        *,
        hard_liveness_active: bool = False,
    ) -> EffectiveStats:
        level = self.conflict_level(no_damage_streak)
        hard = hard_liveness_active or level == 4
        if hard:
            level = 4

        knife_range = self.config.base_knife_range
        bow_range = self.config.base_bow_range
        bow_hit_floor = 0.0

        if level >= 1:
            knife_range += 1
            bow_range += 1
        if level >= 2:
            bow_range = self.config.base_bow_range + 2
            bow_hit_floor = 0.25
        if level >= 3:
            bow_range = self.config.base_bow_range + 3
            bow_hit_floor = 0.50
        if hard:
            bow_range = self.config.max_manhattan_distance
            bow_hit_floor = 1.0

        return EffectiveStats(
            move_range=self.config.base_move_range,
            knife_range=knife_range,
            bow_range=bow_range,
            knife_damage=self.config.knife_damage,
            bow_damage=max(1, self.config.bow_damage),
            bow_hit_floor=bow_hit_floor,
            conflict_level=level,
            hard_liveness=hard,
        )

    @staticmethod
    def conflict_level(no_damage_streak: int) -> int:
        if no_damage_streak >= 12:
            return 4
        if no_damage_streak >= 9:
            return 3
        if no_damage_streak >= 6:
            return 2
        if no_damage_streak >= 3:
            return 1
        return 0

    def _validate_move_path(
        self,
        start: Position,
        path: tuple,
        move_range: int,
    ) -> tuple | None:
        if len(path) > move_range:
            return None

        current = start
        for step in path:
            try:
                current = current.moved(step)
            except (TypeError, ValueError):
                return None
            if not self.config.contains(current):
                return None
        return tuple(path)

    def _resolve_joint_movement(
        self,
        state: GameState,
        actions: Mapping[Team, Action],
    ) -> tuple[dict[Team, Position], list[Event]]:
        positions = {
            Team.RED: state.unit(Team.RED).position,
            Team.BLUE: state.unit(Team.BLUE).position,
        }
        stopped = {Team.RED: False, Team.BLUE: False}
        events: list[Event] = []
        steps = max(
            len(actions[Team.RED].move_path),
            len(actions[Team.BLUE].move_path),
        )

        for index in range(steps):
            current_red = positions[Team.RED]
            current_blue = positions[Team.BLUE]

            red_dest = self._movement_intent(
                current_red,
                actions[Team.RED],
                index,
                stopped[Team.RED],
            )
            blue_dest = self._movement_intent(
                current_blue,
                actions[Team.BLUE],
                index,
                stopped[Team.BLUE],
            )

            if red_dest == blue_dest:
                stopped[Team.RED] = True
                stopped[Team.BLUE] = True
                events.append(
                    Event(
                        "SAME_DESTINATION_CONFLICT",
                        details={
                            "substep": index + 1,
                            "destination": (red_dest.row, red_dest.col),
                        },
                    )
                )
                continue

            is_swap = red_dest == current_blue and blue_dest == current_red
            if is_swap:
                stopped[Team.RED] = True
                stopped[Team.BLUE] = True
                events.append(
                    Event(
                        "SWAP_CONFLICT",
                        details={"substep": index + 1},
                    )
                )
                continue

            positions[Team.RED] = red_dest
            positions[Team.BLUE] = blue_dest

        return positions, events

    @staticmethod
    def _movement_intent(
        current: Position,
        action: Action,
        index: int,
        stopped: bool,
    ) -> Position:
        if stopped or index >= len(action.move_path):
            return current
        return current.moved(action.move_path[index])

    def _resolve_attacks(
        self,
        *,
        round_no: int,
        units: Mapping[Team, UnitState],
        actions: Mapping[Team, Action],
        stats: EffectiveStats,
        match_seed: int,
    ) -> tuple[list[Event], dict[Team, int]]:
        events: list[Event] = []
        incoming_damage = {Team.RED: 0, Team.BLUE: 0}

        chosen_weapons: dict[Team, tuple[Weapon | None, bool]] = {}
        for team in (Team.RED, Team.BLUE):
            weapon = actions[team].attack
            legal = self._is_attack_legal(team, weapon, units, stats)
            forced = False

            if not legal:
                if weapon is not None:
                    events.append(
                        Event(
                            "INVALID_ATTACK",
                            actor=team,
                            details={"weapon": getattr(weapon, "value", str(weapon))},
                        )
                    )
                weapon = None

            if stats.hard_liveness and weapon is None:
                weapon = Weapon.BOW
                forced = True
                events.append(Event("FORCED_BOW", actor=team))

            chosen_weapons[team] = (weapon, forced)

        for team in (Team.RED, Team.BLUE):
            weapon, forced = chosen_weapons[team]
            if weapon is None:
                continue

            opponent = team.opponent
            distance = units[team].position.manhattan_distance(units[opponent].position)

            if weapon is Weapon.KNIFE:
                probability = 1.0
                damage = stats.knife_damage
                roll = 0.0
                hit = True
            else:
                probability = 1.0 if forced else max(
                    0.5 ** (distance - 1),
                    stats.bow_hit_floor,
                )
                probability = min(1.0, probability)
                damage = max(1, stats.bow_damage) if stats.hard_liveness else stats.bow_damage
                roll = self._deterministic_roll(
                    match_seed=match_seed,
                    round_no=round_no,
                    actor=team,
                    weapon=weapon,
                )
                hit = roll < probability

            events.append(
                Event(
                    "ATTACK_RESOLVED",
                    actor=team,
                    details={
                        "weapon": weapon.value,
                        "distance": distance,
                        "probability": probability,
                        "roll": roll,
                        "hit": hit,
                        "forced": forced,
                    },
                )
            )

            if hit:
                incoming_damage[opponent] += damage

        return events, incoming_damage

    @staticmethod
    def _is_attack_legal(
        team: Team,
        weapon: Weapon | None,
        units: Mapping[Team, UnitState],
        stats: EffectiveStats,
    ) -> bool:
        if weapon is None:
            return False
        if not isinstance(weapon, Weapon):
            return False

        distance = units[team].position.manhattan_distance(units[team.opponent].position)
        if weapon is Weapon.KNIFE:
            return distance <= stats.knife_range
        if weapon is Weapon.BOW:
            return distance <= stats.bow_range
        return False

    @staticmethod
    def _terminal_result(units: Mapping[Team, UnitState]) -> MatchResult | None:
        red_dead = units[Team.RED].hp <= 0
        blue_dead = units[Team.BLUE].hp <= 0
        if red_dead and blue_dead:
            return MatchResult.DRAW_MUTUAL_DEATH
        if blue_dead:
            return MatchResult.RED_WIN
        if red_dead:
            return MatchResult.BLUE_WIN
        return None

    @staticmethod
    def _deterministic_roll(
        *,
        match_seed: int,
        round_no: int,
        actor: Team,
        weapon: Weapon,
    ) -> float:
        payload = f"{match_seed}:{round_no}:{actor.value}:{weapon.value}:0".encode("utf-8")
        digest = hashlib.sha256(payload).digest()
        value = int.from_bytes(digest[:8], "big", signed=False)
        return value / 2**64
