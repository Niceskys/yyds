from rules_beyond import (
    Action,
    GameEngine,
    GameState,
    MatchResult,
    Position,
    Team,
    UnitState,
    Weapon,
)


def state_with_streak(streak: int, *, red_hp: int = 4, blue_hp: int = 4) -> GameState:
    return GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(3, 1), red_hp),
            Team.BLUE: UnitState(Team.BLUE, Position(3, 5), blue_hp),
        },
        no_damage_streak=streak,
    )


def test_conflict_level_thresholds() -> None:
    engine = GameEngine()

    assert engine.conflict_level(0) == 0
    assert engine.conflict_level(2) == 0
    assert engine.conflict_level(3) == 1
    assert engine.conflict_level(5) == 1
    assert engine.conflict_level(6) == 2
    assert engine.conflict_level(8) == 2
    assert engine.conflict_level(9) == 3
    assert engine.conflict_level(11) == 3
    assert engine.conflict_level(12) == 4
    assert engine.conflict_level(100) == 4


def test_miss_does_not_reset_no_damage_streak() -> None:
    engine = GameEngine()
    state = GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(3, 1), 4),
            Team.BLUE: UnitState(Team.BLUE, Position(3, 4), 4),
        },
        no_damage_streak=0,
    )

    resolution = engine.resolve_round(
        state,
        {
            Team.RED: Action((), Weapon.BOW),
            Team.BLUE: Action((), Weapon.BOW),
        },
        match_seed=2,
    )

    attacks = [event for event in resolution.events if event.kind == "ATTACK_RESOLVED"]
    assert len(attacks) == 2
    assert all(event.details["hit"] is False for event in attacks)
    assert resolution.state.no_damage_streak == 1


def test_real_damage_resets_no_damage_streak() -> None:
    engine = GameEngine()
    state = GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(3, 1), 4),
            Team.BLUE: UnitState(Team.BLUE, Position(3, 2), 4),
        },
        no_damage_streak=7,
    )

    resolution = engine.resolve_round(
        state,
        {
            Team.RED: Action((), Weapon.KNIFE),
            Team.BLUE: Action((), None),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.BLUE).hp == 2
    assert resolution.state.no_damage_streak == 0


def test_hard_liveness_forces_bow_when_attack_is_missing() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state_with_streak(12),
        {
            Team.RED: Action((), None),
            Team.BLUE: Action((), None),
        },
        match_seed=999,
    )

    forced = [event for event in resolution.events if event.kind == "FORCED_BOW"]
    assert {event.actor for event in forced} == {Team.RED, Team.BLUE}
    assert resolution.state.unit(Team.RED).hp == 3
    assert resolution.state.unit(Team.BLUE).hp == 3
    assert resolution.state.no_damage_streak == 0


def test_hard_liveness_forced_bow_hits_across_maximum_distance() -> None:
    engine = GameEngine()
    state = GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(1, 1), 4),
            Team.BLUE: UnitState(Team.BLUE, Position(5, 5), 4),
        },
        no_damage_streak=12,
    )

    resolution = engine.resolve_round(
        state,
        {Team.RED: Action(), Team.BLUE: Action()},
        match_seed=12345,
    )

    attacks = [event for event in resolution.events if event.kind == "ATTACK_RESOLVED"]
    assert len(attacks) == 2
    assert all(event.details["distance"] == 8 for event in attacks)
    assert all(event.details["probability"] == 1.0 for event in attacks)
    assert all(event.details["hit"] is True for event in attacks)


def test_hard_liveness_can_force_terminal_event_from_one_hp() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state_with_streak(12, red_hp=1, blue_hp=1),
        {Team.RED: Action(), Team.BLUE: Action()},
        match_seed=7,
    )

    assert resolution.state.result is MatchResult.DRAW_MUTUAL_DEATH
    assert resolution.state.unit(Team.RED).hp == 0
    assert resolution.state.unit(Team.BLUE).hp == 0


def test_timeout_is_terminal_when_max_round_is_reached_without_death() -> None:
    engine = GameEngine()
    state = GameState(
        round_no=30,
        units={
            Team.RED: UnitState(Team.RED, Position(1, 1), 4),
            Team.BLUE: UnitState(Team.BLUE, Position(5, 5), 4),
        },
        no_damage_streak=0,
    )

    resolution = engine.resolve_round(
        state,
        {Team.RED: Action(), Team.BLUE: Action()},
        match_seed=1,
    )

    assert resolution.state.result is MatchResult.TIMEOUT
