import json

import pytest

from rules_beyond.mimo_rule_provider import MIMO_TOKEN_PLAN_CN_BASE_URL, MimoProviderError
from rules_beyond.mimo_strategy_provider import MimoStrategyModel


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


def response_with_content(content: str):
    return {"choices": [{"message": {"content": content}}]}


def test_mimo_strategy_request_contract() -> None:
    transport = FakeTransport(response_with_content('{"intent":"KITE"}'))
    model = MimoStrategyModel("tp-secret", transport=transport)

    output = model.generate_strategy(system_prompt="system", observation='{"team":"RED"}')

    assert json.loads(output) == {"intent": "KITE"}
    call = transport.calls[0]
    assert call["url"] == f"{MIMO_TOKEN_PLAN_CN_BASE_URL}/chat/completions"
    assert call["headers"]["api-key"] == "tp-secret"
    assert "tp-secret" not in json.dumps(call["payload"])
    assert call["payload"]["model"] == "mimo-v2.5-pro"
    assert call["payload"]["response_format"] == {"type": "json_object"}
    assert call["payload"]["thinking"] == {"type": "disabled"}
    assert call["payload"]["stream"] is False
    assert call["payload"]["max_completion_tokens"] == 256


def test_malformed_strategy_response_is_provider_error() -> None:
    model = MimoStrategyModel("tp-secret", transport=FakeTransport({"choices": []}))

    with pytest.raises(MimoProviderError, match="missing choices"):
        model.generate_strategy(system_prompt="s", observation="{}")
