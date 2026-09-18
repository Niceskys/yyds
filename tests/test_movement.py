from rules_beyond import (
    Action,
    Direction,
    GameConfig,
    GameEngine,
    GameState,
    Position,
    Team,
    UnitState,
    Weapon,
)


def state(red: Position, blue: Position, *, round_no: int = 1) -> GameState:
    return GameState(
        round_no=round_no,
        units={
            Team.RED: UnitState(Team.RED, red, 4),
            Team.BLUE: UnitState(Team.BLUE, blue, 4),
        },
    )


def event_kinds(resolution) -> list[str]:
    return [event.kind for event in resolution.events]


def test_same_empty_destination_uses_replay_stable_priority() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(Position(3, 2), Position(3, 4)),
        {
            Team.RED: Action((Direction.RIGHT,), None),
            Team.BLUE: Action((Direction.LEFT,), None),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).position == Position(3, 3)
    assert resolution.state.unit(Team.BLUE).position == Position(3, 4)
    assert "SAME_DESTINATION_CONFLICT" in event_kinds(resolution)
    conflict = next(e for e in resolution.events if e.kind == "SAME_DESTINATION_CONFLICT")
    assert conflict.details == {
        "substep": 1,
        "destination": (3, 3),
        "winner": "RED",
        "blocked": "BLUE",
        "resolution": "PRIORITY_ENTRY",
    }


def test_same_empty_destination_priority_alternates_by_round() -> None:
    engine = GameEngine()
    actions = {
        Team.RED: Action((Direction.RIGHT,), None),
        Team.BLUE: Action((Direction.LEFT,), None),
    }

    odd_round = engine.resolve_round(
        state(Position(3, 2), Position(3, 4), round_no=1),
        actions,
        match_seed=1,
    )
    even_round = engine.resolve_round(
        state(Position(3, 2), Position(3, 4), round_no=2),
        actions,
        match_seed=1,
    )

    assert odd_round.state.unit(Team.RED).position == Position(3, 3)
    assert odd_round.state.unit(Team.BLUE).position == Position(3, 4)
    assert even_round.state.unit(Team.RED).position == Position(3, 2)
    assert even_round.state.unit(Team.BLUE).position == Position(3, 3)


def test_same_empty_destination_is_reproducible_for_same_seed_and_round() -> None:
    engine = GameEngine()
    before = state(Position(3, 2), Position(3, 4), round_no=7)
    actions = {
        Team.RED: Action((Direction.RIGHT,), None),
        Team.BLUE: Action((Direction.LEFT,), None),
    }

    first = engine.resolve_round(before, actions, match_seed=42)
    second = engine.resolve_round(before, actions, match_seed=42)

    assert first == second


def test_direct_swap_conflict_keeps_both_in_place() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(Position(3, 2), Position(3, 3)),
        {
            Team.RED: Action((Direction.RIGHT,), None),
            Team.BLUE: Action((Direction.LEFT,), None),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).position == Position(3, 2)
    assert resolution.state.unit(Team.BLUE).position == Position(3, 3)
    assert "SWAP_CONFLICT" in event_kinds(resolution)


def test_entering_opponent_stay_cell_is_blocked() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(Position(3, 2), Position(3, 3)),
        {
            Team.RED: Action((Direction.RIGHT,), None),
            Team.BLUE: Action((), None),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).position == Position(3, 2)
    assert resolution.state.unit(Team.BLUE).position == Position(3, 3)
    assert "SAME_DESTINATION_CONFLICT" in event_kinds(resolution)


def test_unit_can_enter_cell_opponent_vacates_in_same_substep() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(Position(3, 1), Position(3, 2)),
        {
            Team.RED: Action((Direction.RIGHT,), None),
            Team.BLUE: Action((Direction.RIGHT,), None),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).position == Position(3, 2)
    assert resolution.state.unit(Team.BLUE).position == Position(3, 3)
    assert "SAME_DESTINATION_CONFLICT" not in event_kinds(resolution)
    assert "SWAP_CONFLICT" not in event_kinds(resolution)


