import inspect
from dataclasses import replace

import pytest

from rules_beyond import (
    Action,
    GameConfig,
    Position,
    RuleEffectType,
    RuleValidator,
    Team,
    UnitState,
    Weapon,
)
from rules_beyond import dynamic_rule_controller as controller_module
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


def repeat_bow_cooldown():
    return {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "CONSECUTIVE_SAME_WEAPON_USE_GTE", "value": 2}],
        "effect": {"type": "WEAPON_COOLDOWN", "weapon": "BOW", "rounds": 1},
        "duration": "UNTIL_REPLACED",
    }


def empty_actions():
    return {Team.RED: Action(), Team.BLUE: Action()}


def bow_actions():
    return {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action((), Weapon.BOW)}


def test_old_v01_rule_phase_interval_is_removed() -> None:
    assert not hasattr(controller_module, "RULE_PHASE_INTERVAL")


def test_start_match_has_no_pre_game_submission_and_round_one_is_ready() -> None:
    controller = DynamicRuleController()

    assert "submission" not in inspect.signature(controller.start_match).parameters

    started = controller.start_match()

    assert started.state.active_rule is None
    assert started.state.game_state.round_no == 1
    assert started.state.completed_rounds == 0
    assert started.state.rule_change_count == 0
    assert started.state.in_intermission is False
    assert started.state.can_submit_rule is False
    assert started.state.can_advance is True
    assert started.events == ()

    with pytest.raises(ValueError, match="No player decision intermission is open"):
        controller.submit_rule(started.state, bow_range_plus_one())


def test_round_one_resolves_without_rule_and_opens_intermission() -> None:
    controller = DynamicRuleController()
    state = controller.start_match().state

    resolved = controller.resolve_round(state, empty_actions(), match_seed=101)

    assert resolved.resolution.modifiers[Team.RED].bow_range_add == 0
    assert resolved.resolution.modifiers[Team.BLUE].bow_range_add == 0
    assert resolved.state.game_state.round_no == 2
    assert resolved.state.completed_rounds == 1
    assert resolved.state.in_intermission is True
    assert resolved.state.pending_intermission_after_round == 1
    assert resolved.state.can_submit_rule is True
    assert resolved.state.can_advance is True
    assert any(event.kind == "INTERMISSION_OPENED" for event in resolved.events)


def test_every_non_terminal_round_opens_an_intermission() -> None:
    controller = DynamicRuleController()
    state = controller.start_match().state

    for round_no in range(1, 6):
        resolved = controller.resolve_round(state, empty_actions(), match_seed=200 + round_no)
        assert resolved.state.in_intermission is True
        assert resolved.state.pending_intermission_after_round == round_no
        assert resolved.state.completed_rounds == round_no
        state = controller.continue_match(resolved.state).state

    assert state.in_intermission is False


