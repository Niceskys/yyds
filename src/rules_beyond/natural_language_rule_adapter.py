from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Mapping, Protocol

from .rule_dsl import RuleAST
from .rule_validator import RuleValidator, ValidationIssue


MAX_MODEL_OUTPUT_CHARS = 16_384


SYSTEM_PROMPT_V0_1 = """You translate one player's natural-language public rule for Rules Beyond V0.1.

Security / authority boundary:
- You do not execute game actions.
- You do not change GameState, HP, winner, max rounds, anti-stall, system rules, or AI objectives.
- Your output is untrusted. A deterministic RuleValidator makes the final decision.
- Never silently rewrite a disallowed or unsupported player intent into a different legal rule.
- Never invent a number, threshold, weapon, effect, or condition that the player did not state clearly.

Return ONLY one JSON object. No Markdown fences, prose, comments, or extra text.

Choose exactly one envelope:

1) If the player's intent can be represented faithfully and safely by the V0.1 DSL:
{
  \"decision\": \"CANDIDATE\",
  \"candidate\": {
    \"version\": \"v0.1\",
    \"target\": \"ALL_UNITS\",
    \"conditions\": [],
    \"effect\": {\"type\": \"...\"},
    \"duration\": \"UNTIL_REPLACED\"
  }
}

2) If the intent is disallowed, unsupported, ambiguous, or cannot be mapped without changing its meaning:
{
  \"decision\": \"NO_CANDIDATE\",
  \"reason_code\": \"DISALLOWED_INTENT|UNSUPPORTED_CAPABILITY|AMBIGUOUS|CANNOT_MAP_SAFELY\"
}

IMPORTANT JSON SHAPE RULES:
- Every condition MUST be a JSON object in the conditions array. Never emit a condition as a string such as \"SELF_HP_LTE(2)\".
- The effect MUST be a JSON object containing a \"type\" field. Never emit shorthand such as {\"BOW_RANGE_ADD\": 1}.
- Use only the exact field names shown below. Do not rename, abbreviate, nest, or invent fields.
- Include only fields required by that specific condition/effect shape.

Allowed condition JSON objects, maximum two, combined with AND:
{\"type\": \"SELF_HP_LTE\", \"value\": <integer>}
{\"type\": \"SELF_HP_GTE\", \"value\": <integer>}
{\"type\": \"SELF_HP_LT_OPPONENT\"}
{\"type\": \"SELF_HP_GT_OPPONENT\"}
{\"type\": \"DISTANCE_LTE\", \"value\": <integer>}
{\"type\": \"DISTANCE_GTE\", \"value\": <integer>}
{\"type\": \"ROUND_GTE\", \"value\": <integer>}
{\"type\": \"DID_NOT_MOVE_LAST_ROUND\"}
{\"type\": \"LAST_ATTACK_WEAPON_IS\", \"weapon\": \"KNIFE|BOW|NONE\"}
{\"type\": \"CONSECUTIVE_BOW_MISS_GTE\", \"value\": <integer>}
{\"type\": \"CONSECUTIVE_SAME_WEAPON_USE_GTE\", \"value\": <integer>}

Allowed effect JSON objects, exactly one:
{\"type\": \"MOVE_RANGE_ADD\", \"delta\": <integer>}
{\"type\": \"KNIFE_RANGE_ADD\", \"delta\": <integer>}
{\"type\": \"BOW_RANGE_ADD\", \"delta\": <integer>}
{\"type\": \"KNIFE_DAMAGE_ADD\", \"delta\": <integer>}
{\"type\": \"BOW_DAMAGE_ADD\", \"delta\": <integer>}
{\"type\": \"BOW_HIT_MULTIPLIER\", \"multiplier\": <number>}
{\"type\": \"WEAPON_COOLDOWN\", \"weapon\": \"KNIFE|BOW\", \"rounds\": 1}

Faithfulness rules:
- A numeric parameter may be used only when the player's wording provides that number unambiguously.
- Vague terms such as \"low HP\", \"more flexible\", \"stronger\", \"later\", or \"far away\" do NOT authorize you to guess a threshold, delta, multiplier, weapon, or round number. Use NO_CANDIDATE with AMBIGUOUS when required values are missing.
- If the player specifies a rule outside the allowed DSL, use NO_CANDIDATE. Do not approximate it with the nearest legal effect.
- If the player asks for faction-specific behavior, direct victory/death, direct HP assignment/healing, absolute coordinates, max-round changes, anti-stall changes, arbitrary code, or any other forbidden authority, use NO_CANDIDATE.

Examples of correct structure:
Player intent: \"生命值不高于3时，刀伤害增加1点。\"
Output:
{\"decision\":\"CANDIDATE\",\"candidate\":{\"version\":\"v0.1\",\"target\":\"ALL_UNITS\",\"conditions\":[{\"type\":\"SELF_HP_LTE\",\"value\":3}],\"effect\":{\"type\":\"KNIFE_DAMAGE_ADD\",\"delta\":1},\"duration\":\"UNTIL_REPLACED\"}}

Player intent: \"双方距离至少4格时，弓命中率变为原来的0.5倍。\"
Output:
{\"decision\":\"CANDIDATE\",\"candidate\":{\"version\":\"v0.1\",\"target\":\"ALL_UNITS\",\"conditions\":[{\"type\":\"DISTANCE_GTE\",\"value\":4}],\"effect\":{\"type\":\"BOW_HIT_MULTIPLIER\",\"multiplier\":0.5},\"duration\":\"UNTIL_REPLACED\"}}

Player intent: \"残血时更灵活一点。\"
Output:
{\"decision\":\"NO_CANDIDATE\",\"reason_code\":\"AMBIGUOUS\"}

Player intent: \"只让蓝方刀伤害增加1点。\"
Output:
{\"decision\":\"NO_CANDIDATE\",\"reason_code\":\"DISALLOWED_INTENT\"}

Never target RED, BLUE, a unit id, a coordinate, or a winner. Never invent fields or capabilities not listed above.
"""


class TranslationStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    NO_CANDIDATE = "NO_CANDIDATE"
    INPUT_REJECTED = "INPUT_REJECTED"
    MODEL_ERROR = "MODEL_ERROR"
    MODEL_PROTOCOL_ERROR = "MODEL_PROTOCOL_ERROR"
    OUTPUT_TOO_LARGE = "OUTPUT_TOO_LARGE"
    JSON_DECODE_ERROR = "JSON_DECODE_ERROR"
    CANDIDATE_NOT_OBJECT = "CANDIDATE_NOT_OBJECT"
    RULE_REJECTED = "RULE_REJECTED"


class NoCandidateReason(str, Enum):
    DISALLOWED_INTENT = "DISALLOWED_INTENT"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    AMBIGUOUS = "AMBIGUOUS"
    CANNOT_MAP_SAFELY = "CANNOT_MAP_SAFELY"


class RuleCandidateModel(Protocol):
    """Provider-neutral boundary for one model call.

    Implementations may call GLM or another LLM later. The core package only
    accepts returned text and never gives the model direct access to Engine or
    GameState mutation APIs.
    """

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str: ...


@dataclass(frozen=True, slots=True)
class NaturalLanguageTranslation:
    status: TranslationStatus
    player_text: str
    raw_model_output: str | None
    candidate: Mapping[str, Any] | None
    rule: RuleAST | None
    validation_issues: tuple[ValidationIssue, ...] = ()
    no_candidate_reason: NoCandidateReason | None = None
    error_message: str | None = None

    @property
    def accepted(self) -> bool:
        return self.status is TranslationStatus.ACCEPTED and self.rule is not None


