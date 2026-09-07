import pytest

from rules_beyond.engine import GameEngine
from rules_beyond.model import Action, Direction, GameState, Position, Team, UnitState, Weapon, initial_state
from rules_beyond.rule_dsl import (
    RuleAST,
    RuleCondition,
    RuleConditionType,
    RuleDuration,
    RuleEffect,
    RuleEffectType,
    RuleTarget,
    RuleWeapon,
)
from rules_beyond.rule_engine import RuleAwareGameEngine
from rules_beyond.rule_runtime import initial_public_rule_histories


def rule(effect: RuleEffect, *conditions: RuleCondition) -> RuleAST:
    return RuleAST(
        version="v0.1",
        target=RuleTarget.ALL_UNITS,
        conditions=tuple(conditions),
        effect=effect,
        duration=RuleDuration.UNTIL_REPLACED,
    )


def state_at(*, red_hp: int = 4, blue_hp: int = 4, red_col: int = 1, blue_col: int = 5, streak: int = 0, hard: bool = False) -> GameState:
    return GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(3, red_col), red_hp),
            Team.BLUE: UnitState(Team.BLUE, Position(3, blue_col), blue_hp),
        },
        no_damage_streak=streak,
        hard_liveness_active=hard,
    )


def attack_events(resolution, team: Team):
    return [e for e in resolution.events if e.kind == "ATTACK_RESOLVED" and e.actor is team]


def test_no_rule_path_matches_baseline_engine_state_and_events() -> None:
    state = initial_state()
    actions = {
        Team.RED: Action((Direction.RIGHT,), None),
        Team.BLUE: Action((Direction.LEFT,), None),
    }
    baseline = GameEngine().resolve_round(state, actions, match_seed=101)
    ruled = RuleAwareGameEngine().resolve_rule_round(
        state,
        actions,
        rule=None,
        histories=initial_public_rule_histories(),
        match_seed=101,
    )
    assert ruled.state == baseline.state
    assert ruled.events == baseline.events


def test_bow_range_rule_makes_distance_four_attack_legal() -> None:
    state = state_at()
    bow_plus_one = rule(RuleEffect(RuleEffectType.BOW_RANGE_ADD, delta=1))
    engine = RuleAwareGameEngine()

    without_rule = engine.resolve_rule_round(
        state,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action()},
        rule=None,
        match_seed=1,
    )
    with_rule = engine.resolve_rule_round(
        state,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action()},
        rule=bow_plus_one,
        match_seed=1,
    )

    assert attack_events(without_rule, Team.RED) == []
    assert len(attack_events(with_rule, Team.RED)) == 1


def test_hp_condition_can_apply_to_only_one_team_without_faction_bias() -> None:
    state = state_at(red_hp=2, blue_hp=4)
    low_hp_range = rule(
        RuleEffect(RuleEffectType.BOW_RANGE_ADD, delta=1),
        RuleCondition(RuleConditionType.SELF_HP_LTE, value=2),
    )
    resolution = RuleAwareGameEngine().resolve_rule_round(
        state,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action((), Weapon.BOW)},
        rule=low_hp_range,
        match_seed=2,
    )

    assert len(attack_events(resolution, Team.RED)) == 1
    assert attack_events(resolution, Team.BLUE) == []
    assert resolution.modifiers[Team.RED].bow_range_add == 1
    assert resolution.modifiers[Team.BLUE].bow_range_add == 0


def test_move_range_rule_allows_two_step_path() -> None:
    move_plus_one = rule(RuleEffect(RuleEffectType.MOVE_RANGE_ADD, delta=1))
    state = state_at()
    resolution = RuleAwareGameEngine().resolve_rule_round(
        state,
        {
            Team.RED: Action((Direction.UP, Direction.RIGHT), None),
            Team.BLUE: Action(),
        },
        rule=move_plus_one,
        match_seed=3,
    )
    assert resolution.state.unit(Team.RED).position == Position(2, 2)
    assert not any(e.kind == "INVALID_MOVE_PATH" for e in resolution.events)


def test_bow_hit_multiplier_uses_normal_five_percent_to_one_hundred_percent_clamp() -> None:
    half_hit = rule(RuleEffect(RuleEffectType.BOW_HIT_MULTIPLIER, multiplier=0.5))
    state = state_at(red_col=1, blue_col=4)  # distance 3; base probability 25%
    resolution = RuleAwareGameEngine().resolve_rule_round(
        state,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action()},
        rule=half_hit,
        match_seed=4,
    )
    event = attack_events(resolution, Team.RED)[0]
    assert event.details["probability"] == pytest.approx(0.125)


def test_cooldown_blocks_ordinary_attack() -> None:
    bow_cooldown = rule(
        RuleEffect(
            RuleEffectType.WEAPON_COOLDOWN,
            weapon=RuleWeapon.BOW,
            rounds=1,
        )
    )
    state = state_at(red_col=1, blue_col=4)
    resolution = RuleAwareGameEngine().resolve_rule_round(
        state,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action()},
        rule=bow_cooldown,
        match_seed=5,
    )
    assert attack_events(resolution, Team.RED) == []
    assert any(e.kind == "INVALID_ATTACK" and e.actor is Team.RED for e in resolution.events)


def test_hard_liveness_replaces_cooled_down_bow_with_forced_bow() -> None:
    bow_cooldown = rule(
        RuleEffect(
            RuleEffectType.WEAPON_COOLDOWN,
            weapon=RuleWeapon.BOW,
            rounds=1,
        )
    )
    state = state_at(hard=True)
    resolution = RuleAwareGameEngine().resolve_rule_round(
        state,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action()},
        rule=bow_cooldown,
        match_seed=6,
    )
    event = attack_events(resolution, Team.RED)[0]
    assert any(e.kind == "FORCED_BOW" and e.actor is Team.RED for e in resolution.events)
    assert event.details["forced"] is True
    assert event.details["probability"] == 1.0


def test_antistall_range_is_minimum_not_additive_double_bonus() -> None:
    bow_plus_one = rule(RuleEffect(RuleEffectType.BOW_RANGE_ADD, delta=1))
    state = state_at(streak=3)
    stats = RuleAwareGameEngine().effective_stats_for_team(
        state,
        Team.RED,
        rule=bow_plus_one,
    )
    # Player changes 3 -> 4; Level 1 also guarantees at least 4. It does not become 5.
    assert stats.bow_range == 4


def test_engine_rejects_directly_constructed_invalid_rule() -> None:
    invalid = rule(RuleEffect(RuleEffectType.KNIFE_DAMAGE_ADD, delta=-2))
    with pytest.raises(ValueError, match="validated V0.1 rule"):
        RuleAwareGameEngine().resolve_rule_round(
            initial_state(),
            {Team.RED: Action(), Team.BLUE: Action()},
            rule=invalid,
            match_seed=7,
        )
