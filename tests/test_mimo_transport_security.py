"""A3 provider transport security coverage.

No test performs a real network request: the redirect guard is exercised directly on
the handler, and the transport-level cleartext refusal fails before any socket is
opened.
"""

from __future__ import annotations

from urllib.request import Request

import pytest

from rules_beyond.api_runtime import build_runtime_repository_from_env
from rules_beyond.match_repository import InMemoryMatchRepository
from rules_beyond.mimo_rule_provider import (
    DEFAULT_MIMO_API_KEY_ENV,
    DEFAULT_MIMO_BASE_URL_ENV,
    CredentialSafeRedirectHandler,
    MimoRuleCandidateModel,
    MimoTransportSecurityError,
    UrllibMimoJsonPostTransport,
    ensure_https_url,
)
from rules_beyond.mimo_strategy_provider import MimoStrategyModel

SECRET = "tp-secret-must-never-leak"
ORIGIN = "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"


def _post(url: str) -> Request:
    return Request(url, data=b"{}", headers={"api-key": SECRET}, method="POST")


def test_providers_reject_non_https_base_url() -> None:
    for factory in (
        lambda url: MimoRuleCandidateModel(SECRET, base_url=url),
        lambda url: MimoStrategyModel(SECRET, base_url=url),
    ):
        with pytest.raises(ValueError, match="base_url must use https"):
            factory("http://token-plan-cn.xiaomimimo.com/v1")
        with pytest.raises(ValueError, match="base_url must use https"):
            factory("ftp://token-plan-cn.xiaomimimo.com/v1")


def test_ensure_https_url_rejects_blank_and_cleartext() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        ensure_https_url("   ", label="base_url")
    with pytest.raises(ValueError, match="must use https"):
        ensure_https_url("http://example.invalid/v1", label="base_url")
    assert ensure_https_url("https://example.invalid/v1", label="base_url") == (
        "https://example.invalid/v1"
    )


def test_transport_refuses_cleartext_endpoint_even_if_the_provider_check_is_bypassed() -> None:
    transport = UrllibMimoJsonPostTransport()

    with pytest.raises(ValueError, match="MiMo endpoint URL must use https"):
        transport.post_json(
            url="http://127.0.0.1:9/v1/chat/completions",
            headers={"api-key": SECRET},
            payload={},
            timeout_seconds=1.0,
        )


def test_transport_installs_the_credential_safe_redirect_handler() -> None:
    transport = UrllibMimoJsonPostTransport()

    assert any(
        isinstance(handler, CredentialSafeRedirectHandler) for handler in transport.opener.handlers
    )


def test_cross_host_redirect_is_refused() -> None:
    with pytest.raises(MimoTransportSecurityError, match="refused a redirect"):
        CredentialSafeRedirectHandler().redirect_request(
            _post(ORIGIN),
            None,
            302,
            "Found",
            {},
            "https://evil.example/v1/chat/completions",
        )


def test_scheme_downgrade_redirect_on_the_same_host_is_refused() -> None:
    with pytest.raises(MimoTransportSecurityError, match="refused a redirect"):
        CredentialSafeRedirectHandler().redirect_request(
            _post(ORIGIN),
            None,
            302,
            "Found",
            {},
            "http://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        )


def test_same_origin_https_redirect_is_still_followed() -> None:
    redirected = CredentialSafeRedirectHandler().redirect_request(
        _post(ORIGIN),
        None,
        302,
        "Found",
        {},
        ORIGIN + "/",
    )

    assert isinstance(redirected, Request)
    assert redirected.full_url == ORIGIN + "/"
    assert redirected.get_header("Api-key") == SECRET


def test_provider_errors_never_contain_the_api_key_or_request_headers() -> None:
    class FailingTransport:
        def post_json(self, *, url, headers, payload, timeout_seconds):  # noqa: ANN001
            raise MimoTransportSecurityError(
                "MiMo API transport refused a redirect that leaves the original origin"
            )

    model = MimoRuleCandidateModel(SECRET, transport=FailingTransport())

    with pytest.raises(MimoTransportSecurityError) as error:
        model.generate_candidate(system_prompt="system", player_text="text")
    message = str(error.value)
    assert SECRET not in message
    assert "api-key" not in message.lower()
    assert "system" not in message


def test_runtime_repository_rejects_cleartext_base_url_and_a_missing_key(monkeypatch) -> None:
    monkeypatch.setenv(DEFAULT_MIMO_API_KEY_ENV, SECRET)
    monkeypatch.setenv(DEFAULT_MIMO_BASE_URL_ENV, "http://token-plan-cn.xiaomimimo.com/v1")
    with pytest.raises(ValueError, match="base_url must use https"):
        build_runtime_repository_from_env()

    monkeypatch.delenv(DEFAULT_MIMO_API_KEY_ENV)
    monkeypatch.delenv(DEFAULT_MIMO_BASE_URL_ENV, raising=False)
    with pytest.raises(RuntimeError, match=f"{DEFAULT_MIMO_API_KEY_ENV} is not set"):
        build_runtime_repository_from_env()


def test_runtime_repository_builds_providers_without_touching_the_network(monkeypatch) -> None:
    monkeypatch.setenv(DEFAULT_MIMO_API_KEY_ENV, SECRET)
    monkeypatch.delenv(DEFAULT_MIMO_BASE_URL_ENV, raising=False)

    repository = build_runtime_repository_from_env()

    assert isinstance(repository, InMemoryMatchRepository)