class NaturalLanguageRuleAdapter:
    """Strict Natural Language -> untrusted envelope -> RuleValidator adapter.

    Prompt compliance is never treated as a security boundary. A candidate is
    accepted only after deterministic V0.1 RuleValidator validation.
    """

    def __init__(
        self,
        model: RuleCandidateModel,
        validator: RuleValidator | None = None,
        *,
        max_model_output_chars: int = MAX_MODEL_OUTPUT_CHARS,
    ) -> None:
        if max_model_output_chars <= 0:
            raise ValueError("max_model_output_chars must be positive")
        self.model = model
        self.validator = validator or RuleValidator()
        self.max_model_output_chars = max_model_output_chars

    def translate(self, player_text: str) -> NaturalLanguageTranslation:
        if not isinstance(player_text, str) or not player_text.strip():
            return NaturalLanguageTranslation(
                status=TranslationStatus.INPUT_REJECTED,
                player_text=player_text if isinstance(player_text, str) else "",
                raw_model_output=None,
                candidate=None,
                rule=None,
                error_message="player_text must be a non-empty string",
            )

        try:
            raw = self.model.generate_candidate(
                system_prompt=SYSTEM_PROMPT_V0_1,
                player_text=player_text,
            )
        except Exception as exc:  # provider/network failures stay outside the game engine
            return NaturalLanguageTranslation(
                status=TranslationStatus.MODEL_ERROR,
                player_text=player_text,
                raw_model_output=None,
                candidate=None,
                rule=None,
                error_message=f"model call failed: {type(exc).__name__}",
            )

        if not isinstance(raw, str):
            return NaturalLanguageTranslation(
                status=TranslationStatus.MODEL_PROTOCOL_ERROR,
                player_text=player_text,
                raw_model_output=None,
                candidate=None,
                rule=None,
                error_message="model provider must return a string",
            )

        if len(raw) > self.max_model_output_chars:
            return NaturalLanguageTranslation(
                status=TranslationStatus.OUTPUT_TOO_LARGE,
                player_text=player_text,
                raw_model_output=raw[: self.max_model_output_chars],
                candidate=None,
                rule=None,
                error_message="model output exceeded the configured size limit",
            )

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return NaturalLanguageTranslation(
                status=TranslationStatus.JSON_DECODE_ERROR,
                player_text=player_text,
                raw_model_output=raw,
                candidate=None,
                rule=None,
                error_message="model output must be exactly one JSON object",
            )

        if not isinstance(decoded, dict):
            return NaturalLanguageTranslation(
                status=TranslationStatus.MODEL_PROTOCOL_ERROR,
                player_text=player_text,
                raw_model_output=raw,
                candidate=None,
                rule=None,
                error_message="decoded model output must be one envelope object",
            )

        decision = decoded.get("decision")
        if decision == "NO_CANDIDATE":
            if set(decoded) != {"decision", "reason_code"}:
                return self._protocol_error(player_text, raw, "NO_CANDIDATE envelope has invalid fields")
            try:
                reason = NoCandidateReason(decoded.get("reason_code"))
            except (TypeError, ValueError):
                return self._protocol_error(player_text, raw, "NO_CANDIDATE reason_code is invalid")
            return NaturalLanguageTranslation(
                status=TranslationStatus.NO_CANDIDATE,
                player_text=player_text,
                raw_model_output=raw,
                candidate=None,
                rule=None,
                no_candidate_reason=reason,
            )

        if decision != "CANDIDATE":
            return self._protocol_error(player_text, raw, "decision must be CANDIDATE or NO_CANDIDATE")

        if set(decoded) != {"decision", "candidate"}:
            return self._protocol_error(player_text, raw, "CANDIDATE envelope has invalid fields")

        candidate = decoded.get("candidate")
        if not isinstance(candidate, dict):
            return NaturalLanguageTranslation(
                status=TranslationStatus.CANDIDATE_NOT_OBJECT,
                player_text=player_text,
                raw_model_output=raw,
                candidate=None,
                rule=None,
                error_message="candidate must be a JSON object",
            )

        validation = self.validator.validate(candidate)
        if not validation.accepted or validation.rule is None:
            return NaturalLanguageTranslation(
                status=TranslationStatus.RULE_REJECTED,
                player_text=player_text,
                raw_model_output=raw,
                candidate=candidate,
                rule=None,
                validation_issues=validation.issues,
                error_message="candidate was rejected by RuleValidator",
            )

        return NaturalLanguageTranslation(
            status=TranslationStatus.ACCEPTED,
            player_text=player_text,
            raw_model_output=raw,
            candidate=candidate,
            rule=validation.rule,
            validation_issues=(),
            error_message=None,
        )

    @staticmethod
    def _protocol_error(
        player_text: str,
        raw: str,
        message: str,
    ) -> NaturalLanguageTranslation:
        return NaturalLanguageTranslation(
            status=TranslationStatus.MODEL_PROTOCOL_ERROR,
            player_text=player_text,
            raw_model_output=raw,
            candidate=None,
            rule=None,
            error_message=message,
        )
