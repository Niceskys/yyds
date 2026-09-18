from rules_beyond import Action, Direction, GameEngine, GameState, Position, Team, UnitState, Weapon
from rules_beyond.rule_runtime import (
    PublicRuleHistory,
    RuleEvaluator,
    initial_public_rule_histories,
    update_public_rule_histories,
)
from rules_beyond.rule_validator import RuleValidator


def validated_rule(*, conditions, effect):
    result = RuleValidator().validate(
        {
            "version": "v0.1",
            "target": "ALL_UNITS",
            "conditions": conditions,
            "effect": effect,
            "duration": "UNTIL_REPLACED",
        }
    )
    assert result.accepted, result.issues
    assert result.rule is not None
    return result.rule


def state(*, round_no=1, red_hp=4, blue_hp=4, red=(3, 1), blue=(3, 5), streak=0):
    return GameState(
        round_no=round_no,
        units={
            Team.RED: UnitState(Team.RED, Position(*red), red_hp),
            Team.BLUE: UnitState(Team.BLUE, Position(*blue), blue_hp),
        },
        no_damage_streak=streak,
    )


def test_state_condition_can_affect_only_the_unit_that_matches() -> None:
    rule = validated_rule(
        conditions=[{"type": "SELF_HP_LTE", "value": 2}],
        effect={"type": "BOW_RANGE_ADD", "delta": 1},
    )
    modifiers = RuleEvaluator().evaluate(
        rule,
        state(red_hp=2, blue_hp=4),
        initial_public_rule_histories(),
    )

    assert modifiers[Team.RED].bow_range_add == 1
    assert modifiers[Team.BLUE].bow_range_add == 0


def test_two_conditions_use_and_semantics() -> None:
    rule = validated_rule(
        conditions=[
            {"type": "SELF_HP_LTE", "value": 2},
            {"type": "DISTANCE_GTE", "value": 4},
        ],
        effect={"type": "MOVE_RANGE_ADD", "delta": 1},
    )
    evaluator = RuleEvaluator()

    far = evaluator.evaluate(rule, state(red_hp=2, blue_hp=4), initial_public_rule_histories())
    near = evaluator.evaluate(
        rule,
        state(red_hp=2, blue_hp=4, red=(3, 2), blue=(3, 4)),
        initial_public_rule_histories(),
    )

    assert far[Team.RED].move_range_add == 1
    assert near[Team.RED].move_range_add == 0


def test_history_conditions_are_false_on_round_one() -> None:
    evaluator = RuleEvaluator()
    histories = initial_public_rule_histories()
    rules = [
        validated_rule(
            conditions=[{"type": "DID_NOT_MOVE_LAST_ROUND"}],
            effect={"type": "BOW_RANGE_ADD", "delta": 1},
        ),
        validated_rule(
            conditions=[{"type": "LAST_ATTACK_WEAPON_IS", "weapon": "NONE"}],
            effect={"type": "BOW_RANGE_ADD", "delta": 1},
        ),
        validated_rule(
            conditions=[{"type": "CONSECUTIVE_BOW_MISS_GTE", "value": 1}],
            effect={"type": "BOW_RANGE_ADD", "delta": 1},
        ),
    ]

    for rule in rules:
        modifiers = evaluator.evaluate(rule, state(), histories)
        assert modifiers[Team.RED].bow_range_add == 0
        assert modifiers[Team.BLUE].bow_range_add == 0


def test_priority_entry_records_winner_as_moved_and_blocked_team_as_stayed() -> None:
    engine = GameEngine()
    histories = initial_public_rule_histories()
    before = state(red=(3, 2), blue=(3, 4))

    resolution = engine.resolve_round(
        before,
        {
            Team.RED: Action((Direction.RIGHT,), None),
            Team.BLUE: Action((Direction.LEFT,), None),
        },
        match_seed=1,
    )
    updated = update_public_rule_histories(before, resolution.state, resolution.events, histories)

    assert updated[Team.RED].has_previous_round
    assert updated[Team.BLUE].has_previous_round
    assert updated[Team.RED].moved_last_round is True
    assert updated[Team.BLUE].moved_last_round is False

    rule = validated_rule(
        conditions=[{"type": "DID_NOT_MOVE_LAST_ROUND"}],
        effect={"type": "BOW_RANGE_ADD", "delta": 1},
    )
    modifiers = RuleEvaluator().evaluate(rule, resolution.state, updated)
    assert modifiers[Team.RED].bow_range_add == 0
    assert modifiers[Team.BLUE].bow_range_add == 1


def test_successful_movement_is_recorded_from_resolved_positions() -> None:
    engine = GameEngine()
    before = state()
    resolution = engine.resolve_round(
        before,
        {
            Team.RED: Action((Direction.UP,), None),
            Team.BLUE: Action((Direction.DOWN,), None),
        },
        match_seed=2,
    )
    updated = update_public_rule_histories(
        before,
        resolution.state,
        resolution.events,
        initial_public_rule_histories(),
    )
    assert updated[Team.RED].moved_last_round is True
    assert updated[Team.BLUE].moved_last_round is True


def test_invalid_attack_records_none_but_bow_miss_records_bow_and_miss_streak() -> None:
    engine = GameEngine()
    histories = initial_public_rule_histories()

    before_invalid = state(red=(1, 1), blue=(5, 5))
    invalid = engine.resolve_round(
        before_invalid,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action()},
        match_seed=3,
    )
    after_invalid = update_public_rule_histories(
        before_invalid, invalid.state, invalid.events, histories
    )
    assert after_invalid[Team.RED].last_attack_weapon.value == "NONE"
    assert after_invalid[Team.RED].consecutive_bow_miss == 0

    # Distance 3 is legal. Seed 2 is already used by the engine regression suite
    # as a deterministic double miss at D=3.
    before_miss = state(red=(3, 1), blue=(3, 4))
    miss = engine.resolve_round(
        before_miss,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action((), Weapon.BOW)},
        match_seed=2,
    )
    after_miss = update_public_rule_histories(
        before_miss, miss.state, miss.events, histories
    )
    assert after_miss[Team.RED].last_attack_weapon.value == "BOW"
    assert after_miss[Team.RED].consecutive_bow_miss == 1
    assert after_miss[Team.BLUE].consecutive_bow_miss == 1


