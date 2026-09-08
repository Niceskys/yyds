from rules_beyond.verified_natural_language_rule_adapter import has_explicit_unsupported_disjunction


def test_clear_chinese_or_forms_are_rejected() -> None:
    cases = [
        "生命值不超过2或者上一回合没移动时，弓射程增加1格。",
        "生命值不超过2或是上一回合没移动时，弓射程增加1格。",
        "满足任一条件时弓射程增加1格。",
        "任一条件成立时刀伤害增加1点。",
        "二者之一成立时移动距离增加1格。",
    ]
    assert all(has_explicit_unsupported_disjunction(text) for text in cases)


def test_either_or_is_rejected() -> None:
    assert has_explicit_unsupported_disjunction(
        "If either HP is at most 2 or distance is at least 4, increase bow range by 1."
    )


def test_threshold_or_less_is_not_boolean_or() -> None:
    assert not has_explicit_unsupported_disjunction("生命值只剩1点或更少时，弓射程减少1格。")
