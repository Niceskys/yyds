"""A1 MatchApplicationService coverage.

All providers are deterministic test doubles. No test in this module may touch a
real MiMo/network provider.
"""

from __future__ import annotations

import json

import pytest

from rules_beyond.api_contract import (
    IntermissionChoicePublic,
    MatchLifecycle,
    ReplayIntermissionEntry,
    ReplayRoundEntry,
    RuleSubmissionCode,
    StrategyDecisionStatusPublic,
    StrategyIntentPublic,
)
from rules_beyond.match_application_service import (
    MatchAlreadyExistsError,
    MatchApplicationService,
    MatchNotFoundError,
    MatchTerminalError,
    RecoverableMatchFailure,
    RuleSubmissionNotAllowedError,
)
from rules_beyond.model import GameConfig, Team
from rules_beyond.natural_language_dynamic_controller import (
    VerifiedNaturalLanguageDynamicController,
)
from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from rules_beyond.rule_validator import RuleValidator
from rules_beyond.strategy_agent import (
    DeterministicIntentPlanner,
    IsolatedStrategyAgent,
    StrategyIntent,
)
from rules_beyond.verified_natural_language_rule_adapter import (
    VerifiedNaturalLanguageRuleAdapter,
)

MOVE_RULE_TEXT = "双方移动距离增加1格。"
MOVE_RULE_JSON = json.dumps(
    {
        "decision": "CANDIDATE",
        "candidate": {
            "version": "v0.1",
            "target": "ALL_UNITS",
            "conditions": [],
            "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
            "duration": "UNTIL_REPLACED",
        },
    },
    ensure_ascii=False,
)

NO_CANDIDATE_JSON = '{"decision":"NO_CANDIDATE","reason_code":"CANNOT_MAP_SAFELY"}'


class CountingRuleModel:
    """Deterministic translator + faithfulness double with call counters."""

    def __init__(self, responses: dict[str, str] | None = None, *, faithful: bool = True) -> None:
        self.responses = dict(responses or {})
        self.faithful = faithful
        self.translation_calls = 0
        self.faithfulness_calls = 0

    @property
    def calls(self) -> int:
        return self.translation_calls + self.faithfulness_calls

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        if "semantic verifier" in system_prompt:
            self.faithfulness_calls += 1
            if self.faithful:
                return '{"decision":"FAITHFUL"}'
            return '{"decision":"REJECT","reason_code":"DROPPED_INTENT"}'
        self.translation_calls += 1
        return self.responses.get(player_text, NO_CANDIDATE_JSON)


class CountingStrategyModel:
    def __init__(self, intent: str, *, fail: bool = False) -> None:
        self.intent = intent
        self.fail = fail
        self.calls = 0

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider down")
        return json.dumps({"intent": self.intent})


class FlakyStrategyAgent:
    """Forward to a real agent, raising exactly once on a chosen decide() call."""

    def __init__(self, team: Team, agent: IsolatedStrategyAgent, *, fail_on_call: int) -> None:
        self.team = team
        self._agent = agent
        self._fail_on_call = fail_on_call
        self.calls = 0

    def decide(self, state, engine, *, rule, histories, remember: bool = True):  # noqa: ANN001
        self.calls += 1
        if self.calls == self._fail_on_call:
            raise RuntimeError("agent exploded")
        return self._agent.decide(
            state,
            engine,
            rule=rule,
            histories=histories,
            remember=remember,
        )

    def commit_decision_memory(self, decision, *, round_no, rule):  # noqa: ANN001
        self._agent.commit_decision_memory(decision, round_no=round_no, rule=rule)

    @property
    def private_memory(self):
        return self._agent.private_memory


