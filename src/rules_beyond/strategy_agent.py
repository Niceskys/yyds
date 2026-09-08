from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Mapping, Protocol

from .model import Action, Direction, GameState, Position, Team, Weapon
from .rule_dsl import RuleAST
from .rule_engine import RuleAwareGameEngine, RuleEffectiveStats
from .rule_runtime import PublicRuleHistory


MAX_STRATEGY_OUTPUT_CHARS = 4096
MAX_PRIVATE_MEMORY_ENTRIES = 6


class StrategyIntent(str, Enum):
    PRESSURE = "PRESSURE"
    KITE = "KITE"
    EVADE = "EVADE"
    HOLD = "HOLD"


class StrategyDecisionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    FALLBACK_MODEL_ERROR = "FALLBACK_MODEL_ERROR"
    FALLBACK_PROTOCOL_ERROR = "FALLBACK_PROTOCOL_ERROR"


class StrategyModel(Protocol):
    """Narrow provider boundary for one high-level strategic decision."""

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str: ...


STRATEGY_SYSTEM_PROMPT = """You are one competitive combat agent in Rules Beyond V0.1.
Your only objective is to win the match for your own team under the current public rules.
You do not know why the human player changes public rules. Do not infer or optimize for the human player's objective.

You are NOT allowed to choose coordinates, movement paths, attacks, damage, HP, RNG, winners, or GameState mutations.
A deterministic planner will choose the concrete legal action.

Choose exactly one high-level intent:
- PRESSURE: close distance and seek reliable damage quickly.
- KITE: prefer attacking from bow range while maintaining separation.
- EVADE: maximize separation and survival, attacking only when compatible.
- HOLD: minimize movement and exploit attacks available from the current position.

Use only the public observation plus YOUR private strategy memory included in the observation.
Never assume access to the opponent's private strategy memory or hidden reasoning.
Do not output chain-of-thought or rationale.

Return exactly one JSON object and nothing else:
{\"intent\":\"PRESSURE|KITE|EVADE|HOLD\"}
"""


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    status: StrategyDecisionStatus
    intent: StrategyIntent
    raw_model_output: str | None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyMemoryEntry:
    round_no: int
    active_rule_signature: str
    intent: StrategyIntent


@dataclass(frozen=True, slots=True)
class StrategyObservation:
    team: Team
    round_no: int
    own_hp: int
    opponent_hp: int
    own_position: tuple[int, int]
    opponent_position: tuple[int, int]
    distance: int
    no_damage_streak: int
    hard_liveness_active: bool
    active_rule: Mapping[str, object] | None
    own_effective_stats: Mapping[str, object]
    own_public_history: Mapping[str, object]
    opponent_public_history: Mapping[str, object]
    private_memory: tuple[Mapping[str, object], ...]


_MOVE_ORDER: tuple[Direction, ...] = (
    Direction.UP,
    Direction.DOWN,
    Direction.LEFT,
    Direction.RIGHT,
)


def rule_to_public_mapping(rule: RuleAST | None) -> dict[str, object] | None:
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


def _rule_signature(rule: RuleAST | None) -> str:
    mapping = rule_to_public_mapping(rule)
    if mapping is None:
        return "NONE"
    return json.dumps(mapping, sort_keys=True, separators=(",", ":"))


def _history_mapping(history: PublicRuleHistory) -> dict[str, object]:
    return {
        "has_previous_round": history.has_previous_round,
        "moved_last_round": history.moved_last_round,
        "last_attack_weapon": history.last_attack_weapon.value,
        "consecutive_bow_miss": history.consecutive_bow_miss,
        "consecutive_same_weapon_use": history.consecutive_same_weapon_use,
    }


def _stats_mapping(stats: RuleEffectiveStats) -> dict[str, object]:
    return {
        "move_range": stats.move_range,
        "knife_range": stats.knife_range,
        "bow_range": stats.bow_range,
        "knife_damage": stats.knife_damage,
        "bow_damage": stats.bow_damage,
        "bow_hit_multiplier": stats.bow_hit_multiplier,
        "bow_hit_floor": stats.bow_hit_floor,
        "cooldown_weapons": sorted(weapon.value for weapon in stats.cooldown_weapons),
        "conflict_level": stats.conflict_level,
        "hard_liveness": stats.hard_liveness,
    }


