import json

from rules_beyond.live_natural_language_dynamic_match import (
    LIVE_MATCH_CONFIG,
    LIVE_MATCH_SEEDS,
    LIVE_NL_SCHEDULE,
    assert_live_dynamic_match_gate,
    play_live_match,
)
from rules_beyond.natural_language_dynamic_controller import VerifiedNaturalLanguageDynamicController
from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from rules_beyond.rule_validator import RuleValidator
from rules_beyond.verified_natural_language_rule_adapter import VerifiedNaturalLanguageRuleAdapter


PHASE_CANDIDATES = {
    LIVE_NL_SCHEDULE[1]: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": "KNIFE_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    LIVE_NL_SCHEDULE[2]: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    LIVE_NL_SCHEDULE[4]: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "DISTANCE_GTE", "value": 3}],
        "effect": {"type": "BOW_HIT_MULTIPLIER", "multiplier": 0.5},
        "duration": "UNTIL_REPLACED",
    },
    LIVE_NL_SCHEDULE[5]: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "CONSECUTIVE_SAME_WEAPON_USE_GTE", "value": 2}],
        "effect": {"type": "WEAPON_COOLDOWN", "weapon": "BOW", "rounds": 1},
        "duration": "UNTIL_REPLACED",
    },
}


class GateOracleModel:
    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        if "strict semantic verifier" in system_prompt:
            return json.dumps({"decision": "FAITHFUL"})
        candidate = PHASE_CANDIDATES[player_text]
        return json.dumps(
            {"decision": "CANDIDATE", "candidate": candidate},
            ensure_ascii=False,
        )


def make_controller() -> VerifiedNaturalLanguageDynamicController:
    model = GateOracleModel()
    validator = RuleValidator(LIVE_MATCH_CONFIG)
    base = NaturalLanguageRuleAdapter(model, validator)
    verified = VerifiedNaturalLanguageRuleAdapter(
        base,
        NaturalLanguageRuleFaithfulnessVerifier(model),
    )
    return VerifiedNaturalLanguageDynamicController(verified, LIVE_MATCH_CONFIG)


def test_offline_oracle_exercises_full_dynamic_natural_language_gate() -> None:
    traces = tuple(
        play_live_match(make_controller(), seed=seed)
        for seed in LIVE_MATCH_SEEDS
    )

    assert_live_dynamic_match_gate(traces)

    assert all(trace.post_intermission_behavior_changed for trace in traces)
    assert all(trace.rule_modifier_events > 0 for trace in traces)
    assert all({0, 1, 2}.issubset({phase.phase_index for phase in trace.phases}) for trace in traces)

    for trace in traces:
        phase2 = next(phase for phase in trace.phases if phase.phase_index == 2)
        assert phase2.translation_status == "INTENT_GUARD_REJECTED"
        assert phase2.carried_forward_after_translation_rejection
        assert not phase2.controller_replaced
