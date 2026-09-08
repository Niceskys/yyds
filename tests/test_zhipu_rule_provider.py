import json

import pytest

from rules_beyond.natural_language_rule_adapter import (
    NaturalLanguageRuleAdapter,
    TranslationStatus,
)
from rules_beyond.zhipu_rule_provider import (
    DEFAULT_ZHIPU_RULE_MODEL,
    ZHIPU_CHAT_COMPLETIONS_URL,
    ZhipuProviderError,
    ZhipuRuleCandidateModel,
)


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post_json(self, *, url, headers, payload, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


def candidate_envelope():
    return {
        "decision": "CANDIDATE",
        "candidate": {
            "version": "v0.1",
            "target": "ALL_UNITS",
            "conditions": [{"type": "SELF_HP_LTE", "value": 2}],
            "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
            "duration": "UNTIL_REPLACED",
        },
    }


def zhipu_response(content):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }


def test_provider_builds_official_json_mode_request_without_key_in_payload() -> None:
    transport = FakeTransport(zhipu_response(json.dumps(candidate_envelope())))
    provider = ZhipuRuleCandidateModel(
        "secret-key",
        transport=transport,
        timeout_seconds=12.5,
        max_tokens=777,
    )

    content = provider.generate_candidate(
        system_prompt="SYSTEM",
        player_text="生命值低时弓射程+1",
    )

    assert json.loads(content)["decision"] == "CANDIDATE"
    assert len(transport.calls) == 1

    call = transport.calls[0]
    assert call["url"] == ZHIPU_CHAT_COMPLETIONS_URL
    assert call["headers"]["Authorization"] == "Bearer secret-key"
    assert call["headers"]["Content-Type"] == "application/json"
    assert "secret-key" not in json.dumps(call["payload"], ensure_ascii=False)
    assert call["timeout_seconds"] == 12.5

    payload = call["payload"]
    assert payload["model"] == DEFAULT_ZHIPU_RULE_MODEL
    assert payload["messages"] == [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "生命值低时弓射程+1"},
    ]
    assert payload["thinking"] == {"type": "disabled"}
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["stream"] is False
    assert payload["max_tokens"] == 777


def test_provider_model_name_is_configurable() -> None:
    transport = FakeTransport(zhipu_response("{}"))
    provider = ZhipuRuleCandidateModel(
        "secret-key",
        model_name="glm-5.2",
        transport=transport,
    )

    provider.generate_candidate(system_prompt="S", player_text="U")

    assert transport.calls[0]["payload"]["model"] == "glm-5.2"


def test_from_env_uses_key_and_optional_model(monkeypatch) -> None:
    monkeypatch.setenv("ZHIPU_API_KEY", "env-secret")
    monkeypatch.setenv("ZHIPU_RULE_MODEL", "glm-5.2")
    transport = FakeTransport(zhipu_response("{}"))

    provider = ZhipuRuleCandidateModel.from_env(transport=transport)
    provider.generate_candidate(system_prompt="S", player_text="U")

    call = transport.calls[0]
    assert call["headers"]["Authorization"] == "Bearer env-secret"
    assert call["payload"]["model"] == "glm-5.2"


def test_from_env_rejects_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)

    with pytest.raises(ValueError, match="ZHIPU_API_KEY is not set"):
        ZhipuRuleCandidateModel.from_env()


def test_malformed_zhipu_response_is_rejected() -> None:
    provider = ZhipuRuleCandidateModel(
        "secret-key",
        transport=FakeTransport({"choices": []}),
    )

    with pytest.raises(ZhipuProviderError, match="missing choices"):
        provider.generate_candidate(system_prompt="S", player_text="U")


def test_transport_failure_is_contained_by_natural_language_adapter() -> None:
    provider = ZhipuRuleCandidateModel(
        "secret-key",
        transport=FakeTransport(error=ZhipuProviderError("network failed")),
    )
    adapter = NaturalLanguageRuleAdapter(provider)

    result = adapter.translate("生命值低时弓射程+1")

    assert result.status is TranslationStatus.MODEL_ERROR
    assert result.rule is None


def test_provider_and_adapter_accept_valid_envelope_end_to_end_without_network() -> None:
    content = json.dumps(candidate_envelope(), ensure_ascii=False)
    provider = ZhipuRuleCandidateModel(
        "secret-key",
        transport=FakeTransport(zhipu_response(content)),
    )
    adapter = NaturalLanguageRuleAdapter(provider)

    result = adapter.translate("生命值不高于2时，弓射程增加1格")

    assert result.status is TranslationStatus.ACCEPTED
    assert result.rule is not None
