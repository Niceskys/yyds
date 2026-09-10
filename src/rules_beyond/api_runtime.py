"""Runtime-only wiring: build the A2 repository (and therefore the MiMo providers) from env.

Importing this module never requires ``MIMO_API_KEY``, never constructs a provider
and never touches the network. Providers are created only when the ASGI server
actually starts (see :mod:`rules_beyond.api_server`), and one fresh provider object
is created per team per match, so no stateful agent session is ever shared between
matches (A2 ``MatchServiceFactory`` contract).

Environment variables follow the existing MiMo providers::

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


def build_runtime_repository_from_env() -> InMemoryMatchRepository:
    """Build the production in-memory repository from MiMo environment settings.

    Raises ``RuntimeError`` when ``MIMO_API_KEY`` is missing and ``ValueError`` when
    ``MIMO_BASE_URL`` is not an HTTPS URL (see ``ensure_https_url``).
    """

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
