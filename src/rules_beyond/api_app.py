"""A3 FastAPI application: the real V0.2 five-route HTTP vertical slice.

Layering is unchanged from the frozen contract::

    HTTP route
    -> InMemoryMatchRepository   (A2: match lookup / per-match lock / revision CAS / idempotency)
    -> MatchApplicationService   (A1: orchestration + public projection)
    -> DynamicRuleController / Agents / Planner / Engine

The routes only translate HTTP <-> application calls. ``expected_revision`` CAS,
Idempotency-Key replay, per-match locking, strategy calls, the planner, Engine
rounds, Replay assembly, battle escalation, effective stats and the rule pipeline
all stay inside A1/A2 and are never re-implemented here.

Every endpoint is a plain ``def`` function on purpose: FastAPI/Starlette runs
synchronous endpoints in a worker thread, so the synchronous (and potentially
blocking) repository/provider calls never run on the ASGI event loop.

The OpenAPI surface (title / version / description / paths / methods / request
bodies / response models / required ``Idempotency-Key`` header) is frozen and
guarded by ``tests/test_openapi_snapshot.py`` plus the frontend ``contract:check``
drift gate. Do not change it without going through ``CONTRACT CHANGE REQUIRED``.
"""

from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import FastAPI, Header, status

from .api_contract import (
    AdvanceRequest,
    AdvanceResult,
    CreateMatchRequest,
    ErrorEnvelope,
    MatchSnapshot,
    ReplaySnapshot,
    RuleSubmissionRequest,
    RuleSubmissionResult,
)
from .api_errors import RuntimeNotConfiguredError, install_error_handlers


class MatchRepositoryPort(Protocol):
    """The only A2 surface the HTTP layer is allowed to depend on."""

    def create_match(self, *, seed: int | None = None) -> MatchSnapshot: ...

    def get_match_snapshot(self, match_id: str) -> MatchSnapshot: ...

    def submit_public_rule(
        self,
        match_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
        player_text: str,
    ) -> RuleSubmissionResult: ...

    def advance_match(
        self,
        match_id: str,
        *,
        expected_revision: int,
        idempotency_key: str,
    ) -> AdvanceResult: ...

    def get_replay(self, match_id: str) -> ReplaySnapshot: ...


def build_app(repository: MatchRepositoryPort | None = None) -> FastAPI:
    """Build the V0.2 FastAPI app around one injected repository.

    ``repository=None`` builds the contract-only app used for OpenAPI export and
    contract tests. It never constructs a provider and never touches the network;
    calling a route without a wired repository returns a cleaned
    ``INTERNAL_ERROR`` envelope instead of leaking a traceback.
    """

    app = FastAPI(
        title="Rules Beyond MVP API",
        version="0.2.0",
        # Frozen OpenAPI text: the checked-in snapshot and the generated frontend
        # TypeScript must stay byte-identical to this app's schema.
        description=(
            "Frozen MVP V0.2 public HTTP contract for the every-round player-decision flow. "
            "Route bodies are implemented by MatchApplicationService later."
        ),
    )
    app.state.repository = repository
    install_error_handlers(app)

    def repository_port() -> MatchRepositoryPort:
        current = app.state.repository
        if current is None:
            raise RuntimeNotConfiguredError("runtime repository is not configured")
        return current

    @app.post(
        "/api/v1/matches",
        response_model=MatchSnapshot,
        status_code=status.HTTP_201_CREATED,
        responses={400: {"model": ErrorEnvelope}},
    )
    def create_match(request: CreateMatchRequest) -> MatchSnapshot:
        # Creating a match never runs Round 1 and never calls a provider (A1/A2).
        return repository_port().create_match(seed=request.seed)

    @app.get(
        "/api/v1/matches/{match_id}",
        response_model=MatchSnapshot,
        responses={404: {"model": ErrorEnvelope}},
    )
    def get_match(match_id: str) -> MatchSnapshot:
        # Read-only: no revision change, no model call.
        return repository_port().get_match_snapshot(match_id)

    @app.post(
        "/api/v1/matches/{match_id}/rules",
        response_model=RuleSubmissionResult,
        responses={409: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope}},
    )
    def submit_rule(
        match_id: str,
        request: RuleSubmissionRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> RuleSubmissionResult:
        # A rejected rule is a normal 200 RuleSubmissionResult, never an ErrorEnvelope.
        return repository_port().submit_public_rule(
            match_id,
            expected_revision=request.expected_revision,
            idempotency_key=idempotency_key,
            player_text=request.player_text,
        )

    @app.post(
        "/api/v1/matches/{match_id}/advance",
        response_model=AdvanceResult,
        responses={409: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope}},
    )
    def advance_match(
        match_id: str,
        request: AdvanceRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> AdvanceResult:
        # One repository call is the complete mutation: no extra continue/agent/
        # planner/engine step is allowed in this layer.
        return repository_port().advance_match(
            match_id,
            expected_revision=request.expected_revision,
            idempotency_key=idempotency_key,
        )

    @app.get(
        "/api/v1/matches/{match_id}/replay",
        response_model=ReplaySnapshot,
        responses={404: {"model": ErrorEnvelope}},
    )
    def get_replay(match_id: str) -> ReplaySnapshot:
        # Replay is projected from stored public state: zero model calls.
        return repository_port().get_replay(match_id)

    return app
