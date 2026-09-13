"""A3 HTTP error mapping: the single place that turns typed application errors into ``ErrorEnvelope``.

The HTTP layer never re-derives business meaning. A typed application error already
carries its authoritative ``error_code`` and ``retryable`` (A1/A2); this module only
adds the transport-level concern (one HTTP status) plus a fixed, client-safe public
message. Provider raw bodies, request headers, API keys, system prompts, private
memory and stack traces can never reach the response because the message is chosen
from a closed table instead of from ``str(exc)``.
"""

from __future__ import annotations

from typing import Mapping

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api_contract import ErrorCode, ErrorDetail, ErrorEnvelope
from .match_application_service import (
    AdvanceNotAllowedError,
    MatchApplicationError,
    MatchNotFoundError,
    MatchTerminalError,
    RecoverableMatchFailure,
    RuleSubmissionNotAllowedError,
)
from .match_repository import (
    IdempotencyConflictError,
    IdempotencyKeyRequiredError,
    InvalidRequestError,
    RevisionConflictError,
)

IDEMPOTENCY_KEY_HEADER_ALIAS = "Idempotency-Key"


class RuntimeNotConfiguredError(MatchApplicationError):
    """This app instance carries no runtime repository (OpenAPI/contract-only build)."""

    error_code = ErrorCode.INTERNAL_ERROR
    retryable = False


#: HTTP status per typed application error. The lookup walks the exception MRO, so a
#: future subclass of a mapped error keeps a defined status, while an unmapped
#: subclass of ``MatchApplicationError`` falls back to a safe 500 instead of
#: silently inheriting another error's status.
_STATUS_BY_ERROR_TYPE: Mapping[type[MatchApplicationError], int] = {
    MatchNotFoundError: status.HTTP_404_NOT_FOUND,
    RevisionConflictError: status.HTTP_409_CONFLICT,
    MatchTerminalError: status.HTTP_409_CONFLICT,
    RuleSubmissionNotAllowedError: status.HTTP_409_CONFLICT,
    AdvanceNotAllowedError: status.HTTP_409_CONFLICT,
    IdempotencyKeyRequiredError: status.HTTP_400_BAD_REQUEST,
    IdempotencyConflictError: status.HTTP_400_BAD_REQUEST,
    InvalidRequestError: status.HTTP_400_BAD_REQUEST,
    RecoverableMatchFailure: status.HTTP_503_SERVICE_UNAVAILABLE,
    RuntimeNotConfiguredError: status.HTTP_503_SERVICE_UNAVAILABLE,
    MatchApplicationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}

#: Public, client-safe message per frozen ``ErrorCode``. ``REVISION_CONFLICT`` is
#: byte-identical to ``contracts/fixtures/mvp-v0.2/error_revision_conflict.json``.
_PUBLIC_MESSAGES: Mapping[ErrorCode, str] = {
    ErrorCode.REVISION_CONFLICT: "对局状态已经变化，请刷新后重试。",
    ErrorCode.MATCH_NOT_FOUND: "对局不存在。",
    ErrorCode.IDEMPOTENCY_KEY_REQUIRED: "缺少 Idempotency-Key 请求头。",
    ErrorCode.INVALID_REQUEST: "请求无效。",
    ErrorCode.MATCH_TERMINAL: "对局已经结束。",
    ErrorCode.RULE_SUBMISSION_NOT_ALLOWED: "当前阶段不能提交规则。",
    ErrorCode.ADVANCE_NOT_ALLOWED: "当前不能推进回合。",
    ErrorCode.MODEL_UNAVAILABLE: "模型服务暂时不可用，请稍后重试。",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误，请稍后重试。",
}

_FALLBACK_STATUS = status.HTTP_500_INTERNAL_SERVER_ERROR
_FALLBACK_MESSAGE = _PUBLIC_MESSAGES[ErrorCode.INTERNAL_ERROR]


def status_for(error: MatchApplicationError) -> int:
    """Return the HTTP status for one typed application error."""

    for error_type in type(error).__mro__:
        mapped = _STATUS_BY_ERROR_TYPE.get(error_type)
        if mapped is not None:
            return mapped
    return _FALLBACK_STATUS


def detail_for(error: MatchApplicationError) -> ErrorDetail:
    """Build the public error detail from the authoritative typed error."""

    return ErrorDetail(
        code=error.error_code,
        message=_PUBLIC_MESSAGES.get(error.error_code, _FALLBACK_MESSAGE),
        retryable=error.retryable,
    )


def internal_error_detail(*, retryable: bool) -> ErrorDetail:
    """One cleaned INTERNAL_ERROR detail (unexpected failures, unconfigured runtime)."""

    return ErrorDetail(
        code=ErrorCode.INTERNAL_ERROR,
        message=_FALLBACK_MESSAGE,
        retryable=retryable,
    )


def validation_detail(error: RequestValidationError) -> ErrorDetail:
    """Map ``RequestValidationError`` to a frozen ``ErrorEnvelope`` detail.

    FastAPI's default ``{"detail": [...]}`` body is never returned: a missing
    ``Idempotency-Key`` header becomes the frozen ``IDEMPOTENCY_KEY_REQUIRED`` code,
    any other request-shape failure becomes ``INVALID_REQUEST``.
    """

    return _validation_spec(error)[0]


def validation_status(error: RequestValidationError) -> int:
    return _validation_spec(error)[1]


def envelope_response(status_code: int, detail: ErrorDetail) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(error=detail).model_dump(mode="json"),
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register the three centralized handlers (typed, validation, unexpected)."""

    @app.exception_handler(MatchApplicationError)
    async def handle_match_application_error(
        request: Request, exc: MatchApplicationError
    ) -> JSONResponse:
        del request
        return envelope_response(status_for(exc), detail_for(exc))

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        detail, status_code = _validation_spec(exc)
        return envelope_response(status_code, detail)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        del request, exc
        return envelope_response(_FALLBACK_STATUS, internal_error_detail(retryable=False))


def _validation_spec(error: RequestValidationError) -> tuple[ErrorDetail, int]:
    if _is_missing_idempotency_key(error):
        return (
            ErrorDetail(
                code=ErrorCode.IDEMPOTENCY_KEY_REQUIRED,
                message=_PUBLIC_MESSAGES[ErrorCode.IDEMPOTENCY_KEY_REQUIRED],
                retryable=True,
            ),
            status.HTTP_400_BAD_REQUEST,
        )
    return (
        ErrorDetail(
            code=ErrorCode.INVALID_REQUEST,
            message=_PUBLIC_MESSAGES[ErrorCode.INVALID_REQUEST],
            retryable=False,
        ),
        status.HTTP_400_BAD_REQUEST,
    )


def _is_missing_idempotency_key(error: RequestValidationError) -> bool:
    for issue in error.errors():
        location = issue.get("loc") or ()
        if (
            len(location) >= 2
            and location[0] == "header"
            and str(location[-1]).lower() == IDEMPOTENCY_KEY_HEADER_ALIAS.lower()
        ):
            return True
    return False
