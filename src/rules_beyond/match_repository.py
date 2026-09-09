"""A2 application infrastructure: multi-match repository with concurrency safety.

This layer turns the A1 single-match :class:`MatchApplicationService` into a
multi-match application registry that A3 can call directly:

    create_match(seed=None) -> MatchSnapshot
    get_match_snapshot(match_id) -> MatchSnapshot
    submit_public_rule(match_id, *, expected_revision, idempotency_key, player_text)
    advance_match(match_id, *, expected_revision, idempotency_key) -> AdvanceResult
    get_replay(match_id) -> ReplaySnapshot

It owns **only** registry concerns:

- match_id allocation and uniqueness;
- one :class:`MatchApplicationService` (and therefore one RED/BLUE isolated
  strategy session, one controller state, one Replay and one revision) per match;
- one ``threading.Lock`` per match;
- ``expected_revision`` CAS against A1's authoritative ``MatchSnapshot.revision``;
- Idempotency-Key replay of the first public result.

It never re-implements gameplay. Strategy, planner, Engine round resolution,
rule cadence, Replay projection, battle escalation and effective stats all stay
inside the per-match A1 service.

Critical ordering inside the per-match critical section::

    acquire per-match lock
    -> Idempotency-Key lookup (operation + request fingerprint)
       -> exact replay: return a fresh copy of the first saved result
       -> same key, different operation/payload: INVALID_REQUEST
    -> expected_revision check
    -> A1 mutation
    -> save caller-safe public result
    -> release lock

The idempotency lookup deliberately happens **before** the revision check: a
client that retries the same successful request after its own revision advanced
must receive the first result, not ``REVISION_CONFLICT``.

Not implemented here (A3): FastAPI routes, HTTP status/Header mapping,
``ErrorEnvelope`` responses, CORS. Not implemented anywhere in the MVP: DB,
Redis, WebSocket, Celery, distributed locks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import secrets
import threading
from typing import Callable, TypeVar, cast

from .api_contract import (
    AdvanceResult,
    ContractModel,
    ErrorCode,
    MatchSnapshot,
    ReplaySnapshot,
    RuleSubmissionResult,
)
from .match_application_service import (
    MatchApplicationError,
    MatchApplicationService,
    MatchNotFoundError,
)
from .model import GameConfig, Team
from .natural_language_dynamic_controller import VerifiedNaturalLanguageDynamicController
from .natural_language_rule_adapter import NaturalLanguageRuleAdapter, RuleCandidateModel
from .rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from .rule_validator import RuleValidator
from .strategy_agent import IsolatedStrategyAgent, StrategyModel
from .verified_natural_language_rule_adapter import VerifiedNaturalLanguageRuleAdapter


class RevisionConflictError(MatchApplicationError):
    """``expected_revision`` did not match the authoritative match revision.

    The client can refresh its snapshot/revision and retry, so the frozen
    contract (``contracts/fixtures/mvp-v0.2/error_revision_conflict.json``)
    marks ``REVISION_CONFLICT`` as retryable. A3 must not re-derive this.
    """

    error_code = ErrorCode.REVISION_CONFLICT
    retryable = True


class IdempotencyKeyRequiredError(MatchApplicationError):
    """No usable Idempotency-Key was supplied (empty or whitespace-only).

    Distinct from :class:`IdempotencyConflictError`: here the key is missing,
    not illegally reused. A3 maps this to the frozen
    ``ErrorCode.IDEMPOTENCY_KEY_REQUIRED``; it must not re-derive the code.
    """

    error_code = ErrorCode.IDEMPOTENCY_KEY_REQUIRED
    retryable = True


class IdempotencyConflictError(MatchApplicationError):
    """One Idempotency-Key was reused for a different operation or payload."""

    error_code = ErrorCode.INVALID_REQUEST


class InvalidRequestError(MatchApplicationError):
    """Malformed application-level request that is not a revision conflict."""

    error_code = ErrorCode.INVALID_REQUEST


class _Operation(str, Enum):
    ADVANCE = "ADVANCE"
    RULE_SUBMISSION = "RULE_SUBMISSION"


_ResultT = TypeVar("_ResultT", bound=ContractModel)

_MAX_MATCH_ID_ATTEMPTS = 16


class MatchServiceFactory:
    """Build one fully isolated :class:`MatchApplicationService` per match.

    ``red_strategy_model_factory`` / ``blue_strategy_model_factory`` /
    ``rule_model_factory`` are invoked once per match, so every match gets its own
    RED and BLUE :class:`IsolatedStrategyAgent` session, its own private strategy
    memory and its own rule pipeline. Stateless provider transports may be
    captured by the factories and shared; stateful sessions never are.
    """

    def __init__(
        self,
        *,
        config: GameConfig | None = None,
        red_strategy_model_factory: Callable[[], StrategyModel],
        blue_strategy_model_factory: Callable[[], StrategyModel],
        rule_model_factory: Callable[[], RuleCandidateModel],
    ) -> None:
        self._config = config or GameConfig()
        self._red_strategy_model_factory = red_strategy_model_factory
        self._blue_strategy_model_factory = blue_strategy_model_factory
        self._rule_model_factory = rule_model_factory

    @property
    def config(self) -> GameConfig:
        return self._config

    def __call__(self) -> MatchApplicationService:
        config = self._config
        rule_model = self._rule_model_factory()
        validator = RuleValidator(config)
        base = NaturalLanguageRuleAdapter(rule_model, validator)
        verified = VerifiedNaturalLanguageRuleAdapter(
            base,
            NaturalLanguageRuleFaithfulnessVerifier(rule_model),
        )
        rules = VerifiedNaturalLanguageDynamicController(verified, config)
        return MatchApplicationService(
            red_agent=IsolatedStrategyAgent(Team.RED, self._red_strategy_model_factory()),
            blue_agent=IsolatedStrategyAgent(Team.BLUE, self._blue_strategy_model_factory()),
            rule_pipeline=rules,
        )


@dataclass(slots=True)
class _IdempotencyRecord:
    """First public result of one (match, operation, fingerprint, key) mutation."""

    match_id: str
    operation: _Operation
    fingerprint: tuple[object, ...]
    result: ContractModel


@dataclass(slots=True)
class _MatchRecord:
    """One match: its isolated A1 service, its lock and its idempotency history."""

    service: MatchApplicationService
    lock: threading.Lock = field(default_factory=threading.Lock)
    idempotency: dict[str, _IdempotencyRecord] = field(default_factory=dict)


class InMemoryMatchRepository:
    """In-memory multi-match registry for the V0.2 MVP.

    The registry lock is intentionally short-lived and only guards the
    ``match_id -> record`` map. Provider calls, Planner and Engine round
    resolution always run under the per-match lock, never under the registry
    lock, so different matches execute concurrently.
    """

    def __init__(
        self,
        *,
        service_factory: Callable[[], MatchApplicationService],
        match_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._service_factory = service_factory
        self._match_id_factory = match_id_factory or (
            lambda: f"match_{secrets.token_hex(8)}"
        )
        self._registry_lock = threading.Lock()
        self._records: dict[str, _MatchRecord] = {}

    # -- create / read -------------------------------------------------------

    def create_match(self, *, seed: int | None = None) -> MatchSnapshot:
        """Create one isolated match and return its initial public snapshot."""

        for _ in range(_MAX_MATCH_ID_ATTEMPTS):
            service = self._service_factory()
            match_id = self._match_id_factory()
            if not isinstance(match_id, str) or not match_id:
                raise InvalidRequestError("match_id_factory must return a non-empty string")
            snapshot = service.create_match(seed=seed, match_id=match_id)
            with self._registry_lock:
                if match_id in self._records:
                    # Never overwrite an existing match; retry with a new id.
                    continue
                self._records[match_id] = _MatchRecord(service=service)
                return snapshot
        raise InvalidRequestError("Could not allocate a unique match_id")

    def get_match_snapshot(self, match_id: str) -> MatchSnapshot:
        record = self._require_record(match_id)
        with record.lock:
            return record.service.get_match_snapshot()

    def get_replay(self, match_id: str) -> ReplaySnapshot:
        record = self._require_record(match_id)
        with record.lock:
            return record.service.get_replay()

    # -- mutations -----------------------------------------------------------

    def submit_public_rule(
        self,
        match_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        player_text: str,
    ) -> RuleSubmissionResult:
        return self._mutate(
            match_id,
            operation=_Operation.RULE_SUBMISSION,
            fingerprint=(expected_revision, player_text),
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            execute=lambda service: service.submit_public_rule(player_text),
        )

    def advance_match(
        self,
        match_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
    ) -> AdvanceResult:
        return self._mutate(
            match_id,
            operation=_Operation.ADVANCE,
            fingerprint=(expected_revision,),
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
            execute=lambda service: service.advance_match(),
        )

    # -- internals -----------------------------------------------------------

    def _mutate(
        self,
        match_id: str,
        *,
        operation: _Operation,
        fingerprint: tuple[object, ...],
        idempotency_key: str,
        expected_revision: int,
        execute: Callable[[MatchApplicationService], _ResultT],
    ) -> _ResultT:
        self._require_idempotency_key(idempotency_key)
        record = self._require_record(match_id)
        with record.lock:
            cached = self._replay_idempotent(
                record,
                match_id=match_id,
                operation=operation,
                fingerprint=fingerprint,
                idempotency_key=idempotency_key,
            )
            if cached is not None:
                return cast(_ResultT, cached)

            current = record.service.get_match_snapshot()
            if current.revision != expected_revision:
                raise RevisionConflictError(
                    f"expected_revision {expected_revision} does not match "
                    f"current revision {current.revision}"
                )

            result = execute(record.service)
            record.idempotency[idempotency_key] = _IdempotencyRecord(
                match_id=match_id,
                operation=operation,
                fingerprint=fingerprint,
                # A1 already returns a caller-owned copy; store an independent
                # copy so the cache can never be mutated through a caller DTO.
                result=result.model_copy(deep=True),
            )
            return result

    @staticmethod
    def _replay_idempotent(
        record: _MatchRecord,
        *,
        match_id: str,
        operation: _Operation,
        fingerprint: tuple[object, ...],
        idempotency_key: str,
    ) -> ContractModel | None:
        existing = record.idempotency.get(idempotency_key)
        if existing is None:
            return None
        if (
            existing.match_id != match_id
            or existing.operation is not operation
            or existing.fingerprint != fingerprint
        ):
            raise IdempotencyConflictError(
                "Idempotency-Key was already used for a different match, "
                "operation or request payload"
            )
        return existing.result.model_copy(deep=True)

    @staticmethod
    def _require_idempotency_key(idempotency_key: str) -> None:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise IdempotencyKeyRequiredError(
                "Idempotency-Key must be a non-empty, non-whitespace string"
            )

    def _require_record(self, match_id: str) -> _MatchRecord:
        with self._registry_lock:
            record = self._records.get(match_id)
        if record is None:
            raise MatchNotFoundError(f"Unknown match_id: {match_id}")
        return record
