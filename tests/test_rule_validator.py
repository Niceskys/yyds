from rules_beyond.model import GameConfig
from rules_beyond.rule_dsl import RuleConditionType, RuleEffectType
from rules_beyond.rule_validator import RuleValidator


def candidate(*, conditions=None, effect=None, target="ALL_UNITS", duration="UNTIL_REPLACED"):
    return {
        "version": "v0.1",
        "target": target,
        "conditions": [] if conditions is None else conditions,
        "effect": effect or {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": duration,
    }


def codes(result):
    return {issue.code for issue in result.issues}


def test_zero_condition_rule_is_accepted() -> None:
    result = RuleValidator().validate(candidate())
    assert result.accepted
    assert result.rule is not None
    assert result.rule.conditions == ()


def test_one_and_two_conditions_are_accepted() -> None:
    validator = RuleValidator()

    one = validator.validate(
        candidate(conditions=[{"type": "SELF_HP_LTE", "value": 2}])
    )
    two = validator.validate(
        candidate(
            conditions=[
                {"type": "SELF_HP_LTE", "value": 2},
                {"type": "DISTANCE_GTE", "value": 3},
            ]
        )
    )

    assert one.accepted
    assert two.accepted
    assert two.rule is not None
    assert [item.type for item in two.rule.conditions] == [
        RuleConditionType.SELF_HP_LTE,
        RuleConditionType.DISTANCE_GTE,
    ]


def test_three_conditions_are_rejected() -> None:
    result = RuleValidator().validate(
        candidate(
            conditions=[
                {"type": "SELF_HP_LTE", "value": 2},
                {"type": "DISTANCE_GTE", "value": 2},
                {"type": "ROUND_GTE", "value": 3},
            ]
        )
    )
    assert not result.accepted
    assert "CONDITION_COUNT" in codes(result)


def test_or_not_and_nested_boolean_fields_are_rejected() -> None:
    validator = RuleValidator()
    with_or = validator.validate(
        candidate(
            conditions=[
                {"type": "SELF_HP_LTE", "value": 2, "operator": "OR"},
            ]
        )
    )
    with_not = validator.validate(
        candidate(
            conditions=[
                {"type": "SELF_HP_LTE", "value": 2, "not": True},
            ]
        )
    )
    assert not with_or.accepted
    assert not with_not.accepted
    assert "SCHEMA_UNKNOWN_FIELD" in codes(with_or)
    assert "SCHEMA_UNKNOWN_FIELD" in codes(with_not)


def test_red_blue_target_is_rejected() -> None:
    result = RuleValidator().validate(candidate(target="RED"))
    assert not result.accepted
    assert "FACTION_NEUTRALITY" in codes(result)


def test_absolute_position_condition_is_rejected() -> None:
    result = RuleValidator().validate(
        candidate(conditions=[{"type": "ROW_EQ", "value": 1}])
    )
    assert not result.accepted
    assert "ALLOWED_CONDITION" in codes(result)


def test_winner_and_direct_state_capabilities_are_not_in_effect_whitelist() -> None:
    validator = RuleValidator()
    for effect in (
        {"type": "SET_WINNER", "team": "RED"},
        {"type": "SET_HP", "value": 1},
        {"type": "REVIVE"},
        {"type": "SET_MAX_ROUNDS", "value": 999},
        {"type": "DISABLE_HARD_LIVENESS"},
    ):
        result = validator.validate(candidate(effect=effect))
        assert not result.accepted
        assert "ALLOWED_EFFECT" in codes(result)


def test_damage_cannot_be_reduced_to_zero() -> None:
    result = RuleValidator().validate(
        candidate(effect={"type": "KNIFE_DAMAGE_ADD", "delta": -2})
    )
    assert not result.accepted
    assert "NUMERIC_BOUNDS" in codes(result)


def test_safe_negative_modifier_is_accepted() -> None:
    result = RuleValidator().validate(
        candidate(effect={"type": "KNIFE_DAMAGE_ADD", "delta": -1})
    )
    assert result.accepted
    assert result.rule is not None
    assert result.rule.effect.type is RuleEffectType.KNIFE_DAMAGE_ADD
    assert result.rule.effect.delta == -1


def test_bow_range_negative_modifier_respects_final_bounds() -> None:
    validator = RuleValidator()
    assert validator.validate(
        candidate(effect={"type": "BOW_RANGE_ADD", "delta": -2})
    ).accepted
    rejected = validator.validate(
        candidate(effect={"type": "BOW_RANGE_ADD", "delta": -3})
    )
    assert not rejected.accepted
    assert "NUMERIC_BOUNDS" in codes(rejected)


def test_no_effect_rules_are_rejected() -> None:
    validator = RuleValidator()
    delta_zero = validator.validate(
        candidate(effect={"type": "BOW_RANGE_ADD", "delta": 0})
    )
    multiplier_one = validator.validate(
        candidate(effect={"type": "BOW_HIT_MULTIPLIER", "multiplier": 1.0})
    )
    impossible_conditions = validator.validate(
        candidate(
            conditions=[
                {"type": "SELF_HP_LTE", "value": 1},
                {"type": "SELF_HP_GTE", "value": 4},
            ]
        )
    )

    assert "NO_EFFECT_RULE" in codes(delta_zero)
    assert "NO_EFFECT_RULE" in codes(multiplier_one)
    assert "NO_EFFECT_RULE" in codes(impossible_conditions)


def test_condition_numeric_bounds_use_game_config() -> None:
    validator = RuleValidator(GameConfig(initial_hp=5))
    assert validator.validate(
        candidate(conditions=[{"type": "SELF_HP_LTE", "value": 5}])
    ).accepted
    too_high = validator.validate(
        candidate(conditions=[{"type": "SELF_HP_LTE", "value": 6}])
    )
    assert not too_high.accepted
    assert "NUMERIC_BOUNDS" in codes(too_high)


def test_distance_round_and_history_threshold_bounds_are_enforced() -> None:
    validator = RuleValidator()
    bad_distance = validator.validate(
        candidate(conditions=[{"type": "DISTANCE_GTE", "value": 9}])
    )
    bad_round = validator.validate(
        candidate(conditions=[{"type": "ROUND_GTE", "value": 31}])
    )
    bad_history = validator.validate(
        candidate(conditions=[{"type": "CONSECUTIVE_BOW_MISS_GTE", "value": 4}])
    )
    assert "NUMERIC_BOUNDS" in codes(bad_distance)
    assert "NUMERIC_BOUNDS" in codes(bad_round)
    assert "NUMERIC_BOUNDS" in codes(bad_history)


def test_weapon_history_condition_accepts_only_knifebownone() -> None:
    validator = RuleValidator()
    for weapon in ("KNIFE", "BOW", "NONE"):
        assert validator.validate(
            candidate(conditions=[{"type": "LAST_ATTACK_WEAPON_IS", "weapon": weapon}])
        ).accepted

    bad = validator.validate(
        candidate(conditions=[{"type": "LAST_ATTACK_WEAPON_IS", "weapon": "SWORD"}])
    )
    assert not bad.accepted
    assert "ENUM_TYPE" in codes(bad)


def test_one_round_weapon_cooldown_is_accepted_but_other_durations_are_rejected() -> None:
    validator = RuleValidator()
    accepted = validator.validate(
        candidate(effect={"type": "WEAPON_COOLDOWN", "weapon": "BOW", "rounds": 1})
    )
    rejected = validator.validate(
        candidate(effect={"type": "WEAPON_COOLDOWN", "weapon": "BOW", "rounds": 2})
    )
    none_weapon = validator.validate(
        candidate(effect={"type": "WEAPON_COOLDOWN", "weapon": "NONE", "rounds": 1})
    )

    assert accepted.accepted
    assert not rejected.accepted
    assert not none_weapon.accepted


def test_hit_multiplier_uses_final_probability_clamp_contract() -> None:
    validator = RuleValidator()

    # V0.1 freezes the final normal probability to 5%..100%. It does not freeze
    # a raw multiplier range. Therefore 0 still produces a 5% final probability
    # at runtime and is structurally legal; direct hit-probability setters are not.
    zero_multiplier = validator.validate(
        candidate(effect={"type": "BOW_HIT_MULTIPLIER", "multiplier": 0})
    )
    direct_set_zero = validator.validate(
        candidate(effect={"type": "SET_BOW_HIT_PROBABILITY", "value": 0})
    )

    assert zero_multiplier.accepted
    assert not direct_set_zero.accepted
    assert "ALLOWED_EFFECT" in codes(direct_set_zero)


def test_unknown_root_fields_are_rejected_instead_of_ignored() -> None:
    payload = candidate()
    payload["winner"] = "RED"
    result = RuleValidator().validate(payload)
    assert not result.accepted
    assert "SCHEMA_UNKNOWN_FIELD" in codes(result)