class FlakyPlanner:
    """Forward to the real planner, raising exactly once on a chosen call."""

    def __init__(self, planner: DeterministicIntentPlanner, *, fail_on_call: int) -> None:
        self._planner = planner
        self._fail_on_call = fail_on_call
        self.calls = 0

    def choose_action(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.calls += 1
        if self.calls == self._fail_on_call:
            raise RuntimeError("planner exploded")
        return self._planner.choose_action(*args, **kwargs)


def _service(
    *,
    responses: dict[str, str] | None = None,
    faithful: bool = True,
    red_intent: str = "PRESSURE",
    blue_intent: str = "KITE",
    config: GameConfig | None = None,
    red_agent=None,
    blue_agent=None,
    planner=None,
) -> tuple[MatchApplicationService, CountingRuleModel, CountingStrategyModel, CountingStrategyModel]:
    config = config or GameConfig()
    rule_model = CountingRuleModel(responses, faithful=faithful)
    validator = RuleValidator(config)
    base = NaturalLanguageRuleAdapter(rule_model, validator)
    verified = VerifiedNaturalLanguageRuleAdapter(
        base,
        NaturalLanguageRuleFaithfulnessVerifier(rule_model),
    )
    rules = VerifiedNaturalLanguageDynamicController(verified, config)
    red_model = CountingStrategyModel(red_intent)
    blue_model = CountingStrategyModel(blue_intent)
    service = MatchApplicationService(
        red_agent=red_agent or IsolatedStrategyAgent(Team.RED, red_model),
        blue_agent=blue_agent or IsolatedStrategyAgent(Team.BLUE, blue_model),
        rule_pipeline=rules,
        planner=planner,
    )
    return service, rule_model, red_model, blue_model


# 1. create -----------------------------------------------------------------


def test_create_match_is_running_without_round_or_provider_call() -> None:
    service, rule_model, red_model, blue_model = _service()
    snapshot = service.create_match(seed=1_270_000, match_id="match_test_1")

    assert snapshot.lifecycle is MatchLifecycle.RUNNING
    assert snapshot.completed_rounds == 0
    assert snapshot.score_rounds == 0
    assert snapshot.rule_change_count == 0
    assert snapshot.active_rule is None
    assert snapshot.round_no == 1
    assert snapshot.result is None
    assert snapshot.player_decision.after_round is None
    assert snapshot.player_decision.can_submit_rule is False
    assert snapshot.player_decision.rule_changed_this_intermission is False
    assert snapshot.player_decision.can_advance is True
    assert snapshot.latest_strategy.RED is None
    assert snapshot.latest_strategy.BLUE is None

    assert rule_model.calls == 0
    assert red_model.calls == 0
    assert blue_model.calls == 0
    assert service.get_replay().timeline == []


def test_create_match_twice_is_rejected_and_unknown_match_is_not_found() -> None:
    service, *_ = _service()
    with pytest.raises(MatchNotFoundError):
        service.get_match_snapshot()

    service.create_match(seed=1)
    with pytest.raises(MatchAlreadyExistsError):
        service.create_match(seed=2)


def test_submit_before_first_advance_is_not_allowed() -> None:
    service, rule_model, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    service.create_match(seed=1)

    with pytest.raises(RuleSubmissionNotAllowedError):
        service.submit_public_rule(MOVE_RULE_TEXT)
    assert rule_model.calls == 0


# 2. first advance ----------------------------------------------------------


def test_first_advance_resolves_round_one_and_enters_player_decision() -> None:
    service, _, red_model, blue_model = _service()
    service.create_match(seed=1_270_000)

    result = service.advance_match()

    assert result.round.round_no == 1
    assert result.match.completed_rounds == 1
    assert result.match.score_rounds == 1
    assert result.match.lifecycle is MatchLifecycle.PLAYER_DECISION
    assert result.match.player_decision.after_round == 1
    assert result.match.player_decision.can_submit_rule is True
    assert result.match.player_decision.can_advance is True
    assert result.match.revision == 1
    assert red_model.calls == 1
    assert blue_model.calls == 1


def test_round_one_precedes_any_intermission_entry() -> None:
    service, *_ = _service()
    service.create_match(seed=1_270_000)
    service.advance_match()

    # The player has not acted yet, so the first recorded entry is Round 1 and
    # there is no intermission before it.
    timeline = service.get_replay().timeline
    assert isinstance(timeline[0], ReplayRoundEntry)
    assert timeline[0].round_no == 1
    assert not any(isinstance(entry, ReplayIntermissionEntry) for entry in timeline)

    service.advance_match()
    timeline = service.get_replay().timeline
    assert isinstance(timeline[1], ReplayIntermissionEntry)
    assert timeline[1].choice is IntermissionChoicePublic.CONTINUE


def test_advance_records_strategies_actions_and_engine_events() -> None:
    service, *_ = _service()
    service.create_match(seed=1_270_000)
    result = service.advance_match()

    assert result.round.strategies.RED.intent is StrategyIntentPublic.PRESSURE
    assert result.round.strategies.BLUE.intent is StrategyIntentPublic.KITE
    assert result.round.strategies.RED.status is StrategyDecisionStatusPublic.ACCEPTED
    assert result.round.actions.RED.attack is not None
    assert result.round.actions.BLUE.attack is not None
    assert result.round.events
    assert all(event.kind for event in result.round.events)

    assert result.match.latest_strategy.RED.intent is StrategyIntentPublic.PRESSURE
    assert result.match.latest_strategy.BLUE.intent is StrategyIntentPublic.KITE

    round_entry = service.get_replay().timeline[0]
    assert isinstance(round_entry, ReplayRoundEntry)
    assert round_entry.strategies == result.round.strategies
    assert round_entry.actions == result.round.actions
    assert round_entry.events == result.round.events
    assert round_entry.pre_round.lifecycle is MatchLifecycle.RUNNING
    assert round_entry.pre_round.completed_rounds == 0
    assert round_entry.result is None


# 5/6/7. rule submission ----------------------------------------------------


def test_rejected_rule_can_be_retried_and_replay_keeps_every_attempt() -> None:
    service, rule_model, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    service.create_match(seed=1_270_000)
    service.advance_match()

    first = service.submit_public_rule("这句话无法表达")
    assert first.accepted is False
    assert first.public_code is RuleSubmissionCode.NO_CANDIDATE
    assert first.rule_id is None
    assert first.candidate_preview is None
    assert first.match.rule_change_count == 0
    assert first.match.active_rule is None
    assert first.match.lifecycle is MatchLifecycle.PLAYER_DECISION
    assert first.match.player_decision.can_submit_rule is True
    assert first.match.revision == 1

    second = service.submit_public_rule("还是无法表达")
    assert second.accepted is False
    assert second.match.player_decision.can_submit_rule is True

    accepted = service.submit_public_rule(MOVE_RULE_TEXT)
    assert accepted.accepted is True
    assert accepted.public_code is RuleSubmissionCode.ACCEPTED
    assert accepted.rule_id is not None
    assert accepted.candidate_preview is not None

    timeline = service.get_replay().timeline
    assert [entry.entry_type for entry in timeline] == [
        "ROUND",
        "INTERMISSION",
        "INTERMISSION",
        "INTERMISSION",
    ]
    attempts = [entry for entry in timeline if isinstance(entry, ReplayIntermissionEntry)]
    assert [entry.choice for entry in attempts] == [
        IntermissionChoicePublic.RULE_ATTEMPT,
        IntermissionChoicePublic.RULE_ATTEMPT,
        IntermissionChoicePublic.RULE_ATTEMPT,
    ]
    assert [entry.submission_public_code for entry in attempts] == [
        RuleSubmissionCode.NO_CANDIDATE,
        RuleSubmissionCode.NO_CANDIDATE,
        RuleSubmissionCode.ACCEPTED,
    ]
    assert attempts[0].submitted_player_text == "这句话无法表达"
    assert attempts[1].submitted_player_text == "还是无法表达"
    assert rule_model.translation_calls == 3


def test_accepted_rule_updates_count_and_does_not_advance() -> None:
    service, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    service.create_match(seed=1_270_000)
    service.advance_match()

    result = service.submit_public_rule(MOVE_RULE_TEXT)

    assert result.accepted is True
    assert result.match.rule_change_count == 1
    assert result.match.active_rule is not None
    assert result.match.active_rule.player_text == MOVE_RULE_TEXT
    assert result.match.player_decision.rule_changed_this_intermission is True
    assert result.match.player_decision.can_submit_rule is False
    assert result.match.player_decision.after_round == 1
    assert result.match.player_decision.can_advance is True
    assert result.match.lifecycle is MatchLifecycle.PLAYER_DECISION
    assert result.match.completed_rounds == 1
    assert result.match.revision == 2

    # No round may be resolved by an accepted rule.
    assert [entry.entry_type for entry in service.get_replay().timeline] == [
        "ROUND",
        "INTERMISSION",
    ]


def test_second_submission_after_acceptance_is_rejected() -> None:
    service, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    service.create_match(seed=1_270_000)
    service.advance_match()
    service.submit_public_rule(MOVE_RULE_TEXT)

    with pytest.raises(RuleSubmissionNotAllowedError):
        service.submit_public_rule(MOVE_RULE_TEXT)


def test_faithfulness_rejection_maps_to_public_code() -> None:
    service, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON}, faithful=False)
    service.create_match(seed=1_270_000)
    service.advance_match()

    result = service.submit_public_rule(MOVE_RULE_TEXT)
    assert result.accepted is False
    assert result.public_code is RuleSubmissionCode.FAITHFULNESS_REJECTED
    assert result.match.rule_change_count == 0
    assert result.match.active_rule is None


