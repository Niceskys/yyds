from rules_beyond.model import Action, Direction, Team, Weapon, initial_state
from rules_beyond.planner_audit import audit_action_against_snapshot
from rules_beyond.rule_engine import RuleAwareGameEngine
from rules_beyond.rule_runtime import initial_public_rule_histories


def test_snapshot_audit_accepts_move_then_bow_that_is_locally_in_range() -> None:
    state = initial_state()
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()

    audit = audit_action_against_snapshot(
        state,
        Team.RED,
        engine,
        Action((Direction.RIGHT,), Weapon.BOW),
        rule=None,
        histories=histories,
    )

    assert audit.accepted
    assert audit.issues == ()


def test_snapshot_audit_rejects_bow_that_is_out_of_range_without_move() -> None:
    state = initial_state()
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()

    audit = audit_action_against_snapshot(
        state,
        Team.RED,
        engine,
        Action((), Weapon.BOW),
        rule=None,
        histories=histories,
    )

    assert not audit.accepted
    assert "BOW_OUT_OF_RANGE_AT_SUBMISSION" in audit.issues


def test_snapshot_audit_rejects_move_beyond_current_effective_range() -> None:
    state = initial_state()
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()

    audit = audit_action_against_snapshot(
        state,
        Team.RED,
        engine,
        Action((Direction.RIGHT, Direction.RIGHT), None),
        rule=None,
        histories=histories,
    )

    assert not audit.accepted
    assert "MOVE_RANGE_EXCEEDED" in audit.issues
