from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Mapping

from .natural_language_rule_adapter import NaturalLanguageRuleAdapter, NaturalLanguageTranslation
from .rule_dsl import RuleAST
from .rule_faithfulness import (
    FaithfulnessDecision,
    FaithfulnessReason,
    FaithfulnessResult,
    NaturalLanguageRuleFaithfulnessVerifier,
)


_EXPLICIT_DISJUNCTION_MARKERS = (
    "或者",
    "或者是",
    "或是",
    "满足任一",
    "任一条件",
    "任意一个条件",
    "任意一项",
    "二者之一",
)


def has_explicit_unsupported_disjunction(player_text: str) -> bool:
    """Detect explicit OR-style logic that V0.1 cannot represent faithfully.

    V0.1 condition lists are AND-only. This guard intentionally targets clear
    disjunction forms instead of every occurrence of the Chinese character
    ``或`` because valid threshold phrases such as ``1点或更少`` mean <= rather
    than boolean OR.
    """

    normalized = player_text.strip().lower()
    if any(marker in normalized for marker in _EXPLICIT_DISJUNCTION_MARKERS):
        return True
    return bool(re.search(r"\beither\b.*\bor\b", normalized))


class VerifiedTranslationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    BASE_REJECTED = "BASE_REJECTED"
    SEMANTIC_REJECTED = "SEMANTIC_REJECTED"
    VERIFIER_ERROR = "VERIFIER_ERROR"


@dataclass(frozen=True, slots=True)
class VerifiedNaturalLanguageTranslation:
    status: VerifiedTranslationStatus
    base: NaturalLanguageTranslation
    faithfulness: FaithfulnessResult | None

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
    """Translator + deterministic validator + semantic faithfulness gate.

    Only candidates already accepted by the base adapter may reach the semantic
    verifier. Before that model call, deterministic semantic guards reject
    player intent that the V0.1 DSL cannot represent by construction. The
    verifier never repairs a candidate. Any verifier uncertainty fails closed
    and exposes no executable candidate/rule to downstream code.
    """

    def __init__(
        self,
        base_adapter: NaturalLanguageRuleAdapter,
        faithfulness_verifier: NaturalLanguageRuleFaithfulnessVerifier,
    ) -> None:
        self.base_adapter = base_adapter
        self.faithfulness_verifier = faithfulness_verifier

    def translate(self, player_text: str) -> VerifiedNaturalLanguageTranslation:
        base = self.base_adapter.translate(player_text)
        if not base.accepted or base.candidate is None or base.rule is None:
            return VerifiedNaturalLanguageTranslation(
                status=VerifiedTranslationStatus.BASE_REJECTED,
                base=base,
                faithfulness=None,
            )

        if has_explicit_unsupported_disjunction(player_text):
            return VerifiedNaturalLanguageTranslation(
                status=VerifiedTranslationStatus.SEMANTIC_REJECTED,
                base=base,
                faithfulness=FaithfulnessResult(
                    decision=FaithfulnessDecision.REJECT,
                    raw_model_output=None,
                    reason=FaithfulnessReason.ALTERED_INTENT,
                    error_message="V0.1 conditions are AND-only; explicit disjunction cannot be executed faithfully",
                ),
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
            )
        if faithfulness.decision is FaithfulnessDecision.REJECT:
            return VerifiedNaturalLanguageTranslation(
                status=VerifiedTranslationStatus.SEMANTIC_REJECTED,
                base=base,
                faithfulness=faithfulness,
            )
        return VerifiedNaturalLanguageTranslation(
            status=VerifiedTranslationStatus.VERIFIER_ERROR,
            base=base,
            faithfulness=faithfulness,
        )