# 8/9. advance after intermission -------------------------------------------


def test_advance_after_accepted_rule_continues_then_resolves_next_round() -> None:
    service, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    service.create_match(seed=1_270_000)
    service.advance_match()
    accepted = service.submit_public_rule(MOVE_RULE_TEXT)

    result = service.advance_match()

    assert result.round.round_no == 2
    assert result.match.completed_rounds == 2
    assert result.match.rule_change_count == 1
    assert result.match.active_rule is not None
    assert result.match.active_rule.rule_id == accepted.rule_id

    timeline = service.get_replay().timeline
    assert [entry.entry_type for entry in timeline] == [
        "ROUND",
        "INTERMISSION",
        "INTERMISSION",
        "ROUND",
    ]
    continue_entry = timeline[2]
    assert isinstance(continue_entry, ReplayIntermissionEntry)
    assert continue_entry.choice is IntermissionChoicePublic.CONTINUE
    assert continue_entry.after_round == 1
    assert continue_entry.active_rule_before == accepted.match.active_rule
    assert continue_entry.active_rule_after == accepted.match.active_rule
    assert continue_entry.rule_change_count_after == 1

    round_two = timeline[3]
    assert isinstance(round_two, ReplayRoundEntry)
    assert round_two.round_no == 2
    # pre_round is the last stable public state, never the internal
    # "intermission closed, round not yet resolved" RUNNING state.
    assert round_two.pre_round.lifecycle is MatchLifecycle.PLAYER_DECISION
    assert round_two.pre_round.player_decision.after_round == 1
    assert round_two.pre_round.completed_rounds == 1
    assert round_two.pre_round.active_rule == accepted.match.active_rule