class IsolatedStrategyAgent:
    """Per-team LLM strategy session with private memory and fail-safe fallback.

    RED and BLUE must be represented by different instances. Each instance owns
    only its own private strategy memory. Opponent position/HP/history are public;
    opponent private strategy memory is never present in this observation.
    """

    def __init__(
        self,
        team: Team,
        model: StrategyModel,
        *,
        fallback_intent: StrategyIntent = StrategyIntent.PRESSURE,
        max_output_chars: int = MAX_STRATEGY_OUTPUT_CHARS,
    ) -> None:
        if max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self.team = team
        self.model = model
        self.fallback_intent = fallback_intent
        self.max_output_chars = max_output_chars
        self._private_memory: list[StrategyMemoryEntry] = []

    @property
    def private_memory(self) -> tuple[StrategyMemoryEntry, ...]:
        return tuple(self._private_memory)

    def decide(
        self,
        state: GameState,
        engine: RuleAwareGameEngine,
        *,
        rule: RuleAST | None,
        histories: Mapping[Team, PublicRuleHistory],
    ) -> StrategyDecision:
        observation = self._build_observation(state, engine, rule=rule, histories=histories)
        serialized = json.dumps(
            {
                "team": observation.team.value,
                "round_no": observation.round_no,
                "own_hp": observation.own_hp,
                "opponent_hp": observation.opponent_hp,
                "own_position": observation.own_position,
                "opponent_position": observation.opponent_position,
                "distance": observation.distance,
                "no_damage_streak": observation.no_damage_streak,
                "hard_liveness_active": observation.hard_liveness_active,
                "active_rule": observation.active_rule,
                "own_effective_stats": observation.own_effective_stats,
                "own_public_history": observation.own_public_history,
                "opponent_public_history": observation.opponent_public_history,
                "private_memory": observation.private_memory,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        try:
            raw = self.model.generate_strategy(
                system_prompt=STRATEGY_SYSTEM_PROMPT,
                observation=serialized,
            )
        except Exception as exc:
            return self._fallback(
                state.round_no,
                rule,
                StrategyDecisionStatus.FALLBACK_MODEL_ERROR,
                f"strategy model failed: {type(exc).__name__}",
            )

        if not isinstance(raw, str) or len(raw) > self.max_output_chars:
            return self._fallback(
                state.round_no,
                rule,
                StrategyDecisionStatus.FALLBACK_PROTOCOL_ERROR,
                "strategy model returned invalid output type or size",
            )

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return self._fallback(
                state.round_no,
                rule,
                StrategyDecisionStatus.FALLBACK_PROTOCOL_ERROR,
                "strategy output must be one JSON object",
            )

        if not isinstance(decoded, dict) or set(decoded) != {"intent"}:
            return self._fallback(
                state.round_no,
                rule,
                StrategyDecisionStatus.FALLBACK_PROTOCOL_ERROR,
                "strategy output must contain only intent",
            )

        try:
            intent = StrategyIntent(decoded.get("intent"))
        except (TypeError, ValueError):
            return self._fallback(
                state.round_no,
                rule,
                StrategyDecisionStatus.FALLBACK_PROTOCOL_ERROR,
                "strategy intent is not in the closed intent set",
            )

        self._remember(state.round_no, rule, intent)
        return StrategyDecision(
            status=StrategyDecisionStatus.ACCEPTED,
            intent=intent,
            raw_model_output=raw,
            error_message=None,
        )

    def _fallback(
        self,
        round_no: int,
        rule: RuleAST | None,
        status: StrategyDecisionStatus,
        message: str,
    ) -> StrategyDecision:
        self._remember(round_no, rule, self.fallback_intent)
        return StrategyDecision(
            status=status,
            intent=self.fallback_intent,
            raw_model_output=None,
            error_message=message,
        )

    def _remember(self, round_no: int, rule: RuleAST | None, intent: StrategyIntent) -> None:
        self._private_memory.append(
            StrategyMemoryEntry(
                round_no=round_no,
                active_rule_signature=_rule_signature(rule),
                intent=intent,
            )
        )
        if len(self._private_memory) > MAX_PRIVATE_MEMORY_ENTRIES:
            del self._private_memory[:-MAX_PRIVATE_MEMORY_ENTRIES]

    def _build_observation(
        self,
        state: GameState,
        engine: RuleAwareGameEngine,
        *,
        rule: RuleAST | None,
        histories: Mapping[Team, PublicRuleHistory],
    ) -> StrategyObservation:
        own = state.unit(self.team)
        opponent = state.unit(self.team.opponent)
        stats = engine.effective_stats_for_team(
            state,
            self.team,
            rule=rule,
            histories=histories,
        )
        own_history = histories.get(self.team, PublicRuleHistory())
        opponent_history = histories.get(self.team.opponent, PublicRuleHistory())
        memory = tuple(
            {
                "round_no": entry.round_no,
                "active_rule_signature": entry.active_rule_signature,
                "intent": entry.intent.value,
            }
            for entry in self._private_memory
        )
        return StrategyObservation(
            team=self.team,
            round_no=state.round_no,
            own_hp=own.hp,
            opponent_hp=opponent.hp,
            own_position=(own.position.row, own.position.col),
            opponent_position=(opponent.position.row, opponent.position.col),
            distance=own.position.manhattan_distance(opponent.position),
            no_damage_streak=state.no_damage_streak,
            hard_liveness_active=state.hard_liveness_active,
            active_rule=rule_to_public_mapping(rule),
            own_effective_stats=_stats_mapping(stats),
            own_public_history=_history_mapping(own_history),
            opponent_public_history=_history_mapping(opponent_history),
            private_memory=memory,
        )


@dataclass(frozen=True, slots=True)
class _ActionCandidate:
    action: Action
    destination: Position


class DeterministicIntentPlanner:
    """Closed-semantics planner mapping one intent to one concrete legal action."""

    def choose_action(
        self,
        state: GameState,
        team: Team,
        engine: RuleAwareGameEngine,
        *,
        rule: RuleAST | None,
        histories: Mapping[Team, PublicRuleHistory],
        intent: StrategyIntent,
    ) -> Action:
        stats = engine.effective_stats_for_team(
            state,
            team,
            rule=rule,
            histories=histories,
        )
        opponent = state.unit(team.opponent).position
        candidates = self._candidate_actions(state, team, engine, stats)
        selected = min(
            candidates,
            key=lambda item: self._score(item, opponent, stats, intent),
        )
        return selected.action

    def _candidate_actions(
        self,
        state: GameState,
        team: Team,
        engine: RuleAwareGameEngine,
        stats: RuleEffectiveStats,
    ) -> tuple[_ActionCandidate, ...]:
        paths = self._candidate_paths(state.unit(team).position, engine, stats.move_range)
        opponent = state.unit(team.opponent).position
        candidates: list[_ActionCandidate] = []
        for path, destination in paths:
            distance = destination.manhattan_distance(opponent)
            if Weapon.KNIFE not in stats.cooldown_weapons and distance <= stats.knife_range:
                candidates.append(_ActionCandidate(Action(path, Weapon.KNIFE), destination))
            if Weapon.BOW not in stats.cooldown_weapons and distance <= stats.bow_range:
                candidates.append(_ActionCandidate(Action(path, Weapon.BOW), destination))
            candidates.append(_ActionCandidate(Action(path, None), destination))
        return tuple(candidates)

    @staticmethod
    def _candidate_paths(
        start: Position,
        engine: RuleAwareGameEngine,
        move_range: int,
    ) -> tuple[tuple[tuple[Direction, ...], Position], ...]:
        best: dict[Position, tuple[Direction, ...]] = {start: ()}
        frontier: list[tuple[tuple[Direction, ...], Position]] = [((), start)]
        for _ in range(move_range):
            next_frontier: list[tuple[tuple[Direction, ...], Position]] = []
            for path, position in frontier:
                for direction in _MOVE_ORDER:
                    destination = position.moved(direction)
                    if not engine.config.contains(destination):
                        continue
                    new_path = path + (direction,)
                    previous = best.get(destination)
                    if previous is None or len(new_path) < len(previous):
                        best[destination] = new_path
                        next_frontier.append((new_path, destination))
            frontier = next_frontier
        return tuple((path, destination) for destination, path in best.items())

    @staticmethod
    def _bow_probability(distance: int, stats: RuleEffectiveStats) -> float:
        if stats.hard_liveness:
            return 1.0
        base = 0.5 ** max(distance - 1, 0)
        return min(1.0, max(stats.bow_hit_floor, base * stats.bow_hit_multiplier))

    @classmethod
    def _expected_damage(
        cls,
        weapon: Weapon | None,
        distance: int,
        stats: RuleEffectiveStats,
    ) -> float:
        if weapon is Weapon.KNIFE:
            return float(stats.knife_damage)
        if weapon is Weapon.BOW:
            return float(stats.bow_damage) * cls._bow_probability(distance, stats)
        return 0.0

    @classmethod
    def _score(
        cls,
        candidate: _ActionCandidate,
        opponent: Position,
        stats: RuleEffectiveStats,
        intent: StrategyIntent,
    ) -> tuple[object, ...]:
        action = candidate.action
        distance = candidate.destination.manhattan_distance(opponent)
        expected_damage = cls._expected_damage(action.attack, distance, stats)
        path_key = tuple(step.value for step in action.move_path)
        attack_key = action.attack.value if action.attack is not None else "ZZZ"

        if intent is StrategyIntent.PRESSURE:
            return (
                0 if action.attack is not None else 1,
                -expected_damage,
                distance,
                len(action.move_path),
                attack_key,
                path_key,
            )

        if intent is StrategyIntent.KITE:
            preferred = min(3, stats.bow_range)
            bow_rank = 0 if action.attack is Weapon.BOW else (1 if action.attack is not None else 2)
            return (
                bow_rank,
                abs(distance - preferred),
                -distance,
                len(action.move_path),
                attack_key,
                path_key,
            )

        if intent is StrategyIntent.EVADE:
            return (
                -distance,
                0 if action.attack is not None else 1,
                -expected_damage,
                len(action.move_path),
                attack_key,
                path_key,
            )

        # HOLD
        return (
            0 if not action.move_path else 1,
            0 if action.attack is not None else 1,
            -expected_damage,
            distance,
            attack_key,
            path_key,
        )
