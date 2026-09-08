from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api_contract import (
    ActionPublicView,
    AdvanceResult,
    BattleEscalationSnapshot,
    BoardSnapshot,
    EffectiveStatsPublicView,
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    GameConfigPublicView,
    IntermissionChoicePublic,
    MatchLifecycle,
    MatchResultPublic,
    MatchSnapshot,
    PlayerDecisionSnapshot,
    PositionSnapshot,
    PublicStrategyDecision,
    ReplayIntermissionEntry,
    ReplayRoundEntry,
    ReplaySnapshot,
    RiskBudgetPublic,
    RoundEventPublicView,
    RoundExecutionPublicView,
    RuleAstPublicView,
    RuleDurationPublic,
    RuleEffectPublicView,
    RuleEffectTypePublic,
    RulePublicView,
    RuleSubmissionCode,
    RuleSubmissionResult,
    RuleTargetPublic,
    ShortTermGoalPublic,
    StrategyDecisionStatusPublic,
    StrategyIntentPublic,
    TeamActionMap,
    TeamLatestStrategyMap,
    TeamRoundStrategyMap,
    TeamStatsMap,
    TeamUnitMap,
    TeamPublic,
    UnitSnapshot,
    WeaponPreferencePublic,
    WeaponPublic,
)


def _battle(*, no_damage_streak: int = 0, hard: bool = False) -> BattleEscalationSnapshot:
    if hard or no_damage_streak >= 12:
        level = 4
        next_threshold = None
    elif no_damage_streak >= 9:
        level = 3
        next_threshold = 12
    elif no_damage_streak >= 6:
        level = 2
        next_threshold = 9
    elif no_damage_streak >= 3:
        level = 1
        next_threshold = 6
    else:
        level = 0
        next_threshold = 3

    return BattleEscalationSnapshot(
        level=level,
        no_damage_streak=no_damage_streak,
        next_level_at_no_damage=next_threshold,
        rounds_until_next_level=(
            None if next_threshold is None else max(0, next_threshold - no_damage_streak)
        ),
        hard_liveness_active=hard or level == 4,
    )


def _stats(*, move_range: int = 1, conflict_level: int = 0, hard: bool = False) -> EffectiveStatsPublicView:
    return EffectiveStatsPublicView(
        move_range=move_range,
        knife_range=1 if conflict_level == 0 else 2,
        bow_range=3 + min(conflict_level, 3) if not hard else 8,
        knife_damage=2,
        bow_damage=1,
        bow_hit_multiplier=1.0,
        bow_hit_floor={0: 0.0, 1: 0.0, 2: 0.25, 3: 0.50, 4: 1.0}[conflict_level],
        cooldown_weapons=[],
        conflict_level=conflict_level,
        hard_liveness=hard,
    )


def _units(*, red_hp: int = 4, blue_hp: int = 3) -> TeamUnitMap:
    return TeamUnitMap(
        RED=UnitSnapshot(
            team=TeamPublic.RED,
            hp=red_hp,
            position=PositionSnapshot(row=3, col=2),
        ),
        BLUE=UnitSnapshot(
            team=TeamPublic.BLUE,
            hp=blue_hp,
            position=PositionSnapshot(row=3, col=5),
        ),
    )


def _rule() -> RulePublicView:
    return RulePublicView(
        rule_id="rule_fixture_001",
        player_text="双方移动距离增加1格",
        ast=RuleAstPublicView(
            version="0.1",
            target=RuleTargetPublic.ALL_UNITS,
            conditions=[],
            effect=RuleEffectPublicView(
                type=RuleEffectTypePublic.MOVE_RANGE_ADD,
                delta=1,
            ),
            duration=RuleDurationPublic.UNTIL_REPLACED,
        ),
    )


def _strategy(intent: StrategyIntentPublic) -> PublicStrategyDecision:
    if intent is StrategyIntentPublic.KITE:
        return PublicStrategyDecision(
            status=StrategyDecisionStatusPublic.ACCEPTED,
            intent=intent,
            target_distance=3,
            weapon_preference=WeaponPreferencePublic.BOW,
            risk_budget=RiskBudgetPublic.LOW,
            short_term_goal=ShortTermGoalPublic.SURVIVE,
            horizon_rounds=2,
            contingency={"opponent_closes": "increase_separation"},
        )
    return PublicStrategyDecision(
        status=StrategyDecisionStatusPublic.ACCEPTED,
        intent=intent,
    )


