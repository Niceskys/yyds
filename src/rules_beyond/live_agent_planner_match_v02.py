"""V0.2 intermission-cadence Agent / Planner connectivity Gate.

This is a NEW cadence Gate for the V0.2 DynamicRuleController state machine. It
is NOT a rerun of the frozen Agent / Planner Integration Gate V0.1 PASS
(2026-09-08, head 5c1aeccc7d9ef1727c01f416695415f5a9c9477f). That historical
Gate remains reproducible through its pinned workflow
.github/workflows/live-agent-planner-match.yml.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import argparse
import json
import os
from typing import Mapping

from .dynamic_rule_controller import DynamicRuleController
from .mimo_strategy_provider import MimoStrategyModel
from .model import Action, GameConfig, MatchResult, Team
from .planner_audit import audit_action_against_snapshot
from .strategy_agent import (
    DeterministicIntentPlanner,
    IsolatedStrategyAgent,
    StrategyDecision,
    StrategyDecisionStatus,
)


AGENT_GATE_CONFIG = GameConfig(initial_hp=5, knife_damage=2)
AGENT_GATE_SEED = 1_270_000

# Fixed, closed candidates deliberately decouple this Gate from the natural-language
# compiler. Dynamic natural-language translation has its own evidence and failure log.
# V0.2 intermission cadence: keys are the completed round after which the player
# attempts the replacement. Round 1 always resolves without a player rule.
AGENT_RULE_SCHEDULE: Mapping[int, Mapping[str, object] | None] = {
    1: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    2: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [],
        "effect": {"type": "MOVE_RANGE_ADD", "delta": 1},
        "duration": "UNTIL_REPLACED",
    },
    3: {
        "version": "v0.1",
        "target": "ALL_UNITS",
        "conditions": [{"type": "DISTANCE_GTE", "value": 3}],
        "effect": {"type": "BOW_HIT_MULTIPLIER", "multiplier": 0.5},
        "duration": "UNTIL_REPLACED",
    },
}


@dataclass(frozen=True, slots=True)
class AgentDecisionTrace:
    # Number of completed rounds when this strategy decision was taken. 0 is the
    # initial decision before round 1; later values are post-intermission decisions.
    phase_index: int
    round_no: int
    team: str
    status: str
    intent: str


@dataclass(frozen=True, slots=True)
class AgentRoundTrace:
    round_no: int
    red_intent: str
    blue_intent: str
    red_action: str
    blue_action: str
    red_hp_after: int
    blue_hp_after: int
    planner_snapshot_issues: tuple[str, ...]
    event_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentPlannerMatchSummary:
    model_name: str
    seed: int
    config: dict[str, object]
    result: str
    rounds: int
    gate_passed: bool
    gate_failures: tuple[str, ...]
    planner_snapshot_errors: int
    decision_traces: tuple[AgentDecisionTrace, ...]
    round_traces: tuple[AgentRoundTrace, ...]
    event_counts: dict[str, int]


def _action_signature(action: Action) -> str:
    path = ",".join(step.value for step in action.move_path) or "STAY"
    attack = action.attack.value if action.attack is not None else "NONE"
    return f"{path}|{attack}"


def _decision_trace(
    phase_index: int,
    round_no: int,
    team: Team,
    decision: StrategyDecision,
) -> AgentDecisionTrace:
    return AgentDecisionTrace(
        phase_index=phase_index,
        round_no=round_no,
        team=team.value,
        status=decision.status.value,
        intent=decision.intent.value,
    )


def evaluate_agent_gate(summary: AgentPlannerMatchSummary) -> tuple[str, ...]:
    failures: list[str] = []
    if summary.result == MatchResult.TIMEOUT.value:
        failures.append("live Agent/Planner match ended in TIMEOUT")

    by_team: dict[str, list[AgentDecisionTrace]] = {Team.RED.value: [], Team.BLUE.value: []}
    for trace in summary.decision_traces:
        by_team[trace.team].append(trace)

    for team in (Team.RED.value, Team.BLUE.value):
        traces = by_team[team]
        accepted = [trace for trace in traces if trace.status == StrategyDecisionStatus.ACCEPTED.value]
        if len(accepted) < 2:
            failures.append(f"{team} did not produce at least two accepted real strategy decisions")
        if not any(
            trace.phase_index == 0 and trace.status == StrategyDecisionStatus.ACCEPTED.value
            for trace in traces
        ):
            failures.append(f"{team} initial no-rule strategy decision was not accepted")
        if not any(
            trace.phase_index >= 1 and trace.status == StrategyDecisionStatus.ACCEPTED.value
            for trace in traces
        ):
            failures.append(f"{team} never produced an accepted post-rule-change strategy decision")

    if summary.planner_snapshot_errors != 0:
        failures.append("deterministic planner submitted an action illegal in its public snapshot")
    if summary.event_counts.get("INVALID_MOVE_PATH", 0) != 0:
        failures.append("Engine observed INVALID_MOVE_PATH from deterministic planner")
    if summary.event_counts.get("PLAYER_RULE_REPLACED", 0) < 2:
        failures.append("dynamic match did not exercise at least two accepted public-rule replacements")
    if not summary.round_traces:
        failures.append("no combat rounds were resolved")

    return tuple(failures)


def play_agent_match(
    red_agent: IsolatedStrategyAgent,
    blue_agent: IsolatedStrategyAgent,
    *,
    seed: int = AGENT_GATE_SEED,
    config: GameConfig = AGENT_GATE_CONFIG,
    rule_schedule: Mapping[int, Mapping[str, object] | None] = AGENT_RULE_SCHEDULE,
) -> AgentPlannerMatchSummary:
    if red_agent.team is not Team.RED or blue_agent.team is not Team.BLUE:
        raise ValueError("Agent Gate requires one RED session and one BLUE session")
    if red_agent is blue_agent:
        raise ValueError("RED and BLUE must use distinct Agent session objects")

    controller = DynamicRuleController(config)
    planner = DeterministicIntentPlanner()
    started = controller.start_match()
    state = started.state
    event_counts: Counter[str] = Counter(event.kind for event in started.events)

    red_decision = red_agent.decide(
        state.game_state,
        controller.engine,
        rule=state.active_rule,
        histories=state.histories,
    )
    blue_decision = blue_agent.decide(
        state.game_state,
        controller.engine,
        rule=state.active_rule,
        histories=state.histories,
    )
    red_intent = red_decision.intent
    blue_intent = blue_decision.intent
    decision_traces: list[AgentDecisionTrace] = [
        _decision_trace(0, state.game_state.round_no, Team.RED, red_decision),
        _decision_trace(0, state.game_state.round_no, Team.BLUE, blue_decision),
    ]
    round_traces: list[AgentRoundTrace] = []
    planner_snapshot_errors = 0

    while not state.game_state.is_terminal:
        played_round = state.game_state.round_no
        red_action = planner.choose_action(
            state.game_state,
            Team.RED,
            controller.engine,
            rule=state.active_rule,
            histories=state.histories,
            intent=red_intent,
        )
        blue_action = planner.choose_action(
            state.game_state,
            Team.BLUE,
            controller.engine,
            rule=state.active_rule,
            histories=state.histories,
            intent=blue_intent,
        )

        red_audit = audit_action_against_snapshot(
            state.game_state,
            Team.RED,
            controller.engine,
            red_action,
            rule=state.active_rule,
            histories=state.histories,
        )
        blue_audit = audit_action_against_snapshot(
            state.game_state,
            Team.BLUE,
            controller.engine,
            blue_action,
            rule=state.active_rule,
            histories=state.histories,
        )
        snapshot_issues = tuple(
            [f"RED:{issue}" for issue in red_audit.issues]
            + [f"BLUE:{issue}" for issue in blue_audit.issues]
        )
        planner_snapshot_errors += len(snapshot_issues)

        resolved = controller.resolve_round(
            state,
            {Team.RED: red_action, Team.BLUE: blue_action},
            match_seed=seed,
        )
        event_counts.update(event.kind for event in resolved.events)
        state = resolved.state
        round_traces.append(
            AgentRoundTrace(
                round_no=played_round,
                red_intent=red_intent.value,
                blue_intent=blue_intent.value,
                red_action=_action_signature(red_action),
                blue_action=_action_signature(blue_action),
                red_hp_after=state.game_state.unit(Team.RED).hp,
                blue_hp_after=state.game_state.unit(Team.BLUE).hp,
                planner_snapshot_issues=snapshot_issues,
                event_kinds=tuple(event.kind for event in resolved.events),
            )
        )

        if state.in_intermission:
            after_round = state.pending_intermission_after_round
            candidate = rule_schedule.get(after_round)
            replaced = False
            if candidate is not None:
                applied = controller.submit_rule(state, candidate)
                event_counts.update(event.kind for event in applied.events)
                replaced = applied.outcome.replaced
                state = applied.state
            state = controller.continue_match(state).state

            if replaced:
                red_decision = red_agent.decide(
                    state.game_state,
                    controller.engine,
                    rule=state.active_rule,
                    histories=state.histories,
                )
                blue_decision = blue_agent.decide(
                    state.game_state,
                    controller.engine,
                    rule=state.active_rule,
                    histories=state.histories,
                )
                red_intent = red_decision.intent
                blue_intent = blue_decision.intent
                decision_traces.extend(
                    (
                        _decision_trace(
                            state.completed_rounds,
                            state.game_state.round_no,
                            Team.RED,
                            red_decision,
                        ),
                        _decision_trace(
                            state.completed_rounds,
                            state.game_state.round_no,
                            Team.BLUE,
                            blue_decision,
                        ),
                    )
                )

    result = state.game_state.result
    if result is None:
        raise AssertionError("Agent/Planner match ended without a terminal result")

    provisional = AgentPlannerMatchSummary(
        model_name=getattr(red_agent.model, "model_name", type(red_agent.model).__name__),
        seed=seed,
        config=asdict(config),
        result=result.value,
        rounds=len(round_traces),
        gate_passed=False,
        gate_failures=(),
        planner_snapshot_errors=planner_snapshot_errors,
        decision_traces=tuple(decision_traces),
        round_traces=tuple(round_traces),
        event_counts=dict(sorted(event_counts.items())),
    )
    failures = evaluate_agent_gate(provisional)
    return AgentPlannerMatchSummary(
        model_name=provisional.model_name,
        seed=provisional.seed,
        config=provisional.config,
        result=provisional.result,
        rounds=provisional.rounds,
        gate_passed=not failures,
        gate_failures=failures,
        planner_snapshot_errors=provisional.planner_snapshot_errors,
        decision_traces=provisional.decision_traces,
        round_traces=provisional.round_traces,
        event_counts=provisional.event_counts,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live isolated-Agent + deterministic-Planner Gate")
    parser.add_argument("--model", default="mimo-v2.5-pro")
    args = parser.parse_args()

    api_key = os.getenv("MIMO_API_KEY", "")
    if not api_key.strip():
        raise SystemExit("MIMO_API_KEY is not set")

    red_agent = IsolatedStrategyAgent(
        Team.RED,
        MimoStrategyModel(api_key, model_name=args.model),
    )
    blue_agent = IsolatedStrategyAgent(
        Team.BLUE,
        MimoStrategyModel(api_key, model_name=args.model),
    )
    summary = play_agent_match(red_agent, blue_agent)
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    if not summary.gate_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
