from __future__ import annotations

import json
from urllib.error import URLError

import pytest

from rules_beyond import api_runtime
from rules_beyond.api_runtime import build_runtime_repository_from_env
from rules_beyond.match_repository import InMemoryMatchRepository
from rules_beyond.openai_compatible_provider import (
    OpenAICompatibleModel,
    OpenAICompatibleProviderError,
    UrllibJsonPostTransport,
    chat_completions_endpoint,
    ensure_safe_api_url,
)


class FakeTransport:
    def __init__(self, content: str = "{}") -> None:
        self.content = content
        self.calls: list[dict[str, object]] = []

    def post_json(self, *, url, headers, payload, timeout_seconds):  # noqa: ANN001
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "payload": dict(payload),
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"choices": [{"message": {"content": self.content}}]}


def test_generic_model_uses_bearer_auth_for_rule_and_strategy_calls() -> None:
    transport = FakeTransport('{"intent":"KITE"}')
    model = OpenAICompatibleModel(
        "secret-value",
        model_name="glm-5.1",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        json_mode=True,
        transport=transport,
    )

    assert json.loads(model.generate_candidate(system_prompt="rule", player_text="移动加一"))
    assert json.loads(model.generate_strategy(system_prompt="strategy", observation="{}"))

    rule_call, strategy_call = transport.calls
    assert rule_call["url"] == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    assert rule_call["headers"]["Authorization"] == "Bearer secret-value"
    assert "secret-value" not in json.dumps(rule_call["payload"])
    assert rule_call["payload"]["response_format"] == {"type": "json_object"}
    assert rule_call["payload"]["thinking"] == {"type": "disabled"}
    assert rule_call["payload"]["max_tokens"] == 1024
    assert strategy_call["payload"]["max_tokens"] == 1024


def test_non_glm_model_keeps_generic_request_options() -> None:
    transport = FakeTransport('{"intent":"HOLD"}')
    model = OpenAICompatibleModel(
        "secret",
        model_name="custom-model",
        base_url="https://models.example/v1",
        transport=transport,
    )

    model.generate_strategy(system_prompt="strategy", observation="{}")

    payload = transport.calls[0]["payload"]
    assert payload["max_tokens"] == 256
    assert "thinking" not in payload
    assert "response_format" not in payload


def test_full_endpoint_raw_key_and_fenced_json_are_supported() -> None:
    transport = FakeTransport('```json\n{"ok":true}\n```')
    model = OpenAICompatibleModel(
        "raw-key",
        model_name="custom-model",
        base_url="https://models.example/v1/chat/completions",
        auth_header="api-key",
        auth_scheme="none",
        token_field="max_completion_tokens",
        transport=transport,
    )

    assert model.generate_candidate(system_prompt="s", player_text="u") == '{"ok":true}'
    call = transport.calls[0]
    assert call["headers"]["api-key"] == "raw-key"
    assert call["payload"]["max_completion_tokens"] == 1024
    assert "response_format" not in call["payload"]


def test_remote_and_loopback_http_are_allowed_without_a_whitelist() -> None:
    assert ensure_safe_api_url("http://models.example/v1") == "http://models.example/v1"
    assert chat_completions_endpoint("http://127.0.0.1:11434/v1") == (
        "http://127.0.0.1:11434/v1/chat/completions"
    )
    assert chat_completions_endpoint(
        "http://192.0.2.10:32592/mgate/v1/chat/completions"
    ) == "http://192.0.2.10:32592/mgate/v1/chat/completions"
    assert chat_completions_endpoint(
        "https://models.example/deployment/chat/completions?api-version=2026-01-01"
    ).endswith("/chat/completions?api-version=2026-01-01")


@pytest.mark.parametrize(
    "url",
    [
        "ftp://192.0.2.10/model",
        "http://user:secret@192.0.2.10:32592",
        "not-a-url",
    ],
)
def test_model_url_rejects_unsupported_or_malformed_addresses(url: str) -> None:
    with pytest.raises(ValueError):
        chat_completions_endpoint(url)


