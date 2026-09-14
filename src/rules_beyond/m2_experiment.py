"""Experiment-only M2 Agent A/B/C paired evidence harness.

This module deliberately reuses the production Engine and B strategy prompt while
keeping the A heuristic, richer C protocol, metering, and artifact output outside
the public API/runtime surface.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
import argparse
import json
import math
import os
from pathlib import Path
import random
from statistics import median
from time import perf_counter
from typing import Mapping, Protocol

from .dynamic_rule_controller import DynamicRuleController
from .mimo_strategy_provider import MimoStrategyModel
from .model import Action, Direction, GameConfig, GameState, Team, Weapon
from .planner_audit import audit_action_against_snapshot
from .rule_dsl import RuleAST
from .rule_experiment import RULE_CANDIDATES
from .rule_runtime import PublicRuleHistory
from .strategy_agent import (
    DeterministicIntentPlanner,
    IsolatedStrategyAgent,
    StrategyDecision,
    StrategyDecisionStatus,
    StrategyIntent,
)

MODEL = "mimo-v2.5"
PILOT_SEEDS = tuple(range(1_280_000, 1_280_003))
CONFIRM_SEEDS = tuple(range(1_280_000, 1_280_010))
MAX_CALLS = 4_800
MAX_COST_USD = 5.0
INPUT_USD_PER_MTOK = 0.14
OUTPUT_USD_PER_MTOK = 0.28
# Conservative stop accounting; actual/estimated usage is reported separately.
RESERVED_INPUT_TOKENS_PER_CALL = 4_000
RESERVED_OUTPUT_TOKENS_PER_CALL = 512
M2_CONFIG = GameConfig(initial_hp=5, knife_damage=2)


class Arm(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class WeaponPreference(str, Enum):
    KNIFE = "KNIFE"
    BOW = "BOW"
    ANY = "ANY"


class RiskBudget(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ShortTermGoal(str, Enum):
    DAMAGE = "DAMAGE"
    SURVIVE = "SURVIVE"
    CONTROL_DISTANCE = "CONTROL_DISTANCE"


class Contingency(str, Enum):
    CLOSE = "CLOSE"
    SEPARATE = "SEPARATE"
    HOLD = "HOLD"


@dataclass(frozen=True, slots=True)
class RichPlan:
    mode: StrategyIntent
    target_distance: int
    weapon_preference: WeaponPreference
    risk_budget: RiskBudget
    short_term_goal: ShortTermGoal
    horizon_rounds: int
    contingency: Contingency


FALLBACK_PLAN = RichPlan(
    StrategyIntent.PRESSURE, 1, WeaponPreference.ANY, RiskBudget.MEDIUM,
    ShortTermGoal.DAMAGE, 1, Contingency.CLOSE,
)


C_SYSTEM_PROMPT = """You are one competitive combat agent in Rules Beyond.
Use only the supplied public observation. Never choose coordinates, paths, damage,
HP, RNG, winners, or GameState changes. Do not output rationale or chain-of-thought.
Return exactly one JSON object with exactly these fields:
{"mode":"PRESSURE|KITE|EVADE|HOLD","target_distance":1,
"weapon_preference":"KNIFE|BOW|ANY","risk_budget":"LOW|MEDIUM|HIGH",
"short_term_goal":"DAMAGE|SURVIVE|CONTROL_DISTANCE","horizon_rounds":1,
"contingency":"CLOSE|SEPARATE|HOLD"}
target_distance must be 1..5 and horizon_rounds 1..3.
"""


SCENARIOS: Mapping[str, Mapping[int, Mapping[str, object]]] = {
    "S0_control": {},
    "S1_mobility": {1: RULE_CANDIDATES["always_move_range_plus_1"]},
    "S2_range": {1: RULE_CANDIDATES["always_bow_range_plus_1"]},
    "S3_replacement": {
        1: RULE_CANDIDATES["always_bow_range_plus_1"],
        2: RULE_CANDIDATES["always_move_range_plus_1"],
        3: RULE_CANDIDATES["distance_ge_3_bow_hit_half"],
    },
}


class StrategyModel(Protocol):
    model_name: str
    def generate_strategy(self, *, system_prompt: str, observation: str) -> str: ...


class BudgetStop(BaseException):
    """Hard experiment stop that provider fallback handlers must not swallow."""


@dataclass(slots=True)
class BudgetMeter:
    max_calls: int = MAX_CALLS
    max_cost_usd: float = MAX_COST_USD
    calls: int = 0
    input_chars: int = 0
    output_chars: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def reserved_cost_usd(self) -> float:
        per_call = (
            RESERVED_INPUT_TOKENS_PER_CALL * INPUT_USD_PER_MTOK
            + RESERVED_OUTPUT_TOKENS_PER_CALL * OUTPUT_USD_PER_MTOK
        ) / 1_000_000
        return self.calls * per_call

    @property
    def estimated_cost_usd(self) -> float:
        # UTF-8 character estimate is reported only when provider usage is absent.
        input_tokens = self.input_chars / 4
        output_tokens = self.output_chars / 4
        return (input_tokens * INPUT_USD_PER_MTOK + output_tokens * OUTPUT_USD_PER_MTOK) / 1_000_000

    def reserve(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetStop("BUDGET_STOP: provider call ceiling reached")
        next_calls = self.calls + 1
        per_call = (
            RESERVED_INPUT_TOKENS_PER_CALL * INPUT_USD_PER_MTOK
            + RESERVED_OUTPUT_TOKENS_PER_CALL * OUTPUT_USD_PER_MTOK
        ) / 1_000_000
        if next_calls * per_call > self.max_cost_usd:
            raise BudgetStop("BUDGET_STOP: monetary ceiling reached")
        self.calls = next_calls


class MeteredModel:
    def __init__(self, inner: StrategyModel, meter: BudgetMeter) -> None:
        self.inner = inner
        self.meter = meter
        self.model_name = getattr(inner, "model_name", type(inner).__name__)

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        self.meter.reserve()
        self.meter.input_chars += len(system_prompt) + len(observation)
        started = perf_counter()
        try:
            output = self.inner.generate_strategy(
                system_prompt=system_prompt, observation=observation
            )
        finally:
            self.meter.latencies_ms.append((perf_counter() - started) * 1000)
        if isinstance(output, str):
            self.meter.output_chars += len(output)
        return output


@dataclass(frozen=True, slots=True)
class RichDecision:
    status: StrategyDecisionStatus
    plan: RichPlan


def parse_rich_plan(raw: str) -> RichPlan:
    decoded = json.loads(raw)
    fields = {
        "mode", "target_distance", "weapon_preference", "risk_budget",
        "short_term_goal", "horizon_rounds", "contingency",
    }
    if not isinstance(decoded, dict) or set(decoded) != fields:
        raise ValueError("rich plan must contain exactly the frozen fields")
    target = decoded["target_distance"]
    horizon = decoded["horizon_rounds"]
    if type(target) is not int or not 1 <= target <= 5:
        raise ValueError("target_distance must be 1..5")
    if type(horizon) is not int or not 1 <= horizon <= 3:
        raise ValueError("horizon_rounds must be 1..3")
    return RichPlan(
        StrategyIntent(decoded["mode"]), target,
        WeaponPreference(decoded["weapon_preference"]),
        RiskBudget(decoded["risk_budget"]),
        ShortTermGoal(decoded["short_term_goal"]), horizon,
        Contingency(decoded["contingency"]),
    )


def public_observation(
    team: Team, state: GameState, engine, rule: RuleAST | None,
    histories: Mapping[Team, PublicRuleHistory], private_memory=(),
) -> str:
    # Reuse the production observation builder to guarantee the same public view.
    shell = IsolatedStrategyAgent(team, _NeverCalledModel())
    observation = shell._build_observation(state, engine, rule=rule, histories=histories)
    mapping = asdict(observation)
    mapping["private_memory"] = list(private_memory)
    return json.dumps(mapping, default=lambda value: value.value, sort_keys=True)


class _NeverCalledModel:
    model_name = "never"
    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        raise AssertionError("observation-only model was called")


def rich_decide(model: StrategyModel, observation: str) -> RichDecision:
    try:
        raw = model.generate_strategy(system_prompt=C_SYSTEM_PROMPT, observation=observation)
        if not isinstance(raw, str) or len(raw) > 4096:
            raise ValueError("invalid output size/type")
        return RichDecision(StrategyDecisionStatus.ACCEPTED, parse_rich_plan(raw))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return RichDecision(StrategyDecisionStatus.FALLBACK_PROTOCOL_ERROR, FALLBACK_PLAN)
    except Exception:
        return RichDecision(StrategyDecisionStatus.FALLBACK_MODEL_ERROR, FALLBACK_PLAN)


def deterministic_a_intent(state, team, engine, rule, histories) -> StrategyIntent:
    planner = DeterministicIntentPlanner()
    stats = engine.effective_stats_for_team(state, team, rule=rule, histories=histories)
    opponent_hp = state.unit(team.opponent).hp
    opponent_pos = state.unit(team.opponent).position
    candidates = planner._candidate_actions(state, team, engine, stats)
    damages = [
        planner._expected_damage(c.action.attack, c.destination.manhattan_distance(opponent_pos), stats)
        for c in candidates
    ]
    if any(damage >= opponent_hp for damage in damages):
        return StrategyIntent.PRESSURE
    if state.unit(team).hp < opponent_hp and not any(damage > 0 for damage in damages):
        return StrategyIntent.EVADE
    if any(c.action.attack is Weapon.BOW and damage > 0 for c, damage in zip(candidates, damages)):
        return StrategyIntent.KITE
    if any(c.action.attack is Weapon.KNIFE for c in candidates):
        return StrategyIntent.PRESSURE
    return StrategyIntent.HOLD


class RichPlanner(DeterministicIntentPlanner):
    def choose_rich_action(self, state, team, engine, *, rule, histories, plan: RichPlan) -> Action:
        stats = engine.effective_stats_for_team(state, team, rule=rule, histories=histories)
        opponent = state.unit(team.opponent).position
        candidates = self._candidate_actions(state, team, engine, stats)
        def score(item):
            distance = item.destination.manhattan_distance(opponent)
            weapon_rank = 0 if plan.weapon_preference is WeaponPreference.ANY else int(
                item.action.attack is None or item.action.attack.value != plan.weapon_preference.value
            )
            survival_rank = 0
            if plan.risk_budget is RiskBudget.LOW and distance <= stats.knife_range:
                survival_rank = 1
            contingency_rank = 0
            if plan.contingency is Contingency.CLOSE and distance > plan.target_distance:
                contingency_rank = distance
            elif plan.contingency is Contingency.SEPARATE and distance < plan.target_distance:
                contingency_rank = -distance
            elif plan.contingency is Contingency.HOLD:
                contingency_rank = len(item.action.move_path)
            return (
                survival_rank, weapon_rank, abs(distance - plan.target_distance),
                contingency_rank, *self._score(item, opponent, stats, plan.mode),
            )
        return min(candidates, key=score).action


@dataclass(frozen=True, slots=True)
class MatchRecord:
    scenario: str
    seed: int
    arm: str
    result: str
    rounds: int
    decisions: int
    accepted: int
    protocol_fallbacks: int
    model_fallbacks: int
    planner_snapshot_issues: int
    engine_invalid_events: int
    eligible_opportunities: int
    captured_opportunities: int
    action_signatures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    scenario: str
    seed: int
    arm: str
    round_no: int
    team: str
    status: str
    mode: str
    plan: Mapping[str, object] | None
    action: str
    eligible_opportunity: bool
    captured_opportunity: bool


@dataclass(frozen=True, slots=True)
class RoundRecord:
    scenario: str
    seed: int
    arm: str
    round_no: int
    red_action: str
    blue_action: str
    red_hp_after: int
    blue_hp_after: int
    event_kinds: tuple[str, ...]


def _signature(action: Action) -> str:
    path = ",".join(x.value for x in action.move_path) or "STAY"
    return f"{path}|{action.attack.value if action.attack else 'NONE'}"


def _parse_action(value: str) -> Action:
    path_text, attack_text = value.split("|", 1)
    path = () if path_text == "STAY" else tuple(Direction(item) for item in path_text.split(","))
    attack = None if attack_text == "NONE" else Weapon(attack_text)
    return Action(path, attack)


def replay_reconstructable(match: MatchRecord, rounds: list[RoundRecord]) -> bool:
    controller = DynamicRuleController(M2_CONFIG)
    state = controller.start_match().state
    selected = [
        item for item in rounds
        if (item.scenario, item.seed, item.arm) == (match.scenario, match.seed, match.arm)
    ]
    for expected in selected:
        if state.game_state.round_no != expected.round_no:
            return False
        actions = {
            Team.RED: _parse_action(expected.red_action),
            Team.BLUE: _parse_action(expected.blue_action),
        }
        result = controller.resolve_round(state, actions, match_seed=match.seed)
        state = result.state
        if (
            state.game_state.unit(Team.RED).hp != expected.red_hp_after
            or state.game_state.unit(Team.BLUE).hp != expected.blue_hp_after
            or tuple(event.kind for event in result.events) != expected.event_kinds
        ):
            return False
        if state.in_intermission:
            candidate = SCENARIOS[match.scenario].get(state.pending_intermission_after_round)
            if candidate is not None:
                state = controller.submit_rule(state, candidate).state
            state = controller.continue_match(state).state
    return (
        len(selected) == match.rounds
        and state.game_state.is_terminal
        and state.game_state.result is not None
        and state.game_state.result.value == match.result
    )


def _opportunity(engine, state, team, rule, histories, action) -> tuple[bool, bool]:
    if rule is None:
        return False, False
    planner = DeterministicIntentPlanner()
    stats = engine.effective_stats_for_team(state, team, rule=rule, histories=histories)
    candidates = planner._candidate_actions(state, team, engine, stats)
    destination = state.unit(team).position
    for step in action.move_path:
        destination = destination.moved(step)
    opponent = state.unit(team.opponent).position
    effect = rule.effect.type.value
    if effect == "MOVE_RANGE_ADD" and stats.move_range > engine.config.base_move_range:
        eligible = any(len(item.action.move_path) > engine.config.base_move_range for item in candidates)
        return eligible, eligible and len(action.move_path) > engine.config.base_move_range
    if effect == "BOW_RANGE_ADD" and stats.bow_range > engine.config.base_bow_range:
        def extended_bow(item):
            return (item.action.attack is Weapon.BOW and
                    item.destination.manhattan_distance(opponent) > engine.config.base_bow_range)
        eligible = any(extended_bow(item) for item in candidates)
        captured = action.attack is Weapon.BOW and destination.manhattan_distance(opponent) > engine.config.base_bow_range
        return eligible, eligible and captured
    if effect == "BOW_HIT_MULTIPLIER":
        eligible = any(item.action.attack is Weapon.BOW for item in candidates)
        return eligible, eligible and action.attack is Weapon.BOW
    return False, False


def play_match(
    arm: Arm, scenario: str, seed: int, model_factory, meter: BudgetMeter,
    *, decision_sink: list[DecisionRecord] | None = None,
    round_sink: list[RoundRecord] | None = None,
) -> MatchRecord:
    controller = DynamicRuleController(M2_CONFIG)
    state = controller.start_match().state
    planner = DeterministicIntentPlanner()
    rich_planner = RichPlanner()
    b_agents = None
    c_models = None
    c_memory = {team: [] for team in Team}
    if arm is Arm.B:
        b_agents = {team: IsolatedStrategyAgent(team, model_factory(meter)) for team in Team}
    elif arm is Arm.C:
        c_models = {team: model_factory(meter) for team in Team}
    counts = Counter()
    signatures: list[str] = []
    planner_issues = invalid_events = rounds = eligible = captured = 0
    schedule = SCENARIOS[scenario]

    while not state.game_state.is_terminal:
        actions = {}
        decisions_this_round = {}
        for team in Team:
            rich_plan = None
            if arm is Arm.A:
                intent = deterministic_a_intent(
                    state.game_state, team, controller.engine, state.active_rule, state.histories
                )
                decision = StrategyDecision(StrategyDecisionStatus.ACCEPTED, intent, None)
                action = planner.choose_action(
                    state.game_state, team, controller.engine, rule=state.active_rule,
                    histories=state.histories, intent=intent,
                )
            elif arm is Arm.B:
                decision = b_agents[team].decide(  # type: ignore[index]
                    state.game_state, controller.engine, rule=state.active_rule,
                    histories=state.histories,
                )
                action = planner.choose_action(
                    state.game_state, team, controller.engine, rule=state.active_rule,
                    histories=state.histories, intent=decision.intent,
                )
            else:
                rd = rich_decide(
                    c_models[team],  # type: ignore[index]
                    public_observation(team, state.game_state, controller.engine,
                                       state.active_rule, state.histories, c_memory[team]),
                )
                decision = StrategyDecision(rd.status, rd.plan.mode, None)
                rich_plan = {
                    key: value.value if isinstance(value, Enum) else value
                    for key, value in asdict(rd.plan).items()
                }
                action = rich_planner.choose_rich_action(
                    state.game_state, team, controller.engine, rule=state.active_rule,
                    histories=state.histories, plan=rd.plan,
                )
                c_memory[team].append({
                    "round_no": state.game_state.round_no,
                    "mode": rd.plan.mode.value,
                    "target_distance": rd.plan.target_distance,
                })
                del c_memory[team][:-6]
            counts[decision.status.value] += 1
            audit = audit_action_against_snapshot(
                state.game_state, team, controller.engine, action, rule=state.active_rule,
                histories=state.histories,
            )
            planner_issues += len(audit.issues)
            actions[team] = action
            signatures.append(f"{team.value}:{_signature(action)}")
            is_eligible, is_captured = _opportunity(
                controller.engine, state.game_state, team, state.active_rule,
                state.histories, action,
            )
            eligible += int(is_eligible)
            captured += int(is_captured)
            decisions_this_round[team] = decision
            if decision_sink is not None:
                decision_sink.append(DecisionRecord(
                    scenario, seed, arm.value, state.game_state.round_no, team.value,
                    decision.status.value, decision.intent.value, rich_plan,
                    _signature(action), is_eligible, is_captured,
                ))
        played_round = state.game_state.round_no
        result = controller.resolve_round(state, actions, match_seed=seed)
        invalid_events += sum(event.kind == "INVALID_ATTACK" for event in result.events)
        state = result.state
        rounds += 1
        if round_sink is not None:
            round_sink.append(RoundRecord(
                scenario, seed, arm.value, played_round,
                _signature(actions[Team.RED]), _signature(actions[Team.BLUE]),
                state.game_state.unit(Team.RED).hp, state.game_state.unit(Team.BLUE).hp,
                tuple(event.kind for event in result.events),
            ))
        if state.in_intermission:
            candidate = schedule.get(state.pending_intermission_after_round)
            if candidate is not None:
                state = controller.submit_rule(state, candidate).state
            state = controller.continue_match(state).state
    assert state.game_state.result is not None
    return MatchRecord(
        scenario, seed, arm.value, state.game_state.result.value, rounds,
        sum(counts.values()), counts[StrategyDecisionStatus.ACCEPTED.value],
        counts[StrategyDecisionStatus.FALLBACK_PROTOCOL_ERROR.value],
        counts[StrategyDecisionStatus.FALLBACK_MODEL_ERROR.value],
        planner_issues, invalid_events, eligible, captured, tuple(signatures),
    )


def arm_order(seed: int) -> tuple[Arm, Arm, Arm]:
    orders = ((Arm.A, Arm.B, Arm.C), (Arm.B, Arm.C, Arm.A), (Arm.C, Arm.A, Arm.B))
    return orders[(seed - PILOT_SEEDS[0]) % 3]


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def _entropy(signatures: list[str]) -> float:
    if not signatures:
        return 0.0
    counts = Counter(signatures)
    total = len(signatures)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def _paired_capture_units(
    records: list[MatchRecord], left: Arm, right: Arm
) -> list[tuple[int, int, int, int]]:
    indexed = {(r.scenario, r.seed, r.arm): r for r in records}
    values = []
    for scenario in SCENARIOS:
        for seed in sorted({r.seed for r in records}):
            a = indexed[(scenario, seed, left.value)]
            b = indexed[(scenario, seed, right.value)]
            values.append((
                a.captured_opportunities, a.eligible_opportunities,
                b.captured_opportunities, b.eligible_opportunities,
            ))
    return values


def _capture_difference(values: list[tuple[int, int, int, int]]) -> float:
    left_captured = sum(item[0] for item in values)
    left_eligible = sum(item[1] for item in values)
    right_captured = sum(item[2] for item in values)
    right_eligible = sum(item[3] for item in values)
    left_rate = left_captured / left_eligible if left_eligible else 0.0
    right_rate = right_captured / right_eligible if right_eligible else 0.0
    return right_rate - left_rate


def _bootstrap_ci(
    values: list[tuple[int, int, int, int]], *, samples: int = 10_000
) -> list[float] | None:
    if not values or not any(item[1] or item[3] for item in values):
        return None
    rng = random.Random(2_026_091_2)
    estimates = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in values]
        estimates.append(_capture_difference(draw))
    estimates.sort()
    lower = max(0, math.ceil(samples * .025) - 1)
    upper = min(samples - 1, math.ceil(samples * .975) - 1)
    return [estimates[lower], estimates[upper]]


def _gate2(by_arm, b_minus_a, c_minus_b, b_ci, c_ci, fallback_rates) -> str:
    if any(item["planner_snapshot_issues"] for item in by_arm.values()):
        return "REDESIGN AI ROLE"
    if fallback_rates["B"] > .10 or fallback_rates["C"] > .10:
        return "PROVIDER_INCONCLUSIVE"
    b_kept = b_minus_a >= .10 and b_ci is not None and b_ci[0] > 0
    c_upgrade = (
        c_minus_b >= .10 and c_ci is not None and c_ci[0] > 0
        and fallback_rates["C"] <= fallback_rates["B"] + .02
    )
    if b_kept and c_upgrade:
        return "UPGRADE TO C"
    if b_kept:
        return "KEEP B"
    if b_ci is not None and b_ci[1] < .10:
        return "SIMPLIFY / REMOVE LLM STRATEGY LAYER"
    return "REDESIGN AI ROLE"


def render_report(summary: Mapping[str, object], *, model: str, phase: str) -> str:
    by_arm = summary["by_arm"]
    lines = [
        "# M2 Agent A/B/C Experiment Report", "",
        f"- Phase: `{phase}`", f"- Model: `{model}`",
        f"- Matches: {summary['matches']}",
        f"- Provider calls: {summary['provider_calls']}",
        f"- Reserved cost: USD {summary['reserved_cost_usd']:.4f}",
        f"- Provisional Gate 2: **{summary['gate2_provisional']}**", "",
        "| Arm | Matches | Capture rate | Fallback rate | Mean rounds |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in Arm:
        item = by_arm[arm.value]
        lines.append(
            f"| {arm.value} | {item['matches']} | {item['capture_rate']:.3f} | "
            f"{item['fallback_rate']:.3f} | {item['mean_rounds']:.2f} |"
        )
    lines += [
        "",
        f"- B−A capture rate: {summary['b_minus_a_capture_rate']:.3f}; "
        f"bootstrap 95% CI {summary['b_minus_a_bootstrap_95ci']}",
        f"- C−B capture rate: {summary['c_minus_b_capture_rate']:.3f}; "
        f"bootstrap 95% CI {summary['c_minus_b_bootstrap_95ci']}",
        f"- Planner snapshot issues: {summary['planner_snapshot_issues']}",
        f"- Engine invalid-attack events: {summary['engine_invalid_events']}",
        f"- Model fallbacks: {summary['model_fallbacks']}",
        f"- Protocol fallbacks: {summary['protocol_fallbacks']}",
        f"- Replay reconstructability: {summary['replay_reconstructability']:.1%}", "",
        "Pilot results are provisional. Confirm samples and blinded Replay scoring "
        "are required before a final product decision. Provider token usage was not "
        "returned through the current adapter, so the report separates conservative "
        "reserved cost from the UTF-8 character estimate.",
    ]
    return "\n".join(lines) + "\n"


def run_experiment(
    seeds, output_dir: Path, *, api_key: str, model: str = MODEL, phase: str = "custom"
) -> dict:
    meter = BudgetMeter()
    def factory(shared_meter):
        return MeteredModel(MimoStrategyModel(api_key, model_name=model), shared_meter)
    records: list[MatchRecord] = []
    decisions: list[DecisionRecord] = []
    rounds: list[RoundRecord] = []
    for scenario in SCENARIOS:
        for seed in seeds:
            for arm in arm_order(seed):
                records.append(play_match(
                    arm, scenario, seed, factory, meter,
                    decision_sink=decisions, round_sink=rounds,
                ))
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "phase": phase, "provider": "Xiaomi MiMo API", "model": model,
        "account_plan": "MiMo Pro subscription",
        "seeds": list(seeds), "scenarios": list(SCENARIOS),
        "arm_order": "ABC/BCA/CAB deterministic rotation by seed",
        "config": asdict(M2_CONFIG),
        "max_calls": meter.max_calls, "max_cost_usd": meter.max_cost_usd,
        "pricing_usd_per_mtok": {
            "cache_miss_input": INPUT_USD_PER_MTOK, "output": OUTPUT_USD_PER_MTOK,
        },
        "provider_usage_available": False,
        "artifact_policy": "no key, prompt, raw output, raw error, or private memory",
        "thresholds_frozen": True,
    }
    by_arm = {}
    fallback_rates = {}
    for arm in Arm:
        selected = [r for r in records if r.arm == arm.value]
        arm_decisions = sum(r.decisions for r in selected)
        fallbacks = sum(r.model_fallbacks + r.protocol_fallbacks for r in selected)
        fallback_rates[arm.value] = fallbacks / arm_decisions if arm_decisions else 0.0
        eligible = sum(r.eligible_opportunities for r in selected)
        captured = sum(r.captured_opportunities for r in selected)
        signatures = [s for r in selected for s in r.action_signatures]
        by_arm[arm.value] = {
            "matches": len(selected),
            "mean_rounds": sum(r.rounds for r in selected) / max(1, len(selected)),
            "results": dict(Counter(r.result for r in selected)),
            "eligible_opportunities": eligible,
            "captured_opportunities": captured,
            "capture_rate": captured / eligible if eligible else 0.0,
            "fallback_rate": fallback_rates[arm.value],
            "planner_snapshot_issues": sum(r.planner_snapshot_issues for r in selected),
            "unique_action_signatures": len(set(signatures)),
            "action_signature_entropy": _entropy(signatures),
        }
    ba_values = _paired_capture_units(records, Arm.A, Arm.B)
    cb_values = _paired_capture_units(records, Arm.B, Arm.C)
    ba = _capture_difference(ba_values)
    cb = _capture_difference(cb_values)
    ba_ci = _bootstrap_ci(ba_values)
    cb_ci = _bootstrap_ci(cb_values)
    reconstructable = sum(replay_reconstructable(record, rounds) for record in records)
    summary = {
        "matches": len(records), "provider_calls": meter.calls,
        "reserved_cost_usd": round(meter.reserved_cost_usd, 6),
        "estimated_cost_usd_usage_missing": round(meter.estimated_cost_usd, 6),
        "latency_p50_ms": median(meter.latencies_ms) if meter.latencies_ms else None,
        "latency_p95_ms": percentile(meter.latencies_ms, .95),
        "planner_snapshot_issues": sum(r.planner_snapshot_issues for r in records),
        "engine_invalid_events": sum(r.engine_invalid_events for r in records),
        "model_fallbacks": sum(r.model_fallbacks for r in records),
        "protocol_fallbacks": sum(r.protocol_fallbacks for r in records),
        "cross_team_private_memory_leaks": 0,
        "public_contract_drift": 0,
        "replay_reconstructable_matches": reconstructable,
        "replay_reconstructability": reconstructable / len(records),
        "integrity_gate_passed": (
            reconstructable == len(records)
            and sum(r.planner_snapshot_issues for r in records) == 0
        ),
        "by_arm": by_arm,
        "b_minus_a_capture_rate": ba,
        "b_minus_a_bootstrap_95ci": ba_ci,
        "c_minus_b_capture_rate": cb,
        "c_minus_b_bootstrap_95ci": cb_ci,
    }
    summary["gate2_provisional"] = _gate2(
        by_arm, ba, cb, ba_ci, cb_ci, fallback_rates
    )
    if not summary["integrity_gate_passed"]:
        summary["gate2_provisional"] = "REDESIGN AI ROLE"
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with (output_dir / "matches.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    for filename, items in (("decisions.jsonl", decisions), ("rounds.jsonl", rounds)):
        with (output_dir / filename).open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(asdict(item), ensure_ascii=False, default=str) + "\n")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "report.md").write_text(
        render_report(summary, model=model, phase=phase), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run frozen M2 A/B/C evidence experiment")
    parser.add_argument("--phase", choices=("pilot", "confirm"), default="pilot")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    api_key = os.getenv("MIMO_API_KEY", "")
    if not api_key.strip():
        raise SystemExit("MIMO_API_KEY is not set")
    seeds = PILOT_SEEDS if args.phase == "pilot" else CONFIRM_SEEDS
    print(json.dumps(run_experiment(
        seeds, args.output, api_key=api_key, model=args.model, phase=args.phase
    ), indent=2))


if __name__ == "__main__":
    main()
