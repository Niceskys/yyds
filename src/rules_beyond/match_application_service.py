"""A1 application layer: V0.2 match orchestration over the frozen controller.

Scope of this module (Issue #49 / A1):

    create_match()
    get_match_snapshot()
    submit_public_rule()
    advance_match()
    get_replay()

This layer owns *orchestration and public projection only*. It never re-implements
gameplay:

- ``DynamicRuleController`` (V0.2 intermission cadence) owns rule cadence,
  ``active_rule`` and ``rule_change_count``.
- ``VerifiedNaturalLanguageDynamicController`` owns the verified
  text -> Intent Guard -> translator -> RuleValidator -> Faithfulness -> candidate
  pipeline.
- ``IsolatedStrategyAgent`` owns one private per-team strategy session.
- ``DeterministicIntentPlanner`` maps a public intent to a concrete legal action.
- ``RuleAwareGameEngine`` remains the final authority on movement, damage, RNG,
  anti-stall ("战局升温"), and terminal results.

Deliberately NOT implemented here (A2 / A3):

    repository persistence, match_id lookup, revision CAS, per-match lock,
    Idempotency-Key, FastAPI routes, WebSocket, Redis, Celery, DB, web/**

A1 owns exactly one in-memory match aggregate. ``create_match`` may therefore be
called once per service instance. A2 replaces this with a repository keyed by
``match_id``; the method signatures are intentionally small so that A2 can add
``match_id`` resolution without touching the gameplay/projection logic.

Atomicity guarantee
-------------------
``advance_match()`` never publishes ``continue_match()`` alone. All mutations are
committed to the aggregate only after a complete round has been resolved, so a
provider/planner failure cannot leave a half-resolved round visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import secrets
from typing import Any, Mapping

from .api_contract import (
    ActionPublicView,
    AdvanceResult,
    BattleEscalationSnapshot,
    BoardSnapshot,
    DirectionPublic,
    EffectiveStatsPublicView,
    ErrorCode,
    GameConfigPublicView,
    IntermissionChoicePublic,
    MatchLifecycle,
    MatchResultPublic,
    MatchSnapshot,
    PlayerDecisionSnapshot,
    PositionSnapshot,
    PublicStrategyDecision,
    ReplayEntry,
    ReplayIntermissionEntry,
    ReplayRoundEntry,
    ReplaySnapshot,
    RoundEventPublicView,
    RoundExecutionPublicView,
    RuleAstPublicView,
    RuleConditionPublicView,
    RuleConditionTypePublic,
    RuleDurationPublic,
    RuleEffectPublicView,
    RuleEffectTypePublic,
    RulePublicView,
    RuleSubmissionCode,
    RuleSubmissionResult,
    RuleTargetPublic,
    RuleWeaponPublic,
    StrategyDecisionStatusPublic,
    StrategyIntentPublic,
    TeamActionMap,
    TeamLatestStrategyMap,
    TeamRoundStrategyMap,
    TeamStatsMap,
    TeamPublic,
    TeamUnitMap,
    UnitSnapshot,
    WeaponPublic,
)
from .dynamic_rule_controller import DynamicMatchState
from .model import Action, Event, GameConfig, MatchResult, Team
from .natural_language_dynamic_controller import (
    NaturalLanguageRuleAttempt,
    VerifiedNaturalLanguageDynamicController,
)
from .natural_language_rule_adapter import TranslationStatus
from .rule_dsl import RuleAST, RuleEffect
from .rule_engine import RuleAwareGameEngine, RuleEffectiveStats
from .strategy_agent import (
    DeterministicIntentPlanner,
    IsolatedStrategyAgent,
    StrategyDecision,
    StrategyDecisionStatus,
)
from .verified_natural_language_rule_adapter import VerifiedTranslationStatus


# ---------------------------------------------------------------------------
# Application errors (A3 maps these to HTTP ErrorEnvelope; A1 does not)
# ---------------------------------------------------------------------------


class MatchApplicationError(Exception):
    """Base class for typed application-layer failures.

    ``error_code`` uses the frozen public ``ErrorCode`` enum so A3 can map the
    error without re-deriving it. A1 deliberately does not build ``ErrorEnvelope``.
    """

    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR
    retryable: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MatchNotFoundError(MatchApplicationError):
    error_code = ErrorCode.MATCH_NOT_FOUND


class MatchAlreadyExistsError(MatchApplicationError):
    error_code = ErrorCode.INVALID_REQUEST


class MatchTerminalError(MatchApplicationError):
    error_code = ErrorCode.MATCH_TERMINAL


class RuleSubmissionNotAllowedError(MatchApplicationError):
    error_code = ErrorCode.RULE_SUBMISSION_NOT_ALLOWED


class AdvanceNotAllowedError(MatchApplicationError):
    error_code = ErrorCode.ADVANCE_NOT_ALLOWED


class RecoverableMatchFailure(MatchApplicationError):
    """Internal provider/planner failure that must not expose a partial round."""

    error_code = ErrorCode.INTERNAL_ERROR
    retryable = True


# ---------------------------------------------------------------------------
# Public projection helpers
# ---------------------------------------------------------------------------

def _rule_ast_public(rule: RuleAST) -> RuleAstPublicView:
    conditions = [
        RuleConditionPublicView(
            type=RuleConditionTypePublic(condition.type.value),
            value=condition.value,
            weapon=(
                RuleWeaponPublic(condition.weapon.value)
                if condition.weapon is not None
                else None
            ),
        )
        for condition in rule.conditions
    ]
    effect: RuleEffect = rule.effect
    return RuleAstPublicView(
        version=rule.version,
        target=RuleTargetPublic(rule.target.value),
        conditions=conditions,
        effect=RuleEffectPublicView(
            type=RuleEffectTypePublic(effect.type.value),
            delta=effect.delta,
            multiplier=effect.multiplier,
            weapon=(
                RuleWeaponPublic(effect.weapon.value) if effect.weapon is not None else None
            ),
            rounds=effect.rounds,
        ),
        duration=RuleDurationPublic(rule.duration.value),
    )


def _rule_public_view(rule: RuleAST, *, rule_id: str, player_text: str) -> RulePublicView:
    return RulePublicView(
        rule_id=rule_id,
        player_text=player_text,
        ast=_rule_ast_public(rule),
    )


def _strategy_public(decision: StrategyDecision) -> PublicStrategyDecision:
    """Project one isolated-agent decision to the public strategy DTO.

    ``raw_model_output`` and ``error_message`` never cross this boundary.
    """

    return PublicStrategyDecision(
        status=StrategyDecisionStatusPublic(decision.status.value),
        intent=StrategyIntentPublic(decision.intent.value),
        degraded=decision.status is not StrategyDecisionStatus.ACCEPTED,
    )


def _action_public(action: Action) -> ActionPublicView:
    return ActionPublicView(
        move_path=[DirectionPublic(step.value) for step in action.move_path],
        attack=WeaponPublic(action.attack.value) if action.attack is not None else None,
    )


def _json_safe(value: Any) -> Any:
    """Convert Engine event detail values into JSON-safe primitives."""

    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return _json_safe(enum_value)
    return str(value)


def _events_public(events: tuple[Event, ...]) -> list[RoundEventPublicView]:
    return [
        RoundEventPublicView(
            kind=event.kind,
            actor=TeamPublic(event.actor.value) if event.actor is not None else None,
            details=_json_safe(dict(event.details)),
        )
        for event in events
    ]


def _units_public(state: DynamicMatchState) -> TeamUnitMap:
    return TeamUnitMap(
        RED=_unit_public(state, Team.RED),
        BLUE=_unit_public(state, Team.BLUE),
    )


def _unit_public(state: DynamicMatchState, team: Team) -> UnitSnapshot:
    unit = state.game_state.unit(team)
    return UnitSnapshot(
        team=TeamPublic(team.value),
        hp=unit.hp,
        position=PositionSnapshot(row=unit.position.row, col=unit.position.col),
    )


def _stats_public(stats: RuleEffectiveStats) -> EffectiveStatsPublicView:
    return EffectiveStatsPublicView(
        move_range=stats.move_range,
        knife_range=stats.knife_range,
        bow_range=stats.bow_range,
        knife_damage=stats.knife_damage,
        bow_damage=stats.bow_damage,
        bow_hit_multiplier=stats.bow_hit_multiplier,
        bow_hit_floor=stats.bow_hit_floor,
        cooldown_weapons=[
            WeaponPublic(weapon.value)
            for weapon in sorted(stats.cooldown_weapons, key=lambda item: item.value)
        ],
        conflict_level=stats.conflict_level,
        hard_liveness=stats.hard_liveness,
    )


def _result_public(result: MatchResult | None) -> MatchResultPublic | None:
    if result is None:
        return None
    return MatchResultPublic(result.value)


_SUBMISSION_MESSAGES: Mapping[RuleSubmissionCode, str] = {
    RuleSubmissionCode.ACCEPTED: "规则已生效。",
    RuleSubmissionCode.NO_CANDIDATE: "当前规则系统无法把这句话安全地转成一条公共规则。",
    RuleSubmissionCode.RULE_REJECTED: "这条规则不符合当前公共规则限制。",
    RuleSubmissionCode.FAITHFULNESS_REJECTED: "这句话无法被完整、忠实地表达，已拒绝。",
    RuleSubmissionCode.MODEL_UNAVAILABLE: "规则解析服务暂时不可用，请稍后重试。",
}

_REPHRASE_HINT = "请用明确数值描述单一效果，例如：双方移动距离增加1格。"


def _submission_code(attempt: NaturalLanguageRuleAttempt) -> RuleSubmissionCode:
    """Map a verified-pipeline attempt to the frozen public submission code."""

    if attempt.outcome.accepted:
        return RuleSubmissionCode.ACCEPTED

    translation = attempt.translation
    if translation is None:
        return RuleSubmissionCode.NO_CANDIDATE

    status = translation.status
    if status is VerifiedTranslationStatus.SEMANTIC_REJECTED:
        return RuleSubmissionCode.FAITHFULNESS_REJECTED
    if status is VerifiedTranslationStatus.VERIFIER_ERROR:
        return RuleSubmissionCode.MODEL_UNAVAILABLE
    if status is VerifiedTranslationStatus.INTENT_GUARD_REJECTED:
        return RuleSubmissionCode.RULE_REJECTED

    # BASE_REJECTED: the base translator failed before semantic verification.
    base_status = translation.base.status
    if base_status is TranslationStatus.MODEL_ERROR:
        return RuleSubmissionCode.MODEL_UNAVAILABLE
    if base_status is TranslationStatus.NO_CANDIDATE:
        return RuleSubmissionCode.NO_CANDIDATE
    return RuleSubmissionCode.RULE_REJECTED


# ---------------------------------------------------------------------------
# Aggregate + service
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _MatchAggregate:
    """Minimal A1 in-memory match record. A2 replaces this with a repository."""

    match_id: str
    seed: int
    state: DynamicMatchState
    revision: int = 0
    active_rule_view: RulePublicView | None = None
    latest_strategy: dict[Team, PublicStrategyDecision | None] = field(
        default_factory=lambda: {Team.RED: None, Team.BLUE: None}
    )
    timeline: list[ReplayEntry] = field(default_factory=list)


class MatchApplicationService:
    """A1 application service for one in-memory V0.2 match."""

    def __init__(
        self,
        *,
        red_agent: IsolatedStrategyAgent,
        blue_agent: IsolatedStrategyAgent,
        rule_pipeline: VerifiedNaturalLanguageDynamicController,
        planner: DeterministicIntentPlanner | None = None,
    ) -> None:
        if red_agent.team is not Team.RED or blue_agent.team is not Team.BLUE:
            raise ValueError("MatchApplicationService requires one RED and one BLUE agent")
        if red_agent is blue_agent:
            raise ValueError("RED and BLUE must use distinct strategy agent sessions")
        self._red_agent = red_agent
        self._blue_agent = blue_agent
        self._rules = rule_pipeline
        self._planner = planner or DeterministicIntentPlanner()
        self._match: _MatchAggregate | None = None

    # -- read-only accessors -------------------------------------------------

    @property
    def config(self) -> GameConfig:
        return self._rules.config

    @property
    def engine(self) -> RuleAwareGameEngine:
        return self._rules.engine

    @property
    def match_id(self) -> str | None:
        return None if self._match is None else self._match.match_id

    @property
    def seed(self) -> int | None:
        return None if self._match is None else self._match.seed

    @property
    def controller_state(self) -> DynamicMatchState:
        """A1 diagnostic accessor (not part of the public contract)."""

        return self._require_match().state

    # -- application API -----------------------------------------------------

    def create_match(
        self,
        *,
        seed: int | None = None,
        match_id: str | None = None,
    ) -> MatchSnapshot:
        """Create a V0.2 match. Never runs a round and never calls a provider."""

        if self._match is not None:
            raise MatchAlreadyExistsError(
                "This A1 service instance already owns a match; A2 adds repository lookup."
            )

        started = self._rules.start_match()
        self._match = _MatchAggregate(
            match_id=match_id or f"match_{secrets.token_hex(8)}",
            seed=seed if seed is not None else secrets.randbits(31),
            state=started.state,
        )
        return self.get_match_snapshot()

    def get_match_snapshot(self) -> MatchSnapshot:
        match = self._require_match()
        return self._snapshot(match, match.state)

    def submit_public_rule(self, player_text: str) -> RuleSubmissionResult:
        """Attempt one public-rule replacement inside the open intermission."""

        match = self._require_match()
        state = match.state
        if state.game_state.is_terminal:
            raise MatchTerminalError("Terminal matches cannot accept rule submissions")
        if not state.can_submit_rule:
            raise RuleSubmissionNotAllowedError(
                "A public rule may only be submitted in an open player-decision intermission"
            )

        previous_view = match.active_rule_view
        applied = self._rules.submit_rule(state, player_text)
        attempt = applied.attempt
        outcome = attempt.outcome
        code = _submission_code(attempt)

        accepted_rule_view: RulePublicView | None = None
        if outcome.accepted and outcome.active_rule is not None:
            accepted_rule_view = _rule_public_view(
                outcome.active_rule,
                rule_id=f"rule_{match.match_id}_{outcome.rule_change_count}",
                player_text=player_text,
            )

        # Commit only after the whole attempt has been classified.
        if accepted_rule_view is not None:
            match.state = applied.state
            match.active_rule_view = accepted_rule_view
            match.revision += 1

        match.timeline.append(
            ReplayIntermissionEntry(
                after_round=outcome.after_round,
                choice=IntermissionChoicePublic.RULE_ATTEMPT,
                submitted_player_text=player_text,
                submission_public_code=code,
                accepted_rule_id=(
                    accepted_rule_view.rule_id if accepted_rule_view is not None else None
                ),
                accepted_rule=accepted_rule_view,
                active_rule_before=previous_view,
                active_rule_after=(
                    accepted_rule_view if accepted_rule_view is not None else previous_view
                ),
                rule_change_count_after=outcome.rule_change_count,
            )
        )

        accepted = accepted_rule_view is not None
        return RuleSubmissionResult(
            accepted=accepted,
            public_code=code,
            message=_SUBMISSION_MESSAGES.get(code, "规则提交未生效。"),
            suggested_rephrase=(
                None
                if code in (RuleSubmissionCode.ACCEPTED, RuleSubmissionCode.MODEL_UNAVAILABLE)
                else _REPHRASE_HINT
            ),
            candidate_preview=(
                accepted_rule_view.ast if accepted_rule_view is not None else None
            ),
            rule_id=accepted_rule_view.rule_id if accepted_rule_view is not None else None,
            match=self._snapshot(match, match.state),
        )

    def advance_match(self) -> AdvanceResult:
        """Atomically resolve one complete round and return the stable snapshot.

        If the match is paused in ``PLAYER_DECISION``, ``continue_match()`` is an
        internal step of this operation. The intermediate
        "intermission closed, round not yet resolved" state is never returned,
        stored in the aggregate, or written to Replay as a snapshot.
        """

        match = self._require_match()
        state = match.state
        if state.game_state.is_terminal:
            raise MatchTerminalError("Terminal matches cannot advance")
        if not state.can_advance:
            raise AdvanceNotAllowedError("The match is not in an advanceable state")

        pre_round = self._snapshot(match, state)
        played_round = state.game_state.round_no

        pending_entries: list[ReplayEntry] = []
        working = state
        if working.in_intermission:
            after_round = working.pending_intermission_after_round
            if after_round is None:
                raise RecoverableMatchFailure("Intermission state is inconsistent")
            active_view = match.active_rule_view
            pending_entries.append(
                ReplayIntermissionEntry(
                    after_round=after_round,
                    choice=IntermissionChoicePublic.CONTINUE,
                    submitted_player_text=None,
                    submission_public_code=None,
                    accepted_rule_id=None,
                    accepted_rule=None,
                    active_rule_before=active_view,
                    active_rule_after=active_view,
                    rule_change_count_after=working.rule_change_count,
                )
            )
            working = self._rules.continue_match(working).state

        engine = self.engine
        try:
            red_decision = self._red_agent.decide(
                working.game_state,
                engine,
                rule=working.active_rule,
                histories=working.histories,
                remember=False,
            )
            blue_decision = self._blue_agent.decide(
                working.game_state,
                engine,
                rule=working.active_rule,
                histories=working.histories,
                remember=False,
            )
            red_action = self._planner.choose_action(
                working.game_state,
                Team.RED,
                engine,
                rule=working.active_rule,
                histories=working.histories,
                intent=red_decision.intent,
            )
            blue_action = self._planner.choose_action(
                working.game_state,
                Team.BLUE,
                engine,
                rule=working.active_rule,
                histories=working.histories,
                intent=blue_decision.intent,
            )
            resolved = self._rules.resolve_round(
                working,
                {Team.RED: red_action, Team.BLUE: blue_action},
                match_seed=match.seed,
            )
        except Exception as exc:  # no aggregate mutation has happened yet
            raise RecoverableMatchFailure(
                f"Round {played_round} could not be resolved completely: {type(exc).__name__}"
            ) from exc

        next_state = resolved.state
        red_public = _strategy_public(red_decision)
        blue_public = _strategy_public(blue_decision)
        strategies = TeamRoundStrategyMap(RED=red_public, BLUE=blue_public)
        actions = TeamActionMap(
            RED=_action_public(red_action),
            BLUE=_action_public(blue_action),
        )
        # Engine facts only: the controller's INTERMISSION_OPENED event is
        # represented by the intermission timeline entry, not as an Engine event.
        events = _events_public(resolved.resolution.events)
        next_latest_strategy: dict[Team, PublicStrategyDecision | None] = {
            Team.RED: red_public,
            Team.BLUE: blue_public,
        }

        round_entry = ReplayRoundEntry(
            round_no=played_round,
            pre_round=pre_round,
            strategies=strategies,
            actions=actions,
            events=events,
            post_round_units=_units_public(next_state),
            battle_escalation=self._escalation(next_state),
            effective_stats=self._stats_map(next_state),
            result=_result_public(next_state.game_state.result),
        )

        # Build the whole response before mutating anything, so a projection
        # failure cannot leave a partially committed round.
        advance_result = AdvanceResult(
            round=RoundExecutionPublicView(
                round_no=played_round,
                strategies=strategies,
                actions=actions,
                events=events,
            ),
            match=self._snapshot(
                match,
                next_state,
                revision=match.revision + 1,
                latest_strategy=next_latest_strategy,
            ),
        )

        # Atomic commit. Strategy memory is committed last and only after the
        # complete round succeeded, so a failed advance cannot leave phantom
        # round memory in either isolated agent.
        match.state = next_state
        match.latest_strategy = next_latest_strategy
        match.revision += 1
        match.timeline.extend(pending_entries)
        match.timeline.append(round_entry)
        self._red_agent.commit_decision_memory(
            red_decision,
            round_no=played_round,
            rule=working.active_rule,
        )
        self._blue_agent.commit_decision_memory(
            blue_decision,
            round_no=played_round,
            rule=working.active_rule,
        )

        return advance_result

    def get_replay(self) -> ReplaySnapshot:
        """Return the recorded public timeline. Never calls a model or the Engine."""

        match = self._require_match()
        state = match.state
        config = self.config
        return ReplaySnapshot(
            match_id=match.match_id,
            seed=match.seed,
            initial_config=GameConfigPublicView(
                rows=config.rows,
                cols=config.cols,
                initial_hp=config.initial_hp,
                max_rounds=config.max_rounds,
                late_game_hard_round=config.late_game_hard_round,
                base_move_range=config.base_move_range,
                base_knife_range=config.base_knife_range,
                base_bow_range=config.base_bow_range,
                knife_damage=config.knife_damage,
                bow_damage=config.bow_damage,
            ),
            timeline=[entry.model_copy(deep=True) for entry in match.timeline],
            terminal_result=_result_public(state.game_state.result),
            score_rounds=state.completed_rounds,
            rule_change_count=state.rule_change_count,
        )

    # -- projection ----------------------------------------------------------

    def _require_match(self) -> _MatchAggregate:
        if self._match is None:
            raise MatchNotFoundError("No match has been created in this service instance")
        return self._match

    def _stats_map(self, state: DynamicMatchState) -> TeamStatsMap:
        return TeamStatsMap(
            RED=_stats_public(self._team_stats(state, Team.RED)),
            BLUE=_stats_public(self._team_stats(state, Team.BLUE)),
        )

    def _team_stats(self, state: DynamicMatchState, team: Team) -> RuleEffectiveStats:
        return self.engine.effective_stats_for_team(
            state.game_state,
            team,
            rule=state.active_rule,
            histories=state.histories,
        )

    def _escalation(self, state: DynamicMatchState) -> BattleEscalationSnapshot:
        """Project authoritative anti-stall state; never re-implement its math."""

        red = self._team_stats(state, Team.RED)
        blue = self._team_stats(state, Team.BLUE)
        streak = state.game_state.no_damage_streak
        hard = red.hard_liveness or blue.hard_liveness
        level = max(red.conflict_level, blue.conflict_level)
        if hard:
            return BattleEscalationSnapshot(
                level=4,
                no_damage_streak=streak,
                next_level_at_no_damage=None,
                rounds_until_next_level=None,
                hard_liveness_active=True,
            )
        next_threshold = self._next_escalation_threshold(streak)
        return BattleEscalationSnapshot(
            level=level,
            no_damage_streak=streak,
            next_level_at_no_damage=next_threshold,
            rounds_until_next_level=(
                None if next_threshold is None else next_threshold - streak
            ),
            hard_liveness_active=False,
        )

    def _next_escalation_threshold(self, streak: int) -> int | None:
        """Probe the authoritative ``GameEngine.conflict_level`` for the next level."""

        current = self.engine.conflict_level(streak)
        probe = streak + 1
        while True:
            probe_level = self.engine.conflict_level(probe)
            if probe_level > current:
                return probe
            if probe_level >= 4:
                return None
            probe += 1

    def _snapshot(
        self,
        match: _MatchAggregate,
        state: DynamicMatchState,
        *,
        revision: int | None = None,
        latest_strategy: Mapping[Team, PublicStrategyDecision | None] | None = None,
    ) -> MatchSnapshot:
        game = state.game_state
        completed = state.completed_rounds
        latest = match.latest_strategy if latest_strategy is None else latest_strategy

        if game.is_terminal:
            lifecycle = MatchLifecycle.TERMINAL
            player_decision = PlayerDecisionSnapshot(
                after_round=completed if completed >= 1 else None,
                can_submit_rule=False,
                rule_changed_this_intermission=False,
                can_advance=False,
            )
        elif state.in_intermission:
            lifecycle = MatchLifecycle.PLAYER_DECISION
            player_decision = PlayerDecisionSnapshot(
                after_round=state.pending_intermission_after_round,
                can_submit_rule=state.can_submit_rule,
                rule_changed_this_intermission=state.rule_changed_this_intermission,
                can_advance=True,
            )
        else:
            lifecycle = MatchLifecycle.RUNNING
            player_decision = PlayerDecisionSnapshot(
                after_round=None,
                can_submit_rule=False,
                rule_changed_this_intermission=False,
                can_advance=True,
            )

        return MatchSnapshot(
            match_id=match.match_id,
            revision=match.revision if revision is None else revision,
            lifecycle=lifecycle,
            seed=match.seed,
            round_no=game.round_no,
            completed_rounds=completed,
            score_rounds=completed,
            rule_change_count=state.rule_change_count,
            board=BoardSnapshot(rows=self.config.rows, cols=self.config.cols),
            units=_units_public(state),
            active_rule=match.active_rule_view,
            player_decision=player_decision,
            effective_stats=self._stats_map(state),
            latest_strategy=TeamLatestStrategyMap(
                RED=latest.get(Team.RED),
                BLUE=latest.get(Team.BLUE),
            ),
            battle_escalation=self._escalation(state),
            result=_result_public(game.result),
        )
