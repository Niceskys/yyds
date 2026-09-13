from rules_beyond.rule_faithfulness import FAITHFULNESS_PROMPT_V0_1


def test_faithfulness_prompt_preserves_safety_and_equivalence_rules() -> None:
    prompt = FAITHFULNESS_PROMPT_V0_1
    assert "Do NOT repair" in prompt
    assert "Logical connective fidelity is mandatory" in prompt
    assert "OR changed to AND" in prompt
    assert "target=ALL_UNITS" in prompt
    assert "duration=UNTIL_REPLACED" in prompt
    assert "AND-only and commutative" in prompt
    assert "Never treat an original OR as equivalent to candidate AND" in prompt
    assert "BOW_HIT_MULTIPLIER 0.75" in prompt
    assert "WEAPON_COOLDOWN" in prompt
    assert "Rule duration=UNTIL_REPLACED is only the lifespan" in prompt
    assert "negative ADD delta" in prompt
    assert "上一回合不是使用弓" in prompt
    assert "上一轮使用了弓的单位，本轮弓需要冷却1回合" in prompt
