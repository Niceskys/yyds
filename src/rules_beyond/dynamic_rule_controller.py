from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .model import Action, Event, GameConfig, GameState, Team, initial_state
from .rule_dsl import RuleAST
from .rule_engine import RuleAwareGameEngine, RuleRoundResolution
from .rule_runtime import PublicRuleHistory, initial_public_rule_histories
from .rule_validator import RuleValidator, ValidationIssue


RULE_PHASE_INTERVAL = 3
RuleCandidate = Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class RulePhaseOutcome:
    """Result of one player-rule phase.

    phase_index=0 is the pre-game phase. Later phases occur after rounds
    3, 6, 9, ... and affect the following round.
    """

    phase_index: int
    after_round: int | None
    submitted: bool
    accepted: bool
    replaced: bool
    active_rule: RuleAST | None
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True, slots=True)
class DynamicMatchState:
    game_state: GameState
    histories: Mapping[Team, PublicRuleHistory]
    active_rule: RuleAST | None
    last_phase_index: int
    pending_rule_phase_after_round: int | None = None

    @property
    def rule_phase_due(self) -> bool:
        return self.pending_rule_phase_after_round is not None


@dataclass(frozen=True, slots=True)
class DynamicStartResult:
    state: DynamicMatchState
    phase: RulePhaseOutcome
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class DynamicRoundResult:
    state: DynamicMatchState
    resolution: RuleRoundResolution
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class DynamicRulePhaseResult:
    state: DynamicMatchState
    phase: RulePhaseOutcome
    events: tuple[Event, ...]


