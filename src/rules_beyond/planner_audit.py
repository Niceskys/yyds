from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .model import Action, GameState, Team, Weapon
from .rule_dsl import RuleAST
from .rule_engine import RuleAwareGameEngine
from .rule_runtime import PublicRuleHistory


@dataclass(frozen=True, slots=True)
class PlannerSnapshotAudit:
    accepted: bool
    issues: tuple[str, ...]


def audit_action_against_snapshot(
    state: GameState,
    team: Team,
    engine: RuleAwareGameEngine,
    action: Action,
    *,
    rule: RuleAST | None,
    histories: Mapping[Team, PublicRuleHistory],
) -> PlannerSnapshotAudit:
    """Audit one submitted action before simultaneous settlement.

    This checks what the planner can know at submission time: path bounds/range,
    cooldown, and attack range against the opponent's current public position.
    The opponent may then move simultaneously, or movement may conflict, so an
    Engine `INVALID_ATTACK` after settlement is not automatically a planner bug.
    """

    stats = engine.effective_stats_for_team(
        state,
        team,
        rule=rule,
        histories=histories,
    )
    issues: list[str] = []

    if len(action.move_path) > stats.move_range:
        issues.append("MOVE_RANGE_EXCEEDED")

    destination = state.unit(team).position
    for step in action.move_path:
        try:
            destination = destination.moved(step)
        except (TypeError, ValueError):
            issues.append("INVALID_DIRECTION")
            break
        if not engine.config.contains(destination):
            issues.append("OUT_OF_BOUNDS")
            break

    weapon = action.attack
    if weapon is not None:
        if not isinstance(weapon, Weapon):
            issues.append("UNKNOWN_WEAPON")
        elif weapon in stats.cooldown_weapons:
            issues.append("WEAPON_ON_COOLDOWN")
        else:
            opponent = state.unit(team.opponent).position
            distance = destination.manhattan_distance(opponent)
            if weapon is Weapon.KNIFE and distance > stats.knife_range:
                issues.append("KNIFE_OUT_OF_RANGE_AT_SUBMISSION")
            elif weapon is Weapon.BOW and distance > stats.bow_range:
                issues.append("BOW_OUT_OF_RANGE_AT_SUBMISSION")

    return PlannerSnapshotAudit(accepted=not issues, issues=tuple(issues))
