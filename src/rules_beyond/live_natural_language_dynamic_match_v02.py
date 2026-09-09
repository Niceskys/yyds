from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import json
import os
from typing import Mapping

from .live_natural_language_dynamic_match import (
    LIVE_MATCH_CONFIG,
    LIVE_MATCH_SEEDS,
    LiveMatchTrace,
    build_live_controller,
    play_live_match,
)
from .mimo_rule_provider import DEFAULT_MIMO_RULE_MODEL, MimoRuleCandidateModel
from .model import MatchResult
from .natural_language_rule_adapter import RuleCandidateModel


# V0.2 intermission cadence: keys are the completed round after which the player
# submits one natural-language text. The schedule intentionally stops after the
# fourth intermission. Intermissions 1/2 prove legal replacement, intermission 3
# proves fail-closed rejection/carry-forward, and intermission 4 proves the match
# can recover and accept a new legal rule after that rejection.
LIVE_NL_SCHEDULE_V02: Mapping[int, str] = {
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
class LiveDynamicMatchV02Summary:
    provider: str
    model_name: str
    config: dict[str, object]
    schedule: dict[int, str]
    semantic_model_calls: int
    semantic_cache_hits: int
    gate_passed: bool
    gate_failures: tuple[str, ...]
    matches: tuple[LiveMatchTrace, ...]


def evaluate_v02_gate(traces: tuple[LiveMatchTrace, ...]) -> tuple[str, ...]:
    failures: list[str] = []
    if len(traces) < 3:
        failures.append("V0.2 live gate requires at least three combat seeds")
    if any(trace.result == MatchResult.TIMEOUT.value for trace in traces):
        failures.append("V0.2 live schedule ended in TIMEOUT")

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


def run_live_v02_suite(
    *,
    model: MimoRuleCandidateModel,
    seeds: tuple[int, ...] = LIVE_MATCH_SEEDS,
) -> LiveDynamicMatchV02Summary:
    cached_model = MemoizedRuleCandidateModel(model)
    traces = tuple(
        play_live_match(
            build_live_controller(cached_model),  # type: ignore[arg-type]
            seed=seed,
            schedule=LIVE_NL_SCHEDULE_V02,
        )
        for seed in seeds
    )
    failures = evaluate_v02_gate(traces)
    return LiveDynamicMatchV02Summary(
        provider="mimo",
        model_name=model.model_name,
        config=asdict(LIVE_MATCH_CONFIG),
        schedule=dict(LIVE_NL_SCHEDULE_V02),
        semantic_model_calls=cached_model.cache_misses,
        semantic_cache_hits=cached_model.cache_hits,
        gate_passed=not failures,
        gate_failures=failures,
        matches=traces,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run V0.2 live MiMo semantic compile -> multi-seed dynamic match gate"
    )
    parser.add_argument("--model", default=DEFAULT_MIMO_RULE_MODEL)
    args = parser.parse_args()

    api_key = os.getenv("MIMO_API_KEY", "")
    if not api_key.strip():
        raise SystemExit("MIMO_API_KEY is not set")

    model = MimoRuleCandidateModel(api_key, model_name=args.model)
    summary = run_live_v02_suite(model=model)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    if not summary.gate_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
