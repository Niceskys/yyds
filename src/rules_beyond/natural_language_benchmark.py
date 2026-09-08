from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from .natural_language_rule_adapter import (
    NaturalLanguageRuleAdapter,
    NoCandidateReason,
    TranslationStatus,
)
from .rule_validator import RuleValidator
from .zhipu_rule_provider import (
    DEFAULT_ZHIPU_API_KEY_ENV,
    ZhipuRuleCandidateModel,
)


DEFAULT_CORPUS_PATH = Path("evals/natural_language_rule_corpus_v0.1.json")


@dataclass(frozen=True, slots=True)
class NaturalLanguageEvalCase:
    case_id: str
    category: str
    text: str
    expected_decision: str
    expected_candidate: Mapping[str, Any] | None = None
    expected_reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class NaturalLanguageEvalResult:
    case_id: str
    category: str
    text: str
    expected_decision: str
    actual_status: str
    exact_correct: bool
    decision_correct: bool
    candidate_semantics_correct: bool | None
    reason_code_correct: bool | None
    actual_candidate: Mapping[str, Any] | None
    expected_candidate: Mapping[str, Any] | None
    actual_reason_code: str | None
    expected_reason_code: str | None
    validation_issue_codes: tuple[str, ...]
    error_message: str | None


@dataclass(frozen=True, slots=True)
class NaturalLanguageBenchmarkSummary:
    model_name: str
    total: int
    exact_correct: int
    exact_accuracy: float
    decision_correct: int
    decision_accuracy: float
    legal_total: int
    legal_semantic_correct: int
    no_candidate_total: int
    no_candidate_decision_correct: int
    no_candidate_reason_correct: int
    false_accepts: int
    false_rejects: int
    wrong_legal_candidates: int
    results: tuple[NaturalLanguageEvalResult, ...]


def load_corpus(path: str | Path = DEFAULT_CORPUS_PATH) -> list[NaturalLanguageEvalCase]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("natural-language corpus must be a non-empty JSON array")

    cases: list[NaturalLanguageEvalCase] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"corpus[{index}] must be an object")

        case_id = item.get("id")
        category = item.get("category")
        text = item.get("text")
        expected_decision = item.get("expected_decision")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"corpus[{index}].id must be a non-empty string")
        if case_id in seen_ids:
            raise ValueError(f"duplicate corpus id: {case_id}")
        seen_ids.add(case_id)
        if category not in {"LEGAL", "NO_CANDIDATE"}:
            raise ValueError(f"{case_id}: invalid category")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{case_id}: text must be non-empty")
        if expected_decision not in {"CANDIDATE", "NO_CANDIDATE"}:
            raise ValueError(f"{case_id}: invalid expected_decision")

        expected_candidate = item.get("expected_candidate")
        expected_reason = item.get("expected_reason_code")
        if expected_decision == "CANDIDATE":
            if category != "LEGAL" or not isinstance(expected_candidate, dict):
                raise ValueError(f"{case_id}: candidate case must include expected_candidate")
            if expected_reason is not None:
                raise ValueError(f"{case_id}: candidate case cannot include expected_reason_code")
        else:
            if category != "NO_CANDIDATE" or expected_candidate is not None:
                raise ValueError(f"{case_id}: NO_CANDIDATE case cannot include expected_candidate")
            try:
                NoCandidateReason(expected_reason)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{case_id}: invalid expected_reason_code") from exc

        cases.append(
            NaturalLanguageEvalCase(
                case_id=case_id,
                category=category,
                text=text,
                expected_decision=expected_decision,
                expected_candidate=expected_candidate,
                expected_reason_code=expected_reason,
            )
        )
    return cases


def validate_corpus_against_rule_validator(
    cases: Iterable[NaturalLanguageEvalCase],
    validator: RuleValidator | None = None,
) -> None:
    validator = validator or RuleValidator()
    for case in cases:
        if case.expected_decision != "CANDIDATE":
            continue
        assert case.expected_candidate is not None
        result = validator.validate(case.expected_candidate)
        if not result.accepted:
            codes = ",".join(issue.code for issue in result.issues)
            raise ValueError(f"{case.case_id}: expected candidate is invalid: {codes}")


