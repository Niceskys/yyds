from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .dynamic_rule_controller import (
    DynamicMatchState,
    DynamicRuleController,
    RulePhaseOutcome,
)
from .model import Event, GameConfig
from .verified_natural_language_rule_adapter import (
    VerifiedNaturalLanguageRuleAdapter,
    VerifiedNaturalLanguageTranslation,
)


@dataclass(frozen=True, slots=True)
class NaturalLanguageDynamicPhase:
    """One player-rule phase after natural-language safety processing.

    `translation` is None only when the player made no text submission. A rejected
    or failed translation is represented explicitly here while the wrapped
    DynamicRuleController receives `None`, which preserves the previous legal
    rule according to the frozen UNTIL_REPLACED semantics.
    """

    player_text: str | None
    translation: VerifiedNaturalLanguageTranslation | None
    controller_phase: RulePhaseOutcome

    @property
    def text_submitted(self) -> bool:
        return self.player_text is not None

    @property
    def translation_accepted(self) -> bool:
        return self.translation is not None and self.translation.accepted

    @property
    def carried_forward_after_translation_rejection(self) -> bool:
        return (
            self.player_text is not None
            and not self.translation_accepted
            and not self.controller_phase.replaced
        )


@dataclass(frozen=True, slots=True)
class NaturalLanguageDynamicStartResult:
    state: DynamicMatchState
    phase: NaturalLanguageDynamicPhase
    events: tuple[Event, ...]


@dataclass(frozen=True, slots=True)
class NaturalLanguageDynamicRulePhaseResult:
    state: DynamicMatchState
    phase: NaturalLanguageDynamicPhase
    events: tuple[Event, ...]


class VerifiedNaturalLanguageDynamicController:
    """Thin orchestration boundary from player text to DynamicRuleController.

    Security/authority rules:
    - the verified adapter may only produce an untrusted candidate mapping;
    - every accepted mapping is revalidated by DynamicRuleController;
    - rejected/model-error/verifier-error text becomes no valid submission;
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

    def start_match(self, initial_text: str | None = None) -> NaturalLanguageDynamicStartResult:
        candidate, translation = self._translate(initial_text)
        started = self.controller.start_match(candidate)
        phase = NaturalLanguageDynamicPhase(
            player_text=initial_text,
            translation=translation,
            controller_phase=started.phase,
        )
        return NaturalLanguageDynamicStartResult(
            state=started.state,
            phase=phase,
            events=started.events,
        )

    def apply_due_rule_phase(
        self,
        state: DynamicMatchState,
        player_text: str | None = None,
    ) -> NaturalLanguageDynamicRulePhaseResult:
        candidate, translation = self._translate(player_text)
        applied = self.controller.apply_due_rule_phase(state, candidate)
        phase = NaturalLanguageDynamicPhase(
            player_text=player_text,
            translation=translation,
            controller_phase=applied.phase,
        )
        return NaturalLanguageDynamicRulePhaseResult(
            state=applied.state,
            phase=phase,
            events=applied.events,
        )

    def _translate(
        self,
        player_text: str | None,
    ) -> tuple[Mapping[str, object] | None, VerifiedNaturalLanguageTranslation | None]:
        if player_text is None:
            return None, None

        translation = self.adapter.translate(player_text)
        if not translation.accepted or translation.candidate is None:
            return None, translation
        return translation.candidate, translation
