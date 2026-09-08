from rules_beyond.rule_faithfulness import FAITHFULNESS_PROMPT_V0_1


def test_faithfulness_prompt_preserves_safety_and_equivalence_rules() -> None:
    prompt = FAITHFULNESS_PROMPT_V0_1
    assert "Do NOT repair" in prompt
    assert "OR/NOT logic" in prompt
    assert "target=ALL_UNITS" in prompt
    assert "duration=UNTIL_REPLACED" in prompt
    assert "Conditions are AND-only and commutative" in prompt
    assert "BOW_HIT_MULTIPLIER 0.75" in prompt
    assert "WEAPON_COOLDOWN" in prompt
    assert "negative ADD delta" in prompt
    assert "上一回合不是使用弓" in prompt
