from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RuleTarget(str, Enum):
    ALL_UNITS = "ALL_UNITS"


class RuleDuration(str, Enum):
    UNTIL_REPLACED = "UNTIL_REPLACED"


class RuleConditionType(str, Enum):
    SELF_HP_LTE = "SELF_HP_LTE"
    SELF_HP_GTE = "SELF_HP_GTE"
    SELF_HP_LT_OPPONENT = "SELF_HP_LT_OPPONENT"
    SELF_HP_GT_OPPONENT = "SELF_HP_GT_OPPONENT"
    DISTANCE_LTE = "DISTANCE_LTE"
    DISTANCE_GTE = "DISTANCE_GTE"
    ROUND_GTE = "ROUND_GTE"
    DID_NOT_MOVE_LAST_ROUND = "DID_NOT_MOVE_LAST_ROUND"
    LAST_ATTACK_WEAPON_IS = "LAST_ATTACK_WEAPON_IS"
    CONSECUTIVE_BOW_MISS_GTE = "CONSECUTIVE_BOW_MISS_GTE"
    CONSECUTIVE_SAME_WEAPON_USE_GTE = "CONSECUTIVE_SAME_WEAPON_USE_GTE"


class RuleEffectType(str, Enum):
    MOVE_RANGE_ADD = "MOVE_RANGE_ADD"
    KNIFE_RANGE_ADD = "KNIFE_RANGE_ADD"
    BOW_RANGE_ADD = "BOW_RANGE_ADD"
    KNIFE_DAMAGE_ADD = "KNIFE_DAMAGE_ADD"
    BOW_DAMAGE_ADD = "BOW_DAMAGE_ADD"
    BOW_HIT_MULTIPLIER = "BOW_HIT_MULTIPLIER"
    WEAPON_COOLDOWN = "WEAPON_COOLDOWN"


class RuleWeapon(str, Enum):
    KNIFE = "KNIFE"
    BOW = "BOW"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class RuleCondition:
    type: RuleConditionType
    value: int | None = None
    weapon: RuleWeapon | None = None


@dataclass(frozen=True, slots=True)
class RuleEffect:
    type: RuleEffectType
    delta: int | None = None
    multiplier: float | None = None
    weapon: RuleWeapon | None = None
    rounds: int | None = None


@dataclass(frozen=True, slots=True)
class RuleAST:
    version: str
    target: RuleTarget
    conditions: tuple[RuleCondition, ...]
    effect: RuleEffect
    duration: RuleDuration