def test_second_substep_contest_moves_only_priority_team() -> None:
    engine = GameEngine(GameConfig(base_move_range=2))
    resolution = engine.resolve_round(
        state(Position(2, 1), Position(2, 5)),
        {
            Team.RED: Action((Direction.RIGHT, Direction.RIGHT), None),
            Team.BLUE: Action((Direction.LEFT, Direction.LEFT), None),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).position == Position(2, 3)
    assert resolution.state.unit(Team.BLUE).position == Position(2, 4)
    conflicts = [e for e in resolution.events if e.kind == "SAME_DESTINATION_CONFLICT"]
    assert conflicts[0].details["substep"] == 2


def test_contest_stops_both_remaining_paths_after_priority_entry() -> None:
    engine = GameEngine(GameConfig(base_move_range=2))
    resolution = engine.resolve_round(
        state(Position(1, 1), Position(1, 3)),
        {
            Team.RED: Action((Direction.RIGHT, Direction.DOWN), None),
            Team.BLUE: Action((Direction.LEFT, Direction.DOWN), None),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).position == Position(1, 2)
    assert resolution.state.unit(Team.BLUE).position == Position(1, 3)
    assert "SAME_DESTINATION_CONFLICT" in event_kinds(resolution)


def test_invalid_path_becomes_stay_but_attack_is_still_processed() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(Position(1, 1), Position(1, 3)),
        {
            Team.RED: Action((Direction.UP,), Weapon.BOW),
            Team.BLUE: Action((), None),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).position == Position(1, 1)
    assert "INVALID_MOVE_PATH" in event_kinds(resolution)
    assert any(
        event.kind == "ATTACK_RESOLVED" and event.actor is Team.RED
        for event in resolution.events
    )


def test_movement_conflict_does_not_cancel_legal_attacks() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(Position(3, 2), Position(3, 4)),
        {
            Team.RED: Action((Direction.RIGHT,), Weapon.BOW),
            Team.BLUE: Action((Direction.LEFT,), Weapon.BOW),
        },
        match_seed=2,
    )

    assert "SAME_DESTINATION_CONFLICT" in event_kinds(resolution)
    attacks = [event for event in resolution.events if event.kind == "ATTACK_RESOLVED"]
    assert {event.actor for event in attacks} == {Team.RED, Team.BLUE}


def test_priority_entry_makes_contested_center_knife_attacks_legal() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(Position(3, 2), Position(3, 4)),
        {
            Team.RED: Action((Direction.RIGHT,), Weapon.KNIFE),
            Team.BLUE: Action((Direction.LEFT,), Weapon.KNIFE),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).position == Position(3, 3)
    assert resolution.state.unit(Team.BLUE).position == Position(3, 4)
    assert "INVALID_ATTACK" not in event_kinds(resolution)
    attacks = [event for event in resolution.events if event.kind == "ATTACK_RESOLVED"]
    assert {event.actor for event in attacks} == {Team.RED, Team.BLUE}
    assert all(event.details["weapon"] == "KNIFE" for event in attacks)


def test_resolved_positions_never_overlap() -> None:
    engine = GameEngine(GameConfig(base_move_range=2))
    scenarios = [
        (
            Position(3, 1),
            Position(3, 3),
            Action((Direction.RIGHT, Direction.RIGHT), None),
            Action((), None),
        ),
        (
            Position(2, 2),
            Position(2, 3),
            Action((Direction.RIGHT,), None),
            Action((Direction.LEFT,), None),
        ),
    ]

    for red, blue, red_action, blue_action in scenarios:
        resolution = engine.resolve_round(
            state(red, blue),
            {Team.RED: red_action, Team.BLUE: blue_action},
            match_seed=1,
        )
        assert resolution.state.unit(Team.RED).position != resolution.state.unit(Team.BLUE).position
