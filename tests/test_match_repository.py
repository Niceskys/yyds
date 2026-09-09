"""A2 InMemoryMatchRepository coverage.

Concurrency tests are deterministic: they use ``threading.Event`` handshakes and
blocking fakes, never sleeps to guess timing. No test touches a real provider.
"""

from __future__ import annotations

import json
import threading

import pytest

from rules_beyond.api_contract import ErrorCode, StrategyIntentPublic
from rules_beyond.match_application_service import (
    MatchApplicationService,
    MatchNotFoundError,
    RecoverableMatchFailure,
)
from rules_beyond.match_repository import (
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    InMemoryMatchRepository,
    MatchServiceFactory,
    RevisionConflictError,
)
from rules_beyond.model import GameConfig, Team
from rules_beyond.natural_language_dynamic_controller import (
    VerifiedNaturalLanguageDynamicController,
)
from rules_beyond.natural_language_rule_adapter import NaturalLanguageRuleAdapter
from rules_beyond.rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from rules_beyond.rule_validator import RuleValidator
from rules_beyond.strategy_agent import IsolatedStrategyAgent
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

_JOIN_TIMEOUT = 5.0
_ENTRY_TIMEOUT = 5.0


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
    """Strategy double that counts calls, records observations and can block."""

    def __init__(
        self,
        intent: str,
        *,
        fail: bool = False,
        entered: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.intent = intent
        self.fail = fail
        self.calls = 0
        self.observations: list[str] = []
        self._entered = entered
        self._release = release

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        self.calls += 1
        self.observations.append(observation)
        if self._entered is not None:
            self._entered.set()
        if self._release is not None and not self._release.wait(timeout=_ENTRY_TIMEOUT):
            raise RuntimeError("blocking strategy model was never released")
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


def _rule_pipeline(rule_model, config: GameConfig) -> VerifiedNaturalLanguageDynamicController:
    validator = RuleValidator(config)
    base = NaturalLanguageRuleAdapter(rule_model, validator)
    verified = VerifiedNaturalLanguageRuleAdapter(
        base,
        NaturalLanguageRuleFaithfulnessVerifier(rule_model),
    )
    return VerifiedNaturalLanguageDynamicController(verified, config)


def _build_service(
    *,
    rule_model,
    red_model=None,
    blue_model=None,
    config: GameConfig | None = None,
    red_agent=None,
    blue_agent=None,
) -> MatchApplicationService:
    config = config or GameConfig()
    rules = _rule_pipeline(rule_model, config)
    return MatchApplicationService(
        red_agent=red_agent or IsolatedStrategyAgent(Team.RED, red_model),
        blue_agent=blue_agent or IsolatedStrategyAgent(Team.BLUE, blue_model),
        rule_pipeline=rules,
    )


def _counting_factory(
    *,
    red_intent: str = "PRESSURE",
    blue_intent: str = "KITE",
    responses: dict[str, str] | None = None,
    faithful: bool = True,
    config: GameConfig | None = None,
):
    red_models: list[CountingStrategyModel] = []
    blue_models: list[CountingStrategyModel] = []
    rule_models: list[CountingRuleModel] = []

    def red_make() -> CountingStrategyModel:
        model = CountingStrategyModel(red_intent)
        red_models.append(model)
        return model

    def blue_make() -> CountingStrategyModel:
        model = CountingStrategyModel(blue_intent)
        blue_models.append(model)
        return model

    def rule_make() -> CountingRuleModel:
        model = CountingRuleModel(responses, faithful=faithful)
        rule_models.append(model)
        return model

    factory = MatchServiceFactory(
        config=config,
        red_strategy_model_factory=red_make,
        blue_strategy_model_factory=blue_make,
        rule_model_factory=rule_make,
    )
    return factory, red_models, blue_models, rule_models


def _repository(**kwargs):
    factory, red_models, blue_models, rule_models = _counting_factory(**kwargs)
    repo = InMemoryMatchRepository(service_factory=factory)
    return repo, red_models, blue_models, rule_models


def _round_entries(repo: InMemoryMatchRepository, match_id: str) -> int:
    return sum(1 for entry in repo.get_replay(match_id).timeline if entry.entry_type == "ROUND")


def _intermission_entries(repo: InMemoryMatchRepository, match_id: str) -> int:
    return sum(
        1 for entry in repo.get_replay(match_id).timeline if entry.entry_type == "INTERMISSION"
    )


# 1/2. create + lookup ------------------------------------------------------


def test_create_two_matches_returns_distinct_ids_and_revision_zero() -> None:
    repo, red_models, blue_models, _ = _repository()

    first = repo.create_match(seed=1_270_000)
    second = repo.create_match(seed=1_270_000)

    assert first.match_id != second.match_id
    assert first.revision == 0
    assert second.revision == 0
    assert first.lifecycle.value == "RUNNING"
    assert len(red_models) == 2
    assert len(blue_models) == 2


def test_match_id_collision_never_overwrites_an_existing_match() -> None:
    factory, _, _, _ = _counting_factory()
    scripted = iter(["dup", "dup", "unique"])
    repo = InMemoryMatchRepository(
        service_factory=factory,
        match_id_factory=lambda: next(scripted),
    )

    first = repo.create_match(seed=1)
    second = repo.create_match(seed=2)

    assert first.match_id == "dup"
    assert second.match_id == "unique"
    assert repo.get_match_snapshot("dup").match_id == "dup"
    assert repo.get_match_snapshot("dup").revision == 0
    assert repo.get_match_snapshot("unique").match_id == "unique"


def test_unknown_match_id_raises_match_not_found() -> None:
    repo, _, _, _ = _repository()

    with pytest.raises(MatchNotFoundError):
        repo.get_match_snapshot("missing")
    with pytest.raises(MatchNotFoundError):
        repo.get_replay("missing")
    with pytest.raises(MatchNotFoundError):
        repo.advance_match("missing", expected_revision=0, idempotency_key="k")
    with pytest.raises(MatchNotFoundError):
        repo.submit_public_rule(
            "missing",
            expected_revision=0,
            idempotency_key="k",
            player_text=MOVE_RULE_TEXT,
        )


def test_empty_idempotency_key_raises_idempotency_key_required() -> None:
    repo, red_models, blue_models, _ = _repository()
    match = repo.create_match(seed=1)

    with pytest.raises(IdempotencyKeyRequiredError) as error:
        repo.advance_match(match.match_id, expected_revision=0, idempotency_key="")

    assert error.value.error_code is ErrorCode.IDEMPOTENCY_KEY_REQUIRED
    assert error.value.retryable is True
    assert repo.get_match_snapshot(match.match_id).revision == 0
    assert red_models[0].calls == 0
    assert blue_models[0].calls == 0

    with pytest.raises(IdempotencyKeyRequiredError) as rule_error:
        repo.submit_public_rule(
            match.match_id,
            expected_revision=0,
            idempotency_key="",
            player_text=MOVE_RULE_TEXT,
        )
    assert rule_error.value.error_code is ErrorCode.IDEMPOTENCY_KEY_REQUIRED


def test_whitespace_only_idempotency_key_raises_idempotency_key_required() -> None:
    repo, _, _, _ = _repository()
    match = repo.create_match(seed=1)

    for key in ("   ", "\t", "\n \t"):
        with pytest.raises(IdempotencyKeyRequiredError) as error:
            repo.advance_match(match.match_id, expected_revision=0, idempotency_key=key)
        assert error.value.error_code is ErrorCode.IDEMPOTENCY_KEY_REQUIRED
        assert error.value.retryable is True

    assert repo.get_match_snapshot(match.match_id).revision == 0


# 3/4/5. isolation ----------------------------------------------------------


def test_two_matches_advance_independently() -> None:
    repo, _, _, _ = _repository()
    match_a = repo.create_match(seed=1)
    match_b = repo.create_match(seed=2)

    first_a = repo.advance_match(match_a.match_id, expected_revision=0, idempotency_key="a1")
    first_b = repo.advance_match(match_b.match_id, expected_revision=0, idempotency_key="b1")

    assert first_a.match.revision == 1
    assert first_b.match.revision == 1
    assert repo.get_match_snapshot(match_a.match_id).completed_rounds == 1
    assert repo.get_match_snapshot(match_b.match_id).completed_rounds == 1

    second_a = repo.advance_match(match_a.match_id, expected_revision=1, idempotency_key="a2")
    assert second_a.match.completed_rounds == 2
    assert repo.get_match_snapshot(match_b.match_id).completed_rounds == 1
    assert repo.get_match_snapshot(match_b.match_id).revision == 1


def test_two_matches_rule_and_replay_do_not_share_state() -> None:
    repo, _, _, _ = _repository(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    match_a = repo.create_match(seed=1)
    match_b = repo.create_match(seed=2)

    repo.advance_match(match_a.match_id, expected_revision=0, idempotency_key="a1")
    accepted = repo.submit_public_rule(
        match_a.match_id,
        expected_revision=1,
        idempotency_key="a2",
        player_text=MOVE_RULE_TEXT,
    )

    assert accepted.accepted is True
    snapshot_a = repo.get_match_snapshot(match_a.match_id)
    snapshot_b = repo.get_match_snapshot(match_b.match_id)
    assert snapshot_a.active_rule is not None
    assert snapshot_a.rule_change_count == 1
    assert snapshot_b.active_rule is None
    assert snapshot_b.rule_change_count == 0
    assert snapshot_b.revision == 0
    assert repo.get_replay(match_b.match_id).timeline == []
    assert repo.get_replay(match_a.match_id).timeline


def test_per_match_strategy_sessions_and_private_memory_are_isolated() -> None:
    repo, red_models, blue_models, _ = _repository()
    match_a = repo.create_match(seed=1)
    match_b = repo.create_match(seed=2)

    assert len(red_models) == 2
    assert len(blue_models) == 2
    assert red_models[0] is not red_models[1]
    assert blue_models[0] is not blue_models[1]

    repo.advance_match(match_a.match_id, expected_revision=0, idempotency_key="a1")
    repo.advance_match(match_a.match_id, expected_revision=1, idempotency_key="a2")
    repo.advance_match(match_b.match_id, expected_revision=0, idempotency_key="b1")

    a_observations = red_models[0].observations
    b_observations = red_models[1].observations
    assert len(a_observations) == 2
    assert len(b_observations) == 1
    assert json.loads(b_observations[0])["private_memory"] == []
    assert [entry["round_no"] for entry in json.loads(a_observations[1])["private_memory"]] == [1]


# 6. revision CAS -----------------------------------------------------------


def test_wrong_expected_revision_raises_conflict_without_side_effects() -> None:
    repo, red_models, blue_models, rule_models = _repository(
        responses={MOVE_RULE_TEXT: MOVE_RULE_JSON}
    )
    match = repo.create_match(seed=1)

    with pytest.raises(RevisionConflictError) as conflict:
        repo.advance_match(match.match_id, expected_revision=5, idempotency_key="adv")
    assert conflict.value.error_code is ErrorCode.REVISION_CONFLICT
    assert conflict.value.retryable is True

    assert repo.get_match_snapshot(match.match_id).revision == 0
    assert repo.get_replay(match.match_id).timeline == []
    assert red_models[0].calls == 0
    assert blue_models[0].calls == 0

    with pytest.raises(RevisionConflictError):
        repo.submit_public_rule(
            match.match_id,
            expected_revision=5,
            idempotency_key="rule",
            player_text=MOVE_RULE_TEXT,
        )
    assert rule_models[0].calls == 0
    assert repo.get_replay(match.match_id).timeline == []


def test_revision_conflict_error_carries_frozen_code_and_retryable() -> None:
    error = RevisionConflictError("stale revision")

    assert error.error_code is ErrorCode.REVISION_CONFLICT
    assert error.retryable is True
    assert error.message == "stale revision"


def test_idempotency_key_required_error_carries_frozen_code_and_retryable() -> None:
    error = IdempotencyKeyRequiredError("missing key")

    assert error.error_code is ErrorCode.IDEMPOTENCY_KEY_REQUIRED
    assert error.retryable is True
    assert error.message == "missing key"


# 7/8/9. revision semantics -------------------------------------------------


def test_advance_increments_revision_by_one() -> None:
    repo, _, _, _ = _repository()
    match = repo.create_match(seed=1)

    result = repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")

    assert result.match.revision == 1
    assert result.match.completed_rounds == 1
    assert repo.get_match_snapshot(match.match_id).revision == 1


def test_accepted_rule_increments_revision_and_rejected_rule_does_not() -> None:
    repo, _, _, rule_models = _repository(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    match = repo.create_match(seed=1)
    repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")
    assert repo.get_match_snapshot(match.match_id).revision == 1

    rejected = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rejected",
        player_text="这句话无法表达",
    )
    assert rejected.accepted is False
    assert repo.get_match_snapshot(match.match_id).revision == 1
    assert repo.get_match_snapshot(match.match_id).rule_change_count == 0

    accepted = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="accepted",
        player_text=MOVE_RULE_TEXT,
    )
    assert accepted.accepted is True
    assert repo.get_match_snapshot(match.match_id).revision == 2
    assert repo.get_match_snapshot(match.match_id).rule_change_count == 1
    assert rule_models[0].calls == 3


# 10/11/12. idempotent replay ----------------------------------------------


def test_same_advance_key_replays_first_result_without_re_execution() -> None:
    repo, red_models, blue_models, _ = _repository()
    match = repo.create_match(seed=1)

    first = repo.advance_match(match.match_id, expected_revision=0, idempotency_key="key")
    calls_after_first = (red_models[0].calls, blue_models[0].calls)

    # The client retries with the original expected_revision even though the
    # server revision has already advanced: it must get the first result.
    second = repo.advance_match(match.match_id, expected_revision=0, idempotency_key="key")

    assert second == first
    assert (red_models[0].calls, blue_models[0].calls) == calls_after_first
    snapshot = repo.get_match_snapshot(match.match_id)
    assert snapshot.completed_rounds == 1
    assert snapshot.revision == 1
    assert _round_entries(repo, match.match_id) == 1


def test_same_accepted_rule_key_replays_first_result_without_re_execution() -> None:
    repo, _, _, rule_models = _repository(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    match = repo.create_match(seed=1)
    repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")

    first = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule-key",
        player_text=MOVE_RULE_TEXT,
    )
    calls_after_first = rule_models[0].calls
    intermissions_after_first = _intermission_entries(repo, match.match_id)

    second = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule-key",
        player_text=MOVE_RULE_TEXT,
    )

    assert second == first
    assert second.rule_id == first.rule_id
    assert repo.get_match_snapshot(match.match_id).rule_change_count == 1
    assert repo.get_match_snapshot(match.match_id).revision == 2
    assert rule_models[0].calls == calls_after_first
    assert _intermission_entries(repo, match.match_id) == intermissions_after_first