def test_connection_check_validates_strategy_response_shape() -> None:
    working = OpenAICompatibleModel(
        "secret",
        model_name="custom-model",
        base_url="http://models.example/v1",
        transport=FakeTransport('{"intent":"HOLD"}'),
    )
    working.check_connection()

    incompatible = OpenAICompatibleModel(
        "secret",
        model_name="custom-model",
        base_url="http://models.example/v1",
        transport=FakeTransport('{"message":"ok"}'),
    )
    with pytest.raises(OpenAICompatibleProviderError, match="incompatible"):
        incompatible.check_connection()


def test_real_transport_accepts_remote_http_and_retries_one_network_failure() -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):  # noqa: ARG002
            return b'{"choices":[{"message":{"content":"{\\"intent\\":\\"HOLD\\"}"}}]}'

    class FlakyOpener:
        calls = 0

        def open(self, request, timeout):  # noqa: ARG002
            self.calls += 1
            if self.calls == 1:
                raise URLError("temporary")
            return Response()

    opener = FlakyOpener()
    model = OpenAICompatibleModel(
        "secret",
        model_name="custom-model",
        base_url="http://192.0.2.10:32592/mgate/v1/chat/completions",
        transport=UrllibJsonPostTransport(opener=opener, retry_delay_seconds=0),
    )

    model.check_connection()
    assert opener.calls == 2


def test_malformed_response_has_a_provider_error() -> None:
    class BadTransport:
        def post_json(self, **kwargs):  # noqa: ANN003, ANN201
            return {"choices": []}

    model = OpenAICompatibleModel(
        "secret", model_name="model", base_url="https://models.example/v1", transport=BadTransport()
    )
    with pytest.raises(OpenAICompatibleProviderError, match="missing choices"):
        model.generate_strategy(system_prompt="s", observation="{}")


class ProbeModel:
    probes = 0

    def __init__(self, *args, **kwargs):
        pass

    def check_connection(self) -> None:
        type(self).probes += 1


class FailingProbeModel(ProbeModel):
    def check_connection(self) -> None:
        raise OpenAICompatibleProviderError("Model API returned HTTP 401")


def test_runtime_prefers_complete_custom_configuration(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "custom-secret")
    monkeypatch.setenv("MODEL_API_MODEL", "glm-5.1")
    monkeypatch.setenv("MODEL_API_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    ProbeModel.probes = 0
    monkeypatch.setattr(api_runtime, "OpenAICompatibleModel", ProbeModel)

    repository = build_runtime_repository_from_env()

    assert isinstance(repository, InMemoryMatchRepository)
    assert ProbeModel.probes == 1


def test_runtime_accepts_remote_http_without_a_whitelist(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "custom-secret")
    monkeypatch.setenv("MODEL_API_MODEL", "custom-model")
    monkeypatch.setenv(
        "MODEL_API_BASE_URL",
        "http://192.0.2.10:32592/mgate/v1/chat/completions",
    )
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    ProbeModel.probes = 0
    monkeypatch.setattr(api_runtime, "OpenAICompatibleModel", ProbeModel)

    repository = build_runtime_repository_from_env()

    assert isinstance(repository, InMemoryMatchRepository)
    assert ProbeModel.probes == 1


def test_runtime_stops_when_connection_check_fails(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "wrong-secret")
    monkeypatch.setenv("MODEL_API_MODEL", "custom-model")
    monkeypatch.setenv("MODEL_API_BASE_URL", "http://192.0.2.10:32592/v1")
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.setattr(api_runtime, "OpenAICompatibleModel", FailingProbeModel)

    with pytest.raises(OpenAICompatibleProviderError, match="HTTP 401"):
        build_runtime_repository_from_env()


def test_runtime_reports_incomplete_custom_configuration(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "custom-secret")
    monkeypatch.delenv("MODEL_API_MODEL", raising=False)
    monkeypatch.delenv("MODEL_API_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="MODEL_API_MODEL, MODEL_API_BASE_URL is not set"):
        build_runtime_repository_from_env()
