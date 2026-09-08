from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
import os
from typing import Mapping

from .dynamic_rule_controller import DynamicMatchState
from .mimo_rule_provider import DEFAULT_MIMO_RULE_MODEL, MimoRuleCandidateModel
from .model import Action, GameConfig, MatchResult, Team
from .natural_language_dynamic_controller import (
    NaturalLanguageDynamicPhase,
    VerifiedNaturalLanguageDynamicController,
)
from .natural_language_rule_adapter import NaturalLanguageRuleAdapter
from .rule_bots import RuleAwareAttackFirstBot
from .rule_dsl import RuleAST
from .rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from .rule_validator import RuleValidator
from .verified_natural_language_rule_adapter import VerifiedNaturalLanguageRuleAdapter


LIVE_MATCH_CONFIG = GameConfig(initial_hp=5, knife_damage=2)
LIVE_MATCH_SEEDS = (1_260_000, 1_260_001, 1_260_002)

# phase 0 is pre-game; later phases occur after rounds 3, 6, 9, 12...
# Phase 2 is intentionally unsupported OR logic. The verified pipeline must
# reject it and DynamicRuleController must carry the phase-1 rule forward.
LIVE_NL_SCHEDULE: Mapping[int, str] = {
    0: "双方弓的最大射程增加1格。",
    1: "双方移动距离增加1格。",
    2: "生命值不超过2或者上一回合没移动时，弓射程增加1格。",
    3: "双方相距至少3格时，弓箭命中率按原来的一半计算。",
    4: "连续2回合使用同一种武器后，弓冷却1回合。",
}


@dataclass(frozen=True, slots=True)
class LivePhaseTrace:
    phase_index: int
    after_round: int | None
    player_text: str | None
    translation_status: str | None
    base_status: str | None
    faithfulness_decision: str | None
    intent_guard_allowed: bool | None
    controller_submitted: bool
    controller_accepted: bool
    controller_replaced: bool
    carried_forward_after_translation_rejection: bool
    active_rule: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class LiveRoundTrace:
    round_no: int
    red_action: str
    blue_action: str
    red_hp_after: int
    blue_hp_after: int
    active_rule: dict[str, object] | None
    event_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LiveMatchTrace:
    seed: int
    result: str
    rounds: int
    baseline_round1_actions: tuple[str, str]
    live_round1_actions: tuple[str, str]
    round1_behavior_changed: bool
    rule_modifier_events: int
    phases: tuple[LivePhaseTrace, ...]
    rounds_trace: tuple[LiveRoundTrace, ...]


@dataclass(frozen=True, slots=True)
class LiveDynamicMatchSummary:
    provider: str
    model_name: str
    config: dict[str, object]
    schedule: dict[int, str]
    gate_passed: bool
    matches: tuple[LiveMatchTrace, ...]


def _action_signature(action: Action) -> str:
    path = ",".join(step.value for step in action.move_path) or "STAY"
    attack = action.attack.value if action.attack is not None else "NONE"
    return f"{path}|{attack}"


def _rule_to_mapping(rule: RuleAST | None) -> dict[str, object] | None:
    if rule is None:
        return None

    conditions: list[dict[str, object]] = []
    for condition in rule.conditions:
        item: dict[str, object] = {"type": condition.type.value}
        if condition.value is not None:
            item["value"] = condition.value
        if condition.weapon is not None:
            item["weapon"] = condition.weapon.value
        conditions.append(item)

    effect: dict[str, object] = {"type": rule.effect.type.value}
    if rule.effect.delta is not None:
        effect["delta"] = rule.effect.delta
    if rule.effect.multiplier is not None:
        effect["multiplier"] = rule.effect.multiplier
    if rule.effect.weapon is not None:
        effect["weapon"] = rule.effect.weapon.value
    if rule.effect.rounds is not None:
        effect["rounds"] = rule.effect.rounds

    return {
        "version": rule.version,
        "target": rule.target.value,
        "conditions": conditions,
        "effect": effect,
        "duration": rule.duration.value,
    }


