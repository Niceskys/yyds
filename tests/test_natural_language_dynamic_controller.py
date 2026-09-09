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


def resolve_to_next_intermission(controller, state, *, match_seed):
    resolved = controller.resolve_round(
        state,
        {Team.RED: Action(), Team.BLUE: Action()},
        match_seed=match_seed,
    )
    assert resolved.state.in_intermission is True
    return resolved.state


def test_start_match_has_no_pre_game_rule_and_round_one_is_ready() -> None:
    controller, model = make_controller()

    started = controller.start_match()

    assert started.state.active_rule is None
    assert started.state.game_state.round_no == 1
    assert started.state.can_submit_rule is False
    assert model.calls == []


def test_first_intermission_accepts_revalidated_text_as_active_rule() -> None:
    controller, _ = make_controller()
    state = resolve_to_next_intermission(
        controller,
        controller.start_match().state,
        match_seed=11,
    )

    applied = controller.submit_rule(state, "弓射程增加1格。")

    assert applied.attempt.translation_accepted
    assert applied.attempt.outcome.accepted
    assert applied.attempt.outcome.replaced
    assert applied.state.active_rule is not None
    assert applied.state.active_rule.effect.type.value == "BOW_RANGE_ADD"
    assert applied.state.active_rule.effect.delta == 1
    assert applied.state.rule_change_count == 1


def test_rejected_text_keeps_previous_rule_and_leaves_intermission_open() -> None:
    controller, _ = make_controller()
    first = resolve_to_next_intermission(
        controller,
        controller.start_match().state,
        match_seed=21,
    )
    accepted = controller.submit_rule(first, "弓射程增加1格。")
    previous_rule = accepted.state.active_rule
    continued = controller.continue_match(accepted.state).state
    second = resolve_to_next_intermission(controller, continued, match_seed=22)

    applied = controller.submit_rule(second, "给单位回血1点。")

    assert applied.attempt.translation is not None
    assert applied.attempt.translation.status is VerifiedTranslationStatus.BASE_REJECTED
    assert not applied.attempt.translation_accepted
    assert applied.attempt.carried_forward_after_translation_rejection
    assert applied.state.active_rule == previous_rule
    assert applied.state.rule_change_count == 1
    assert applied.state.in_intermission is True
    assert applied.state.can_submit_rule is True
    assert not applied.attempt.outcome.replaced

    retry = controller.submit_rule(applied.state, "移动距离增加1格。")

    assert retry.attempt.translation_accepted
    assert retry.attempt.outcome.accepted
    assert retry.state.active_rule is not None
    assert retry.state.active_rule.effect.type.value == "MOVE_RANGE_ADD"
    assert retry.state.rule_change_count == 2


def test_explicit_or_is_guard_rejected_before_model_call_and_rule_is_carried() -> None:
    controller, model = make_controller()
    first = resolve_to_next_intermission(
        controller,
        controller.start_match().state,
        match_seed=31,
    )
    accepted = controller.submit_rule(first, "弓射程增加1格。")
    continued = controller.continue_match(accepted.state).state
    second = resolve_to_next_intermission(controller, continued, match_seed=32)
    calls_before = len(model.calls)

    applied = controller.submit_rule(
        second,
        "生命值不超过2或者上一回合没移动时，弓射程增加1格。",
    )

    assert applied.attempt.translation is not None
    assert applied.attempt.translation.status is VerifiedTranslationStatus.INTENT_GUARD_REJECTED
    assert len(model.calls) == calls_before
    assert applied.state.active_rule == accepted.state.active_rule
    assert applied.state.in_intermission is True
    assert applied.state.can_submit_rule is True


def test_accepted_text_locks_further_replacement_until_continue() -> None:
    controller, _ = make_controller()
    state = resolve_to_next_intermission(
        controller,
        controller.start_match().state,
        match_seed=41,
    )

    applied = controller.submit_rule(state, "弓射程增加1格。")

    assert applied.state.can_submit_rule is False

    with pytest.raises(ValueError, match="already accepted a rule replacement"):
        controller.submit_rule(applied.state, "移动距离增加1格。")


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
