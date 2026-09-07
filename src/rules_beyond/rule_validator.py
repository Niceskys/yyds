from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .model import GameConfig
from .rule_dsl import (
    RuleAST,
    RuleCondition,
    RuleConditionType,
    RuleDuration,
    RuleEffect,
    RuleEffectType,
    RuleTarget,
    RuleWeapon,
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    accepted: bool
    rule: RuleAST | None
    issues: tuple[ValidationIssue, ...]


class RuleValidator:
    """Deterministic validator for the frozen V0.1 Rule DSL.

    The validator accepts untrusted JSON-like mappings. It does not call an LLM,
    does not mutate GameState, and only accepts capabilities explicitly listed by
    the P0 rule freeze.
    """

    _ROOT_KEYS = {"version", "target", "conditions", "effect", "duration"}
    _COND_VALUE_TYPES = {
        RuleConditionType.SELF_HP_LTE,
        RuleConditionType.SELF_HP_GTE,
        RuleConditionType.DISTANCE_LTE,
        RuleConditionType.DISTANCE_GTE,
        RuleConditionType.ROUND_GTE,
        RuleConditionType.CONSECUTIVE_BOW_MISS_GTE,
        RuleConditionType.CONSECUTIVE_SAME_WEAPON_USE_GTE,
    }
    _COND_NO_ARG_TYPES = {
        RuleConditionType.SELF_HP_LT_OPPONENT,
        RuleConditionType.SELF_HP_GT_OPPONENT,
        RuleConditionType.DID_NOT_MOVE_LAST_ROUND,
    }
    _ADD_EFFECTS = {
        RuleEffectType.MOVE_RANGE_ADD,
        RuleEffectType.KNIFE_RANGE_ADD,
        RuleEffectType.BOW_RANGE_ADD,
        RuleEffectType.KNIFE_DAMAGE_ADD,
        RuleEffectType.BOW_DAMAGE_ADD,
    }

    def __init__(self, config: GameConfig | None = None) -> None:
        self.config = config or GameConfig()

    def validate(self, candidate: Mapping[str, Any] | Any) -> ValidationResult:
        issues: list[ValidationIssue] = []

        if not isinstance(candidate, Mapping):
            return self._reject("SCHEMA_INVALID", "$", "Rule candidate must be an object")

        extra_root = set(candidate) - self._ROOT_KEYS
        missing_root = self._ROOT_KEYS - set(candidate)
        for key in sorted(extra_root):
            issues.append(self._issue("SCHEMA_UNKNOWN_FIELD", f"$.{key}", "Unknown root field"))
        for key in sorted(missing_root):
            issues.append(self._issue("SCHEMA_MISSING_FIELD", f"$.{key}", "Required root field is missing"))
        if issues:
            return ValidationResult(False, None, tuple(issues))

        if candidate["version"] != "v0.1":
            issues.append(self._issue("UNSUPPORTED_VERSION", "$.version", "Only version v0.1 is supported"))
        if candidate["target"] != RuleTarget.ALL_UNITS.value:
            issues.append(self._issue("FACTION_NEUTRALITY", "$.target", "target must be ALL_UNITS"))
        if candidate["duration"] != RuleDuration.UNTIL_REPLACED.value:
            issues.append(self._issue("INVALID_DURATION", "$.duration", "duration must be UNTIL_REPLACED"))

        conditions_raw = candidate["conditions"]
        if not isinstance(conditions_raw, list):
            issues.append(self._issue("SCHEMA_INVALID", "$.conditions", "conditions must be an array"))
            conditions_raw = []
        elif len(conditions_raw) > 2:
            issues.append(self._issue("CONDITION_COUNT", "$.conditions", "V0.1 allows at most two AND conditions"))

        parsed_conditions: list[RuleCondition] = []
        for index, raw in enumerate(conditions_raw[:2]):
            condition, condition_issues = self._parse_condition(raw, index)
            issues.extend(condition_issues)
            if condition is not None:
                parsed_conditions.append(condition)

        effect, effect_issues = self._parse_effect(candidate["effect"])
        issues.extend(effect_issues)

        if issues or effect is None:
            return ValidationResult(False, None, tuple(issues))

        if self._conditions_directly_contradict(tuple(parsed_conditions)):
            issues.append(
                self._issue(
                    "NO_EFFECT_RULE",
                    "$.conditions",
                    "The condition set is directly contradictory and can never activate",
                )
            )

        effect_issue = self._validate_effect_bounds(effect)
        if effect_issue is not None:
            issues.append(effect_issue)

        if issues:
            return ValidationResult(False, None, tuple(issues))

        rule = RuleAST(
            version="v0.1",
            target=RuleTarget.ALL_UNITS,
            conditions=tuple(parsed_conditions),
            effect=effect,
            duration=RuleDuration.UNTIL_REPLACED,
        )
        return ValidationResult(True, rule, ())

    def _parse_condition(
        self,
        raw: Any,
        index: int,
    ) -> tuple[RuleCondition | None, list[ValidationIssue]]:
        path = f"$.conditions[{index}]"
        issues: list[ValidationIssue] = []
        if not isinstance(raw, Mapping):
            return None, [self._issue("SCHEMA_INVALID", path, "Condition must be an object")]

        raw_type = raw.get("type")
        try:
            condition_type = RuleConditionType(raw_type)
        except (ValueError, TypeError):
            return None, [self._issue("ALLOWED_CONDITION", f"{path}.type", "Unsupported condition type")]

        if condition_type in self._COND_VALUE_TYPES:
            allowed = {"type", "value"}
            self._check_exact_keys(raw, allowed, path, issues)
            value = raw.get("value")
            if not self._is_int(value):
                issues.append(self._issue("ENUM_TYPE", f"{path}.value", "value must be an integer"))
                return None, issues
            self._validate_condition_value(condition_type, value, f"{path}.value", issues)
            return RuleCondition(condition_type, value=value), issues

        if condition_type is RuleConditionType.LAST_ATTACK_WEAPON_IS:
            allowed = {"type", "weapon"}
            self._check_exact_keys(raw, allowed, path, issues)
            try:
                weapon = RuleWeapon(raw.get("weapon"))
            except (ValueError, TypeError):
                issues.append(
                    self._issue(
                        "ENUM_TYPE",
                        f"{path}.weapon",
                        "weapon must be KNIFE, BOW, or NONE",
                    )
                )
                return None, issues
            return RuleCondition(condition_type, weapon=weapon), issues

        if condition_type in self._COND_NO_ARG_TYPES:
            allowed = {"type"}
            self._check_exact_keys(raw, allowed, path, issues)
            return RuleCondition(condition_type), issues

        return None, [self._issue("ALLOWED_CONDITION", f"{path}.type", "Unsupported condition type")]

    def _parse_effect(self, raw: Any) -> tuple[RuleEffect | None, list[ValidationIssue]]:
        path = "$.effect"
        issues: list[ValidationIssue] = []
        if not isinstance(raw, Mapping):
            return None, [self._issue("SCHEMA_INVALID", path, "effect must be an object")]

        raw_type = raw.get("type")
        try:
            effect_type = RuleEffectType(raw_type)
        except (ValueError, TypeError):
            return None, [self._issue("ALLOWED_EFFECT", f"{path}.type", "Unsupported effect type")]

        if effect_type in self._ADD_EFFECTS:
            self._check_exact_keys(raw, {"type", "delta"}, path, issues)
            delta = raw.get("delta")
            if not self._is_int(delta):
                issues.append(self._issue("ENUM_TYPE", f"{path}.delta", "delta must be an integer"))
                return None, issues
            return RuleEffect(effect_type, delta=delta), issues

        if effect_type is RuleEffectType.BOW_HIT_MULTIPLIER:
            self._check_exact_keys(raw, {"type", "multiplier"}, path, issues)
            multiplier = raw.get("multiplier")
            if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)):
                issues.append(self._issue("ENUM_TYPE", f"{path}.multiplier", "multiplier must be numeric"))
                return None, issues
            multiplier = float(multiplier)
            if not math.isfinite(multiplier):
                issues.append(self._issue("NUMERIC_BOUNDS", f"{path}.multiplier", "multiplier must be finite"))
                return None, issues
            return RuleEffect(effect_type, multiplier=multiplier), issues

        if effect_type is RuleEffectType.WEAPON_COOLDOWN:
            self._check_exact_keys(raw, {"type", "weapon", "rounds"}, path, issues)
            try:
                weapon = RuleWeapon(raw.get("weapon"))
            except (ValueError, TypeError):
                issues.append(self._issue("ENUM_TYPE", f"{path}.weapon", "weapon must be KNIFE or BOW"))
                return None, issues
            if weapon is RuleWeapon.NONE:
                issues.append(self._issue("ALLOWED_EFFECT", f"{path}.weapon", "NONE cannot be put on cooldown"))
            rounds = raw.get("rounds")
            if not self._is_int(rounds) or rounds != 1:
                issues.append(self._issue("NUMERIC_BOUNDS", f"{path}.rounds", "V0.1 cooldown must be exactly 1 round"))
            return RuleEffect(effect_type, weapon=weapon, rounds=rounds if self._is_int(rounds) else None), issues

        return None, [self._issue("ALLOWED_EFFECT", f"{path}.type", "Unsupported effect type")]

    def _validate_condition_value(
        self,
        condition_type: RuleConditionType,
        value: int,
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        if condition_type in {RuleConditionType.SELF_HP_LTE, RuleConditionType.SELF_HP_GTE}:
            low, high = 1, self.config.initial_hp
        elif condition_type in {RuleConditionType.DISTANCE_LTE, RuleConditionType.DISTANCE_GTE}:
            low, high = 1, self.config.max_manhattan_distance
        elif condition_type is RuleConditionType.ROUND_GTE:
            low, high = 1, self.config.max_rounds
        else:
            low, high = 1, 3
        if not low <= value <= high:
            issues.append(self._issue("NUMERIC_BOUNDS", path, f"value must be in {low}..{high}"))

    def _validate_effect_bounds(self, effect: RuleEffect) -> ValidationIssue | None:
        effect_type = effect.type
        if effect_type in self._ADD_EFFECTS:
            assert effect.delta is not None
            if effect.delta == 0:
                return self._issue("NO_EFFECT_RULE", "$.effect.delta", "delta=0 can never change the game")

            if effect_type is RuleEffectType.MOVE_RANGE_ADD:
                base, low, high = self.config.base_move_range, 1, 2
            elif effect_type is RuleEffectType.KNIFE_RANGE_ADD:
                base, low, high = self.config.base_knife_range, 1, 2
            elif effect_type is RuleEffectType.BOW_RANGE_ADD:
                base, low, high = self.config.base_bow_range, 1, 4
            elif effect_type is RuleEffectType.KNIFE_DAMAGE_ADD:
                base, low, high = self.config.knife_damage, 1, 3
            else:
                base, low, high = self.config.bow_damage, 1, 2

            final_value = base + effect.delta
            if not low <= final_value <= high:
                return self._issue(
                    "NUMERIC_BOUNDS",
                    "$.effect.delta",
                    f"final ordinary-mode value would be {final_value}, allowed range is {low}..{high}",
                )
            return None

        if effect_type is RuleEffectType.BOW_HIT_MULTIPLIER:
            assert effect.multiplier is not None
            if effect.multiplier == 1.0:
                return self._issue(
                    "NO_EFFECT_RULE",
                    "$.effect.multiplier",
                    "multiplier=1 has no effect",
                )
            # The frozen V0.1 specification constrains the final probability, not
            # the raw multiplier. Runtime evaluation will apply the required
            # 5%..100% normal clamp before anti-stall overrides.
            return None

        if effect_type is RuleEffectType.WEAPON_COOLDOWN:
            # One weapon for exactly one current round cannot permanently disable
            # all attacks, and Hard Liveness FORCED_BOW is explicitly exempt.
            return None

        return self._issue("ALLOWED_EFFECT", "$.effect.type", "Unsupported effect type")

    @staticmethod
    def _conditions_directly_contradict(conditions: tuple[RuleCondition, ...]) -> bool:
        if len(conditions) < 2:
            return False
        first, second = conditions

        pair = {first.type, second.type}
        if pair == {RuleConditionType.SELF_HP_LT_OPPONENT, RuleConditionType.SELF_HP_GT_OPPONENT}:
            return True

        if first.type is second.type is RuleConditionType.LAST_ATTACK_WEAPON_IS:
            return first.weapon is not second.weapon

        hp_lte = next((c.value for c in conditions if c.type is RuleConditionType.SELF_HP_LTE), None)
        hp_gte = next((c.value for c in conditions if c.type is RuleConditionType.SELF_HP_GTE), None)
        if hp_lte is not None and hp_gte is not None and hp_gte > hp_lte:
            return True

        distance_lte = next((c.value for c in conditions if c.type is RuleConditionType.DISTANCE_LTE), None)
        distance_gte = next((c.value for c in conditions if c.type is RuleConditionType.DISTANCE_GTE), None)
        if distance_lte is not None and distance_gte is not None and distance_gte > distance_lte:
            return True

        return False

    @staticmethod
    def _is_int(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    def _check_exact_keys(
        self,
        raw: Mapping[str, Any],
        allowed: set[str],
        path: str,
        issues: list[ValidationIssue],
    ) -> None:
        for key in sorted(set(raw) - allowed):
            issues.append(self._issue("SCHEMA_UNKNOWN_FIELD", f"{path}.{key}", "Unknown field"))
        for key in sorted(allowed - set(raw)):
            issues.append(self._issue("SCHEMA_MISSING_FIELD", f"{path}.{key}", "Required field is missing"))

    @staticmethod
    def _issue(code: str, path: str, message: str) -> ValidationIssue:
        return ValidationIssue(code, path, message)

    def _reject(self, code: str, path: str, message: str) -> ValidationResult:
        return ValidationResult(False, None, (self._issue(code, path, message),))
