from __future__ import annotations

from .natural_language_rule_adapter import RuleCandidateModel


TRANSLATOR_GUIDANCE_V0_1_1 = """
Additional V0.1 mapping guidance:
- A listed ADD effect may use a negative delta when the player explicitly asks to reduce that stat. Do not reject solely because delta is negative; emit the faithful candidate and let deterministic RuleValidator enforce numeric bounds.
- LAST_ATTACK_WEAPON_IS supports KNIFE, BOW, and NONE. Player wording such as "上一回合没有进行攻击" maps to weapon NONE.
- WEAPON_COOLDOWN is supported for KNIFE or BOW when rounds is exactly 1.
- CONSECUTIVE_SAME_WEAPON_USE_GTE may be combined with WEAPON_COOLDOWN when that is exactly what the player asks.
- Up to two conditions combined with AND are supported.
- An unqualified public rule applies symmetrically to ALL_UNITS. This fixed target is DSL scaffolding, not an invented faction preference.
- If the player does not state a temporary duration, use the fixed DSL duration UNTIL_REPLACED. If the player explicitly requests a different/temporary duration, return NO_CANDIDATE instead of erasing that duration.
- Do not reject a faithfully representable candidate merely because RuleValidator may later reject its numeric bounds. The validator, not the model, is authoritative for final numeric legality.
"""


class GuidedRuleCandidateModel:
    """Provider-neutral translator wrapper that appends frozen mapping guidance.

    This wrapper changes only the translator system prompt. It does not parse,
    repair, validate, or execute candidates and has no Engine/GameState access.
    """

    def __init__(self, model: RuleCandidateModel) -> None:
        self.model = model

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        return self.model.generate_candidate(
            system_prompt=f"{system_prompt.rstrip()}\n\n{TRANSLATOR_GUIDANCE_V0_1_1.strip()}\n",
            player_text=player_text,
        )
