import json

from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.rule_semantics import semantically_equal_candidates
from rules_beyond.translator_guidance import (
    GuidedRuleCandidateModel,
    TRANSLATOR_GUIDANCE_V0_1_1,
)


class CaptureModel:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        self.calls.append((system_prompt, player_text))
        return self.output


def test_guided_model_appends_supported_semantics_without_touching_player_text() -> None:
    output = json.dumps({"decision": "NO_CANDIDATE", "reason_code": "AMBIGUOUS"})
    inner = CaptureModel(output)
    guided = GuidedRuleCandidateModel(inner)
    adapter = NaturalLanguageRuleAdapter(guided)

    adapter.translate("双方的刀伤害减少1点。")

    assert len(inner.calls) == 1
    system_prompt, player_text = inner.calls[0]
    assert player_text == "双方的刀伤害减少1点。"
    assert "negative delta" in system_prompt
    assert "LAST_ATTACK_WEAPON_IS supports KNIFE, BOW, and NONE" in system_prompt
    assert "WEAPON_COOLDOWN" in system_prompt
    assert "UNTIL_REPLACED" in system_prompt


def test_guidance_does_not_authorize_repair_or_numeric_bypass() -> None:
    assert "let deterministic RuleValidator enforce numeric bounds" in TRANSLATOR_GUIDANCE_V0_1_1
    assert "temporary duration" in TRANSLATOR_GUIDANCE_V0_1_1
    assert "return NO_CANDIDATE" in TRANSLATOR_GUIDANCE_V0_1_1


def test_semantic_comparison_ignores_and_condition_order() -> None:
    left = {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [
            {"type": "SELF_HP_LTE", "value": 2},
            {"type": "DISTANCE_GTE", "value": 3},
        ],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }
    right = {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [
            {"type": "DISTANCE_GTE", "value": 3},
            {"type": "SELF_HP_LTE", "value": 2},
        ],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }

    assert semantically_equal_candidates(left, right) is True


def test_semantic_comparison_still_detects_real_meaning_change() -> None:
    left = {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "SELF_HP_LTE", "value": 2}],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }
    right = {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "SELF_HP_LTE", "value": 3}],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }

    assert semantically_equal_candidates(left, right) is False
