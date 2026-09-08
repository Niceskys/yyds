from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ZHIPU_CHAT_COMPLETIONS_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_ZHIPU_RULE_MODEL = "glm-5.1"
DEFAULT_ZHIPU_API_KEY_ENV = "ZHIPU_API_KEY"
DEFAULT_ZHIPU_MODEL_ENV = "ZHIPU_RULE_MODEL"
MAX_HTTP_RESPONSE_BYTES = 1_048_576


class ZhipuProviderError(RuntimeError):
    pass


class JsonPostTransport(Protocol):
    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class UrllibJsonPostTransport:
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
        request = Request(
            url,
            data=body,
            headers=dict(headers),
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            raise ZhipuProviderError(f"Zhipu API returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise ZhipuProviderError("Zhipu API network request failed") from exc
        except TimeoutError as exc:
            raise ZhipuProviderError("Zhipu API request timed out") from exc

        if len(raw) > self.max_response_bytes:
            raise ZhipuProviderError("Zhipu API response exceeded size limit")

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ZhipuProviderError("Zhipu API returned an invalid JSON response") from exc

        if not isinstance(decoded, dict):
            raise ZhipuProviderError("Zhipu API response root must be an object")
        return decoded


class ZhipuRuleCandidateModel:
    """Official BigModel Chat Completions adapter for rule translation only.

    This class intentionally implements only the narrow RuleCandidateModel
    contract. It never receives GameState or Engine mutation capabilities.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_ZHIPU_RULE_MODEL,
        endpoint: str = ZHIPU_CHAT_COMPLETIONS_URL,
        timeout_seconds: float = 20.0,
        max_tokens: int = 1024,
        transport: JsonPostTransport | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a non-empty string")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-empty string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        self._api_key = api_key
        self.model_name = model_name
        self.endpoint = endpoint
        self.timeout_seconds = float(timeout_seconds)
        self.max_tokens = int(max_tokens)
        self.transport = transport or UrllibJsonPostTransport()

    @classmethod
    def from_env(
        cls,
        *,
        api_key_env: str = DEFAULT_ZHIPU_API_KEY_ENV,
        model_env: str = DEFAULT_ZHIPU_MODEL_ENV,
        **kwargs: Any,
    ) -> "ZhipuRuleCandidateModel":
        api_key = os.getenv(api_key_env, "")
        if not api_key.strip():
            raise ValueError(f"{api_key_env} is not set")
        model_name = os.getenv(model_env, DEFAULT_ZHIPU_RULE_MODEL)
        return cls(api_key, model_name=model_name, **kwargs)

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": player_text},
            ],
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "stream": False,
            "max_tokens": self.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
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
            raise ZhipuProviderError("Zhipu API response is missing choices")

        first = choices[0]
        if not isinstance(first, Mapping):
            raise ZhipuProviderError("Zhipu API choice must be an object")

        message = first.get("message")
        if not isinstance(message, Mapping):
            raise ZhipuProviderError("Zhipu API choice is missing message")

        content = message.get("content")
        if not isinstance(content, str):
            raise ZhipuProviderError("Zhipu API message content must be a string")

        return content
