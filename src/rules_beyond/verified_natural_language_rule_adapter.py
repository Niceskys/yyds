from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .natural_language_rule_adapter import (
    NaturalLanguageRuleAdapter,
    NaturalLanguageTranslation,
    NoCandidateReason,
    TranslationStatus,
)
from .rule_dsl import RuleAST
from .rule_faithfulness import (
    FaithfulnessDecision,
    FaithfulnessResult,
    NaturalLanguageRuleFaithfulnessVerifier,
)
from .rule_intent_guard import IntentGuardResult, guard_player_intent_v0_1


class VerifiedTranslationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    INTENT_GUARD_REJECTED = "INTENT_GUARD_REJECTED"
    BASE_REJECTED = "BASE_REJECTED"
    SEMANTIC_REJECTED = "SEMANTIC_REJECTED"
    VERIFIER_ERROR = "VERIFIER_ERROR"


@dataclass(frozen=True, slots=True)
class VerifiedNaturalLanguageTranslation:
    status: VerifiedTranslationStatus
    base: NaturalLanguageTranslation
    faithfulness: FaithfulnessResult | None
    intent_guard: IntentGuardResult | None = None

    @property
    def accepted(self) -> bool:
        return self.status is VerifiedTranslationStatus.ACCEPTED

    @property
    def candidate(self) -> Mapping[str, object] | None:
        if not self.accepted:
            return None
        return self.base.candidate

    @property
    def rule(self) -> RuleAST | None:
        if not self.accepted:
            return None
        return self.base.rule


class VerifiedNaturalLanguageRuleAdapter:
    """Deterministic intent guard + translator + validator + semantic verifier.

    The deterministic guard is deliberately narrow and catches only explicit
    unsupported logic that V0.1 cannot represent faithfully. Candidates that
    pass it still require both deterministic RuleValidator acceptance and the
    independent semantic faithfulness verdict. No rejection path exposes an
    executable candidate/rule downstream.
    """

    def __init__(
        self,
        base_adapter: NaturalLanguageRuleAdapter,
        faithfulness_verifier: NaturalLanguageRuleFaithfulnessVerifier,
    ) -> None:
        self.base_adapter = base_adapter
        self.faithfulness_verifier = faithfulness_verifier

    def translate(self, player_text: str) -> VerifiedNaturalLanguageTranslation:
        guard = guard_player_intent_v0_1(player_text)
        if not guard.allowed:
            base = NaturalLanguageTranslation(
                status=TranslationStatus.NO_CANDIDATE,
                player_text=player_text,
                raw_model_output=None,
                candidate=None,
                rule=None,
                no_candidate_reason=NoCandidateReason.CANNOT_MAP_SAFELY,
                error_message="deterministic intent guard rejected unsupported explicit OR logic",
            )
            return VerifiedNaturalLanguageTranslation(
                status=VerifiedTranslationStatus.INTENT_GUARD_REJECTED,
                base=base,
                faithfulness=None,
                intent_guard=guard,
            )

        base = self.base_adapter.translate(player_text)
        if not base.accepted or base.candidate is None or base.rule is None:
            return VerifiedNaturalLanguageTranslation(
                status=VerifiedTranslationStatus.BASE_REJECTED,
                base=base,
                faithfulness=None,
                intent_guard=guard,
            )

        faithfulness = self.faithfulness_verifier.verify(
            player_text=player_text,
            candidate=base.candidate,
        )
        if faithfulness.decision is FaithfulnessDecision.FAITHFUL:
            return VerifiedNaturalLanguageTranslation(
                status=VerifiedTranslationStatus.ACCEPTED,
                base=base,
                faithfulness=faithfulness,
                intent_guard=guard,
            )
        if faithfulness.decision is FaithfulnessDecision.REJECT:
            return VerifiedNaturalLanguageTranslation(
                status=VerifiedTranslationStatus.SEMANTIC_REJECTED,
                base=base,
                faithfulness=faithfulness,
                intent_guard=guard,
            )
        return VerifiedNaturalLanguageTranslation(
            status=VerifiedTranslationStatus.VERIFIER_ERROR,
            base=base,
            faithfulness=faithfulness,
            intent_guard=guard,
        )
