from __future__ import annotations

from typing import Any, Mapping

from .rule_dsl import RuleAST, RuleCondition
from .rule_validator import RuleValidator


def _condition_key(condition: RuleCondition) -> tuple[str, int | None, str | None]:
    return (
        condition.type.value,
        condition.value,
        condition.weapon.value if condition.weapon is not None else None,
    )


def canonical_rule_semantics(rule: RuleAST) -> tuple[object, ...]:
    """Canonical semantic identity for V0.1 rules.

    V0.1 conditions are AND-only, so condition order is not semantic. Other
    fields are compared directly because the DSL has one target, one effect and
    one duration.
    """

    effect = rule.effect
    return (
        rule.version,
        rule.target.value,
        tuple(sorted((_condition_key(condition) for condition in rule.conditions))),
        (
            effect.type.value,
            effect.delta,
            effect.multiplier,
            effect.weapon.value if effect.weapon is not None else None,
            effect.rounds,
        ),
        rule.duration.value,
    )


def semantically_equal_candidates(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    validator: RuleValidator | None = None,
) -> bool:
    validator = validator or RuleValidator()
    left_result = validator.validate(left)
    right_result = validator.validate(right)
    if not left_result.accepted or left_result.rule is None:
        return False
    if not right_result.accepted or right_result.rule is None:
        return False
    return canonical_rule_semantics(left_result.rule) == canonical_rule_semantics(right_result.rule)
