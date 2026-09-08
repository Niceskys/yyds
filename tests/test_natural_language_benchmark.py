import json

from rules_beyond.mimo_rule_provider import MimoRuleCandidateModel
from rules_beyond.natural_language_benchmark import (
    _build_provider,
    load_corpus,
    run_benchmark,
    validate_corpus_against_rule_validator,
)
from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.zhipu_rule_provider import ZhipuRuleCandidateModel


HOLDOUT_CORPUS = "evals/natural_language_rule_holdout_v0.1.json"


class CorpusOracleModel:
    def __init__(self, cases, *, override=None):
        self.by_text = {case.text: case for case in cases}
        self.override = override or {}

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        del system_prompt
        if player_text in self.override:
            return json.dumps(self.override[player_text], ensure_ascii=False)
        case = self.by_text[player_text]
        if case.expected_decision == "CANDIDATE":
            payload = {
                "decision": "CANDIDATE",
                "candidate": case.expected_candidate,
            }
        else:
            payload = {
                "decision": "NO_CANDIDATE",
                "reason_code": case.expected_reason_code,
            }
        return json.dumps(payload, ensure_ascii=False)


def test_fixed_corpus_loads_and_all_expected_candidates_are_validator_legal() -> None:
    cases = load_corpus()

    assert len(cases) == 18
    assert len({case.case_id for case in cases}) == len(cases)
    assert any(case.expected_decision == "CANDIDATE" for case in cases)
    assert any(case.expected_decision == "NO_CANDIDATE" for case in cases)

    validate_corpus_against_rule_validator(cases)


def test_holdout_corpus_is_frozen_balanced_and_validator_legal() -> None:
    cases = load_corpus(HOLDOUT_CORPUS)

    assert len(cases) == 40
    assert len({case.case_id for case in cases}) == 40
    assert sum(case.expected_decision == "CANDIDATE" for case in cases) == 20
    assert sum(case.expected_decision == "NO_CANDIDATE" for case in cases) == 20

    validate_corpus_against_rule_validator(cases)


def test_oracle_model_scores_perfectly_on_benchmark_logic() -> None:
    cases = load_corpus()
    adapter = NaturalLanguageRuleAdapter(CorpusOracleModel(cases))

    summary = run_benchmark(adapter, cases, model_name="oracle")

    assert summary.provider == "test"
    assert summary.total == 18
    assert summary.exact_correct == 18
    assert summary.exact_accuracy == 1.0
    assert summary.decision_correct == 18
    assert summary.decision_accuracy == 1.0
    assert summary.legal_total == 8
    assert summary.legal_semantic_correct == 8
    assert summary.no_candidate_total == 10
    assert summary.no_candidate_decision_correct == 10
    assert summary.no_candidate_reason_correct == 10
    assert summary.false_accepts == 0
    assert summary.false_rejects == 0
    assert summary.wrong_legal_candidates == 0


def test_holdout_oracle_scores_perfectly_without_prompt_changes() -> None:
    cases = load_corpus(HOLDOUT_CORPUS)
    adapter = NaturalLanguageRuleAdapter(CorpusOracleModel(cases))

    summary = run_benchmark(adapter, cases, model_name="holdout-oracle")

    assert summary.total == 40
    assert summary.legal_total == 20
    assert summary.legal_semantic_correct == 20
    assert summary.no_candidate_total == 20
    assert summary.no_candidate_decision_correct == 20
    assert summary.false_accepts == 0
    assert summary.false_rejects == 0
    assert summary.wrong_legal_candidates == 0


def test_benchmark_counts_silent_sanitization_as_false_accept() -> None:
    cases = load_corpus()
    red_only = next(case for case in cases if case.case_id == "reject_red_only")
    illegal_sanitization = {
        "decision": "CANDIDATE",
        "candidate": {
            "version": "v0.1",
            "target": "ALL_UNITS",
            "conditions": [],
            "effect": {"type": "KNIFE_DAMAGE_ADD", "delta": 1},
            "duration": "UNTIL_REPLACED",
        },
    }
    adapter = NaturalLanguageRuleAdapter(
        CorpusOracleModel(cases, override={red_only.text: illegal_sanitization})
    )

    summary = run_benchmark(adapter, cases, model_name="bad-sanitizer")

    assert summary.exact_correct == 17
    assert summary.decision_correct == 17
    assert summary.false_accepts == 1
    failed = next(result for result in summary.results if result.case_id == "reject_red_only")
    assert failed.exact_correct is False
    assert failed.decision_correct is False
    assert failed.actual_status == "ACCEPTED"


def test_safe_rejection_with_different_reason_is_decision_correct_but_not_exact() -> None:
    cases = load_corpus()
    healing = next(case for case in cases if case.case_id == "reject_healing")
    alternate_safe_rejection = {
        "decision": "NO_CANDIDATE",
        "reason_code": "CANNOT_MAP_SAFELY",
    }
    adapter = NaturalLanguageRuleAdapter(
        CorpusOracleModel(cases, override={healing.text: alternate_safe_rejection})
    )

    summary = run_benchmark(adapter, cases, model_name="safe-different-reason")

    assert summary.decision_correct == 18
    assert summary.exact_correct == 17
    assert summary.false_accepts == 0
    result = next(result for result in summary.results if result.case_id == "reject_healing")
    assert result.decision_correct is True
    assert result.reason_code_correct is False
    assert result.exact_correct is False


def test_build_provider_selects_mimo_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "tp-test")
    provider = _build_provider("mimo", "mimo-v2.5-pro", 3.0)
    assert isinstance(provider, MimoRuleCandidateModel)
    assert provider.model_name == "mimo-v2.5-pro"


def test_build_provider_selects_zhipu_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ZHIPU_API_KEY", "sk-test")
    provider = _build_provider("zhipu", "glm-5.1", 3.0)
    assert isinstance(provider, ZhipuRuleCandidateModel)
    assert provider.model_name == "glm-5.1"


def test_invalid_corpus_duplicate_id_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "same",
                    "category": "NO_CANDIDATE",
                    "text": "a",
                    "expected_decision": "NO_CANDIDATE",
                    "expected_reason_code": "AMBIGUOUS",
                },
                {
                    "id": "same",
                    "category": "NO_CANDIDATE",
                    "text": "b",
                    "expected_decision": "NO_CANDIDATE",
                    "expected_reason_code": "AMBIGUOUS",
                },
            ]
        ),
        encoding="utf-8",
    )

    try:
        load_corpus(path)
    except ValueError as exc:
        assert "duplicate corpus id" in str(exc)
    else:
        raise AssertionError("duplicate corpus id must be rejected")