def _phase_trace(phase: NaturalLanguageDynamicPhase) -> LivePhaseTrace:
    translation = phase.translation
    base_status = None
    faithfulness_decision = None
    intent_guard_allowed = None
    translation_status = None
    if translation is not None:
        translation_status = translation.status.value
        base_status = translation.base.status.value
        if translation.faithfulness is not None:
            faithfulness_decision = translation.faithfulness.decision.value
        if translation.intent_guard is not None:
            intent_guard_allowed = translation.intent_guard.allowed

    controller_phase = phase.controller_phase
    return LivePhaseTrace(
        phase_index=controller_phase.phase_index,
        after_round=controller_phase.after_round,
        player_text=phase.player_text,
        translation_status=translation_status,
        base_status=base_status,
        faithfulness_decision=faithfulness_decision,
        intent_guard_allowed=intent_guard_allowed,
        controller_submitted=controller_phase.submitted,
        controller_accepted=controller_phase.accepted,
        controller_replaced=controller_phase.replaced,
        carried_forward_after_translation_rejection=(
            phase.carried_forward_after_translation_rejection
        ),
        active_rule=_rule_to_mapping(controller_phase.active_rule),
    )


def _baseline_round1_actions(config: GameConfig, seed: int) -> tuple[str, str]:
    bot = RuleAwareAttackFirstBot()
    controller = VerifiedNaturalLanguageDynamicController.__new__(
        VerifiedNaturalLanguageDynamicController
    )
    # Baseline needs no natural-language layer: use the deterministic dynamic
    # controller directly so the comparison isolates the phase-0 public rule.
    from .dynamic_rule_controller import DynamicRuleController

    dynamic = DynamicRuleController(config)
    started = dynamic.start_match(None)
    state = started.state
    red = bot.choose_action(
        state.game_state,
        Team.RED,
        dynamic.engine,
        rule=None,
        histories=state.histories,
        match_seed=seed,
    )
    blue = bot.choose_action(
        state.game_state,
        Team.BLUE,
        dynamic.engine,
        rule=None,
        histories=state.histories,
        match_seed=seed,
    )
    del controller
    return _action_signature(red), _action_signature(blue)


def play_live_match(
    controller: VerifiedNaturalLanguageDynamicController,
    *,
    seed: int,
    schedule: Mapping[int, str] = LIVE_NL_SCHEDULE,
) -> LiveMatchTrace:
    bot = RuleAwareAttackFirstBot()
    baseline_round1 = _baseline_round1_actions(controller.config, seed)

    started = controller.start_match(schedule.get(0))
    state = started.state
    phase_traces: list[LivePhaseTrace] = [_phase_trace(started.phase)]
    round_traces: list[LiveRoundTrace] = []
    event_counts: Counter[str] = Counter(event.kind for event in started.events)
    live_round1: tuple[str, str] | None = None

    while not state.game_state.is_terminal:
        played_round = state.game_state.round_no
        red_action = bot.choose_action(
            state.game_state,
            Team.RED,
            controller.controller.engine,
            rule=state.active_rule,
            histories=state.histories,
            match_seed=seed,
        )
        blue_action = bot.choose_action(
            state.game_state,
            Team.BLUE,
            controller.controller.engine,
            rule=state.active_rule,
            histories=state.histories,
            match_seed=seed,
        )
        action_pair = (_action_signature(red_action), _action_signature(blue_action))
        if played_round == 1:
            live_round1 = action_pair

        active_before = _rule_to_mapping(state.active_rule)
        resolved = controller.controller.resolve_round(
            state,
            {Team.RED: red_action, Team.BLUE: blue_action},
            match_seed=seed,
        )
        event_counts.update(event.kind for event in resolved.events)
        state = resolved.state
        round_traces.append(
            LiveRoundTrace(
                round_no=played_round,
                red_action=action_pair[0],
                blue_action=action_pair[1],
                red_hp_after=state.game_state.unit(Team.RED).hp,
                blue_hp_after=state.game_state.unit(Team.BLUE).hp,
                active_rule=active_before,
                event_kinds=tuple(event.kind for event in resolved.events),
            )
        )

        if state.rule_phase_due:
            next_phase = state.last_phase_index + 1
            applied = controller.apply_due_rule_phase(state, schedule.get(next_phase))
            event_counts.update(event.kind for event in applied.events)
            phase_traces.append(_phase_trace(applied.phase))
            state = applied.state

    if live_round1 is None:
        raise AssertionError("live match did not resolve round 1")
    if state.game_state.result is None:
        raise AssertionError("live match ended without a terminal result")

    return LiveMatchTrace(
        seed=seed,
        result=state.game_state.result.value,
        rounds=len(round_traces),
        baseline_round1_actions=baseline_round1,
        live_round1_actions=live_round1,
        round1_behavior_changed=live_round1 != baseline_round1,
        rule_modifier_events=event_counts["RULE_MODIFIER_APPLIED"],
        phases=tuple(phase_traces),
        rounds_trace=tuple(round_traces),
    )


