import pytest

from rules_beyond import Action, RuleEffectType, Team
from rules_beyond.dynamic_rule_controller import DynamicRuleController


def candidate(effect_type: str, **effect_fields):
    return {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": effect_type, **effect_fields},
        "duration": "UNTIL_REPLACED",
    }


def bow_range_plus_one():
    return candidate("BOW_RANGE_ADD", delta=1)


def move_range_plus_one():
    return candidate("MOVE_RANGE_ADD", delta=1)


def empty_actions():
    return {Team.RED: Action(), Team.BLUE: Action()}


def test_pregame_phase_accepts_initial_rule_before_round_one() -> None:
    controller = DynamicRuleController()
    started = controller.start_match(bow_range_plus_one())

    assert started.phase.phase_index == 0
    assert started.phase.after_round is None
    assert started.phase.accepted is True
    assert started.phase.replaced is True
    assert started.state.active_rule is not None
    assert started.state.active_rule.effect.type is RuleEffectType.BOW_RANGE_ADD
    assert started.state.game_state.round_no == 1
    assert started.state.rule_phase_due is False


def test_round_three_uses_old_rule_and_replacement_starts_on_round_four() -> None:
    controller = DynamicRuleController()
    state = controller.start_match(bow_range_plus_one()).state

    for expected_round in (1, 2):
        result = controller.resolve_round(state, empty_actions(), match_seed=100 + expected_round)
        assert result.resolution.modifiers[Team.RED].bow_range_add == 1
        assert result.state.rule_phase_due is False
        state = result.state

    round_three = controller.resolve_round(state, empty_actions(), match_seed=103)
    assert round_three.resolution.modifiers[Team.RED].bow_range_add == 1
    assert round_three.resolution.modifiers[Team.RED].move_range_add == 0
    assert round_three.state.game_state.round_no == 4
    assert round_three.state.rule_phase_due is True
    assert round_three.state.pending_rule_phase_after_round == 3

    replaced = controller.apply_due_rule_phase(round_three.state, move_range_plus_one())
    assert replaced.phase.phase_index == 1
    assert replaced.phase.after_round == 3
    assert replaced.phase.accepted is True
    assert replaced.state.active_rule is not None
    assert replaced.state.active_rule.effect.type is RuleEffectType.MOVE_RANGE_ADD

    round_four = controller.resolve_round(replaced.state, empty_actions(), match_seed=104)
    assert round_four.resolution.modifiers[Team.RED].bow_range_add == 0
    assert round_four.resolution.modifiers[Team.RED].move_range_add == 1


def test_no_submission_carries_previous_rule_instead_of_expiring_it() -> None:
    controller = DynamicRuleController()
    state = controller.start_match(bow_range_plus_one()).state
    original_rule = state.active_rule

    for round_no in range(1, 7):
        resolved = controller.resolve_round(state, empty_actions(), match_seed=200 + round_no)
        state = resolved.state
        if round_no in (3, 6):
            assert state.rule_phase_due is True
            carried = controller.apply_due_rule_phase(state, None)
            assert carried.phase.submitted is False
            assert carried.phase.accepted is False
            assert carried.phase.replaced is False
            assert carried.state.active_rule == original_rule
            state = carried.state

    assert state.active_rule == original_rule
    assert state.last_phase_index == 2


def test_invalid_submission_is_rejected_and_previous_rule_is_retained() -> None:
    controller = DynamicRuleController()
    state = controller.start_match(bow_range_plus_one()).state
    original_rule = state.active_rule

    for round_no in range(1, 4):
        state = controller.resolve_round(state, empty_actions(), match_seed=300 + round_no).state

    invalid = {
        "version": "v0.1",
        "target": "RED",
        "conditions": [],
        "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }
    rejected = controller.apply_due_rule_phase(state, invalid)

    assert rejected.phase.submitted is True
    assert rejected.phase.accepted is False
    assert rejected.phase.replaced is False
    assert rejected.state.active_rule == original_rule
    assert "FACTION_NEUTRALITY" in {issue.code for issue in rejected.phase.issues}
    assert any(event.kind == "PLAYER_RULE_REJECTED" for event in rejected.events)


def test_due_rule_phase_cannot_be_skipped_before_next_round() -> None:
    controller = DynamicRuleController()
    state = controller.start_match().state

    for round_no in range(1, 4):
        state = controller.resolve_round(state, empty_actions(), match_seed=400 + round_no).state

    assert state.rule_phase_due is True
    with pytest.raises(ValueError, match="due rule phase"):
        controller.resolve_round(state, empty_actions(), match_seed=404)


def test_rule_phase_cannot_be_applied_at_arbitrary_round() -> None:
    controller = DynamicRuleController()
    state = controller.start_match().state

    with pytest.raises(ValueError, match="No rule phase is due"):
        controller.apply_due_rule_phase(state, move_range_plus_one())

    state = controller.resolve_round(state, empty_actions(), match_seed=501).state
    with pytest.raises(ValueError, match="No rule phase is due"):
        controller.apply_due_rule_phase(state, move_range_plus_one())


def test_invalid_pregame_submission_starts_without_active_player_rule() -> None:
    controller = DynamicRuleController()
    invalid = {
        "version": "v0.1",
        "target": "BLUE",
        "conditions": [],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }
    started = controller.start_match(invalid)

    assert started.phase.accepted is False
    assert started.state.active_rule is None
    assert any(event.kind == "PLAYER_RULE_REJECTED" for event in started.events)