def test_advance_without_rule_records_continue_entry() -> None:
    service, *_ = _service()
    service.create_match(seed=1_270_000)
    service.advance_match()

    result = service.advance_match()

    timeline = service.get_replay().timeline
    assert [entry.entry_type for entry in timeline] == [
        "ROUND",
        "INTERMISSION",
        "ROUND",
    ]
    continue_entry = timeline[1]
    assert isinstance(continue_entry, ReplayIntermissionEntry)
    assert continue_entry.choice is IntermissionChoicePublic.CONTINUE
    assert continue_entry.submitted_player_text is None
    assert continue_entry.submission_public_code is None
    assert continue_entry.rule_change_count_after == 0
    assert result.match.completed_rounds == 2
    assert result.match.rule_change_count == 0


# 10. terminal --------------------------------------------------------------


def test_terminal_snapshot_blocks_submission_and_advance() -> None:
    config = GameConfig(initial_hp=4, base_bow_range=1, knife_damage=2)
    service, rule_model, *_ = _service(
        config=config,
        red_intent="PRESSURE",
        blue_intent="HOLD",
    )
    service.create_match(seed=1_270_000)

    snapshot = service.advance_match().match
    for _ in range(40):
        if snapshot.lifecycle is MatchLifecycle.TERMINAL:
            break
        snapshot = service.advance_match().match

    assert snapshot.lifecycle is MatchLifecycle.TERMINAL
    assert snapshot.result is not None
    assert snapshot.player_decision.can_submit_rule is False
    assert snapshot.player_decision.rule_changed_this_intermission is False
    assert snapshot.player_decision.can_advance is False
    assert snapshot.player_decision.after_round == snapshot.completed_rounds

    replay = service.get_replay()
    assert replay.terminal_result is not None
    assert replay.score_rounds == snapshot.completed_rounds

    with pytest.raises(MatchTerminalError):
        service.advance_match()
    with pytest.raises(MatchTerminalError):
        service.submit_public_rule("双方移动距离增加1格。")
    assert rule_model.calls == 0