def test_rejected_submission_can_retry_in_same_intermission() -> None:
    controller = DynamicRuleController()
    state = controller.resolve_round(
        controller.start_match().state,
        empty_actions(),
        match_seed=301,
    ).state

    invalid = {
        "version": "v0.1",
        "target": "RED",
        "conditions": [],
        "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    }
    rejected = controller.submit_rule(state, invalid)

    assert rejected.outcome.submitted is True
    assert rejected.outcome.accepted is False
    assert rejected.outcome.replaced is False
    assert "FACTION_NEUTRALITY" in {issue.code for issue in rejected.outcome.issues}
    assert rejected.state.active_rule is None
    assert rejected.state.rule_change_count == 0
    assert rejected.state.in_intermission is True
    assert rejected.state.can_submit_rule is True
    assert rejected.state.rule_changed_this_intermission is False
    assert any(event.kind == "PLAYER_RULE_REJECTED" for event in rejected.events)

    accepted = controller.submit_rule(rejected.state, bow_range_plus_one())

    assert accepted.outcome.accepted is True
    assert accepted.outcome.replaced is True
    assert accepted.state.rule_change_count == 1


def test_no_candidate_submission_is_a_rejected_attempt_not_a_continue() -> None:
    controller = DynamicRuleController()
    state = controller.resolve_round(
        controller.start_match().state,
        empty_actions(),
        match_seed=302,
    ).state

    rejected = controller.submit_rule(state, None)

    assert rejected.outcome.submitted is True
    assert rejected.outcome.accepted is False
    assert rejected.state.in_intermission is True
    assert rejected.state.rule_change_count == 0
    assert any(
        event.kind == "PLAYER_RULE_REJECTED" and event.details.get("reason") == "NO_CANDIDATE"
        for event in rejected.events
    )


def test_accepted_submission_locks_same_intermission() -> None:
    controller = DynamicRuleController()
    state = controller.resolve_round(
        controller.start_match().state,
        empty_actions(),
        match_seed=401,
    ).state

    accepted = controller.submit_rule(state, bow_range_plus_one())

    assert accepted.state.rule_changed_this_intermission is True
    assert accepted.state.can_submit_rule is False
    assert accepted.state.active_rule is not None
    assert accepted.state.active_rule.effect.type is RuleEffectType.BOW_RANGE_ADD

    with pytest.raises(ValueError, match="already accepted a rule replacement"):
        controller.submit_rule(accepted.state, move_range_plus_one())


def test_accepted_submission_still_waits_for_explicit_continue() -> None:
    controller = DynamicRuleController()
    state = controller.resolve_round(
        controller.start_match().state,
        empty_actions(),
        match_seed=501,
    ).state

    accepted = controller.submit_rule(state, bow_range_plus_one())

    assert accepted.state.in_intermission is True
    assert accepted.state.pending_intermission_after_round == 1
    assert accepted.state.can_advance is True

    with pytest.raises(ValueError, match="intermission is pending"):
        controller.resolve_round(accepted.state, empty_actions(), match_seed=502)


def test_continue_closes_intermission_and_allows_next_round() -> None:
    controller = DynamicRuleController()
    state = controller.resolve_round(
        controller.start_match().state,
        empty_actions(),
        match_seed=601,
    ).state
    accepted = controller.submit_rule(state, bow_range_plus_one())

    continued = controller.continue_match(accepted.state)

    assert continued.state.in_intermission is False
    assert continued.state.rule_changed_this_intermission is False
    assert continued.state.active_rule == accepted.state.active_rule
    assert continued.state.rule_change_count == 1
    assert any(event.kind == "PLAYER_CONTINUED" for event in continued.events)

    round_two = controller.resolve_round(continued.state, empty_actions(), match_seed=602)

    assert round_two.state.completed_rounds == 2
    assert round_two.resolution.modifiers[Team.RED].bow_range_add == 1
    assert round_two.resolution.modifiers[Team.BLUE].bow_range_add == 1


def test_direct_continue_without_rule_advances_to_next_round() -> None:
    controller = DynamicRuleController()
    state = controller.resolve_round(
        controller.start_match().state,
        empty_actions(),
        match_seed=701,
    ).state

    assert state.can_submit_rule is True

    continued = controller.continue_match(state)

    assert continued.state.active_rule is None
    assert continued.state.rule_change_count == 0
    assert continued.state.in_intermission is False

    round_two = controller.resolve_round(continued.state, empty_actions(), match_seed=702)

    assert round_two.state.completed_rounds == 2
    assert round_two.state.in_intermission is True


def test_continue_requires_an_open_intermission() -> None:
    controller = DynamicRuleController()
    state = controller.start_match().state

    with pytest.raises(ValueError, match="No player decision intermission is open"):
        controller.continue_match(state)


def test_terminal_round_does_not_open_intermission() -> None:
    controller = DynamicRuleController()
    started = controller.start_match()
    terminal_setup = replace(
        started.state.game_state,
        round_no=3,
        units={
            Team.RED: UnitState(Team.RED, Position(3, 2), 1),
            Team.BLUE: UnitState(Team.BLUE, Position(3, 3), 1),
        },
    )
    state = replace(started.state, game_state=terminal_setup)

    resolved = controller.resolve_round(
        state,
        {
            Team.RED: Action((), Weapon.KNIFE),
            Team.BLUE: Action((), Weapon.KNIFE),
        },
        match_seed=801,
    )

    assert resolved.state.game_state.is_terminal is True
    assert resolved.state.in_intermission is False
    assert resolved.state.can_submit_rule is False
    assert resolved.state.can_advance is False
    assert not any(event.kind == "INTERMISSION_OPENED" for event in resolved.events)

    with pytest.raises(ValueError):
        controller.submit_rule(resolved.state, move_range_plus_one())
    with pytest.raises(ValueError):
        controller.continue_match(resolved.state)
    with pytest.raises(ValueError):
        controller.resolve_round(resolved.state, empty_actions(), match_seed=802)


def test_rule_replacement_preserves_public_rule_history() -> None:
    config = GameConfig(initial_hp=6, base_bow_range=4)
    controller = DynamicRuleController(config)
    state = controller.start_match().state

    first = controller.resolve_round(state, bow_actions(), match_seed=901)
    state = controller.continue_match(first.state).state
    second = controller.resolve_round(state, bow_actions(), match_seed=902)
    state = second.state

    assert state.in_intermission is True
    assert state.histories[Team.RED].consecutive_same_weapon_use == 2
    assert state.histories[Team.BLUE].consecutive_same_weapon_use == 2
    history_before_replacement = state.histories

    replaced = controller.submit_rule(state, repeat_bow_cooldown())

    assert replaced.outcome.accepted is True
    assert replaced.state.histories == history_before_replacement
    assert replaced.state.game_state == state.game_state

    continued = controller.continue_match(replaced.state)
    round_three = controller.resolve_round(continued.state, bow_actions(), match_seed=903)

    assert Weapon.BOW in round_three.resolution.modifiers[Team.RED].cooldown_weapons
    assert Weapon.BOW in round_three.resolution.modifiers[Team.BLUE].cooldown_weapons
    invalid_bows = [event for event in round_three.events if event.kind == "INVALID_ATTACK"]
    assert {event.actor for event in invalid_bows} == {Team.RED, Team.BLUE}


def test_rule_replacement_preserves_no_damage_streak() -> None:
    controller = DynamicRuleController()
    state = controller.start_match().state

    first = controller.resolve_round(state, empty_actions(), match_seed=1001)
    state = controller.continue_match(first.state).state
    second = controller.resolve_round(state, empty_actions(), match_seed=1002)
    state = second.state

    assert state.in_intermission is True
    assert state.game_state.no_damage_streak == 2

    replaced = controller.submit_rule(state, bow_range_plus_one())

    assert replaced.outcome.accepted is True
    assert replaced.state.game_state.no_damage_streak == 2

    continued = controller.continue_match(replaced.state)
    round_three = controller.resolve_round(continued.state, empty_actions(), match_seed=1003)

    assert round_three.state.game_state.no_damage_streak == 3


def test_validator_config_must_match_controller_config() -> None:
    controller_config = GameConfig(initial_hp=4)
    mismatched_validator = RuleValidator(GameConfig(initial_hp=5))

    with pytest.raises(ValueError, match="validator.config"):
        DynamicRuleController(controller_config, validator=mismatched_validator)
