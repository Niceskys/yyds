from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable, Mapping, Any

from .natural_language_benchmark import (
    DEFAULT_CORPUS_PATH,
    NaturalLanguageEvalCase,
    SUPPORTED_PROVIDERS,
    _build_provider,
    load_corpus,
    validate_corpus_against_rule_validator,
)
from .natural_language_rule_adapter import NaturalLanguageRuleAdapter
from .rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from .rule_semantics import semantically_equal_candidates
from .translator_guidance import GuidedRuleCandidateModel
from .verified_natural_language_rule_adapter import (
    VerifiedNaturalLanguageRuleAdapter,
    VerifiedTranslationStatus,
)


@dataclass(frozen=True, slots=True)
class VerifiedEvalResult:
    case_id: str
    category: str
    text: str
    pipeline_status: str
    pipeline_accepted: bool
    candidate_semantics_correct: bool | None
    actual_candidate: Mapping[str, Any] | None
    expected_candidate: Mapping[str, Any] | None
    base_status: str
    intent_guard_decision: str | None
    intent_guard_reason: str | None
    faithfulness_decision: str | None
    faithfulness_reason: str | None


@dataclass(frozen=True, slots=True)
class VerifiedBenchmarkSummary:
    provider: str
    model_name: str
    total: int
    legal_total: int
    legal_semantic_correct: int
    legal_blocked: int
    no_candidate_total: int
    no_candidate_blocked: int
    false_accepts: int
    wrong_legal_candidates: int
    intent_guard_rejections: int
    semantic_rejections: int
    verifier_errors: int
    results: tuple[VerifiedEvalResult, ...]


def run_verified_benchmark(
    adapter: VerifiedNaturalLanguageRuleAdapter,
    cases: Iterable[NaturalLanguageEvalCase],
    *,
    provider: str,
    model_name: str,
) -> VerifiedBenchmarkSummary:
    results: list[VerifiedEvalResult] = []
    legal_total = 0
    legal_semantic_correct = 0
    legal_blocked = 0
    no_candidate_total = 0
    no_candidate_blocked = 0
    false_accepts = 0
    wrong_legal_candidates = 0
    intent_guard_rejections = 0
    semantic_rejections = 0
    verifier_errors = 0

    for case in cases:
        translated = adapter.translate(case.text)
        accepted = translated.accepted
        actual_candidate = translated.candidate
        faithfulness = translated.faithfulness
        intent_guard = translated.intent_guard

        if translated.status is VerifiedTranslationStatus.INTENT_GUARD_REJECTED:
            intent_guard_rejections += 1
        elif translated.status is VerifiedTranslationStatus.SEMANTIC_REJECTED:
            semantic_rejections += 1
        elif translated.status is VerifiedTranslationStatus.VERIFIER_ERROR:
            verifier_errors += 1

        if case.expected_decision == "CANDIDATE":
            legal_total += 1
            candidate_correct = bool(
                accepted
                and actual_candidate is not None
                and case.expected_candidate is not None
                and semantically_equal_candidates(actual_candidate, case.expected_candidate)
            )
            if candidate_correct:
                legal_semantic_correct += 1
            elif accepted:
                wrong_legal_candidates += 1
            else:
                legal_blocked += 1
        else:
            no_candidate_total += 1
            candidate_correct = None
            if accepted:
                false_accepts += 1
            else:
                no_candidate_blocked += 1

        results.append(
            VerifiedEvalResult(
                case_id=case.case_id,
                category=case.category,
                text=case.text,
                pipeline_status=translated.status.value,
                pipeline_accepted=accepted,
                candidate_semantics_correct=candidate_correct,
                actual_candidate=actual_candidate,
                expected_candidate=case.expected_candidate,
                base_status=translated.base.status.value,
                intent_guard_decision=(
                    intent_guard.decision.value if intent_guard is not None else None
                ),
                intent_guard_reason=(
                    intent_guard.reason.value
                    if intent_guard is not None and intent_guard.reason is not None
                    else None
                ),
                faithfulness_decision=(
                    faithfulness.decision.value if faithfulness is not None else None
                ),
                faithfulness_reason=(
                    faithfulness.reason.value
                    if faithfulness is not None and faithfulness.reason is not None
                    else None
                ),
            )
        )

    return VerifiedBenchmarkSummary(
        provider=provider,
        model_name=model_name,
        total=len(results),
        legal_total=legal_total,
        legal_semantic_correct=legal_semantic_correct,
        legal_blocked=legal_blocked,
        no_candidate_total=no_candidate_total,
        no_candidate_blocked=no_candidate_blocked,
        false_accepts=false_accepts,
        wrong_legal_candidates=wrong_legal_candidates,
        intent_guard_rejections=intent_guard_rejections,
        semantic_rejections=semantic_rejections,
        verifier_errors=verifier_errors,
        results=tuple(results),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic intent guard + translator + RuleValidator + semantic verifier benchmark"
    )
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS_PATH))
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="mimo")
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()

    cases = load_corpus(Path(args.corpus))
    validate_corpus_against_rule_validator(cases)
    provider = _build_provider(args.provider, args.model, args.timeout_seconds)

    adapter = VerifiedNaturalLanguageRuleAdapter(
        NaturalLanguageRuleAdapter(GuidedRuleCandidateModel(provider)),
        NaturalLanguageRuleFaithfulnessVerifier(provider),
    )
    summary = run_verified_benchmark(
        adapter,
        cases,
        provider=args.provider,
        model_name=provider.model_name,
    )
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