# 11/12. read-only replay + privacy -----------------------------------------


def test_replay_and_snapshot_reads_do_not_call_any_provider() -> None:
    service, rule_model, red_model, blue_model = _service(
        responses={MOVE_RULE_TEXT: MOVE_RULE_JSON}
    )
    service.create_match(seed=1_270_000)
    service.advance_match()
    service.submit_public_rule(MOVE_RULE_TEXT)
    service.advance_match()

    calls_before = (rule_model.calls, red_model.calls, blue_model.calls)
    for _ in range(3):
        service.get_replay()
        service.get_match_snapshot()
    assert (rule_model.calls, red_model.calls, blue_model.calls) == calls_before


def test_public_projection_excludes_private_and_provider_fields() -> None:
    service, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    service.create_match(seed=1_270_000)
    service.advance_match()
    service.submit_public_rule(MOVE_RULE_TEXT)
    service.advance_match()

    payload = json.dumps(
        {
            "snapshot": service.get_match_snapshot().model_dump(mode="json"),
            "replay": service.get_replay().model_dump(mode="json"),
        },
        ensure_ascii=False,
    )
    for forbidden in (
        "private_memory",
        "raw_model_output",
        "error_message",
        "system_prompt",
        "chain_of_thought",
        "reasoning",
        "provider down",
        "stack",
    ):
        assert forbidden not in payload


def test_replay_entries_are_defensive_copies() -> None:
    service, *_ = _service()
    service.create_match(seed=1_270_000)
    service.advance_match()
    assert len(service.get_replay().timeline) == 1

    first = service.get_replay()
    first.timeline.clear()
    assert len(service.get_replay().timeline) == 1


# 13. rule replacement continuity -------------------------------------------


def test_rule_replacement_preserves_public_history_and_no_damage_streak() -> None:
    service, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    service.create_match(seed=1_270_000)
    service.advance_match()

    state_before = service.controller_state
    histories_before = dict(state_before.histories)
    streak_before = state_before.game_state.no_damage_streak

    service.submit_public_rule(MOVE_RULE_TEXT)

    state_after = service.controller_state
    assert dict(state_after.histories) == histories_before
    assert state_after.game_state.no_damage_streak == streak_before
    assert state_after.active_rule is not None
    assert state_after.rule_change_count == 1

    result = service.advance_match()
    assert result.match.rule_change_count == 1
    assert result.match.active_rule is not None


