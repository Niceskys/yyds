"""Runtime-only wiring for configurable model providers.

Importing this module never requires ``MIMO_API_KEY``, never constructs a provider
and never touches the network. Providers are created only when the ASGI server
actually starts (see :mod:`rules_beyond.api_server`), and one fresh provider object
is created per team per match, so no stateful agent session is ever shared between
matches (A2 ``MatchServiceFactory`` contract).

The playable runtime accepts a generic OpenAI-compatible endpoint::

    MODEL_API_KEY       required for custom mode
    MODEL_API_MODEL     required for custom mode
    MODEL_API_BASE_URL  required for custom mode; base URL or /chat/completions URL

If none of those variables is present, the legacy MiMo variables remain supported::

    MIMO_API_KEY      required, never logged, never returned to a client
    MIMO_RULE_MODEL   optional, defaults to the provider default
    MIMO_BASE_URL     optional, must be HTTPS
"""

from __future__ import annotations

import os

from .match_repository import InMemoryMatchRepository, MatchServiceFactory
from .mimo_rule_provider import (
    DEFAULT_MIMO_API_KEY_ENV,
    DEFAULT_MIMO_BASE_URL_ENV,
    DEFAULT_MIMO_MODEL_ENV,
    DEFAULT_MIMO_RULE_MODEL,
    MIMO_TOKEN_PLAN_CN_BASE_URL,
    MimoRuleCandidateModel,
    ensure_https_url,
)
from .mimo_strategy_provider import MimoStrategyModel
from .openai_compatible_provider import (
    DEFAULT_MODEL_API_AUTH_HEADER_ENV,
    DEFAULT_MODEL_API_AUTH_SCHEME_ENV,
    DEFAULT_MODEL_API_BASE_URL_ENV,
    DEFAULT_MODEL_API_JSON_MODE_ENV,
    DEFAULT_MODEL_API_KEY_ENV,
    DEFAULT_MODEL_API_MODEL_ENV,
    DEFAULT_MODEL_API_TOKEN_FIELD_ENV,
    DEFAULT_MODEL_API_TIMEOUT_ENV,
    OpenAICompatibleModel,
)


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def build_runtime_repository_from_env() -> InMemoryMatchRepository:
    """Build the production repository from custom or legacy MiMo settings.

    Raises ``RuntimeError`` when ``MIMO_API_KEY`` is missing and ``ValueError`` when
    ``MIMO_BASE_URL`` is not an HTTPS URL (see ``ensure_https_url``).
    """

    custom_names = (
        DEFAULT_MODEL_API_KEY_ENV,
        DEFAULT_MODEL_API_MODEL_ENV,
        DEFAULT_MODEL_API_BASE_URL_ENV,
    )
    custom_mode = any(os.getenv(name, "").strip() for name in custom_names)
    if custom_mode:
        values = {name: os.getenv(name, "").strip() for name in custom_names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"{', '.join(missing)} is not set")

        auth_header = os.getenv(DEFAULT_MODEL_API_AUTH_HEADER_ENV, "Authorization").strip()
        auth_scheme = os.getenv(DEFAULT_MODEL_API_AUTH_SCHEME_ENV, "Bearer")
        json_mode = _read_bool_env(DEFAULT_MODEL_API_JSON_MODE_ENV)
        token_field = os.getenv(DEFAULT_MODEL_API_TOKEN_FIELD_ENV, "max_tokens").strip()
        timeout_seconds = float(os.getenv(DEFAULT_MODEL_API_TIMEOUT_ENV, "30"))

        def custom_model_factory() -> OpenAICompatibleModel:
            return OpenAICompatibleModel(
                values[DEFAULT_MODEL_API_KEY_ENV],
                model_name=values[DEFAULT_MODEL_API_MODEL_ENV],
                base_url=values[DEFAULT_MODEL_API_BASE_URL_ENV],
                auth_header=auth_header,
                auth_scheme=auth_scheme,
                json_mode=json_mode,
                token_field=token_field,
                timeout_seconds=timeout_seconds,
            )

        service_factory = MatchServiceFactory(
            red_strategy_model_factory=custom_model_factory,
            blue_strategy_model_factory=custom_model_factory,
            rule_model_factory=custom_model_factory,
        )
        return InMemoryMatchRepository(service_factory=service_factory)

    api_key = os.getenv(DEFAULT_MIMO_API_KEY_ENV, "")
    if not api_key.strip():
        raise RuntimeError(f"{DEFAULT_MIMO_API_KEY_ENV} is not set")
    model_name = os.getenv(DEFAULT_MIMO_MODEL_ENV, DEFAULT_MIMO_RULE_MODEL)
    base_url = os.getenv(DEFAULT_MIMO_BASE_URL_ENV, MIMO_TOKEN_PLAN_CN_BASE_URL)
    # Fail fast at startup instead of on the first match creation.
    ensure_https_url(base_url, label="base_url")

    def strategy_model_factory() -> MimoStrategyModel:
        # Stateless transport per team session; no shared private strategy memory.
        return MimoStrategyModel(api_key, model_name=model_name, base_url=base_url)

    def rule_model_factory() -> MimoRuleCandidateModel:
        return MimoRuleCandidateModel(api_key, model_name=model_name, base_url=base_url)

    service_factory = MatchServiceFactory(
        red_strategy_model_factory=strategy_model_factory,
        blue_strategy_model_factory=strategy_model_factory,
        rule_model_factory=rule_model_factory,
    )
    return InMemoryMatchRepository(service_factory=service_factory)
