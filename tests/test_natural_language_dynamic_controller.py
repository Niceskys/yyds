import json

import pytest

from rules_beyond.dynamic_rule_controller import DynamicRuleController
from rules_beyond.model import Action, GameConfig, Team
from rules_beyond.natural_language_dynamic_controller import VerifiedNaturalLanguageDynamicController
from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from rules_beyond.rule_validator import RuleValidator
from rules_beyond.verified_natural_language_rule_adapter import (
    VerifiedNaturalLanguageRuleAdapter,
    VerifiedTranslationStatus,
)


BOW_PLUS_ONE = {
    "version": "v0.1",
    "target": "ALL_UNITS",
    "conditions": [],
    "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
    "duration": "UNTIL_REPLACED",
}
MOVE_PLUS_ONE = {
    "version": "v0.1",
    "target": "ALL_UNITS",
    "conditions": [],
    "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
    "duration": "UNTIL_REPLACED",
}


class ScriptedModel:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        self.calls.append((system_prompt, player_text))
        if "strict semantic verifier" in system_prompt:
            return json.dumps({"decision": "FAITHFUL"})
        if player_text == "弓射程增加1格。":
            return json.dumps({"decision": "CANDIDATE", "candidate": BOW_PLUS_ONE})
        if player_text == "移动距离增加1格。":
            return json.dumps({"decision": "CANDIDATE", "candidate": MOVE_PLUS_ONE})
        return json.dumps({"decision": "NO_CANDIDATE", "reason_code": "UNSUPPORTED_CAPABILITY"})


def make_controller(config: GameConfig | None = None):
    config = config or GameConfig()
    model = ScriptedModel()
    base = NaturalLanguageRuleAdapter(model, RuleValidator(config))
    verified = VerifiedNaturalLanguageRuleAdapter(
        base,
        NaturalLanguageRuleFaithfulnessVerifier(model),
    )
    return VerifiedNaturalLanguageDynamicController(verified, config), model


def resolve_to_first_due_phase(controller, state):
    while not state.rule_phase_due:
        resolved = controller.controller.resolve_round(
            state,
            {Team.RED: Action(), Team.BLUE: Action()},
            match_seed=123,
        )
        state = resolved.state
    return state


def test_accepted_initial_text_is_revalidated_and_becomes_active_rule() -> None:
    controller, _ = make_controller()

    started = controller.start_match("弓射程增加1格。")

    assert started.phase.translation_accepted
    assert started.phase.controller_phase.accepted
    assert started.phase.controller_phase.replaced
    assert started.state.active_rule is not None
    assert started.state.active_rule.effect.type.value == "BOW_RANGE_ADD"
    assert started.state.active_rule.effect.delta == 1


def test_rejected_text_carries_previous_rule_without_exposing_candidate() -> None:
    controller, _ = make_controller()
    started = controller.start_match("弓射程增加1格。")
    previous_rule = started.state.active_rule
    due_state = resolve_to_first_due_phase(controller, started.state)

    applied = controller.apply_due_rule_phase(due_state, "给单位回血1点。")

    assert applied.phase.translation is not None
    assert applied.phase.translation.status is VerifiedTranslationStatus.BASE_REJECTED
    assert not applied.phase.translation_accepted
    assert applied.phase.carried_forward_after_translation_rejection
    assert applied.state.active_rule == previous_rule
    assert not applied.phase.controller_phase.replaced


def test_explicit_or_is_guard_rejected_before_model_call_and_rule_is_carried() -> None:
    controller, model = make_controller()
    started = controller.start_match("弓射程增加1格。")
    due_state = resolve_to_first_due_phase(controller, started.state)
    calls_before = len(model.calls)

    applied = controller.apply_due_rule_phase(
        due_state,
        "生命值不超过2或者上一回合没移动时，弓射程增加1格。",
    )

    assert applied.phase.translation is not None
    assert applied.phase.translation.status is VerifiedTranslationStatus.INTENT_GUARD_REJECTED
    assert len(model.calls) == calls_before
    assert applied.state.active_rule == started.state.active_rule


def test_due_phase_can_replace_rule_from_second_accepted_text() -> None:
    controller, _ = make_controller()
    started = controller.start_match("弓射程增加1格。")
    due_state = resolve_to_first_due_phase(controller, started.state)

    applied = controller.apply_due_rule_phase(due_state, "移动距离增加1格。")

    assert applied.phase.translation_accepted
    assert applied.phase.controller_phase.replaced
    assert applied.state.active_rule is not None
    assert applied.state.active_rule.effect.type.value == "MOVE_RANGE_ADD"


def test_adapter_and_dynamic_controller_configs_must_match() -> None:
    adapter_config = GameConfig(initial_hp=5)
    controller_config = GameConfig(initial_hp=4)
    model = ScriptedModel()
    base = NaturalLanguageRuleAdapter(model, RuleValidator(adapter_config))
    verified = VerifiedNaturalLanguageRuleAdapter(
        base,
        NaturalLanguageRuleFaithfulnessVerifier(model),
    )

    with pytest.raises(ValueError, match="adapter RuleValidator config"):
        VerifiedNaturalLanguageDynamicController(
            verified,
            controller=DynamicRuleController(controller_config),
        )
