from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Mapping

from .natural_language_rule_adapter import RuleCandidateModel


FAITHFULNESS_PROMPT_V0_1 = """You are a strict semantic verifier for Rules Beyond V0.1.

You receive a player's original natural-language rule and one already validator-legal RuleAST candidate.
Your only task is to decide whether the candidate preserves the player's complete meaning exactly enough for safe execution.

Important:
- Do NOT repair, rewrite, simplify, or improve the candidate.
- Do NOT judge whether the candidate is syntactically legal; deterministic RuleValidator already did that.
- Reject if any part of the player's intent is dropped, weakened, strengthened, substituted, guessed, or approximated.
- Logical connective fidelity is mandatory. Having the same atomic conditions is NOT enough: OR changed to AND, AND changed to OR, or NOT removed/rewritten is ALTERED_INTENT and must be rejected.
- Reject if OR/NOT logic, a third condition, a second effect, a temporary duration, a faction restriction, a number, a weapon, a threshold, or another semantic fragment from the original text is absent from the candidate.
- Reject if the candidate adds any semantic condition/effect/number not stated by the player.
- If you cannot confidently prove full semantic coverage, reject.

V0.1 semantic equivalence rules you MUST honor:
- version=v0.1, target=ALL_UNITS, and duration=UNTIL_REPLACED are fixed DSL scaffolding when the player does not explicitly request a conflicting target/duration. Their presence alone is NOT added intent.
- If the player explicitly asks for a faction-specific target or temporary/different duration, a candidate using the fixed defaults is NOT faithful.
- Conditions in a legal V0.1 RuleAST are AND-only and commutative: A AND B is semantically identical to B AND A. This equivalence applies ONLY when the original player intent is also AND. Never treat an original OR as equivalent to candidate AND.
- "第N回合起" or "第N回合开始" corresponds to ROUND_GTE(N).
- "上一回合没有实际移动" corresponds to DID_NOT_MOVE_LAST_ROUND.
- "上一回合没有进行攻击" corresponds to LAST_ATTACK_WEAPON_IS with weapon NONE.
- "上一回合使用弓/刀" corresponds to LAST_ATTACK_WEAPON_IS with BOW/KNIFE.
- "连续N回合使用同一种武器" corresponds to CONSECUTIVE_SAME_WEAPON_USE_GTE(N).
- "连续N次弓箭未命中" corresponds to CONSECUTIVE_BOW_MISS_GTE(N).
- "弓命中率变为原来的75%" corresponds to BOW_HIT_MULTIPLIER 0.75; "减半" is 0.5; "2倍" is 2.0.
- "弓/刀冷却1回合" corresponds to WEAPON_COOLDOWN for that weapon with rounds=1.
- A conditional cooldown is faithful when the condition matches the original trigger and WEAPON_COOLDOWN rounds=1 matches the requested one-round cooldown. Rule duration=UNTIL_REPLACED is only the lifespan of the public rule; it does NOT mean a triggered cooldown lasts forever.
- A negative ADD delta faithfully represents an explicit decrease, e.g. "伤害减少1" -> delta=-1.

Return ONLY one JSON object.

Faithful:
{"decision":"FAITHFUL"}

Not faithful:
{"decision":"REJECT","reason_code":"DROPPED_INTENT|ALTERED_INTENT|ADDED_INTENT|AMBIGUOUS_COVERAGE"}

Examples:
Original: 生命值不高于2或者距离至少4格时，弓射程增加1格。
Candidate: one condition SELF_HP_LTE=2, BOW_RANGE_ADD=1
Result: {"decision":"REJECT","reason_code":"DROPPED_INTENT"}

Original: 生命值不高于2或者上一回合没移动时，弓射程增加1格。
Candidate: SELF_HP_LTE=2 AND DID_NOT_MOVE_LAST_ROUND, BOW_RANGE_ADD=1
Result: {"decision":"REJECT","reason_code":"ALTERED_INTENT"}

Original: 生命值不高于2并且距离至少4格时，弓射程增加1格。
Candidate: SELF_HP_LTE=2 AND DISTANCE_GTE=4, BOW_RANGE_ADD=1
Result: {"decision":"FAITHFUL"}

Original: 第12回合起，如果上一回合没有实际移动，刀射程增加1格。
Candidate: ROUND_GTE=12 AND DID_NOT_MOVE_LAST_ROUND, KNIFE_RANGE_ADD=1
Result: {"decision":"FAITHFUL"}

Original: 上一轮使用了弓的单位，本轮弓需要冷却1回合。
Candidate: LAST_ATTACK_WEAPON_IS=BOW, WEAPON_COOLDOWN(BOW, rounds=1), duration=UNTIL_REPLACED
Result: {"decision":"FAITHFUL"}

Original: 上一回合不是使用弓的单位，移动距离增加1格。
Candidate: LAST_ATTACK_WEAPON_IS=KNIFE, MOVE_RANGE_ADD=1
Result: {"decision":"REJECT","reason_code":"DROPPED_INTENT"}
"""


