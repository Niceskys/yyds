from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .model import Action, Event, GameConfig, GameState, Team, initial_state
from .rule_dsl import RuleAST
from .rule_engine import RuleAwareGameEngine, RuleRoundResolution
from .rule_runtime import PublicRuleHistory, initial_public_rule_histories
from .rule_validator import RuleValidator, ValidationIssue


RuleCandidate = Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class IntermissionOutcome:
    """Result of one rule attempt inside a single player-decision intermission.

    A rejected attempt keeps ``active_rule`` and ``rule_change_count`` unchanged
    and leaves the intermission open so the player may retry. An accepted attempt
    replaces ``active_rule``, increments ``rule_change_count`` and locks further
    replacement until the intermission is closed by ``continue_match``.
    """

    after_round: int
    submitted: bool
    accepted: bool
    replaced: bool
    active_rule: RuleAST | None
    issues: tuple[ValidationIssue, ...]
    rule_changed_this_intermission: bool
    rule_change_count: int


@dataclass(frozen=True, slots=True)
class DynamicMatchState:
    """Authoritative V0.2 controller state for one match.

    ``pending_intermission_after_round`` is set exactly when a non-terminal
    complete round has just been resolved and the match is paused in the
    player-decision intermission. ``rule_changed_this_intermission`` tracks
    whether the current intermission already accepted one successful
    replacement.
    """

    game_state: GameState
    histories: Mapping[Team, PublicRuleHistory]
    active_rule: RuleAST | None
    rule_change_count: int = 0
    pending_intermission_after_round: int | None = None
    rule_changed_this_intermission: bool = False

    @property
    def in_intermission(self) -> bool:
        return self.pending_intermission_after_round is not None

    @property
    def completed_rounds(self) -> int:
        """Number of fully resolved rounds.

        ``GameState.round_no`` is the next Engine round to resolve, except on a
        terminal round where it stays on the round that just ended.
        """

        if self.game_state.is_terminal:
            return self.game_state.round_no
        return self.game_state.round_no - 1

    @property
    def can_submit_rule(self) -> bool:
        return (
            self.in_intermission
            and not self.rule_changed_this_intermission
            and not self.game_state.is_terminal
        )

    @property
    def can_advance(self) -> bool:
        return not self.game_state.is_terminal


@dataclass(frozen=True, slots=True)
class DynamicStartResult:
    state: DynamicMatchState
    events: tuple[Event, ...] = ()


@dataclass(frozen=True, slots=True)
class DynamicRoundResult:
    state: DynamicMatchState
    resolution: RuleRoundResolution
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class DynamicRuleSubmissionResult:
    state: DynamicMatchState
    outcome: IntermissionOutcome
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class DynamicContinueResult:
    state: DynamicMatchState
    events: tuple[Event, ...]