def test_bow_hit_resets_miss_streak_and_same_weapon_streak_counts_actual_use() -> None:
    engine = GameEngine()
    old = {
        Team.RED: PublicRuleHistory(
            has_previous_round=True,
            last_attack_weapon=__import__("rules_beyond.rule_dsl", fromlist=["RuleWeapon"]).RuleWeapon.BOW,
            consecutive_bow_miss=2,
            consecutive_same_weapon_use=2,
        ),
        Team.BLUE: PublicRuleHistory(),
    }
    before = state(red=(3, 1), blue=(3, 2))
    resolution = engine.resolve_round(
        before,
        {Team.RED: Action((), Weapon.BOW), Team.BLUE: Action()},
        match_seed=10,
    )
    updated = update_public_rule_histories(before, resolution.state, resolution.events, old)

    assert updated[Team.RED].last_attack_weapon.value == "BOW"
    assert updated[Team.RED].consecutive_bow_miss == 0
    assert updated[Team.RED].consecutive_same_weapon_use == 3


def test_switching_weapon_resets_same_weapon_count_to_one_and_no_attack_to_zero() -> None:
    from rules_beyond.rule_dsl import RuleWeapon

    engine = GameEngine()
    old = {
        Team.RED: PublicRuleHistory(
            has_previous_round=True,
            last_attack_weapon=RuleWeapon.BOW,
            consecutive_same_weapon_use=3,
        ),
        Team.BLUE: PublicRuleHistory(),
    }
    before = state(red=(3, 1), blue=(3, 2))
    knife = engine.resolve_round(
        before,
        {Team.RED: Action((), Weapon.KNIFE), Team.BLUE: Action()},
        match_seed=11,
    )
    after_knife = update_public_rule_histories(before, knife.state, knife.events, old)
    assert after_knife[Team.RED].consecutive_same_weapon_use == 1

    # Use a fresh non-terminal state so the history update is independently tested.
    before_none = state(red=(1, 1), blue=(5, 5))
    none_round = engine.resolve_round(
        before_none,
        {Team.RED: Action(), Team.BLUE: Action()},
        match_seed=12,
    )
    after_none = update_public_rule_histories(
        before_none, none_round.state, none_round.events, after_knife
    )
    assert after_none[Team.RED].last_attack_weapon is RuleWeapon.NONE
    assert after_none[Team.RED].consecutive_same_weapon_use == 0


def test_forced_bow_is_public_actual_bow_use() -> None:
    engine = GameEngine()
    before = state(streak=12)
    resolution = engine.resolve_round(
        before,
        {Team.RED: Action(), Team.BLUE: Action()},
        match_seed=13,
    )
    updated = update_public_rule_histories(
        before,
        resolution.state,
        resolution.events,
        initial_public_rule_histories(),
    )
    assert updated[Team.RED].last_attack_weapon.value == "BOW"
    assert updated[Team.BLUE].last_attack_weapon.value == "BOW"
    assert updated[Team.RED].consecutive_same_weapon_use == 1
    assert updated[Team.RED].consecutive_bow_miss == 0


def _mirror_swap_state(original: GameState) -> GameState:
    def mirrored(position: Position) -> Position:
        return Position(position.row, 6 - position.col)

    return GameState(
        round_no=original.round_no,
        units={
            Team.RED: UnitState(
                Team.RED,
                mirrored(original.unit(Team.BLUE).position),
                original.unit(Team.BLUE).hp,
            ),
            Team.BLUE: UnitState(
                Team.BLUE,
                mirrored(original.unit(Team.RED).position),
                original.unit(Team.RED).hp,
            ),
        },
        no_damage_streak=original.no_damage_streak,
        hard_liveness_active=original.hard_liveness_active,
        result=None,
    )


def test_rule_evaluator_is_symmetric_under_team_swap_and_board_mirror() -> None:
    from rules_beyond.rule_dsl import RuleWeapon

    rule = validated_rule(
        conditions=[
            {"type": "SELF_HP_LT_OPPONENT"},
            {"type": "LAST_ATTACK_WEAPON_IS", "weapon": "BOW"},
        ],
        effect={"type": "MOVE_RANGE_ADD", "delta": 1},
    )
    original = state(round_no=5, red_hp=2, blue_hp=4, red=(2, 1), blue=(4, 5))
    histories = {
        Team.RED: PublicRuleHistory(
            has_previous_round=True,
            moved_last_round=False,
            last_attack_weapon=RuleWeapon.BOW,
            consecutive_same_weapon_use=2,
        ),
        Team.BLUE: PublicRuleHistory(
            has_previous_round=True,
            moved_last_round=True,
            last_attack_weapon=RuleWeapon.KNIFE,
            consecutive_same_weapon_use=1,
        ),
    }

    mirrored = _mirror_swap_state(original)
    mirrored_histories = {
        Team.RED: histories[Team.BLUE],
        Team.BLUE: histories[Team.RED],
    }

    evaluator = RuleEvaluator()
    first = evaluator.evaluate(rule, original, histories)
    second = evaluator.evaluate(rule, mirrored, mirrored_histories)

    assert first[Team.RED] == second[Team.BLUE]
    assert first[Team.BLUE] == second[Team.RED]
