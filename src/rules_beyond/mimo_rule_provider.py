from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MIMO_TOKEN_PLAN_CN_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
DEFAULT_MIMO_RULE_MODEL = "mimo-v2.5-pro"
DEFAULT_MIMO_API_KEY_ENV = "MIMO_API_KEY"
DEFAULT_MIMO_MODEL_ENV = "MIMO_RULE_MODEL"
DEFAULT_MIMO_BASE_URL_ENV = "MIMO_BASE_URL"
MAX_HTTP_RESPONSE_BYTES = 1_048_576


class MimoProviderError(RuntimeError):
    pass


class MimoJsonPostTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class UrllibMimoJsonPostTransport:
    max_response_bytes: int = MAX_HTTP_RESPONSE_BYTES

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(url, data=body, headers=dict(headers), method="POST")

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            raise MimoProviderError(f"MiMo API returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise MimoProviderError("MiMo API network request failed") from exc
        except TimeoutError as exc:
            raise MimoProviderError("MiMo API request timed out") from exc

        if len(raw) > self.max_response_bytes:
            raise MimoProviderError("MiMo API response exceeded size limit")

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MimoProviderError("MiMo API returned an invalid JSON response") from exc

        if not isinstance(decoded, dict):
            raise MimoProviderError("MiMo API response root must be an object")
        return decoded


class MimoRuleCandidateModel:
    """MiMo OpenAI-compatible Chat Completions adapter for rule translation.

    The default endpoint targets the China Token Plan cluster. The provider only
    implements the narrow RuleCandidateModel contract and never receives Engine
    or GameState mutation capabilities.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_MIMO_RULE_MODEL,
        base_url: str = MIMO_TOKEN_PLAN_CN_BASE_URL,
        timeout_seconds: float = 20.0,
        max_completion_tokens: int = 1024,
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
    ) -> "MimoRuleCandidateModel":
        api_key = os.getenv(api_key_env, "")
        if not api_key.strip():
            raise ValueError(f"{api_key_env} is not set")
        model_name = os.getenv(model_env, DEFAULT_MIMO_RULE_MODEL)
        base_url = os.getenv(base_url_env, MIMO_TOKEN_PLAN_CN_BASE_URL)
        return cls(api_key, model_name=model_name, base_url=base_url, **kwargs)

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": player_text},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
            "max_completion_tokens": self.max_completion_tokens,
        }
        headers = {
            "api-key": self._api_key,
            "Content-Type": "application/json",
        }

        response = self.transport.post_json(
            url=self.endpoint,
            headers=headers,
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )
        return self._extract_content(response)

    @staticmethod
    def _extract_content(response: Mapping[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise MimoProviderError("MiMo API response is missing choices")

        first = choices[0]
        if not isinstance(first, Mapping):
            raise MimoProviderError("MiMo API choice must be an object")

        message = first.get("message")
        if not isinstance(message, Mapping):
            raise MimoProviderError("MiMo API choice is missing message")

        content = message.get("content")
        if not isinstance(content, str):
            raise MimoProviderError("MiMo API message content must be a string")
        return content