def _empty_strategies() -> TeamLatestStrategyMap:
    return TeamLatestStrategyMap(RED=None, BLUE=None)


def _strategies() -> TeamRoundStrategyMap:
    return TeamRoundStrategyMap(
        RED=_strategy(StrategyIntentPublic.PRESSURE),
        BLUE=_strategy(StrategyIntentPublic.KITE),
    )


def _initial_match() -> MatchSnapshot:
    return MatchSnapshot(
        match_id="match_fixture_001",
        revision=0,
        lifecycle=MatchLifecycle.RUNNING,
        seed=1_270_000,
        round_no=1,
        completed_rounds=0,
        score_rounds=0,
        rule_change_count=0,
        board=BoardSnapshot(rows=5, cols=5),
        units=_units(red_hp=4, blue_hp=4),
        active_rule=None,
        player_decision=PlayerDecisionSnapshot(
            after_round=None,
            can_submit_rule=False,
            rule_changed_this_intermission=False,
            can_advance=True,
        ),
        effective_stats=TeamStatsMap(RED=_stats(), BLUE=_stats()),
        latest_strategy=_empty_strategies(),
        battle_escalation=_battle(),
        result=None,
    )


def _decision_match(*, revision: int = 1) -> MatchSnapshot:
    return MatchSnapshot(
        match_id="match_fixture_001",
        revision=revision,
        lifecycle=MatchLifecycle.PLAYER_DECISION,
        seed=1_270_000,
        round_no=2,
        completed_rounds=1,
        score_rounds=1,
        rule_change_count=0,
        board=BoardSnapshot(rows=5, cols=5),
        units=_units(),
        active_rule=None,
        player_decision=PlayerDecisionSnapshot(
            after_round=1,
            can_submit_rule=True,
            rule_changed_this_intermission=False,
            can_advance=True,
        ),
        effective_stats=TeamStatsMap(RED=_stats(), BLUE=_stats()),
        latest_strategy=TeamLatestStrategyMap(
            RED=_strategy(StrategyIntentPublic.PRESSURE),
            BLUE=_strategy(StrategyIntentPublic.KITE),
        ),
        battle_escalation=_battle(no_damage_streak=0),
        result=None,
    )


def _post_rule_match() -> MatchSnapshot:
    base = _decision_match(revision=2)
    return base.model_copy(
        update={
            "active_rule": _rule(),
            "rule_change_count": 1,
            "player_decision": PlayerDecisionSnapshot(
                after_round=1,
                can_submit_rule=False,
                rule_changed_this_intermission=True,
                can_advance=True,
            ),
            "effective_stats": TeamStatsMap(
                RED=_stats(move_range=2),
                BLUE=_stats(move_range=2),
            ),
        }
    )


def _terminal_match() -> MatchSnapshot:
    return MatchSnapshot(
        match_id="match_fixture_001",
        revision=4,
        lifecycle=MatchLifecycle.TERMINAL,
        seed=1_270_000,
        round_no=2,
        completed_rounds=2,
        score_rounds=2,
        rule_change_count=1,
        board=BoardSnapshot(rows=5, cols=5),
        units=_units(red_hp=2, blue_hp=0),
        active_rule=_rule(),
        player_decision=PlayerDecisionSnapshot(
            after_round=2,
            can_submit_rule=False,
            rule_changed_this_intermission=False,
            can_advance=False,
        ),
        effective_stats=TeamStatsMap(
            RED=_stats(move_range=2),
            BLUE=_stats(move_range=2),
        ),
        latest_strategy=TeamLatestStrategyMap(
            RED=_strategy(StrategyIntentPublic.PRESSURE),
            BLUE=_strategy(StrategyIntentPublic.KITE),
        ),
        battle_escalation=_battle(no_damage_streak=0),
        result=MatchResultPublic.RED_WIN,
    )