def assert_live_dynamic_match_gate(traces: tuple[LiveMatchTrace, ...]) -> None:
    if len(traces) < 3:
        raise AssertionError("live gate requires at least three deterministic seeds")
    if any(trace.result == MatchResult.TIMEOUT.value for trace in traces):
        raise AssertionError("live natural-language schedule must not end in TIMEOUT")
    if any(not trace.round1_behavior_changed for trace in traces):
        raise AssertionError("phase-0 natural-language rule did not change deterministic round-1 behavior")
    if any(trace.rule_modifier_events <= 0 for trace in traces):
        raise AssertionError("accepted natural-language rule produced no Engine modifier event")

    reached_phase3 = 0
    for trace in traces:
        by_index = {phase.phase_index: phase for phase in trace.phases}
        for required in (0, 1, 2):
            if required not in by_index:
                raise AssertionError(f"seed {trace.seed} did not reach required phase {required}")

        for phase_index in (0, 1):
            phase = by_index[phase_index]
            if phase.translation_status != "ACCEPTED" or not phase.controller_replaced:
                raise AssertionError(
                    f"seed {trace.seed} legal phase {phase_index} was not accepted and replaced"
                )

        rejected_or = by_index[2]
        if rejected_or.translation_status != "INTENT_GUARD_REJECTED":
            raise AssertionError(f"seed {trace.seed} explicit OR was not rejected by intent guard")
        if rejected_or.controller_replaced:
            raise AssertionError(f"seed {trace.seed} rejected OR unexpectedly replaced active rule")
        if not rejected_or.carried_forward_after_translation_rejection:
            raise AssertionError(f"seed {trace.seed} rejected OR did not carry prior rule forward")

        for phase_index in (3, 4):
            phase = by_index.get(phase_index)
            if phase is None:
                continue
            reached_phase3 += int(phase_index == 3)
            if phase.translation_status != "ACCEPTED" or not phase.controller_replaced:
                raise AssertionError(
                    f"seed {trace.seed} reached legal phase {phase_index} but did not accept it"
                )

    if reached_phase3 == 0:
        raise AssertionError("no live match survived long enough to exercise a post-rejection replacement")


def build_live_controller(model: MimoRuleCandidateModel) -> VerifiedNaturalLanguageDynamicController:
    validator = RuleValidator(LIVE_MATCH_CONFIG)
    base = NaturalLanguageRuleAdapter(model, validator)
    verified = VerifiedNaturalLanguageRuleAdapter(
        base,
        NaturalLanguageRuleFaithfulnessVerifier(model),
    )
    return VerifiedNaturalLanguageDynamicController(verified, LIVE_MATCH_CONFIG)


def run_live_suite(
    *,
    model: MimoRuleCandidateModel,
    seeds: tuple[int, ...] = LIVE_MATCH_SEEDS,
) -> LiveDynamicMatchSummary:
    traces = tuple(
        play_live_match(build_live_controller(model), seed=seed)
        for seed in seeds
    )
    assert_live_dynamic_match_gate(traces)
    return LiveDynamicMatchSummary(
        provider="mimo",
        model_name=model.model_name,
        config=asdict(LIVE_MATCH_CONFIG),
        schedule=dict(LIVE_NL_SCHEDULE),
        gate_passed=True,
        matches=traces,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live MiMo -> verified rule -> dynamic match gate")
    parser.add_argument("--model", default=DEFAULT_MIMO_RULE_MODEL)
    args = parser.parse_args()

    api_key = os.getenv("MIMO_API_KEY", "")
    if not api_key.strip():
        raise SystemExit("MIMO_API_KEY is not set")

    model = MimoRuleCandidateModel(api_key, model_name=args.model)
    summary = run_live_suite(model=model)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