def test_same_rejected_rule_key_replays_without_extra_replay_or_model_call() -> None:
    repo, _, _, rule_models = _repository()
    match = repo.create_match(seed=1)
    repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")

    first = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule-key",
        player_text="这句话无法表达",
    )
    calls_after_first = rule_models[0].calls
    intermissions_after_first = _intermission_entries(repo, match.match_id)

    second = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule-key",
        player_text="这句话无法表达",
    )

    assert first.accepted is False
    assert second == first
    assert repo.get_match_snapshot(match.match_id).revision == 1
    assert rule_models[0].calls == calls_after_first
    assert _intermission_entries(repo, match.match_id) == intermissions_after_first


# 13/14. idempotency conflicts ---------------------------------------------


def test_same_key_with_different_player_text_is_invalid_request() -> None:
    repo, _, _, rule_models = _repository(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    match = repo.create_match(seed=1)
    repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")

    repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="shared",
        player_text=MOVE_RULE_TEXT,
    )
    calls_after_first = rule_models[0].calls
    intermissions_after_first = _intermission_entries(repo, match.match_id)

    with pytest.raises(IdempotencyConflictError) as conflict:
        repo.submit_public_rule(
            match.match_id,
            expected_revision=1,
            idempotency_key="shared",
            player_text="换一句完全不同的话",
        )
    assert conflict.value.error_code is ErrorCode.INVALID_REQUEST
    assert conflict.value.retryable is False

    assert rule_models[0].calls == calls_after_first
    assert _intermission_entries(repo, match.match_id) == intermissions_after_first
    assert repo.get_match_snapshot(match.match_id).rule_change_count == 1