def run_benchmark(
    adapter: NaturalLanguageRuleAdapter,
    cases: Iterable[NaturalLanguageEvalCase],
    *,
    model_name: str,
) -> NaturalLanguageBenchmarkSummary:
    results: list[NaturalLanguageEvalResult] = []
    legal_total = 0
    legal_semantic_correct = 0
    no_candidate_total = 0
    no_candidate_decision_correct = 0
    no_candidate_reason_correct = 0
    false_accepts = 0
    false_rejects = 0
    wrong_legal_candidates = 0

    for case in cases:
        translation = adapter.translate(case.text)
        actual_reason = (
            translation.no_candidate_reason.value
            if translation.no_candidate_reason is not None
            else None
        )

        if case.expected_decision == "CANDIDATE":
            legal_total += 1
            decision_correct = translation.status is TranslationStatus.ACCEPTED
            candidate_semantics_correct = (
                decision_correct and translation.candidate == case.expected_candidate
            )
            reason_code_correct = None
            exact_correct = bool(candidate_semantics_correct)
            if candidate_semantics_correct:
                legal_semantic_correct += 1
            elif decision_correct:
                wrong_legal_candidates += 1
            else:
                false_rejects += 1
        else:
            no_candidate_total += 1
            decision_correct = translation.status is TranslationStatus.NO_CANDIDATE
            candidate_semantics_correct = None
            reason_code_correct = (
                decision_correct and actual_reason == case.expected_reason_code
            )
            exact_correct = bool(reason_code_correct)
            if decision_correct:
                no_candidate_decision_correct += 1
            if reason_code_correct:
                no_candidate_reason_correct += 1
            if translation.status is TranslationStatus.ACCEPTED:
                false_accepts += 1

        results.append(
            NaturalLanguageEvalResult(
                case_id=case.case_id,
                category=case.category,
                text=case.text,
                expected_decision=case.expected_decision,
                actual_status=translation.status.value,
                exact_correct=exact_correct,
                decision_correct=decision_correct,
                candidate_semantics_correct=candidate_semantics_correct,
                reason_code_correct=reason_code_correct,
                actual_candidate=translation.candidate,
                expected_candidate=case.expected_candidate,
                actual_reason_code=actual_reason,
                expected_reason_code=case.expected_reason_code,
                validation_issue_codes=tuple(
                    issue.code for issue in translation.validation_issues
                ),
                error_message=translation.error_message,
            )
        )

    total = len(results)
    exact_count = sum(result.exact_correct for result in results)
    decision_count = sum(result.decision_correct for result in results)
    return NaturalLanguageBenchmarkSummary(
        model_name=model_name,
        total=total,
        exact_correct=exact_count,
        exact_accuracy=exact_count / total if total else 0.0,
        decision_correct=decision_count,
        decision_accuracy=decision_count / total if total else 0.0,
        legal_total=legal_total,
        legal_semantic_correct=legal_semantic_correct,
        no_candidate_total=no_candidate_total,
        no_candidate_decision_correct=no_candidate_decision_correct,
        no_candidate_reason_correct=no_candidate_reason_correct,
        false_accepts=false_accepts,
        false_rejects=false_rejects,
        wrong_legal_candidates=wrong_legal_candidates,
        results=tuple(results),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the fixed natural-language RuleAST benchmark against Zhipu API"
    )
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS_PATH))
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()

    cases = load_corpus(args.corpus)
    validate_corpus_against_rule_validator(cases)

    if args.model is None:
        provider = ZhipuRuleCandidateModel.from_env(
            timeout_seconds=args.timeout_seconds,
        )
    else:
        api_key = os.getenv(DEFAULT_ZHIPU_API_KEY_ENV, "")
        if not api_key.strip():
            raise ValueError(f"{DEFAULT_ZHIPU_API_KEY_ENV} is not set")
        provider = ZhipuRuleCandidateModel(
            api_key,
            model_name=args.model,
            timeout_seconds=args.timeout_seconds,
        )

    adapter = NaturalLanguageRuleAdapter(provider)
    summary = run_benchmark(adapter, cases, model_name=provider.model_name)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