def build_fixtures() -> dict[str, object]:
    initial = _initial_match()
    decision = _decision_match()
    post_rule = _post_rule_match()
    terminal = _terminal_match()
    rule = _rule()
    strategies = _strategies()
    actions = TeamActionMap(
        RED=ActionPublicView(move_path=[], attack=WeaponPublic.BOW),
        BLUE=ActionPublicView(move_path=[], attack=WeaponPublic.BOW),
    )
    round_one_events = [
        RoundEventPublicView(
            kind="DAMAGE_APPLIED",
            actor=TeamPublic.RED,
            details={"amount": 1, "hp_after": 3, "hp_before": 4, "target": "BLUE"},
        )
    ]
    round_two_events = [
        RoundEventPublicView(
            kind="DAMAGE_APPLIED",
            actor=TeamPublic.RED,
            details={"amount": 3, "hp_after": 0, "hp_before": 3, "target": "BLUE"},
        )
    ]

    accepted = RuleSubmissionResult(
        accepted=True,
        public_code=RuleSubmissionCode.ACCEPTED,
        message="规则已生效。",
        suggested_rephrase=None,
        candidate_preview=None,
        rule_id=rule.rule_id,
        match=post_rule,
    )
    rejected = RuleSubmissionResult(
        accepted=False,
        public_code=RuleSubmissionCode.NO_CANDIDATE,
        message="当前规则系统无法安全表达这句话。",
        suggested_rephrase="双方的移动距离增加1格",
        candidate_preview=None,
        rule_id=None,
        match=decision,
    )
    revision_conflict = ErrorEnvelope(
        error=ErrorDetail(
            code=ErrorCode.REVISION_CONFLICT,
            message="对局状态已经变化，请刷新后重试。",
            retryable=True,
        )
    )
    advance = AdvanceResult(
        round=RoundExecutionPublicView(
            round_no=1,
            strategies=strategies,
            actions=actions,
            events=round_one_events,
        ),
        match=decision,
    )
    replay = ReplaySnapshot(
        match_id=terminal.match_id,
        seed=terminal.seed,
        initial_config=GameConfigPublicView(
            rows=5,
            cols=5,
            initial_hp=4,
            max_rounds=30,
            late_game_hard_round=24,
            base_move_range=1,
            base_knife_range=1,
            base_bow_range=3,
            knife_damage=2,
            bow_damage=1,
        ),
        timeline=[
            ReplayRoundEntry(
                round_no=1,
                pre_round=initial,
                strategies=strategies,
                actions=actions,
                events=round_one_events,
                post_round_units=decision.units,
                battle_escalation=decision.battle_escalation,
                effective_stats=decision.effective_stats,
                result=None,
            ),
            ReplayIntermissionEntry(
                after_round=1,
                choice=IntermissionChoicePublic.RULE_ATTEMPT,
                submitted_player_text=rule.player_text,
                submission_public_code=RuleSubmissionCode.ACCEPTED,
                accepted_rule_id=rule.rule_id,
                accepted_rule=rule,
                active_rule_before=None,
                active_rule_after=rule,
                rule_change_count_after=1,
            ),
            ReplayIntermissionEntry(
                after_round=1,
                choice=IntermissionChoicePublic.CONTINUE,
                submitted_player_text=None,
                submission_public_code=None,
                accepted_rule_id=None,
                accepted_rule=None,
                active_rule_before=rule,
                active_rule_after=rule,
                rule_change_count_after=1,
            ),
            ReplayRoundEntry(
                round_no=2,
                pre_round=post_rule,
                strategies=strategies,
                actions=actions,
                events=round_two_events,
                post_round_units=terminal.units,
                battle_escalation=terminal.battle_escalation,
                effective_stats=terminal.effective_stats,
                result=MatchResultPublic.RED_WIN,
            ),
        ],
        terminal_result=MatchResultPublic.RED_WIN,
        score_rounds=2,
        rule_change_count=1,
    )

    return {
        "match_initial.json": initial,
        "match_player_decision.json": decision,
        "rule_accepted.json": accepted,
        "rule_rejected.json": rejected,
        "match_terminal.json": terminal,
        "error_revision_conflict.json": revision_conflict,
        "advance_round.json": advance,
        "replay_terminal.json": replay,
    }


def export_fixtures(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, model in build_fixtures().items():
        payload = model.model_dump(mode="json")
        (output_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Export schema-validated MVP API fixtures.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("contracts/fixtures/mvp-v0.2"),
    )
    args = parser.parse_args()
    export_fixtures(args.output_dir)


if __name__ == "__main__":
    main()
