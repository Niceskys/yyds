import json

from rules_beyond.natural_language_benchmark import (
    load_corpus,
    validate_corpus_against_rule_validator,
)
from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from rules_beyond.verified_natural_language_benchmark import run_verified_benchmark
from rules_beyond.verified_natural_language_rule_adapter import VerifiedNaturalLanguageRuleAdapter


V03_CORPUS = "evals/natural_language_rule_holdout_v0.3.json"


class V03OracleModel:
    def __init__(self, cases):
        self.by_text = {case.text: case for case in cases}

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        if "strict semantic verifier" in system_prompt:
            return json.dumps({"decision": "FAITHFUL"})

        case = self.by_text[player_text]
        if case.expected_decision == "CANDIDATE":
            return json.dumps(
                {"decision": "CANDIDATE", "candidate": case.expected_candidate},
                ensure_ascii=False,
            )
        return json.dumps(
            {"decision": "NO_CANDIDATE", "reason_code": case.expected_reason_code},
            ensure_ascii=False,
        )


def test_v03_holdout_is_balanced_unique_and_validator_legal() -> None:
    cases = load_corpus(V03_CORPUS)

    assert len(cases) == 50
    assert len({case.case_id for case in cases}) == 50
    assert len({case.text for case in cases}) == 50
    assert sum(case.expected_decision == "CANDIDATE" for case in cases) == 25
    assert sum(case.expected_decision == "NO_CANDIDATE" for case in cases) == 25

    validate_corpus_against_rule_validator(cases)


def test_v03_verified_oracle_scores_perfectly() -> None:
    cases = load_corpus(V03_CORPUS)
    model = V03OracleModel(cases)
    adapter = VerifiedNaturalLanguageRuleAdapter(
        NaturalLanguageRuleAdapter(model),
        NaturalLanguageRuleFaithfulnessVerifier(model),
    )

    summary = run_verified_benchmark(
        adapter,
        cases,
        provider="test",
        model_name="v03-oracle",
    )

    assert summary.total == 50
    assert summary.legal_total == 25
    assert summary.legal_semantic_correct == 25
    assert summary.legal_blocked == 0
    assert summary.no_candidate_total == 25
    assert summary.no_candidate_blocked == 25
    assert summary.false_accepts == 0
    assert summary.wrong_legal_candidates == 0
    assert summary.verifier_errors == 0
