import json

import pytest

from rules_beyond.mimo_rule_provider import (
    DEFAULT_MIMO_RULE_MODEL,
    MIMO_TOKEN_PLAN_CN_BASE_URL,
    MimoProviderError,
    MimoRuleCandidateModel,
)
from rules_beyond.natural_language_rule_adapter import (
    NaturalLanguageRuleAdapter,
    TranslationStatus,
)


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, *, url, headers, payload, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "payload": dict(payload),
                "timeout_seconds": timeout_seconds,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def candidate_envelope():
    return {
        "decision": "CANDIDATE",
        "candidate": {
            "version": "v0.1",
            "target": "ALL_UNITS",
            "conditions": [],
            "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
            "duration": "UNTIL_REPLACED",
        },
    }


def response_with_content(content: str):
    return {"choices": [{"message": {"content": content}}]}


def test_mimo_token_plan_request_contract() -> None:
    transport = FakeTransport(response_with_content(json.dumps(candidate_envelope())))
    model = MimoRuleCandidateModel("tp-secret", transport=transport)

    output = model.generate_candidate(system_prompt="system", player_text="弓射程增加1格")

    assert json.loads(output) == candidate_envelope()
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == f"{MIMO_TOKEN_PLAN_CN_BASE_URL}/chat/completions"
    assert call["headers"]["api-key"] == "tp-secret"
    assert "tp-secret" not in json.dumps(call["payload"], ensure_ascii=False)
    assert call["payload"]["model"] == DEFAULT_MIMO_RULE_MODEL
    assert call["payload"]["response_format"] == {"type": "json_object"}
    assert call["payload"]["thinking"] == {"type": "disabled"}
    assert call["payload"]["stream"] is False
    assert call["payload"]["max_completion_tokens"] == 1024


def test_model_and_base_url_are_configurable() -> None:
    transport = FakeTransport(response_with_content("{}"))
    model = MimoRuleCandidateModel(
        "tp-secret",
        model_name="mimo-v2.5",
        base_url="https://example.invalid/v1/",
        transport=transport,
    )

    model.generate_candidate(system_prompt="s", player_text="u")

    call = transport.calls[0]
    assert call["url"] == "https://example.invalid/v1/chat/completions"
    assert call["payload"]["model"] == "mimo-v2.5"


def test_from_env_uses_token_plan_defaults(monkeypatch) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "tp-env")
    monkeypatch.delenv("MIMO_RULE_MODEL", raising=False)
    monkeypatch.delenv("MIMO_BASE_URL", raising=False)

    model = MimoRuleCandidateModel.from_env(transport=FakeTransport(response_with_content("{}")))

    assert model.model_name == "mimo-v2.5-pro"
    assert model.base_url == MIMO_TOKEN_PLAN_CN_BASE_URL


def test_from_env_allows_console_base_url_override(monkeypatch) -> None:
    monkeypatch.setenv("MIMO_API_KEY", "tp-env")
    monkeypatch.setenv("MIMO_RULE_MODEL", "mimo-v2.5")
    monkeypatch.setenv("MIMO_BASE_URL", "https://token-plan-custom.example/v1")

    model = MimoRuleCandidateModel.from_env(transport=FakeTransport(response_with_content("{}")))

    assert model.model_name == "mimo-v2.5"
    assert model.base_url == "https://token-plan-custom.example/v1"


def test_missing_env_key_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    with pytest.raises(ValueError, match="MIMO_API_KEY is not set"):
        MimoRuleCandidateModel.from_env()


def test_malformed_response_is_explicit_provider_error() -> None:
    model = MimoRuleCandidateModel(
        "tp-secret",
        transport=FakeTransport({"choices": []}),
    )
    with pytest.raises(MimoProviderError, match="missing choices"):
        model.generate_candidate(system_prompt="s", player_text="u")


def test_provider_failure_is_contained_by_natural_language_adapter() -> None:
    model = MimoRuleCandidateModel(
        "tp-secret",
        transport=FakeTransport(MimoProviderError("offline")),
    )
    result = NaturalLanguageRuleAdapter(model).translate("弓射程增加1格")

    assert result.status is TranslationStatus.MODEL_ERROR
    assert result.rule is None


def test_mimo_provider_to_adapter_mock_integration() -> None:
    transport = FakeTransport(response_with_content(json.dumps(candidate_envelope())))
    model = MimoRuleCandidateModel("tp-secret", transport=transport)

    result = NaturalLanguageRuleAdapter(model).translate("弓射程增加1格")

    assert result.status is TranslationStatus.ACCEPTED
    assert result.rule is not None
