from rules_beyond.rule_intent_guard import (
    IntentGuardDecision,
    IntentGuardReason,
    guard_player_intent_v0_1,
)


def test_explicit_chinese_or_markers_are_rejected() -> None:
    for text in (
        "生命值不超过2或者上一回合没移动时，弓射程增加1格。",
        "生命值不超过2或是上一回合没移动时，弓射程增加1格。",
        "要么生命值不超过2，要么上一回合没移动，弓射程增加1格。",
    ):
        result = guard_player_intent_v0_1(text)
        assert result.decision is IntentGuardDecision.REJECT
        assert result.reason is IntentGuardReason.EXPLICIT_OR_UNSUPPORTED


def test_english_or_word_is_rejected_case_insensitively() -> None:
    assert guard_player_intent_v0_1("HP <= 2 OR distance >= 4: bow range +1").allowed is False


def test_and_and_ordinary_chinese_are_not_rejected() -> None:
    for text in (
        "生命值不超过2并且上一回合没移动时，弓射程增加1格。",
        "上一轮使用了弓的单位，本轮弓需要冷却1回合。",
        "弓射程增加1格。",
    ):
        result = guard_player_intent_v0_1(text)
        assert result.decision is IntentGuardDecision.ALLOW
        assert result.reason is None
