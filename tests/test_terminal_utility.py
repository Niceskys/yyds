from rules_beyond import MatchResult, Team, terminal_utility


def test_terminal_outcome_order_is_frozen() -> None:
    win = terminal_utility(MatchResult.RED_WIN, Team.RED, terminal_round=10, own_hp=2)
    draw = terminal_utility(
        MatchResult.DRAW_MUTUAL_DEATH,
        Team.RED,
        terminal_round=10,
        own_hp=0,
    )
    loss = terminal_utility(MatchResult.BLUE_WIN, Team.RED, terminal_round=10, own_hp=0)
    timeout = terminal_utility(MatchResult.TIMEOUT, Team.RED, terminal_round=30, own_hp=2)

    assert win > draw > loss > timeout


def test_earlier_win_is_preferred_when_outcome_is_same() -> None:
    early = terminal_utility(MatchResult.RED_WIN, Team.RED, terminal_round=7, own_hp=1)
    late = terminal_utility(MatchResult.RED_WIN, Team.RED, terminal_round=8, own_hp=4)

    assert early > late


def test_hp_breaks_tie_after_higher_priority_components() -> None:
    high_hp = terminal_utility(MatchResult.RED_WIN, Team.RED, terminal_round=8, own_hp=3)
    low_hp = terminal_utility(MatchResult.RED_WIN, Team.RED, terminal_round=8, own_hp=1)

    assert high_hp > low_hp