def test_same_key_across_operations_is_invalid_request() -> None:
    repo, red_models, blue_models, rule_models = _repository(
        responses={MOVE_RULE_TEXT: MOVE_RULE_JSON}
    )
    match = repo.create_match(seed=1)

    repo.advance_match(match.match_id, expected_revision=0, idempotency_key="shared")
    calls_after_advance = (red_models[0].calls, blue_models[0].calls)

    with pytest.raises(IdempotencyConflictError) as rule_conflict:
        repo.submit_public_rule(
            match.match_id,
            expected_revision=1,
            idempotency_key="shared",
            player_text=MOVE_RULE_TEXT,
        )
    assert rule_conflict.value.error_code is ErrorCode.INVALID_REQUEST
    assert (red_models[0].calls, blue_models[0].calls) == calls_after_advance
    assert rule_models[0].calls == 0

    repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule-shared",
        player_text=MOVE_RULE_TEXT,
    )
    with pytest.raises(IdempotencyConflictError) as advance_conflict:
        repo.advance_match(match.match_id, expected_revision=2, idempotency_key="rule-shared")
    assert advance_conflict.value.error_code is ErrorCode.INVALID_REQUEST


# 15. cache isolation -------------------------------------------------------


def test_caller_mutation_does_not_pollute_the_idempotency_cache() -> None:
    repo, _, _, rule_models = _repository(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    match = repo.create_match(seed=1)

    first = repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")
    baseline = first.model_copy(deep=True)
    first.match.units.RED.hp = 999
    first.match.latest_strategy.RED.intent = StrategyIntentPublic.HOLD
    first.round.events.clear()

    replay = repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")
    assert replay == baseline
    assert replay.match.units.RED.hp == baseline.match.units.RED.hp
    assert replay.round.events == baseline.round.events

    rule_result = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule",
        player_text=MOVE_RULE_TEXT,
    )
    rule_baseline = rule_result.model_copy(deep=True)
    assert rule_result.match.active_rule is not None
    rule_result.match.active_rule.player_text = "被篡改"
    rule_result.match.active_rule.ast.effect.delta = 99
    calls_after_first = rule_models[0].calls

    replayed_rule = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule",
        player_text=MOVE_RULE_TEXT,
    )
    assert replayed_rule == rule_baseline
    assert replayed_rule.match.active_rule.player_text == MOVE_RULE_TEXT
    assert rule_models[0].calls == calls_after_first