class DynamicRuleController:
    """Deterministic V0.2 match controller for public-rule replacement.

    This controller owns *when* a player rule may be replaced. It does not own
    AI strategy, natural-language parsing, or rule semantics. Candidate rules
    are validated by RuleValidator and accepted rules are executed by the
    existing RuleAwareGameEngine.

    V0.2 cadence:
      - ``start_match()`` creates the match with ``active_rule = None``;
      - Round 1 resolves immediately with no pre-game phase and no player rule;
      - every non-terminal complete round opens exactly one intermission
        (``PLAYER_DECISION``) and no round may resolve until it is closed;
      - inside one intermission the player may make zero or more rejected rule
        attempts and at most one successful replacement;
      - a rejected attempt keeps the previous rule and does not increment
        ``rule_change_count``; the intermission stays open for a retry;
      - an accepted replacement increments ``rule_change_count``, locks further
        replacement for this intermission, and does not resolve the next round;
      - ``continue_match()`` closes the intermission; only then may the next
        complete round be resolved;
      - terminal matches never open another intermission.

    PublicRuleHistory is match-global public battle history. Replacing a rule
    changes only ``active_rule``; it does not reset already resolved public
    facts, and it does not touch ``GameState.no_damage_streak``.
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

    def start_match(self) -> DynamicStartResult:
        """Create a V0.2 match. Round 1 has no player rule and no pre-game phase."""

        state = DynamicMatchState(
            game_state=initial_state(self.config),
            histories=initial_public_rule_histories(),
            active_rule=None,
            rule_change_count=0,
            pending_intermission_after_round=None,
            rule_changed_this_intermission=False,
        )
        return DynamicStartResult(state=state, events=())

    def resolve_round(
        self,
        state: DynamicMatchState,
        actions: Mapping[Team, Action],
        *,
        match_seed: int,
    ) -> DynamicRoundResult:
        if state.game_state.is_terminal:
            raise ValueError("Cannot resolve a terminal game state")
        if state.in_intermission:
            raise ValueError("An intermission is pending; continue before resolving the next round")

        played_round = state.game_state.round_no
        resolution = self.engine.resolve_rule_round(
            state.game_state,
            actions,
            rule=state.active_rule,
            histories=state.histories,
            match_seed=match_seed,
        )

        events = list(resolution.events)
        pending_intermission_after_round: int | None = None
        if not resolution.state.is_terminal:
            pending_intermission_after_round = played_round
            events.append(
                Event(
                    "INTERMISSION_OPENED",
                    details={"after_round": played_round},
                )
            )

        next_state = DynamicMatchState(
            game_state=resolution.state,
            histories=resolution.histories,
            active_rule=state.active_rule,
            rule_change_count=state.rule_change_count,
            pending_intermission_after_round=pending_intermission_after_round,
            rule_changed_this_intermission=False,
        )
        return DynamicRoundResult(
            state=next_state,
            resolution=resolution,
            events=tuple(events),
        )

    def submit_rule(
        self,
        state: DynamicMatchState,
        candidate: RuleCandidate = None,
    ) -> DynamicRuleSubmissionResult:
        """Attempt one rule replacement inside the open intermission.

        ``candidate is None`` means the player attempted a submission but no
        candidate rule was produced; it is a rejected attempt, not a silent
        continue. Use ``continue_match`` to leave the intermission without a
        rule attempt.
        """

        after_round = self._require_open_intermission(state)
        if state.rule_changed_this_intermission:
            raise ValueError("This intermission already accepted a rule replacement")

        previous_rule = state.active_rule

        if candidate is None:
            outcome = IntermissionOutcome(
                after_round=after_round,
                submitted=True,
                accepted=False,
                replaced=False,
                active_rule=previous_rule,
                issues=(),
                rule_changed_this_intermission=False,
                rule_change_count=state.rule_change_count,
            )
            events = (
                Event(
                    "PLAYER_RULE_REJECTED",
                    details={
                        "after_round": after_round,
                        "reason": "NO_CANDIDATE",
                        "issue_codes": (),
                        "previous_rule_retained": previous_rule is not None,
                    },
                ),
            )
            return DynamicRuleSubmissionResult(state=state, outcome=outcome, events=events)

        validation = self.validator.validate(candidate)
        if not validation.accepted or validation.rule is None:
            issues = validation.issues
            outcome = IntermissionOutcome(
                after_round=after_round,
                submitted=True,
                accepted=False,
                replaced=False,
                active_rule=previous_rule,
                issues=issues,
                rule_changed_this_intermission=False,
                rule_change_count=state.rule_change_count,
            )
            events = (
                Event(
                    "PLAYER_RULE_REJECTED",
                    details={
                        "after_round": after_round,
                        "reason": "RULE_REJECTED",
                        "issue_codes": tuple(issue.code for issue in issues),
                        "previous_rule_retained": previous_rule is not None,
                    },
                ),
            )
            return DynamicRuleSubmissionResult(state=state, outcome=outcome, events=events)

        rule_change_count = state.rule_change_count + 1
        outcome = IntermissionOutcome(
            after_round=after_round,
            submitted=True,
            accepted=True,
            replaced=True,
            active_rule=validation.rule,
            issues=(),
            rule_changed_this_intermission=True,
            rule_change_count=rule_change_count,
        )
        next_state = DynamicMatchState(
            game_state=state.game_state,
            histories=state.histories,
            active_rule=validation.rule,
            rule_change_count=rule_change_count,
            pending_intermission_after_round=after_round,
            rule_changed_this_intermission=True,
        )
        events = (
            Event(
                "PLAYER_RULE_REPLACED",
                details={
                    "after_round": after_round,
                    "had_previous_rule": previous_rule is not None,
                    "rule_change_count": rule_change_count,
                },
            ),
        )
        return DynamicRuleSubmissionResult(state=next_state, outcome=outcome, events=events)

    def continue_match(self, state: DynamicMatchState) -> DynamicContinueResult:
        """Close the open intermission and allow the next complete round."""

        after_round = self._require_open_intermission(state)
        next_state = DynamicMatchState(
            game_state=state.game_state,
            histories=state.histories,
            active_rule=state.active_rule,
            rule_change_count=state.rule_change_count,
            pending_intermission_after_round=None,
            rule_changed_this_intermission=False,
        )
        events = (
            Event(
                "PLAYER_CONTINUED",
                details={
                    "after_round": after_round,
                    "rule_changed_this_intermission": state.rule_changed_this_intermission,
                },
            ),
        )
        return DynamicContinueResult(state=next_state, events=events)

    def _require_open_intermission(self, state: DynamicMatchState) -> int:
        if state.game_state.is_terminal:
            raise ValueError("Terminal matches cannot enter a player decision intermission")
        if state.pending_intermission_after_round is None:
            raise ValueError("No player decision intermission is open")
        return state.pending_intermission_after_round