# 14. ordering --------------------------------------------------------------


def test_timeline_order_and_active_rule_before_after_are_factual() -> None:
    service, *_ = _service(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    service.create_match(seed=1_270_000)
    service.advance_match()
    service.submit_public_rule(MOVE_RULE_TEXT)
    service.advance_match()
    service.submit_public_rule(MOVE_RULE_TEXT)

    timeline = service.get_replay().timeline
    assert [entry.entry_type for entry in timeline] == [
        "ROUND",
        "INTERMISSION",
        "INTERMISSION",
        "ROUND",
        "INTERMISSION",
    ]
    accepted = timeline[1]
    assert isinstance(accepted, ReplayIntermissionEntry)
    assert accepted.active_rule_before is None
    assert accepted.active_rule_after is not None
    assert accepted.rule_change_count_after == 1

    second_attempt = timeline[4]
    assert isinstance(second_attempt, ReplayIntermissionEntry)
    # A new intermission may accept one replacement; it replaces rule 1 with rule 2.
    assert second_attempt.active_rule_before == accepted.active_rule_after
    assert second_attempt.active_rule_after is not None
    assert second_attempt.active_rule_after.rule_id != accepted.active_rule_after.rule_id
    assert second_attempt.rule_change_count_after == 2

    for entry in timeline:
        if isinstance(entry, ReplayRoundEntry) and entry.round_no > 1:
            assert entry.pre_round.lifecycle is MatchLifecycle.PLAYER_DECISION


# 15/16. failure containment ------------------------------------------------


def test_provider_failure_uses_agent_fallback_without_half_round() -> None:
    service, _, _, _ = _service(
        red_agent=IsolatedStrategyAgent(Team.RED, CountingStrategyModel("PRESSURE", fail=True)),
        blue_agent=IsolatedStrategyAgent(Team.BLUE, CountingStrategyModel("KITE", fail=True)),
    )
    service.create_match(seed=1_270_000)

    first = service.advance_match()
    assert first.match.completed_rounds == 1
    assert first.round.strategies.RED.status is StrategyDecisionStatusPublic.FALLBACK_MODEL_ERROR
    assert first.round.strategies.BLUE.status is StrategyDecisionStatusPublic.FALLBACK_MODEL_ERROR
    assert first.round.strategies.RED.degraded is True

    second = service.advance_match()
    assert second.match.completed_rounds == 2
    assert second.match.lifecycle is MatchLifecycle.PLAYER_DECISION
    assert second.round.strategies.RED.status is StrategyDecisionStatusPublic.FALLBACK_MODEL_ERROR


def test_agent_failure_leaves_aggregate_and_memory_unchanged() -> None:
    red_agent = FlakyStrategyAgent(
        Team.RED,
        IsolatedStrategyAgent(Team.RED, CountingStrategyModel("PRESSURE")),
        fail_on_call=2,
    )
    service, rule_model, _, _ = _service(red_agent=red_agent)
    service.create_match(seed=1_270_000, match_id="match_atomic")
    service.advance_match()

    revision_before = service.get_match_snapshot().revision
    timeline_before = len(service.get_replay().timeline)
    memory_before = red_agent.private_memory

    with pytest.raises(RecoverableMatchFailure):
        service.advance_match()

    snapshot = service.get_match_snapshot()
    assert snapshot.revision == revision_before
    assert snapshot.completed_rounds == 1
    assert snapshot.lifecycle is MatchLifecycle.PLAYER_DECISION
    assert len(service.get_replay().timeline) == timeline_before
    assert red_agent.private_memory == memory_before
    assert rule_model.calls == 0


def test_blue_failure_after_red_decision_leaves_no_private_memory() -> None:
    red_agent = IsolatedStrategyAgent(Team.RED, CountingStrategyModel("PRESSURE"))
    blue_agent = FlakyStrategyAgent(
        Team.BLUE,
        IsolatedStrategyAgent(Team.BLUE, CountingStrategyModel("KITE")),
        fail_on_call=2,
    )
    service, *_ = _service(red_agent=red_agent, blue_agent=blue_agent)
    service.create_match(seed=1_270_000)
    service.advance_match()

    revision_before = service.get_match_snapshot().revision
    timeline_before = len(service.get_replay().timeline)
    red_before = red_agent.private_memory
    blue_before = blue_agent.private_memory

    with pytest.raises(RecoverableMatchFailure):
        service.advance_match()

    snapshot = service.get_match_snapshot()
    assert snapshot.revision == revision_before
    assert snapshot.completed_rounds == 1
    assert len(service.get_replay().timeline) == timeline_before
    assert red_agent.private_memory == red_before
    assert blue_agent.private_memory == blue_before
    assert [entry.round_no for entry in red_agent.private_memory] == [1]
    assert [entry.round_no for entry in blue_agent.private_memory] == [1]


def test_planner_failure_after_both_decisions_leaves_no_private_memory() -> None:
    red_agent = IsolatedStrategyAgent(Team.RED, CountingStrategyModel("PRESSURE"))
    blue_agent = IsolatedStrategyAgent(Team.BLUE, CountingStrategyModel("KITE"))
    planner = FlakyPlanner(DeterministicIntentPlanner(), fail_on_call=3)
    service, *_ = _service(red_agent=red_agent, blue_agent=blue_agent, planner=planner)
    service.create_match(seed=1_270_000)
    service.advance_match()

    red_before = red_agent.private_memory
    blue_before = blue_agent.private_memory
    timeline_before = len(service.get_replay().timeline)

    with pytest.raises(RecoverableMatchFailure):
        service.advance_match()

    assert red_agent.private_memory == red_before
    assert blue_agent.private_memory == blue_before
    assert service.get_match_snapshot().completed_rounds == 1
    assert len(service.get_replay().timeline) == timeline_before


def test_retry_after_failure_commits_round_memory_once() -> None:
    red_agent = IsolatedStrategyAgent(Team.RED, CountingStrategyModel("PRESSURE"))
    blue_agent = FlakyStrategyAgent(
        Team.BLUE,
        IsolatedStrategyAgent(Team.BLUE, CountingStrategyModel("KITE")),
        fail_on_call=2,
    )
    service, *_ = _service(red_agent=red_agent, blue_agent=blue_agent)
    service.create_match(seed=1_270_000)
    service.advance_match()

    with pytest.raises(RecoverableMatchFailure):
        service.advance_match()

    result = service.advance_match()

    assert result.match.completed_rounds == 2
    assert [entry.round_no for entry in red_agent.private_memory] == [1, 2]
    assert [entry.round_no for entry in blue_agent.private_memory] == [1, 2]
    assert [entry.intent for entry in red_agent.private_memory] == [
        StrategyIntent.PRESSURE,
        StrategyIntent.PRESSURE,
    ]


def test_fallback_strategy_is_committed_after_successful_round() -> None:
    red_agent = IsolatedStrategyAgent(Team.RED, CountingStrategyModel("PRESSURE", fail=True))
    blue_agent = IsolatedStrategyAgent(
        Team.BLUE,
        CountingStrategyModel("KITE", fail=True),
        fallback_intent=StrategyIntent.KITE,
    )
    service, *_ = _service(red_agent=red_agent, blue_agent=blue_agent)
    service.create_match(seed=1_270_000)

    result = service.advance_match()

    assert result.round.strategies.RED.status is StrategyDecisionStatusPublic.FALLBACK_MODEL_ERROR
    assert [entry.round_no for entry in red_agent.private_memory] == [1]
    assert [entry.round_no for entry in blue_agent.private_memory] == [1]
    assert red_agent.private_memory[0].intent is StrategyIntent.PRESSURE
    assert blue_agent.private_memory[0].intent is StrategyIntent.KITE