# 16/17/18. concurrency -----------------------------------------------------


def test_concurrent_different_keys_same_revision_executes_exactly_one_round() -> None:
    entered = threading.Event()
    release = threading.Event()
    red = CountingStrategyModel("PRESSURE", entered=entered, release=release)
    blue = CountingStrategyModel("KITE")
    service = _build_service(rule_model=CountingRuleModel(), red_model=red, blue_model=blue)
    repo = InMemoryMatchRepository(service_factory=lambda: service)
    match = repo.create_match(seed=1_270_000)

    results: dict[str, object] = {}
    errors: dict[str, BaseException] = {}

    def worker(name: str, key: str) -> None:
        try:
            results[name] = repo.advance_match(
                match.match_id, expected_revision=0, idempotency_key=key
            )
        except BaseException as exc:  # noqa: BLE001 - recorded for assertions
            errors[name] = exc

    threads = [
        threading.Thread(target=worker, args=("a", "key-a"), daemon=True),
        threading.Thread(target=worker, args=("b", "key-b"), daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        assert entered.wait(timeout=_ENTRY_TIMEOUT)
    finally:
        release.set()
    for thread in threads:
        thread.join(timeout=_JOIN_TIMEOUT)

    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(next(iter(errors.values())), RevisionConflictError)
    snapshot = repo.get_match_snapshot(match.match_id)
    assert snapshot.revision == 1
    assert snapshot.completed_rounds == 1
    assert red.calls == 1
    assert blue.calls == 1
    assert _round_entries(repo, match.match_id) == 1


def test_concurrent_same_key_executes_once_and_returns_equivalent_results() -> None:
    entered = threading.Event()
    release = threading.Event()
    red = CountingStrategyModel("PRESSURE", entered=entered, release=release)
    blue = CountingStrategyModel("KITE")
    service = _build_service(rule_model=CountingRuleModel(), red_model=red, blue_model=blue)
    repo = InMemoryMatchRepository(service_factory=lambda: service)
    match = repo.create_match(seed=1_270_000)

    results: dict[str, object] = {}

    def worker(name: str) -> None:
        results[name] = repo.advance_match(
            match.match_id, expected_revision=0, idempotency_key="shared"
        )

    threads = [
        threading.Thread(target=worker, args=("a",), daemon=True),
        threading.Thread(target=worker, args=("b",), daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        assert entered.wait(timeout=_ENTRY_TIMEOUT)
    finally:
        release.set()
    for thread in threads:
        thread.join(timeout=_JOIN_TIMEOUT)

    assert set(results) == {"a", "b"}
    assert results["a"] == results["b"]
    snapshot = repo.get_match_snapshot(match.match_id)
    assert snapshot.revision == 1
    assert snapshot.completed_rounds == 1
    assert red.calls == 1
    assert blue.calls == 1
    assert _round_entries(repo, match.match_id) == 1


def test_different_matches_are_not_serialized_by_a_global_lock() -> None:
    entered_a = threading.Event()
    release_a = threading.Event()
    entered_b = threading.Event()
    release_b = threading.Event()
    service_a = _build_service(
        rule_model=CountingRuleModel(),
        red_model=CountingStrategyModel("PRESSURE", entered=entered_a, release=release_a),
        blue_model=CountingStrategyModel("KITE"),
    )
    service_b = _build_service(
        rule_model=CountingRuleModel(),
        red_model=CountingStrategyModel("PRESSURE", entered=entered_b, release=release_b),
        blue_model=CountingStrategyModel("KITE"),
    )
    services = iter([service_a, service_b])
    repo = InMemoryMatchRepository(service_factory=lambda: next(services))
    match_a = repo.create_match(seed=1)
    match_b = repo.create_match(seed=2)

    results: dict[str, object] = {}

    def worker(name: str, match_id: str, key: str) -> None:
        results[name] = repo.advance_match(
            match_id, expected_revision=0, idempotency_key=key
        )

    thread_a = threading.Thread(
        target=worker, args=("a", match_a.match_id, "ka"), daemon=True
    )
    thread_a.start()
    try:
        # Match A is inside its own provider call and holds only its own lock.
        assert entered_a.wait(timeout=_ENTRY_TIMEOUT)
        thread_b = threading.Thread(
            target=worker, args=("b", match_b.match_id, "kb"), daemon=True
        )
        thread_b.start()
        # If a single global lock serialized all matches, B could not enter
        # until A was released, so this would deadlock and time out.
        assert entered_b.wait(timeout=_ENTRY_TIMEOUT)
    finally:
        release_a.set()
        release_b.set()
    thread_a.join(timeout=_JOIN_TIMEOUT)
    if "thread_b" in locals():
        thread_b.join(timeout=_JOIN_TIMEOUT)

    assert results["a"].match.revision == 1
    assert results["b"].match.revision == 1
    assert repo.get_match_snapshot(match_a.match_id).completed_rounds == 1
    assert repo.get_match_snapshot(match_b.match_id).completed_rounds == 1


# 19/20/21. failure, reads, privacy ----------------------------------------


def test_recoverable_failure_is_not_cached_as_success() -> None:
    flaky_red = FlakyStrategyAgent(
        Team.RED,
        IsolatedStrategyAgent(Team.RED, CountingStrategyModel("PRESSURE")),
        fail_on_call=1,
    )
    service = _build_service(
        rule_model=CountingRuleModel(),
        blue_model=CountingStrategyModel("KITE"),
        red_agent=flaky_red,
    )
    repo = InMemoryMatchRepository(service_factory=lambda: service)
    match = repo.create_match(seed=1_270_000)

    with pytest.raises(RecoverableMatchFailure):
        repo.advance_match(match.match_id, expected_revision=0, idempotency_key="retry")
    assert repo.get_match_snapshot(match.match_id).revision == 0
    assert repo.get_replay(match.match_id).timeline == []

    # The same key must be able to really retry after the transient failure.
    result = repo.advance_match(match.match_id, expected_revision=0, idempotency_key="retry")
    assert result.match.revision == 1
    assert result.match.completed_rounds == 1
    assert _round_entries(repo, match.match_id) == 1


def test_reads_are_side_effect_free() -> None:
    repo, red_models, blue_models, rule_models = _repository(
        responses={MOVE_RULE_TEXT: MOVE_RULE_JSON}
    )
    match = repo.create_match(seed=1)
    repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")
    repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule",
        player_text=MOVE_RULE_TEXT,
    )

    calls_before = (red_models[0].calls, blue_models[0].calls, rule_models[0].calls)
    snapshot_before = repo.get_match_snapshot(match.match_id)
    replay_before = repo.get_replay(match.match_id)

    for _ in range(3):
        assert repo.get_match_snapshot(match.match_id) == snapshot_before
        assert repo.get_replay(match.match_id) == replay_before

    assert (red_models[0].calls, blue_models[0].calls, rule_models[0].calls) == calls_before
    assert repo.get_match_snapshot(match.match_id).revision == 2


def test_public_and_cached_responses_hide_private_and_provider_fields() -> None:
    repo, _, _, _ = _repository(responses={MOVE_RULE_TEXT: MOVE_RULE_JSON})
    match = repo.create_match(seed=1)
    advance_result = repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")
    rule_result = repo.submit_public_rule(
        match.match_id,
        expected_revision=1,
        idempotency_key="rule",
        player_text=MOVE_RULE_TEXT,
    )
    replay_result = repo.advance_match(
        match.match_id, expected_revision=2, idempotency_key="adv2"
    )
    # Replay the first advance to exercise the cached copy as well.
    cached_advance = repo.advance_match(match.match_id, expected_revision=0, idempotency_key="adv")

    payload = json.dumps(
        {
            "snapshot": repo.get_match_snapshot(match.match_id).model_dump(mode="json"),
            "replay": repo.get_replay(match.match_id).model_dump(mode="json"),
            "advance": advance_result.model_dump(mode="json"),
            "rule": rule_result.model_dump(mode="json"),
            "cached_advance": cached_advance.model_dump(mode="json"),
            "later": replay_result.model_dump(mode="json"),
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