class FaithfulnessDecision(str, Enum):
    FAITHFUL = "FAITHFUL"
    REJECT = "REJECT"
    MODEL_ERROR = "MODEL_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"


class FaithfulnessReason(str, Enum):
    DROPPED_INTENT = "DROPPED_INTENT"
    ALTERED_INTENT = "ALTERED_INTENT"
    ADDED_INTENT = "ADDED_INTENT"
    AMBIGUOUS_COVERAGE = "AMBIGUOUS_COVERAGE"


@dataclass(frozen=True, slots=True)
class FaithfulnessResult:
    decision: FaithfulnessDecision
    raw_model_output: str | None
    reason: FaithfulnessReason | None = None
    error_message: str | None = None

    @property
    def faithful(self) -> bool:
        return self.decision is FaithfulnessDecision.FAITHFUL


class NaturalLanguageRuleFaithfulnessVerifier:
    """Second model gate that checks semantic coverage only.

    The verifier receives no GameState and has no Engine mutation capability.
    Any model/protocol uncertainty fails closed.
    """

    def __init__(self, model: RuleCandidateModel, *, max_output_chars: int = 4096) -> None:
        if max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self.model = model
        self.max_output_chars = max_output_chars

    def verify(self, *, player_text: str, candidate: Mapping[str, object]) -> FaithfulnessResult:
        payload = {
            "player_text": player_text,
            "candidate": candidate,
        }
        try:
            raw = self.model.generate_candidate(
                system_prompt=FAITHFULNESS_PROMPT_V0_1,
                player_text=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception as exc:
            return FaithfulnessResult(
                decision=FaithfulnessDecision.MODEL_ERROR,
                raw_model_output=None,
                error_message=f"faithfulness model call failed: {type(exc).__name__}",
            )

        if not isinstance(raw, str):
            return FaithfulnessResult(
                decision=FaithfulnessDecision.PROTOCOL_ERROR,
                raw_model_output=None,
                error_message="faithfulness provider must return a string",
            )
        if len(raw) > self.max_output_chars:
            return FaithfulnessResult(
                decision=FaithfulnessDecision.PROTOCOL_ERROR,
                raw_model_output=raw[: self.max_output_chars],
                error_message="faithfulness output exceeded size limit",
            )

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return FaithfulnessResult(
                decision=FaithfulnessDecision.PROTOCOL_ERROR,
                raw_model_output=raw,
                error_message="faithfulness output must be one JSON object",
            )
        if not isinstance(decoded, dict):
            return FaithfulnessResult(
                decision=FaithfulnessDecision.PROTOCOL_ERROR,
                raw_model_output=raw,
                error_message="faithfulness output root must be an object",
            )

        decision = decoded.get("decision")
        if decision == "FAITHFUL":
            if set(decoded) != {"decision"}:
                return self._protocol_error(raw, "FAITHFUL envelope has invalid fields")
            return FaithfulnessResult(FaithfulnessDecision.FAITHFUL, raw)

        if decision == "REJECT":
            if set(decoded) != {"decision", "reason_code"}:
                return self._protocol_error(raw, "REJECT envelope has invalid fields")
            try:
                reason = FaithfulnessReason(decoded.get("reason_code"))
            except (TypeError, ValueError):
                return self._protocol_error(raw, "faithfulness reason_code is invalid")
            return FaithfulnessResult(FaithfulnessDecision.REJECT, raw, reason=reason)

        return self._protocol_error(raw, "decision must be FAITHFUL or REJECT")

    @staticmethod
    def _protocol_error(raw: str, message: str) -> FaithfulnessResult:
        return FaithfulnessResult(
            decision=FaithfulnessDecision.PROTOCOL_ERROR,
            raw_model_output=raw,
            error_message=message,
        )
