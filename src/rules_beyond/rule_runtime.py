from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .model import Event, GameState, Team, Weapon
from .rule_dsl import (
    RuleAST,
    RuleCondition,
    RuleConditionType,
    RuleEffectType,
    RuleWeapon,
)


@dataclass(frozen=True, slots=True)
class PublicRuleHistory:
    has_previous_round: bool = False
    moved_last_round: bool = False
    last_attack_weapon: RuleWeapon = RuleWeapon.NONE
    consecutive_bow_miss: int = 0
    consecutive_same_weapon_use: int = 0


@dataclass(frozen=True, slots=True)
class RuleModifiers:
    move_range_add: int = 0
    knife_range_add: int = 0
    bow_range_add: int = 0
    knife_damage_add: int = 0
    bow_damage_add: int = 0
    bow_hit_multiplier: float = 1.0
    cooldown_weapons: frozenset[Weapon] = frozenset()


class RuleEvaluator:
    """Pure V0.1 Round-Start RuleAST evaluator.

    It reads public state/history and returns per-team modifiers. It does not mutate
    GameState and does not apply anti-stall; Engine integration is a later layer.
    """

    def evaluate(
        self,
        rule: RuleAST | None,
        state: GameState,
        histories: Mapping[Team, PublicRuleHistory],
    ) -> dict[Team, RuleModifiers]:
        if rule is None:
            return {
                Team.RED: RuleModifiers(),
                Team.BLUE: RuleModifiers(),
            }

        result: dict[Team, RuleModifiers] = {}
        for team in (Team.RED, Team.BLUE):
            history = histories.get(team, PublicRuleHistory())
            active = all(
                self._condition_matches(condition, state, team, history)
                for condition in rule.conditions
            )
            result[team] = self._modifier_for(rule) if active else RuleModifiers()
        return result

    def _condition_matches(
        self,
        condition: RuleCondition,
        state: GameState,
        team: Team,
        history: PublicRuleHistory,
    ) -> bool:
        me = state.unit(team)
        opponent = state.unit(team.opponent)
        distance = me.position.manhattan_distance(opponent.position)
        condition_type = condition.type

        if condition_type is RuleConditionType.SELF_HP_LTE:
            assert condition.value is not None
            return me.hp <= condition.value
        if condition_type is RuleConditionType.SELF_HP_GTE:
            assert condition.value is not None
            return me.hp >= condition.value
        if condition_type is RuleConditionType.SELF_HP_LT_OPPONENT:
            return me.hp < opponent.hp
        if condition_type is RuleConditionType.SELF_HP_GT_OPPONENT:
            return me.hp > opponent.hp
        if condition_type is RuleConditionType.DISTANCE_LTE:
            assert condition.value is not None
            return distance <= condition.value
        if condition_type is RuleConditionType.DISTANCE_GTE:
            assert condition.value is not None
            return distance >= condition.value
        if condition_type is RuleConditionType.ROUND_GTE:
            assert condition.value is not None
            return state.round_no >= condition.value

        # No previous round exists at Round 1. Every history predicate must be
        # false regardless of the default field values.
        if not history.has_previous_round:
            return False

        if condition_type is RuleConditionType.DID_NOT_MOVE_LAST_ROUND:
            return not history.moved_last_round
        if condition_type is RuleConditionType.LAST_ATTACK_WEAPON_IS:
            assert condition.weapon is not None
            return history.last_attack_weapon is condition.weapon
        if condition_type is RuleConditionType.CONSECUTIVE_BOW_MISS_GTE:
            assert condition.value is not None
            return history.consecutive_bow_miss >= condition.value
        if condition_type is RuleConditionType.CONSECUTIVE_SAME_WEAPON_USE_GTE:
            assert condition.value is not None
            return history.consecutive_same_weapon_use >= condition.value

        raise ValueError(f"Unsupported validated condition: {condition_type}")

    @staticmethod
    def _modifier_for(rule: RuleAST) -> RuleModifiers:
        effect = rule.effect
        if effect.type is RuleEffectType.MOVE_RANGE_ADD:
            assert effect.delta is not None
            return RuleModifiers(move_range_add=effect.delta)
        if effect.type is RuleEffectType.KNIFE_RANGE_ADD:
            assert effect.delta is not None
            return RuleModifiers(knife_range_add=effect.delta)
        if effect.type is RuleEffectType.BOW_RANGE_ADD:
            assert effect.delta is not None
            return RuleModifiers(bow_range_add=effect.delta)
        if effect.type is RuleEffectType.KNIFE_DAMAGE_ADD:
            assert effect.delta is not None
            return RuleModifiers(knife_damage_add=effect.delta)
        if effect.type is RuleEffectType.BOW_DAMAGE_ADD:
            assert effect.delta is not None
            return RuleModifiers(bow_damage_add=effect.delta)
        if effect.type is RuleEffectType.BOW_HIT_MULTIPLIER:
            assert effect.multiplier is not None
            return RuleModifiers(bow_hit_multiplier=effect.multiplier)
        if effect.type is RuleEffectType.WEAPON_COOLDOWN:
            assert effect.weapon is not None
            if effect.weapon is RuleWeapon.KNIFE:
                return RuleModifiers(cooldown_weapons=frozenset({Weapon.KNIFE}))
            if effect.weapon is RuleWeapon.BOW:
                return RuleModifiers(cooldown_weapons=frozenset({Weapon.BOW}))
            raise ValueError("Validated cooldown cannot target NONE")
        raise ValueError(f"Unsupported validated effect: {effect.type}")


def initial_public_rule_histories() -> dict[Team, PublicRuleHistory]:
    return {
        Team.RED: PublicRuleHistory(),
        Team.BLUE: PublicRuleHistory(),
    }


def update_public_rule_histories(
    before_state: GameState,
    after_state: GameState,
    events: tuple[Event, ...] | list[Event],
    previous: Mapping[Team, PublicRuleHistory],
) -> dict[Team, PublicRuleHistory]:
    """Build next Round-Start public history from resolved Engine facts only."""

    actual_weapon: dict[Team, RuleWeapon] = {
        Team.RED: RuleWeapon.NONE,
        Team.BLUE: RuleWeapon.NONE,
    }
    bow_missed: dict[Team, bool] = {Team.RED: False, Team.BLUE: False}

    for event in events:
        if event.kind != "ATTACK_RESOLVED" or event.actor is None:
            continue
        weapon_raw = event.details.get("weapon")
        if weapon_raw == Weapon.KNIFE.value:
            actual_weapon[event.actor] = RuleWeapon.KNIFE
        elif weapon_raw == Weapon.BOW.value:
            actual_weapon[event.actor] = RuleWeapon.BOW
            bow_missed[event.actor] = event.details.get("hit") is False

    result: dict[Team, PublicRuleHistory] = {}
    for team in (Team.RED, Team.BLUE):
        old = previous.get(team, PublicRuleHistory())
        weapon = actual_weapon[team]
        moved = before_state.unit(team).position != after_state.unit(team).position

        if bow_missed[team]:
            bow_miss_streak = old.consecutive_bow_miss + 1
        else:
            bow_miss_streak = 0

        if weapon is RuleWeapon.NONE:
            same_weapon_streak = 0
        elif old.has_previous_round and old.last_attack_weapon is weapon:
            same_weapon_streak = old.consecutive_same_weapon_use + 1
        else:
            same_weapon_streak = 1

        result[team] = PublicRuleHistory(
            has_previous_round=True,
            moved_last_round=moved,
            last_attack_weapon=weapon,
            consecutive_bow_miss=bow_miss_streak,
            consecutive_same_weapon_use=same_weapon_streak,
        )

    return result
