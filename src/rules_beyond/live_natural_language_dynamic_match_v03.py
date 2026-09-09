"""V0.2 intermission-cadence natural-language dynamic match Gate (V0.3).

This is a NEW cadence Gate created after DynamicRuleController migrated to the
V0.2 intermission state machine. It is NOT a rerun of the frozen
Natural-Language Dynamic Match Gate V0.1 (FAIL, head
9239cfa876f5a7fb3d050ad960ceacf851e43324) or V0.2 (FAIL, head
62a1ec52899ab16e47fcf957ab9a246b0452c658). Those historical gates remain
reproducible through their pinned workflows:

  .github/workflows/live-natural-language-dynamic-match.yml
  .github/workflows/live-natural-language-dynamic-match-v02.yml

This V0.3 Gate keeps the V0.2 evaluation-only memoization semantics: one real
semantic provider decision per unique (system_prompt, player_text), reused across
the three deterministic combat seeds.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
import os
from typing import Mapping

from .dynamic_rule_controller import DynamicRuleController
from .mimo_rule_provider import DEFAULT_MIMO_RULE_MODEL, MimoRuleCandidateModel
from .model import Action, GameConfig, MatchResult, Team
from .natural_language_dynamic_controller import (
    NaturalLanguageRuleAttempt,
    VerifiedNaturalLanguageDynamicController,
)
from .natural_language_rule_adapter import NaturalLanguageRuleAdapter, RuleCandidateModel
from .rule_bots import RuleAwareAttackFirstBot
from .rule_dsl import RuleAST
from .rule_faithfulness import NaturalLanguageRuleFaithfulnessVerifier
from .rule_validator import RuleValidator
from .verified_natural_language_rule_adapter import VerifiedNaturalLanguageRuleAdapter


LIVE_MATCH_CONFIG = GameConfig(initial_hp=5, knife_damage=2)
LIVE_MATCH_SEEDS = (1_260_000, 1_260_001, 1_260_002)

# V0.3 intermission cadence: keys are the completed round after which the player
# submits one natural-language text, then continues. Round 1 always resolves
# without a player rule. The round-3 text is intentionally unsupported OR logic:
# the verified pipeline must reject it, the previous legal rule must be carried
# forward, and the intermission must stay usable for a later legal replacement.
LIVE_NL_SCHEDULE_V03: Mapping[int, str] = {
    1: "双方刀的攻击距离增加1格。",
    2: "双方移动距离增加1格。",
    3: "生命值不超过2或者上一回合没移动时，弓射程增加1格。",
    4: "双方相距至少3格时，弓箭命中率按原来的一半计算。",
}


class MemoizedRuleCandidateModel:
    """Evaluation-only cache: one semantic model decision per unique submission.

    The verified NL layer never sees GameState, so identical (system prompt,
    player text) pairs should represent the same player submission semantics.
    Combat seeds must not create extra LLM decisions for that same submission.
    Provider exceptions are not cached.
    """

    def __init__(self, model: RuleCandidateModel) -> None:
        self.model = model
        self._cache: dict[tuple[str, str], str] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        key = (system_prompt, player_text)
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]
        raw = self.model.generate_candidate(system_prompt=system_prompt, player_text=player_text)
        self._cache[key] = raw
        self.cache_misses += 1
        return raw


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
    baseline_round2_actions: tuple[str, str]
    live_round2_actions: tuple[str, str]
    post_intermission_behavior_changed: bool
    rule_modifier_events: int
    phases: tuple[LivePhaseTrace, ...]
    rounds_trace: tuple[LiveRoundTrace, ...]


@dataclass(frozen=True, slots=True)
class LiveDynamicMatchV03Summary:
    provider: str
    model_name: str
    config: dict[str, object]
    schedule: dict[int, str]
    semantic_model_calls: int
    semantic_cache_hits: int
    gate_passed: bool
    gate_failures: tuple[str, ...]
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


def _phase_trace(attempt: NaturalLanguageRuleAttempt, after_round: int) -> LivePhaseTrace:
    translation = attempt.translation
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

    outcome = attempt.outcome
    return LivePhaseTrace(
        phase_index=after_round - 1,
        after_round=after_round,
        player_text=attempt.player_text,
        translation_status=translation_status,
        base_status=base_status,
        faithfulness_decision=faithfulness_decision,
        intent_guard_allowed=intent_guard_allowed,
        controller_submitted=outcome.submitted,
        controller_accepted=outcome.accepted,
        controller_replaced=outcome.replaced,
        carried_forward_after_translation_rejection=(
            attempt.carried_forward_after_translation_rejection
        ),
        active_rule=_rule_to_mapping(outcome.active_rule),
    )


def _baseline_round2_actions(config: GameConfig, seed: int) -> tuple[str, str]:
    """Round-2 actions of a no-player-rule match.

    Baseline deliberately bypasses all natural-language code so the comparison
    isolates whether the public rule accepted in the first intermission changes
    planner behavior on the following round. Round 1 is identical by design:
    V0.2 never allows a player rule before round 1.
    """

    bot = RuleAwareAttackFirstBot()
    dynamic = DynamicRuleController(config)
    state = dynamic.start_match().state
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
    state = dynamic.resolve_round(
        state,
        {Team.RED: red, Team.BLUE: blue},
        match_seed=seed,
    ).state
    state = dynamic.continue_match(state).state
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
    return _action_signature(red), _action_signature(blue)


def play_live_match_v03(
    controller: VerifiedNaturalLanguageDynamicController,
    *,
    seed: int,
    schedule: Mapping[int, str] = LIVE_NL_SCHEDULE_V03,
) -> LiveMatchTrace:
    bot = RuleAwareAttackFirstBot()
    baseline_round2 = _baseline_round2_actions(controller.config, seed)

    started = controller.start_match()
    state = started.state
    phase_traces: list[LivePhaseTrace] = []
    round_traces: list[LiveRoundTrace] = []
    event_counts: Counter[str] = Counter(event.kind for event in started.events)
    live_round2: tuple[str, str] | None = None

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
        if played_round == 2:
            live_round2 = action_pair

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

        if state.in_intermission:
            after_round = state.pending_intermission_after_round
            player_text = schedule.get(after_round)
            if player_text is not None:
                applied = controller.submit_rule(state, player_text)
                event_counts.update(event.kind for event in applied.events)
                phase_traces.append(_phase_trace(applied.attempt, after_round))
                state = applied.state
            state = controller.continue_match(state).state

    if live_round2 is None:
        raise AssertionError("live match did not resolve round 2")
    if state.game_state.result is None:
        raise AssertionError("live match ended without a terminal result")

    return LiveMatchTrace(
        seed=seed,
        result=state.game_state.result.value,
        rounds=len(round_traces),
        baseline_round2_actions=baseline_round2,
        live_round2_actions=live_round2,
        post_intermission_behavior_changed=live_round2 != baseline_round2,
        rule_modifier_events=event_counts["RULE_MODIFIER_APPLIED"],
        phases=tuple(phase_traces),
        rounds_trace=tuple(round_traces),
    )


def evaluate_v03_gate(traces: tuple[LiveMatchTrace, ...]) -> tuple[str, ...]:
    failures: list[str] = []
    if len(traces) < 3:
        failures.append("V0.3 live gate requires at least three combat seeds")
    if any(trace.result == MatchResult.TIMEOUT.value for trace in traces):
        failures.append("V0.3 live schedule ended in TIMEOUT")

    phase3_seen = False
    for trace in traces:
        if not trace.post_intermission_behavior_changed:
            failures.append(
                f"seed {trace.seed}: first-intermission accepted rule did not change "
                "round-2 planner behavior"
            )
        if trace.rule_modifier_events <= 0:
            failures.append(f"seed {trace.seed}: no RULE_MODIFIER_APPLIED Engine event")

        by_index = {phase.phase_index: phase for phase in trace.phases}
        missing = [index for index in (0, 1, 2) if index not in by_index]
        if missing:
            failures.append(f"seed {trace.seed}: missing required phases {missing}")
            continue

        for index in (0, 1):
            phase = by_index[index]
            if phase.translation_status != "ACCEPTED" or not phase.controller_replaced:
                failures.append(
                    f"seed {trace.seed}: legal phase {index} was not accepted/replaced "
                    f"(translation={phase.translation_status}, replaced={phase.controller_replaced})"
                )

        phase2 = by_index[2]
        if phase2.translation_status != "INTENT_GUARD_REJECTED":
            failures.append(
                f"seed {trace.seed}: explicit OR was not intent-guard rejected "
                f"(translation={phase2.translation_status})"
            )
        if phase2.controller_replaced:
            failures.append(f"seed {trace.seed}: rejected OR replaced active_rule")
        if not phase2.carried_forward_after_translation_rejection:
            failures.append(f"seed {trace.seed}: rejected OR did not carry previous legal rule")

        phase3 = by_index.get(3)
        if phase3 is not None:
            phase3_seen = True
            if phase3.translation_status != "ACCEPTED" or not phase3.controller_replaced:
                failures.append(
                    f"seed {trace.seed}: post-rejection phase 3 was not accepted/replaced "
                    f"(translation={phase3.translation_status}, replaced={phase3.controller_replaced})"
                )

    if not phase3_seen:
        failures.append("no combat seed reached post-rejection legal phase 3")
    return tuple(failures)


def assert_live_v03_gate(traces: tuple[LiveMatchTrace, ...]) -> None:
    failures = evaluate_v03_gate(traces)
    if failures:
        raise AssertionError("; ".join(failures))


def build_live_controller_v03(
    model: MimoRuleCandidateModel,
) -> VerifiedNaturalLanguageDynamicController:
    validator = RuleValidator(LIVE_MATCH_CONFIG)
    base = NaturalLanguageRuleAdapter(model, validator)
    verified = VerifiedNaturalLanguageRuleAdapter(
        base,
        NaturalLanguageRuleFaithfulnessVerifier(model),
    )
    return VerifiedNaturalLanguageDynamicController(verified, LIVE_MATCH_CONFIG)


def run_live_v03_suite(
    *,
    model: MimoRuleCandidateModel,
    seeds: tuple[int, ...] = LIVE_MATCH_SEEDS,
) -> LiveDynamicMatchV03Summary:
    cached_model = MemoizedRuleCandidateModel(model)
    traces = tuple(
        play_live_match_v03(
            build_live_controller_v03(cached_model),  # type: ignore[arg-type]
            seed=seed,
            schedule=LIVE_NL_SCHEDULE_V03,
        )
        for seed in seeds
    )
    failures = evaluate_v03_gate(traces)
    return LiveDynamicMatchV03Summary(
        provider="mimo",
        model_name=model.model_name,
        config=asdict(LIVE_MATCH_CONFIG),
        schedule=dict(LIVE_NL_SCHEDULE_V03),
        semantic_model_calls=cached_model.cache_misses,
        semantic_cache_hits=cached_model.cache_hits,
        gate_passed=not failures,
        gate_failures=failures,
        matches=traces,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run V0.3 intermission-cadence MiMo semantic compile -> multi-seed dynamic match gate"
    )
    parser.add_argument("--model", default=DEFAULT_MIMO_RULE_MODEL)
    args = parser.parse_args()

    api_key = os.getenv("MIMO_API_KEY", "")
    if not api_key.strip():
        raise SystemExit("MIMO_API_KEY is not set")

    model = MimoRuleCandidateModel(api_key, model_name=args.model)
    summary = run_live_v03_suite(model=model)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    if not summary.gate_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
