from __future__ import annotations

from typing import Any

from .mimo_rule_provider import (
    DEFAULT_MIMO_API_KEY_ENV,
    DEFAULT_MIMO_BASE_URL_ENV,
    DEFAULT_MIMO_MODEL_ENV,
    DEFAULT_MIMO_RULE_MODEL,
    MIMO_TOKEN_PLAN_CN_BASE_URL,
    MimoJsonPostTransport,
    MimoProviderError,
    UrllibMimoJsonPostTransport,
)


class MimoStrategyModel:
    """MiMo adapter for closed high-level strategy JSON.

    This provider has no Engine/GameState write access. It only turns one system
    prompt plus one serialized observation into a JSON string for StrategyAgent.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_MIMO_RULE_MODEL,
        base_url: str = MIMO_TOKEN_PLAN_CN_BASE_URL,
        timeout_seconds: float = 20.0,
        max_completion_tokens: int = 256,
        transport: MimoJsonPostTransport | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a non-empty string")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-empty string")
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url must be a non-empty string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_completion_tokens <= 0:
            raise ValueError("max_completion_tokens must be positive")

        self._api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/chat/completions"
        self.timeout_seconds = float(timeout_seconds)
        self.max_completion_tokens = int(max_completion_tokens)
        self.transport = transport or UrllibMimoJsonPostTransport()

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env: str = DEFAULT_MIMO_API_KEY_ENV,
        model_env: str = DEFAULT_MIMO_MODEL_ENV,
        base_url_env: str = DEFAULT_MIMO_BASE_URL_ENV,
        **kwargs: Any,
    ) -> "MimoStrategyModel":
        import os

        api_key = os.getenv(api_key_env, "")
        if not api_key.strip():
            raise ValueError(f"{api_key_env} is not set")
        model_name = os.getenv(model_env, DEFAULT_MIMO_RULE_MODEL)
        base_url = os.getenv(base_url_env, MIMO_TOKEN_PLAN_CN_BASE_URL)
        return cls(api_key, model_name=model_name, base_url=base_url, **kwargs)

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": observation},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
            "max_completion_tokens": self.max_completion_tokens,
        }
        response = self.transport.post_json(
            url=self.endpoint,
            headers={
                "api-key": self._api_key,
                "Content-Type": "application/json",
            },
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )
        return self._extract_content(response)

    @staticmethod
    def _extract_content(response: dict[str, Any] | Any) -> str:
        if not isinstance(response, dict):
            raise MimoProviderError("MiMo strategy response root must be an object")
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise MimoProviderError("MiMo strategy response is missing choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise MimoProviderError("MiMo strategy choice must be an object")
        message = first.get("message")
        if not isinstance(message, dict):
            raise MimoProviderError("MiMo strategy choice is missing message")
        content = message.get("content")
        if not isinstance(content, str):
            raise MimoProviderError("MiMo strategy message content must be a string")
        return content
