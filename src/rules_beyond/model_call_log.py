"""Small, privacy-safe proof that configured model providers were called."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import Lock
from time import perf_counter
from typing import Any, Callable, TypeVar
from urllib.parse import urlparse


MAX_RETAINED_MODEL_CALLS = 256
BEIJING_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


class ModelCallPurpose(str, Enum):
    STRATEGY_RED = "STRATEGY_RED"
    STRATEGY_BLUE = "STRATEGY_BLUE"
    RULE_TRANSLATION = "RULE_TRANSLATION"
    RULE_FAITHFULNESS = "RULE_FAITHFULNESS"


class ModelCallOutcome(str, Enum):
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
    CALL_FAILED = "CALL_FAILED"


@dataclass(frozen=True, slots=True)
class ModelCallEntry:
    sequence: int
    time: str
    purpose: ModelCallPurpose
    model: str
    endpoint_origin: str | None
    outcome: ModelCallOutcome
    duration_ms: int


@dataclass(frozen=True, slots=True)
class ModelCallLogSnapshot:
    attempted_calls: int
    confirmed_responses: int
    failed_attempts: int
    entries: tuple[ModelCallEntry, ...]

    @property
    def truncated(self) -> bool:
        return self.attempted_calls > len(self.entries)


def safe_endpoint_origin(url: str | None) -> str | None:
    """Return only scheme + host + optional port; never path/query/credentials."""

    if not isinstance(url, str) or not url.strip():
        return None
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            return None
        host = parsed.hostname
        if ":" in host:
            host = f"[{host}]"
        port = parsed.port
        suffix = f":{port}" if port is not None else ""
        return f"{parsed.scheme.lower()}://{host.lower()}{suffix}"
    except (TypeError, ValueError):
        return None


def beijing_time_strings(utc_time: str) -> tuple[str, str]:
    """Convert one ISO-8601 UTC timestamp to machine and human Beijing time."""

    normalized = utc_time[:-1] + "+00:00" if utc_time.endswith("Z") else utc_time
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("Model call time must include a UTC offset")
    beijing = parsed.astimezone(BEIJING_TIMEZONE)
    return (
        beijing.isoformat(),
        beijing.strftime("%Y年%m月%d日 %H:%M:%S"),
    )


class ModelCallRecorder:
    """Thread-safe, bounded per-match call receipt recorder."""

    def __init__(self, *, max_entries: int = MAX_RETAINED_MODEL_CALLS) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._entries: deque[ModelCallEntry] = deque(maxlen=max_entries)
        self._attempted_calls = 0
        self._confirmed_responses = 0
        self._failed_attempts = 0
        self._lock = Lock()

    def record(
        self,
        *,
        time: str,
        purpose: ModelCallPurpose,
        model: str,
        endpoint_origin: str | None,
        outcome: ModelCallOutcome,
        duration_ms: int,
    ) -> None:
        """Best-effort only: logging must never affect model or game behavior."""

        try:
            with self._lock:
                self._attempted_calls += 1
                if outcome is ModelCallOutcome.RESPONSE_RECEIVED:
                    self._confirmed_responses += 1
                else:
                    self._failed_attempts += 1
                self._entries.append(
                    ModelCallEntry(
                        sequence=self._attempted_calls,
                        time=time,
                        purpose=purpose,
                        model=model,
                        endpoint_origin=endpoint_origin,
                        outcome=outcome,
                        duration_ms=max(0, int(duration_ms)),
                    )
                )
        except Exception:
            # A proof-of-call feature must never turn a successful model call into
            # a failed game round, nor hide the provider's original exception.
            return

    def snapshot(self) -> ModelCallLogSnapshot:
        with self._lock:
            return ModelCallLogSnapshot(
                attempted_calls=self._attempted_calls,
                confirmed_responses=self._confirmed_responses,
                failed_attempts=self._failed_attempts,
                entries=tuple(self._entries),
            )


_ResultT = TypeVar("_ResultT")


class LoggedModel:
    """Transparent wrapper for strategy and rule provider protocols."""

    def __init__(
        self,
        model: Any,
        recorder: ModelCallRecorder,
        *,
        purpose: ModelCallPurpose,
        model_name: str,
        endpoint_url: str | None,
    ) -> None:
        self._model = model
        self._recorder = recorder
        self._purpose = purpose
        self._model_name = model_name.strip() or "unknown"
        self._endpoint_origin = safe_endpoint_origin(endpoint_url)

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        return self._call(
            lambda: self._model.generate_strategy(
                system_prompt=system_prompt,
                observation=observation,
            )
        )

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        return self._call(
            lambda: self._model.generate_candidate(
                system_prompt=system_prompt,
                player_text=player_text,
            )
        )

    def _call(self, invoke: Callable[[], _ResultT]) -> _ResultT:
        started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        started = perf_counter()
        try:
            result = invoke()
        except Exception:
            self._safe_record(
                time=started_at,
                outcome=ModelCallOutcome.CALL_FAILED,
                duration_ms=round((perf_counter() - started) * 1000),
            )
            raise
        self._safe_record(
            time=started_at,
            outcome=ModelCallOutcome.RESPONSE_RECEIVED,
            duration_ms=round((perf_counter() - started) * 1000),
        )
        return result

    def _safe_record(
        self,
        *,
        time: str,
        outcome: ModelCallOutcome,
        duration_ms: int,
    ) -> None:
        try:
            self._recorder.record(
                time=time,
                purpose=self._purpose,
                model=self._model_name,
                endpoint_origin=self._endpoint_origin,
                outcome=outcome,
                duration_ms=duration_ms,
            )
        except Exception:
            return
