import json

from rules_beyond.live_natural_language_dynamic_match import LIVE_MATCH_CONFIG, LIVE_MATCH_SEEDS, build_live_controller, play_live_match
from rules_beyond.live_natural_language_dynamic_match_v02 import (
    LIVE_NL_SCHEDULE_V02,
    MemoizedRuleCandidateModel,
    evaluate_v02_gate,
)


PHASE_CANDIDATES = {
    LIVE_NL_SCHEDULE_V02[0]: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    LIVE_NL_SCHEDULE_V02[1]: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    LIVE_NL_SCHEDULE_V02[3]: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "DISTANCE_GTE", "value": 3}],
        "effect": {"type": "BOW_HIT_MULTIPLIER", "multiplier": 0.5},
        "duration": "UNTIL_REPLACED",
    },
}


class CountingGateOracleModel:
    def __init__(self) -> None:
        self.calls = 0

    def generate_candidate(self, *, system_prompt: str, player_text: str) -> str:
        self.calls += 1
        if "strict semantic verifier" in system_prompt:
            return json.dumps({"decision": "FAITHFUL"})
        return json.dumps(
            {"decision": "CANDIDATE", "candidate": PHASE_CANDIDATES[player_text]},
            ensure_ascii=False,
        )


def test_memoized_model_returns_one_provider_decision_per_identical_request() -> None:
    underlying = CountingGateOracleModel()
    cached = MemoizedRuleCandidateModel(underlying)
    player_text = LIVE_NL_SCHEDULE_V02[0]

    first = cached.generate_candidate(system_prompt="translator", player_text=player_text)
    second = cached.generate_candidate(system_prompt="translator", player_text=player_text)

    assert first == second
    assert underlying.calls == 1
    assert cached.cache_misses == 1
    assert cached.cache_hits == 1


def test_v02_offline_gate_compiles_each_semantic_request_once_across_combat_seeds() -> None:
    underlying = CountingGateOracleModel()
    cached = MemoizedRuleCandidateModel(underlying)

    traces = tuple(
        play_live_match(
            build_live_controller(cached),  # type: ignore[arg-type]
            seed=seed,
            schedule=LIVE_NL_SCHEDULE_V02,
        )
        for seed in LIVE_MATCH_SEEDS
    )

    assert evaluate_v02_gate(traces) == ()
    assert all(trace.round1_behavior_changed for trace in traces)
    assert all(trace.rule_modifier_events > 0 for trace in traces)

    # Three legal texts each require translator + verifier once. The explicit
    # OR phase is rejected by the deterministic guard before any model call.
    assert cached.cache_misses == 6
    assert underlying.calls == 6
    assert cached.cache_hits > 0

    for trace in traces:
        by_index = {phase.phase_index: phase for phase in trace.phases}
        assert by_index[0].translation_status == "ACCEPTED"
        assert by_index[1].translation_status == "ACCEPTED"
        assert by_index[2].translation_status == "INTENT_GUARD_REJECTED"
        if 3 in by_index:
            assert by_index[3].translation_status == "ACCEPTED"
