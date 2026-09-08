from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api_contract import (
    ActionPublicView,
    AdvanceResult,
    BoardSnapshot,
    EffectiveStatsPublicView,
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    GameConfigPublicView,
    MatchLifecycle,
    MatchResultPublic,
    MatchSnapshot,
    PositionSnapshot,
    PublicStrategyDecision,
    ReplayRoundEntry,
    ReplayRulePhaseEntry,
    ReplaySnapshot,
    RiskBudgetPublic,
    RoundEventPublicView,
    RoundExecutionPublicView,
    RuleAstPublicView,
    RuleDurationPublic,
    RuleEffectPublicView,
    RuleEffectTypePublic,
    RulePhaseSnapshot,
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


def _stats(*, move_range: int = 1, hard: bool = False) -> EffectiveStatsPublicView:
    return EffectiveStatsPublicView(
        move_range=move_range,
        knife_range=1,
        bow_range=3,
        knife_damage=2,
        bow_damage=1,
        bow_hit_multiplier=1.0,
        bow_hit_floor=0.0,
        cooldown_weapons=[],
        conflict_level=0,
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


def _running_match(*, revision: int = 7) -> MatchSnapshot:
    rule = _rule()
    return MatchSnapshot(
        match_id="match_fixture_001",
        revision=revision,
        lifecycle=MatchLifecycle.RUNNING,
        seed=1_270_000,
        round_no=2,
        board=BoardSnapshot(rows=5, cols=5),
        units=_units(),
        active_rule=rule,
        rule_phase=RulePhaseSnapshot(
            phase_index=0,
            due=False,
            next_due_after_round=3,
        ),
        effective_stats=TeamStatsMap(
            RED=_stats(move_range=2),
            BLUE=_stats(move_range=2),
        ),
        latest_strategy=TeamLatestStrategyMap(
            RED=_strategy(StrategyIntentPublic.PRESSURE),
            BLUE=_strategy(StrategyIntentPublic.KITE),
        ),
        no_damage_streak=0,
        hard_liveness_active=False,
        result=None,
    )


def _awaiting_rule_match() -> MatchSnapshot:
    base = _running_match(revision=8)
    return base.model_copy(
        update={
            "lifecycle": MatchLifecycle.AWAITING_RULE,
            "round_no": 4,
            "rule_phase": RulePhaseSnapshot(
                phase_index=1,
                due=True,
                next_due_after_round=6,
            ),
        }
    )


def _terminal_match() -> MatchSnapshot:
    base = _running_match(revision=12)
    return base.model_copy(
        update={
            "lifecycle": MatchLifecycle.TERMINAL,
            "round_no": 5,
            "units": _units(red_hp=2, blue_hp=0),
            "rule_phase": RulePhaseSnapshot(
                phase_index=1,
                due=False,
                next_due_after_round=None,
            ),
            "result": MatchResultPublic.RED_WIN,
        }
    )


def build_fixtures() -> dict[str, object]:
    running = _running_match()
    awaiting = _awaiting_rule_match()
    terminal = _terminal_match()
    rule = _rule()
    strategies = TeamRoundStrategyMap(
        RED=_strategy(StrategyIntentPublic.PRESSURE),
        BLUE=_strategy(StrategyIntentPublic.KITE),
    )
    actions = TeamActionMap(
        RED=ActionPublicView(move_path=[], attack=WeaponPublic.BOW),
        BLUE=ActionPublicView(move_path=[], attack=WeaponPublic.BOW),
    )
    events = [
        RoundEventPublicView(
            kind="BOW_HIT",
            actor=TeamPublic.RED,
            details={"damage": 1, "target": "BLUE"},
        )
    ]

    accepted = RuleSubmissionResult(
        accepted=True,
        public_code=RuleSubmissionCode.ACCEPTED,
        message="规则已生效。",
        suggested_rephrase=None,
        candidate_preview=None,
        rule_id=rule.rule_id,
        match=running,
    )
    rejected = RuleSubmissionResult(
        accepted=False,
        public_code=RuleSubmissionCode.NO_CANDIDATE,
        message="当前规则系统无法安全表达这句话。",
        suggested_rephrase="双方的移动距离增加1格",
        candidate_preview=None,
        rule_id=None,
        match=awaiting,
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
            round_no=2,
            strategies=strategies,
            actions=actions,
            events=events,
        ),
        match=running,
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
            ReplayRulePhaseEntry(
                phase_index=0,
                submitted_player_text=rule.player_text,
                submission_public_code=RuleSubmissionCode.ACCEPTED,
                accepted_rule_id=rule.rule_id,
                accepted_rule=rule,
                active_rule_before=None,
                active_rule_after=rule,
            ),
            ReplayRoundEntry(
                round_no=2,
                pre_round=running,
                strategies=strategies,
                actions=actions,
                events=events,
                post_round_units=terminal.units,
                no_damage_streak=0,
                hard_liveness_active=False,
                effective_stats=terminal.effective_stats,
                result=MatchResultPublic.RED_WIN,
            ),
        ],
        terminal_result=MatchResultPublic.RED_WIN,
    )

    return {
        "match_running.json": running,
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
        default=Path("contracts/fixtures/mvp-v0.1"),
    )
    args = parser.parse_args()
    export_fixtures(args.output_dir)


if __name__ == "__main__":
    main()