class DynamicRuleController:
    """Deterministic V0.1 match controller for public-rule replacement.

    This controller owns *when* a player rule may be replaced. It does not own
    AI strategy, natural-language parsing, or rule semantics. Candidate rules
    are validated by RuleValidator and accepted rules are executed by the
    existing RuleAwareGameEngine.

    V0.1 cadence:
      - phase 0 before round 1;
      - then after rounds 3, 6, 9, ...;
      - an accepted rule replaces the previous player rule;
      - no submission or an invalid submission carries the previous rule;
      - rules do not expire automatically after three rounds.

    PublicRuleHistory is match-global public battle history. Replacing a rule
    changes only active_rule; it does not reset already resolved public facts.
    """

    def __init__(
        self,
        config: GameConfig | None = None,
        *,
        engine: RuleAwareGameEngine | None = None,
        validator: RuleValidator | None = None,
    ) -> None:
        if engine is not None and config is not None and engine.config != config:
            raise ValueError("engine.config must match controller config")
        self.config = config or (engine.config if engine is not None else GameConfig())
        if validator is not None and validator.config != self.config:
            raise ValueError("validator.config must match controller config")
        self.engine = engine or RuleAwareGameEngine(self.config)
        self.validator = validator or RuleValidator(self.config)

    def start_match(self, initial_submission: RuleCandidate = None) -> DynamicStartResult:
        game_state = initial_state(self.config)
        histories = initial_public_rule_histories()
        phase, phase_events = self._evaluate_phase(
            previous_rule=None,
            submission=initial_submission,
            phase_index=0,
            after_round=None,
        )
        state = DynamicMatchState(
            game_state=game_state,
            histories=histories,
            active_rule=phase.active_rule,
            last_phase_index=0,
            pending_rule_phase_after_round=None,
        )
        return DynamicStartResult(state=state, phase=phase, events=phase_events)

    def resolve_round(
        self,
        state: DynamicMatchState,
        actions: Mapping[Team, Action],
        *,
        match_seed: int,
    ) -> DynamicRoundResult:
        if state.rule_phase_due:
            raise ValueError("A due rule phase must be processed before resolving the next round")
        if state.game_state.is_terminal:
            raise ValueError("Cannot resolve a terminal game state")

        played_round = state.game_state.round_no
        resolution = self.engine.resolve_rule_round(
            state.game_state,
            actions,
            rule=state.active_rule,
            histories=state.histories,
            match_seed=match_seed,
        )

        events = list(resolution.events)
        phase_after_round: int | None = None
        if not resolution.state.is_terminal and played_round % RULE_PHASE_INTERVAL == 0:
            phase_after_round = played_round
            events.append(
                Event(
                    "RULE_PHASE_DUE",
                    details={
                        "after_round": played_round,
                        "next_phase_index": state.last_phase_index + 1,
                    },
                )
            )

        next_state = DynamicMatchState(
            game_state=resolution.state,
            histories=resolution.histories,
            active_rule=state.active_rule,
            last_phase_index=state.last_phase_index,
            pending_rule_phase_after_round=phase_after_round,
        )
        return DynamicRoundResult(
            state=next_state,
            resolution=resolution,
            events=tuple(events),
        )

    def apply_due_rule_phase(
        self,
        state: DynamicMatchState,
        submission: RuleCandidate = None,
    ) -> DynamicRulePhaseResult:
        after_round = state.pending_rule_phase_after_round
        if after_round is None:
            raise ValueError("No rule phase is due")
        if state.game_state.is_terminal:
            raise ValueError("Terminal matches cannot enter another rule phase")

        phase_index = state.last_phase_index + 1
        phase, events = self._evaluate_phase(
            previous_rule=state.active_rule,
            submission=submission,
            phase_index=phase_index,
            after_round=after_round,
        )
        next_state = DynamicMatchState(
            game_state=state.game_state,
            histories=state.histories,
            active_rule=phase.active_rule,
            last_phase_index=phase_index,
            pending_rule_phase_after_round=None,
        )
        return DynamicRulePhaseResult(state=next_state, phase=phase, events=events)

    def _evaluate_phase(
        self,
        *,
        previous_rule: RuleAST | None,
        submission: RuleCandidate,
        phase_index: int,
        after_round: int | None,
    ) -> tuple[RulePhaseOutcome, tuple[Event, ...]]:
        events: list[Event] = [
            Event(
                "RULE_PHASE_OPENED",
                details={"phase_index": phase_index, "after_round": after_round},
            )
        ]

        if submission is None:
            outcome = RulePhaseOutcome(
                phase_index=phase_index,
                after_round=after_round,
                submitted=False,
                accepted=False,
                replaced=False,
                active_rule=previous_rule,
                issues=(),
            )
            events.append(
                Event(
                    "PLAYER_RULE_CARRIED_FORWARD",
                    details={
                        "phase_index": phase_index,
                        "after_round": after_round,
                        "has_active_rule": previous_rule is not None,
                        "reason": "NO_SUBMISSION",
                    },
                )
            )
            return outcome, tuple(events)

        validation = self.validator.validate(submission)
        if not validation.accepted or validation.rule is None:
            outcome = RulePhaseOutcome(
                phase_index=phase_index,
                after_round=after_round,
                submitted=True,
                accepted=False,
                replaced=False,
                active_rule=previous_rule,
                issues=validation.issues,
            )
            events.append(
                Event(
                    "PLAYER_RULE_REJECTED",
                    details={
                        "phase_index": phase_index,
                        "after_round": after_round,
                        "issue_codes": tuple(issue.code for issue in validation.issues),
                        "previous_rule_retained": previous_rule is not None,
                    },
                )
            )
            return outcome, tuple(events)

        outcome = RulePhaseOutcome(
            phase_index=phase_index,
            after_round=after_round,
            submitted=True,
            accepted=True,
            replaced=True,
            active_rule=validation.rule,
            issues=(),
        )
        events.append(
            Event(
                "PLAYER_RULE_REPLACED",
                details={
                    "phase_index": phase_index,
                    "after_round": after_round,
                    "had_previous_rule": previous_rule is not None,
                },
            )
        )
        return outcome, tuple(events)
