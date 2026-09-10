"""Unit coverage for the single A3 typed-error -> HTTP ErrorEnvelope mapping point."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.exceptions import RequestValidationError

from rules_beyond.api_contract import SCHEMA_VERSION, ErrorCode, ErrorEnvelope
from rules_beyond.api_errors import (
    RuntimeNotConfiguredError,
    detail_for,
    internal_error_detail,
    status_for,
    validation_detail,
    validation_status,
)
from rules_beyond.match_application_service import (
    AdvanceNotAllowedError,
    MatchApplicationError,
    MatchNotFoundError,
    MatchTerminalError,
    RecoverableMatchFailure,
    RuleSubmissionNotAllowedError,
)
from rules_beyond.match_repository import (
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    InvalidRequestError,
    RevisionConflictError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REVISION_CONFLICT_FIXTURE = (
    REPOSITORY_ROOT / "contracts" / "fixtures" / "mvp-v0.2" / "error_revision_conflict.json"
)


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (MatchNotFoundError("x"), 404),
        (RevisionConflictError("x"), 409),
        (MatchTerminalError("x"), 409),
        (RuleSubmissionNotAllowedError("x"), 409),
        (AdvanceNotAllowedError("x"), 409),
        (IdempotencyKeyRequiredError("x"), 400),
        (IdempotencyConflictError("x"), 400),
        (InvalidRequestError("x"), 400),
        (RecoverableMatchFailure("x"), 503),
        (RuntimeNotConfiguredError("x"), 503),
    ],
)
def test_typed_application_errors_map_to_the_frozen_http_status(
    error: MatchApplicationError, expected_status: int
) -> None:
    assert status_for(error) == expected_status


def test_unmapped_application_error_falls_back_to_500_instead_of_another_errors_status() -> None:
    class FutureApplicationError(MatchApplicationError):
        pass

    assert status_for(FutureApplicationError("x")) == 500


def test_error_detail_uses_the_authoritative_typed_values() -> None:
    revision = detail_for(RevisionConflictError("internal developer text"))
    assert revision.code is ErrorCode.REVISION_CONFLICT
    assert revision.retryable is True

    required = detail_for(IdempotencyKeyRequiredError("internal developer text"))
    assert required.code is ErrorCode.IDEMPOTENCY_KEY_REQUIRED
    assert required.retryable is True

    conflict = detail_for(IdempotencyConflictError("internal developer text"))
    assert conflict.code is ErrorCode.INVALID_REQUEST
    assert conflict.retryable is False

    missing = detail_for(MatchNotFoundError("Unknown match_id: match_deadbeef"))
    assert missing.code is ErrorCode.MATCH_NOT_FOUND
    assert missing.retryable is False


def test_revision_conflict_message_matches_the_frozen_fixture() -> None:
    fixture = json.loads(REVISION_CONFLICT_FIXTURE.read_text(encoding="utf-8"))

    detail = detail_for(RevisionConflictError("expected_revision 5 does not match current revision 0"))

    assert detail.code.value == fixture["error"]["code"]
    assert detail.retryable is fixture["error"]["retryable"] is True
    assert detail.message == fixture["error"]["message"]


def test_error_detail_never_repeats_the_internal_exception_message() -> None:
    internal = "raw provider body api-key tp-secret system prompt private_memory traceback"

    for error in (
        RevisionConflictError(internal),
        IdempotencyKeyRequiredError(internal),
        InvalidRequestError(internal),
        MatchNotFoundError(internal),
        MatchTerminalError(internal),
        RecoverableMatchFailure(internal),
        RuntimeNotConfiguredError(internal),
    ):
        payload = json.dumps(detail_for(error).model_dump(mode="json"), ensure_ascii=False)
        for token in ("tp-secret", "api-key", "system prompt", "private_memory", "traceback"):
            assert token not in payload


def test_error_envelope_always_carries_the_frozen_schema_version() -> None:
    envelope = ErrorEnvelope(error=detail_for(RevisionConflictError("x")))
    assert envelope.model_dump(mode="json")["schema_version"] == SCHEMA_VERSION == "mvp-v0.2"


def test_internal_error_detail_is_cleaned() -> None:
    detail = internal_error_detail(retryable=False)
    assert detail.code is ErrorCode.INTERNAL_ERROR
    assert detail.retryable is False
    assert detail.message


def _validation_error(loc, type_: str = "missing") -> RequestValidationError:
    return RequestValidationError(
        [{"type": type_, "loc": loc, "msg": "Field required", "input": None}]
    )


def test_missing_idempotency_key_header_is_400_idempotency_key_required() -> None:
    error = _validation_error(("header", "Idempotency-Key"))

    detail = validation_detail(error)

    assert detail.code is ErrorCode.IDEMPOTENCY_KEY_REQUIRED
    assert detail.retryable is True
    assert validation_status(error) == 400


def test_idempotency_key_header_match_is_case_insensitive() -> None:
    error = _validation_error(("header", "idempotency-key"))

    assert validation_detail(error).code is ErrorCode.IDEMPOTENCY_KEY_REQUIRED


def test_any_other_request_validation_failure_is_400_invalid_request() -> None:
    for error in (
        _validation_error(("body", "expected_revision")),
        _validation_error(("body",), type_="json_invalid"),
        _validation_error(("path", "match_id")),
    ):
        detail = validation_detail(error)
        assert detail.code is ErrorCode.INVALID_REQUEST
        assert detail.retryable is False
        assert validation_status(error) == 400
