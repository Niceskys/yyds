from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


class IntentGuardDecision(str, Enum):
    ALLOW = "ALLOW"
    REJECT = "REJECT"


class IntentGuardReason(str, Enum):
    EXPLICIT_OR_UNSUPPORTED = "EXPLICIT_OR_UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class IntentGuardResult:
    decision: IntentGuardDecision
    reason: IntentGuardReason | None = None

    @property
    def allowed(self) -> bool:
        return self.decision is IntentGuardDecision.ALLOW


_ENGLISH_OR = re.compile(r"\bor\b", re.IGNORECASE)
_CHINESE_OR_MARKERS = ("或者", "或是", "要么")


def guard_player_intent_v0_1(player_text: str) -> IntentGuardResult:
    """Reject explicit OR logic before any model call.

    V0.1 conditions are AND-only. This guard is intentionally narrow: it does
    not try to parse arbitrary natural language or replace the faithfulness
    verifier. It only catches explicit OR markers that cannot be represented
    faithfully by the current DSL.
    """

    if any(marker in player_text for marker in _CHINESE_OR_MARKERS) or _ENGLISH_OR.search(player_text):
        return IntentGuardResult(
            decision=IntentGuardDecision.REJECT,
            reason=IntentGuardReason.EXPLICIT_OR_UNSUPPORTED,
        )
    return IntentGuardResult(decision=IntentGuardDecision.ALLOW)
