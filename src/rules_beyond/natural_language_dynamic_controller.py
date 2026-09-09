from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .dynamic_rule_controller import (
    DynamicContinueResult,
    DynamicMatchState,
    DynamicRoundResult,
    DynamicRuleController,
    IntermissionOutcome,
)
from .model import Action, Event, GameConfig, Team
from .rule_engine import RuleAwareGameEngine
from .verified_natural_language_rule_adapter import (
    VerifiedNaturalLanguageRuleAdapter,
    VerifiedNaturalLanguageTranslation,
)


@dataclass(frozen=True, slots=True)
class NaturalLanguageRuleAttempt:
    """One natural-language rule attempt inside a player-decision intermission.

    ``translation`` is None only when the submission was passed as no text. A
    rejected or failed translation is represented explicitly here while the
    wrapped DynamicRuleController receives no candidate, which keeps the previous
    legal rule and leaves the intermission open for a retry.
    """

    player_text: str
    translation: VerifiedNaturalLanguageTranslation | None
    outcome: IntermissionOutcome

    @property
    def translation_accepted(self) -> bool:
        return self.translation is not None and self.translation.accepted

    @property
    def carried_forward_after_translation_rejection(self) -> bool:
        return not self.translation_accepted and not self.outcome.replaced


@dataclass(frozen=True, slots=True)
class NaturalLanguageDynamicStartResult:
    state: DynamicMatchState
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class NaturalLanguageRuleSubmissionResult:
    state: DynamicMatchState
    attempt: NaturalLanguageRuleAttempt
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class NaturalLanguageContinueResult:
    state: DynamicMatchState
    events: tuple[Event, ...]


class VerifiedNaturalLanguageDynamicController:
    """Thin orchestration boundary from player text to DynamicRuleController.

    Security/authority rules:
    - the verified adapter may only produce an untrusted candidate mapping;
    - every accepted mapping is revalidated by DynamicRuleController;
    - rejected/model-error/verifier-error text becomes a rejected rule attempt
      that leaves the intermission open, never a silent continue;
    - no natural-language path mutates GameState directly;
    - the wrapped controller remains the owner of rule cadence and active_rule.
    """

    def __init__(
        self,
        adapter: VerifiedNaturalLanguageRuleAdapter,
        config: GameConfig | None = None,
        *,
        controller: DynamicRuleController | None = None,
    ) -> None:
        if controller is not None and config is not None and controller.config != config:
            raise ValueError("controller.config must match orchestration config")
        self.controller = controller or DynamicRuleController(config)
        self.adapter = adapter

        base_validator = adapter.base_adapter.validator
        if base_validator.config != self.controller.config:
            raise ValueError("adapter RuleValidator config must match controller config")

    @property
    def config(self) -> GameConfig:
        return self.controller.config

    @property
    def engine(self) -> RuleAwareGameEngine:
        return self.controller.engine

    def start_match(self) -> NaturalLanguageDynamicStartResult:
        started = self.controller.start_match()
        return NaturalLanguageDynamicStartResult(state=started.state, events=started.events)

    def resolve_round(
        self,
        state: DynamicMatchState,
        actions: Mapping[Team, Action],
        *,
        match_seed: int,
    ) -> DynamicRoundResult:
        return self.controller.resolve_round(
            state,
            actions,
            match_seed=match_seed,
        )

    def submit_rule(
        self,
        state: DynamicMatchState,
        player_text: str,
    ) -> NaturalLanguageRuleSubmissionResult:
        candidate, translation = self._translate(player_text)
        applied = self.controller.submit_rule(state, candidate)
        attempt = NaturalLanguageRuleAttempt(
            player_text=player_text,
            translation=translation,
            outcome=applied.outcome,
        )
        return NaturalLanguageRuleSubmissionResult(
            state=applied.state,
            attempt=attempt,
            events=applied.events,
        )

    def continue_match(self, state: DynamicMatchState) -> NaturalLanguageContinueResult:
        continued = self.controller.continue_match(state)
        return NaturalLanguageContinueResult(state=continued.state, events=continued.events)

    def _translate(
        self,
        player_text: str,
    ) -> tuple[Mapping[str, object] | None, VerifiedNaturalLanguageTranslation | None]:
        translation = self.adapter.translate(player_text)
        if not translation.accepted or translation.candidate is None:
            return None, translation
        return translation.candidate, translation
