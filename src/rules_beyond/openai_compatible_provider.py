"""Configurable OpenAI-compatible model adapter used by the playable runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, OpenerDirector, Request, build_opener


DEFAULT_MODEL_API_KEY_ENV = "MODEL_API_KEY"
DEFAULT_MODEL_API_MODEL_ENV = "MODEL_API_MODEL"
DEFAULT_MODEL_API_BASE_URL_ENV = "MODEL_API_BASE_URL"
DEFAULT_MODEL_API_AUTH_HEADER_ENV = "MODEL_API_AUTH_HEADER"
DEFAULT_MODEL_API_AUTH_SCHEME_ENV = "MODEL_API_AUTH_SCHEME"
DEFAULT_MODEL_API_JSON_MODE_ENV = "MODEL_API_JSON_MODE"
DEFAULT_MODEL_API_TOKEN_FIELD_ENV = "MODEL_API_TOKEN_FIELD"
DEFAULT_MODEL_API_TIMEOUT_ENV = "MODEL_API_TIMEOUT_SECONDS"
MAX_HTTP_RESPONSE_BYTES = 1_048_576

_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_TOKEN_FIELDS = {"max_tokens", "max_completion_tokens", "none"}


class OpenAICompatibleProviderError(RuntimeError):
    pass


class OpenAICompatibleTransportSecurityError(OpenAICompatibleProviderError):
    pass


def ensure_safe_api_url(url: str, *, label: str = "API URL") -> str:
    """Allow HTTPS endpoints and cleartext HTTP only on the local computer."""

    if not isinstance(url, str) or not url.strip():
        raise ValueError(f"{label} must be a non-empty string")
    parsed = urlparse(url.strip())
    if parsed.username or parsed.password:
        raise ValueError(f"{label} must not contain credentials")
    if not parsed.hostname or parsed.fragment:
        raise ValueError(f"{label} must be an absolute URL without a fragment")
    scheme = parsed.scheme.lower()
    if scheme == "https":
        return url.strip()
    if scheme == "http" and parsed.hostname.lower() in _LOOPBACK_HOSTS:
        return url.strip()
    raise ValueError(f"{label} must use HTTPS (HTTP is allowed only for localhost)")


def chat_completions_endpoint(base_or_endpoint: str) -> str:
    value = ensure_safe_api_url(base_or_endpoint, label="MODEL_API_BASE_URL")
    parsed = urlparse(value)
    path = parsed.path.rstrip("/")
    if not path.lower().endswith("/chat/completions"):
        path = f"{path}/chat/completions"
    return parsed._replace(path=path).geturl()


class CredentialSafeRedirectHandler(HTTPRedirectHandler):
    """Only follow redirects that stay on the exact original origin."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        origin = urlparse(req.full_url)
        target = urlparse(newurl)
        if (target.scheme.lower(), target.netloc.lower()) != (
            origin.scheme.lower(),
            origin.netloc.lower(),
        ):
            raise OpenAICompatibleTransportSecurityError(
                "Model API refused a redirect that leaves the configured origin"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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
    opener: OpenerDirector = field(
        default_factory=lambda: build_opener(CredentialSafeRedirectHandler()),
        compare=False,
        repr=False,
    )

    def post_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        ensure_safe_api_url(url, label="model API endpoint")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = Request(url, data=body, headers=dict(headers), method="POST")
        try:
            with self.opener.open(request, timeout=timeout_seconds) as response:
                raw = response.read(self.max_response_bytes + 1)
        except HTTPError as exc:
            raise OpenAICompatibleProviderError(f"Model API returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise OpenAICompatibleProviderError("Model API network request failed") from exc
        except TimeoutError as exc:
            raise OpenAICompatibleProviderError("Model API request timed out") from exc

        if len(raw) > self.max_response_bytes:
            raise OpenAICompatibleProviderError("Model API response exceeded size limit")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenAICompatibleProviderError("Model API returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise OpenAICompatibleProviderError("Model API response root must be an object")
        return decoded


class OpenAICompatibleModel:
    """One adapter implementing both rule and strategy model contracts."""

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str,
        base_url: str,
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        timeout_seconds: float = 30.0,
        json_mode: bool = False,
        token_field: str = "max_tokens",
        transport: JsonPostTransport | None = None,
    ) -> None:
        if (
            not isinstance(api_key, str)
            or not api_key.strip()
            or "\r" in api_key
            or "\n" in api_key
        ):
            raise ValueError("api_key must be a non-empty string")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-empty string")
        if not isinstance(auth_header, str) or not _HEADER_NAME_RE.fullmatch(auth_header):
            raise ValueError("auth_header must be a valid HTTP header name")
        if not isinstance(auth_scheme, str) or "\r" in auth_scheme or "\n" in auth_scheme:
            raise ValueError("auth_scheme must not contain line breaks")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if token_field not in _TOKEN_FIELDS:
            raise ValueError("token_field must be max_tokens, max_completion_tokens, or none")

        self._api_key = api_key.strip()
        self.model_name = model_name.strip()
        self.endpoint = chat_completions_endpoint(base_url)
        self.auth_header = auth_header
        normalized_scheme = auth_scheme.strip()
        self.auth_scheme = "" if normalized_scheme.lower() in {"none", "raw"} else normalized_scheme
        self.timeout_seconds = float(timeout_seconds)
        self.json_mode = bool(json_mode)
        self.token_field = token_field
        self.transport = transport or UrllibJsonPostTransport()

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        return self._complete(system_prompt, player_text, max_tokens=1024)

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        return self._complete(system_prompt, observation, max_tokens=256)

    def _complete(self, system_prompt: str, user_content: str, *, max_tokens: int) -> str:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
        }
        is_glm_51 = self.model_name.casefold() == "glm-5.1"
        if is_glm_51:
            # GLM-5.1 enables thinking by default. These game calls need only one
            # small, closed JSON object, so disable thinking and use its native
            # JSON mode. GLM recommends at least 1024 output tokens.
            payload["thinking"] = {"type": "disabled"}
            payload["response_format"] = {"type": "json_object"}
            payload["max_tokens"] = max(1024, max_tokens)
        elif self.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if not is_glm_51 and self.token_field != "none":
            payload[self.token_field] = max_tokens

        credential = (
            f"{self.auth_scheme} {self._api_key}" if self.auth_scheme else self._api_key
        )
        response = self.transport.post_json(
            url=self.endpoint,
            headers={self.auth_header: credential, "Content-Type": "application/json"},
            payload=payload,
            timeout_seconds=self.timeout_seconds,
        )
        return self._extract_content(response)

    @staticmethod
    def _extract_content(response: Mapping[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenAICompatibleProviderError("Model API response is missing choices")
        first = choices[0]
        if not isinstance(first, Mapping):
            raise OpenAICompatibleProviderError("Model API choice must be an object")
        message = first.get("message")
        if not isinstance(message, Mapping):
            raise OpenAICompatibleProviderError("Model API choice is missing message")
        content = message.get("content")
        if not isinstance(content, str):
            raise OpenAICompatibleProviderError("Model API message content must be a string")
        value = content.strip()
        if value.startswith("```") and value.endswith("```"):
            lines = value.splitlines()
            if len(lines) >= 3:
                value = "\n".join(lines[1:-1]).strip()
        return value
