import json

from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.rule_faithfulness import (
    FaithfulnessDecision,
    FaithfulnessReason,
    NaturalLanguageRuleFaithfulnessVerifier,
)
from rules_beyond.verified_natural_language_rule_adapter import (
    VerifiedNaturalLanguageRuleAdapter,
    VerifiedTranslationStatus,
)


class StubModel:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def generate_candidate(self, *, system_prompt: str, player_text: str):
        self.calls.append((system_prompt, player_text))
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def candidate_envelope(conditions=None):
    return json.dumps(
        {
            "decision": "CANDIDATE",
            "candidate": {
                "version": "v0.1",
                "target": "ALL_UNITS",
                "conditions": conditions or [],
                "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
                "duration": "UNTIL_REPLACED",
            },
        },
        ensure_ascii=False,
    )


def test_faithful_verdict_accepts_exact_candidate() -> None:
    model = StubModel(json.dumps({"decision": "FAITHFUL"}))
    verifier = NaturalLanguageRuleFaithfulnessVerifier(model)
    candidate = {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "SELF_HP_LTE", "value": 2}],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }

    result = verifier.verify(
        player_text="生命值不高于2时，弓射程增加1格。",
        candidate=candidate,
    )

    assert result.decision is FaithfulnessDecision.FAITHFUL
    assert result.faithful is True
    sent = json.loads(model.calls[0][1])
    assert sent["player_text"] == "生命值不高于2时，弓射程增加1格。"
    assert sent["candidate"] == candidate


def test_or_fragment_omission_can_be_rejected_without_repair() -> None:
    model = StubModel(
        json.dumps({"decision": "REJECT", "reason_code": "DROPPED_INTENT"})
    )
    verifier = NaturalLanguageRuleFaithfulnessVerifier(model)
    candidate = {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "SELF_HP_LTE", "value": 2}],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }

    result = verifier.verify(
        player_text="生命值不高于2或者距离至少4格时，弓射程增加1格。",
        candidate=candidate,
    )

    assert result.decision is FaithfulnessDecision.REJECT
    assert result.reason is FaithfulnessReason.DROPPED_INTENT
    assert result.faithful is False


def test_verifier_protocol_error_fails_closed() -> None:
    verifier = NaturalLanguageRuleFaithfulnessVerifier(StubModel("not-json"))
    result = verifier.verify(player_text="x", candidate={})
    assert result.decision is FaithfulnessDecision.PROTOCOL_ERROR
    assert result.faithful is False


def test_verifier_model_error_fails_closed() -> None:
    verifier = NaturalLanguageRuleFaithfulnessVerifier(StubModel(RuntimeError("down")))
    result = verifier.verify(player_text="x", candidate={})
    assert result.decision is FaithfulnessDecision.MODEL_ERROR
    assert result.faithful is False


def test_verified_adapter_accepts_only_after_second_gate() -> None:
    translator = StubModel(
        candidate_envelope([{"type": "SELF_HP_LTE", "value": 2}])
    )
    checker = StubModel(json.dumps({"decision": "FAITHFUL"}))
    adapter = VerifiedNaturalLanguageRuleAdapter(
        NaturalLanguageRuleAdapter(translator),
        NaturalLanguageRuleFaithfulnessVerifier(checker),
    )

    result = adapter.translate("生命值不高于2时，弓射程增加1格。")

    assert result.status is VerifiedTranslationStatus.ACCEPTED
    assert result.accepted is True
    assert result.candidate is not None
    assert result.rule is not None
    assert len(checker.calls) == 1


def test_verified_adapter_hides_candidate_when_semantics_are_rejected() -> None:
    translator = StubModel(
        candidate_envelope([{"type": "SELF_HP_LTE", "value": 2}])
    )
    checker = StubModel(
        json.dumps({"decision": "REJECT", "reason_code": "DROPPED_INTENT"})
    )
    adapter = VerifiedNaturalLanguageRuleAdapter(
        NaturalLanguageRuleAdapter(translator),
        NaturalLanguageRuleFaithfulnessVerifier(checker),
    )

    result = adapter.translate("生命值不高于2或者距离至少4格时，弓射程增加1格。")

    assert result.status is VerifiedTranslationStatus.SEMANTIC_REJECTED
    assert result.accepted is False
    assert result.candidate is None
    assert result.rule is None
    assert result.base.candidate is not None


def test_base_rejection_never_calls_semantic_verifier() -> None:
    translator = StubModel(
        json.dumps({"decision": "NO_CANDIDATE", "reason_code": "AMBIGUOUS"})
    )
    checker = StubModel(json.dumps({"decision": "FAITHFUL"}))
    adapter = VerifiedNaturalLanguageRuleAdapter(
        NaturalLanguageRuleAdapter(translator),
        NaturalLanguageRuleFaithfulnessVerifier(checker),
    )

    result = adapter.translate("残血的时候更灵活一点。")

    assert result.status is VerifiedTranslationStatus.BASE_REJECTED
    assert result.accepted is False
    assert checker.calls == []


def test_verifier_error_does_not_expose_executable_candidate() -> None:
    translator = StubModel(candidate_envelope())
    checker = StubModel("oops")
    adapter = VerifiedNaturalLanguageRuleAdapter(
        NaturalLanguageRuleAdapter(translator),
        NaturalLanguageRuleFaithfulnessVerifier(checker),
    )

    result = adapter.translate("弓射程增加1格。")

    assert result.status is VerifiedTranslationStatus.VERIFIER_ERROR
    assert result.candidate is None
    assert result.rule is None
