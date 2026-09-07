from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .engine import GameEngine
from .model import Action, Event, GameConfig, GameState, MatchResult, Team, UnitState, Weapon
from .rule_dsl import RuleAST
from .rule_runtime import (
    PublicRuleHistory,
    RuleEvaluator,
    RuleModifiers,
    initial_public_rule_histories,
    update_public_rule_histories,
)
from .rule_validator import RuleValidator


@dataclass(frozen=True, slots=True)
class RuleEffectiveStats:
    move_range: int
    knife_range: int
    bow_range: int
    knife_damage: int
    bow_damage: int
    bow_hit_multiplier: float
    bow_hit_floor: float
    cooldown_weapons: frozenset[Weapon]
    conflict_level: int
    hard_liveness: bool


@dataclass(frozen=True, slots=True)
class RuleRoundResolution:
    state: GameState
    events: tuple[Event, ...]
    histories: Mapping[Team, PublicRuleHistory]
    modifiers: Mapping[Team, RuleModifiers]


class RuleAwareGameEngine(GameEngine):
    """Isolated V0.1 integration of validated public rules with GameEngine semantics.

    The original GameEngine is intentionally left unchanged as the no-rule baseline.
    This class applies player modifiers per team, then system anti-stall minimums.
    """

    def __init__(
        self,
        config: GameConfig | None = None,
        *,
        evaluator: RuleEvaluator | None = None,
        validator: RuleValidator | None = None,
    ) -> None:
        super().__init__(config)
        self.evaluator = evaluator or RuleEvaluator()
        self.validator = validator or RuleValidator(self.config)

    def resolve_rule_round(
        self,
        state: GameState,
        actions: Mapping[Team, Action],
        *,
        rule: RuleAST | None,
        histories: Mapping[Team, PublicRuleHistory] | None = None,
        match_seed: int,
    ) -> RuleRoundResolution:
        if state.is_terminal:
            raise ValueError("Cannot resolve a terminal game state")

        histories = histories or initial_public_rule_histories()
        if rule is not None:
            self._require_valid_rule(rule)

        modifiers = self.evaluator.evaluate(rule, state, histories)
        stats = {
            team: self._effective_rule_stats(
                state.no_damage_streak,
                modifiers[team],
                hard_liveness_active=state.hard_liveness_active,
            )
            for team in (Team.RED, Team.BLUE)
        }

        events: list[Event] = []
        for team in (Team.RED, Team.BLUE):
            if modifiers[team] != RuleModifiers():
                events.append(
                    Event(
                        "RULE_MODIFIER_APPLIED",
                        actor=team,
                        details=self._modifier_details(modifiers[team]),
                    )
                )

        normalized_actions: dict[Team, Action] = {}
        for team in (Team.RED, Team.BLUE):
            action = actions.get(team, Action())
            move_path = self._validate_move_path(
                state.unit(team).position,
                action.move_path,
                stats[team].move_range,
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

        positions, movement_events = self._resolve_joint_movement(state, normalized_actions)
        events.extend(movement_events)

        moved_units = {
            team: UnitState(team, positions[team], state.unit(team).hp)
            for team in (Team.RED, Team.BLUE)
        }

        attack_events, damages = self._resolve_rule_attacks(
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
        hard = stats[Team.RED].hard_liveness or stats[Team.BLUE].hard_liveness
        next_hard_liveness = state.hard_liveness_active or hard

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
        next_histories = update_public_rule_histories(
            state,
            next_state,
            events,
            histories,
        )
        return RuleRoundResolution(
            state=next_state,
            events=tuple(events),
            histories=next_histories,
            modifiers=modifiers,
        )

    def effective_stats_for_team(
        self,
        state: GameState,
        team: Team,
        *,
        rule: RuleAST | None,
        histories: Mapping[Team, PublicRuleHistory] | None = None,
    ) -> RuleEffectiveStats:
        """Public query for bots/planners; uses the same Round-Start semantics as resolution."""
        histories = histories or initial_public_rule_histories()
        if rule is not None:
            self._require_valid_rule(rule)
        modifiers = self.evaluator.evaluate(rule, state, histories)
        return self._effective_rule_stats(
            state.no_damage_streak,
            modifiers[team],
            hard_liveness_active=state.hard_liveness_active,
        )

    def _effective_rule_stats(
        self,
        no_damage_streak: int,
        modifier: RuleModifiers,
        *,
        hard_liveness_active: bool,
    ) -> RuleEffectiveStats:
        level = self.conflict_level(no_damage_streak)
        hard = hard_liveness_active or level == 4
        if hard:
            level = 4

        # Base -> player rule -> ordinary safety clamp.
        move_range = _clamp(self.config.base_move_range + modifier.move_range_add, 1, 2)
        knife_range = _clamp(self.config.base_knife_range + modifier.knife_range_add, 1, 2)
        bow_range = _clamp(self.config.base_bow_range + modifier.bow_range_add, 1, 4)
        knife_damage = _clamp(self.config.knife_damage + modifier.knife_damage_add, 1, 3)
        bow_damage = _clamp(self.config.bow_damage + modifier.bow_damage_add, 1, 2)

        # System anti-stall is a minimum/override, not an extra additive bonus.
        bow_hit_floor = 0.0
        if level >= 1:
            knife_range = max(knife_range, self.config.base_knife_range + 1)
            bow_range = max(bow_range, self.config.base_bow_range + 1)
        if level >= 2:
            bow_range = max(bow_range, self.config.base_bow_range + 2)
            bow_hit_floor = max(bow_hit_floor, 0.25)
        if level >= 3:
            bow_range = max(bow_range, self.config.base_bow_range + 3)
            bow_hit_floor = max(bow_hit_floor, 0.50)
        if hard:
            bow_range = self.config.max_manhattan_distance
            bow_hit_floor = 1.0
            bow_damage = max(1, bow_damage)

        return RuleEffectiveStats(
            move_range=move_range,
            knife_range=knife_range,
            bow_range=bow_range,
            knife_damage=knife_damage,
            bow_damage=bow_damage,
            bow_hit_multiplier=modifier.bow_hit_multiplier,
            bow_hit_floor=bow_hit_floor,
            cooldown_weapons=modifier.cooldown_weapons,
            conflict_level=level,
            hard_liveness=hard,
        )

    def _resolve_rule_attacks(
        self,
        *,
        round_no: int,
        units: Mapping[Team, UnitState],
        actions: Mapping[Team, Action],
        stats: Mapping[Team, RuleEffectiveStats],
        match_seed: int,
    ) -> tuple[list[Event], dict[Team, int]]:
        events: list[Event] = []
        incoming_damage = {Team.RED: 0, Team.BLUE: 0}
        chosen_weapons: dict[Team, tuple[Weapon | None, bool]] = {}

        for team in (Team.RED, Team.BLUE):
            team_stats = stats[team]
            weapon = actions[team].attack
            legal = self._is_rule_attack_legal(team, weapon, units, team_stats)
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

            # Cooldown and other player constraints apply to ordinary attacks.
            # Hard Liveness only bypasses them through the system-generated FORCED_BOW.
            if team_stats.hard_liveness and weapon is None:
                weapon = Weapon.BOW
                forced = True
                events.append(Event("FORCED_BOW", actor=team))

            chosen_weapons[team] = (weapon, forced)

        for team in (Team.RED, Team.BLUE):
            weapon, forced = chosen_weapons[team]
            if weapon is None:
                continue

            team_stats = stats[team]
            opponent = team.opponent
            distance = units[team].position.manhattan_distance(units[opponent].position)

            if weapon is Weapon.KNIFE:
                probability = 1.0
                damage = team_stats.knife_damage
                roll = 0.0
                hit = True
            else:
                if forced:
                    probability = 1.0
                else:
                    player_probability = (0.5 ** (distance - 1)) * team_stats.bow_hit_multiplier
                    normal_probability = _clamp_float(player_probability, 0.05, 1.0)
                    probability = max(normal_probability, team_stats.bow_hit_floor)
                    probability = _clamp_float(probability, 0.0, 1.0)
                damage = max(1, team_stats.bow_damage) if team_stats.hard_liveness else team_stats.bow_damage
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
    def _is_rule_attack_legal(
        team: Team,
        weapon: Weapon | None,
        units: Mapping[Team, UnitState],
        stats: RuleEffectiveStats,
    ) -> bool:
        if weapon is None or not isinstance(weapon, Weapon):
            return False

        if weapon in stats.cooldown_weapons:
            return False

        distance = units[team].position.manhattan_distance(units[team.opponent].position)
        if weapon is Weapon.KNIFE:
            return distance <= stats.knife_range
        if weapon is Weapon.BOW:
            return distance <= stats.bow_range
        return False

    def _require_valid_rule(self, rule: RuleAST) -> None:
        candidate = _rule_to_candidate(rule)
        result = self.validator.validate(candidate)
        if not result.accepted:
            codes = ", ".join(issue.code for issue in result.issues)
            raise ValueError(f"RuleAwareGameEngine requires a validated V0.1 rule: {codes}")

    @staticmethod
    def _modifier_details(modifier: RuleModifiers) -> dict[str, object]:
        return {
            "move_range_add": modifier.move_range_add,
            "knife_range_add": modifier.knife_range_add,
            "bow_range_add": modifier.bow_range_add,
            "knife_damage_add": modifier.knife_damage_add,
            "bow_damage_add": modifier.bow_damage_add,
            "bow_hit_multiplier": modifier.bow_hit_multiplier,
            "cooldown_weapons": tuple(sorted(weapon.value for weapon in modifier.cooldown_weapons)),
        }


def _rule_to_candidate(rule: RuleAST) -> dict[str, object]:
    conditions: list[dict[str, object]] = []
    for condition in rule.conditions:
        item: dict[str, object] = {"type": condition.type.value}
        if condition.value is not None:
            item["value"] = condition.value
        if condition.weapon is not None:
            item["weapon"] = condition.weapon.value
        conditions.append(item)

    effect: dict[str, object] = {"type": rule.effect.type.value}
    if rule.effect.delta is not None:
        effect["delta"] = rule.effect.delta
    if rule.effect.multiplier is not None:
        effect["multiplier"] = rule.effect.multiplier
    if rule.effect.weapon is not None:
        effect["weapon"] = rule.effect.weapon.value
    if rule.effect.rounds is not None:
        effect["rounds"] = rule.effect.rounds

    return {
        "version": rule.version,
        "target": rule.target.value,
        "conditions": conditions,
        "effect": effect,
        "duration": rule.duration.value,
    }


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
