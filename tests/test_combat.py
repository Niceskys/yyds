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


def state(red_hp: int, blue_hp: int, *, red_col: int = 2, blue_col: int = 3) -> GameState:
    return GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(3, red_col), red_hp),
            Team.BLUE: UnitState(Team.BLUE, Position(3, blue_col), blue_hp),
        },
    )


def test_simultaneous_knife_damage_allows_mutual_death() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(2, 2),
        {
            Team.RED: Action((), Weapon.KNIFE),
            Team.BLUE: Action((), Weapon.KNIFE),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.RED).hp == 0
    assert resolution.state.unit(Team.BLUE).hp == 0
    assert resolution.state.result is MatchResult.DRAW_MUTUAL_DEATH


def test_dead_target_does_not_cancel_its_same_round_attack() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(2, 2),
        {
            Team.RED: Action((), Weapon.KNIFE),
            Team.BLUE: Action((), Weapon.KNIFE),
        },
        match_seed=1,
    )

    attacks = [event for event in resolution.events if event.kind == "ATTACK_RESOLVED"]
    assert {event.actor for event in attacks} == {Team.RED, Team.BLUE}


def test_out_of_range_attack_becomes_null_in_normal_mode() -> None:
    engine = GameEngine()
    resolution = engine.resolve_round(
        state(4, 4, red_col=1, blue_col=5),
        {
            Team.RED: Action((), Weapon.KNIFE),
            Team.BLUE: Action(),
        },
        match_seed=1,
    )

    assert resolution.state.unit(Team.BLUE).hp == 4
    assert any(
        event.kind == "INVALID_ATTACK" and event.actor is Team.RED
        for event in resolution.events
    )
    assert not any(
        event.kind == "FORCED_BOW" and event.actor is Team.RED
        for event in resolution.events
    )


def test_same_seed_produces_same_bow_rolls() -> None:
    engine = GameEngine()
    game_state = GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(3, 1), 4),
            Team.BLUE: UnitState(Team.BLUE, Position(3, 3), 4),
        },
    )
    actions = {
        Team.RED: Action((), Weapon.BOW),
        Team.BLUE: Action((), Weapon.BOW),
    }

    first = engine.resolve_round(game_state, actions, match_seed=42)
    second = engine.resolve_round(game_state, actions, match_seed=42)

    first_attacks = [e.details for e in first.events if e.kind == "ATTACK_RESOLVED"]
    second_attacks = [e.details for e in second.events if e.kind == "ATTACK_RESOLVED"]
    assert first_attacks == second_attacks
    assert first.state == second.state
