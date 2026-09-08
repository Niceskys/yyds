from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, status

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


def _not_implemented() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Contract-only route. MatchApplicationService is implemented in the next task.",
    )


def build_contract_app() -> FastAPI:
    app = FastAPI(
        title="Rules Beyond MVP API",
        version="0.1.0",
        description=(
            "Frozen MVP V0.1 public HTTP contract. Route bodies are implemented "
            "by MatchApplicationService later."
        ),
    )

    @app.post(
        "/api/v1/matches",
        response_model=MatchSnapshot,
        status_code=status.HTTP_201_CREATED,
        responses={400: {"model": ErrorEnvelope}},
    )
    async def create_match(request: CreateMatchRequest) -> MatchSnapshot:
        del request
        _not_implemented()

    @app.get(
        "/api/v1/matches/{match_id}",
        response_model=MatchSnapshot,
        responses={404: {"model": ErrorEnvelope}},
    )
    async def get_match(match_id: str) -> MatchSnapshot:
        del match_id
        _not_implemented()

    @app.post(
        "/api/v1/matches/{match_id}/rules",
        response_model=RuleSubmissionResult,
        responses={409: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope}},
    )
    async def submit_rule(
        match_id: str,
        request: RuleSubmissionRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> RuleSubmissionResult:
        del match_id, request, idempotency_key
        _not_implemented()

    @app.post(
        "/api/v1/matches/{match_id}/advance",
        response_model=AdvanceResult,
        responses={409: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope}},
    )
    async def advance_match(
        match_id: str,
        request: AdvanceRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> AdvanceResult:
        del match_id, request, idempotency_key
        _not_implemented()

    @app.get(
        "/api/v1/matches/{match_id}/replay",
        response_model=ReplaySnapshot,
        responses={404: {"model": ErrorEnvelope}},
    )
    async def get_replay(match_id: str) -> ReplaySnapshot:
        del match_id
        _not_implemented()

    return app


contract_app = build_contract_app()


def export_openapi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(contract_app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the frozen Rules Beyond MVP OpenAPI contract."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("contracts/openapi/mvp-v0.1.json"),
    )
    args = parser.parse_args()
    export_openapi(args.output)


if __name__ == "__main__":
    main()
