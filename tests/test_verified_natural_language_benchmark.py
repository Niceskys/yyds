import json

from rules_beyond.natural_language_benchmark import NaturalLanguageEvalCase
from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from rules_beyond.verified_natural_language_benchmark import run_verified_benchmark
from rules_beyond.verified_natural_language_rule_adapter import VerifiedNaturalLanguageRuleAdapter


class RoutingModel:
    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        if "strict semantic verifier" in system_prompt:
            payload = json.loads(player_text)
            if "或者" in payload["player_text"]:
                return json.dumps({"decision": "REJECT", "reason_code": "DROPPED_INTENT"})
            return json.dumps({"decision": "FAITHFUL"})

        if "或者" in player_text:
            conditions = [{"type": "SELF_HP_LTE", "value": 2}]
        else:
            conditions = [{"type": "SELF_HP_LTE", "value": 2}]
        return json.dumps(
            {
                "decision": "CANDIDATE",
                "candidate": {
                    "version": "v0.1",
                    "target": "ALL_UNITS",
                    "conditions": conditions,
                    "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
                    "duration": "UNTIL_REPLACED",
                },
            },
            ensure_ascii=False,
        )


def test_verified_benchmark_counts_semantic_rejection_as_safe_block() -> None:
    legal_candidate = {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "SELF_HP_LTE", "value": 2}],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }
    cases = [
        NaturalLanguageEvalCase(
            case_id="legal",
            category="LEGAL",
            text="生命值不高于2时，弓射程增加1格。",
            expected_decision="CANDIDATE",
            expected_candidate=legal_candidate,
        ),
        NaturalLanguageEvalCase(
            case_id="or-reject",
            category="NO_CANDIDATE",
            text="生命值不高于2或者距离至少4格时，弓射程增加1格。",
            expected_decision="NO_CANDIDATE",
            expected_reason_code="UNSUPPORTED_CAPABILITY",
        ),
    ]
    model = RoutingModel()
    adapter = VerifiedNaturalLanguageRuleAdapter(
        NaturalLanguageRuleAdapter(model),
        NaturalLanguageRuleFaithfulnessVerifier(model),
    )

    summary = run_verified_benchmark(
        adapter,
        cases,
        provider="test",
        model_name="routing",
    )

    assert summary.total == 2
    assert summary.legal_semantic_correct == 1
    assert summary.no_candidate_blocked == 1
    assert summary.false_accepts == 0
    assert summary.wrong_legal_candidates == 0
    assert summary.semantic_rejections == 1
