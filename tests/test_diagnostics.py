from rules_beyond.bots import AggressiveBot
from rules_beyond.diagnostics import AttackFirstAggressiveBot
from rules_beyond.simulation import run_batch


def test_attack_first_policy_removes_naive_center_collision_loop() -> None:
    naive = run_batch(AggressiveBot(), AggressiveBot(), range(300))
    attack_first = run_batch(
        AttackFirstAggressiveBot(),
        AttackFirstAggressiveBot(),
        range(10_000, 10_300),
    )

    # Baseline AggressiveBot repeatedly tries to enter the contested middle cell.
    assert naive.total_same_destination_conflicts > 0

    # A one-line behavioral change (attack when already in range) avoids that loop
    # without changing any game rule.
    assert attack_first.total_same_destination_conflicts == 0

    # The naive 100% mutual-death result must not be treated as a rule invariant.
    assert attack_first.results != {"DRAW_MUTUAL_DEATH": 300}
