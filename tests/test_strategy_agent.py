import json

from rules_beyond.model import GameState, Position, Team, UnitState, Weapon, initial_state
from rules_beyond.rule_engine import RuleAwareGameEngine
from rules_beyond.rule_runtime import initial_public_rule_histories
from rules_beyond.rule_validator import RuleValidator
from rules_beyond.strategy_agent import (
    DeterministicIntentPlanner,
    IsolatedStrategyAgent,
    StrategyDecisionStatus,
    StrategyIntent,
)


def bow_range_plus_one_rule():
    validation = RuleValidator().validate(
        {
            "version": "v0.1",
            "target": "ALL_UNITS",
            "conditions": [],
            "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
            "duration": "UNTIL_REPLACED",
        }
    )
    assert validation.accepted and validation.rule is not None
    return validation.rule


class FixedStrategyModel:
    def __init__(self, intent: str) -> None:
        self.intent = intent

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        assert "human player" in system_prompt
        assert "private_memory" in observation
        return json.dumps({"intent": self.intent})


class TeamAwareSpyModel:
    def __init__(self) -> None:
        self.observations: list[dict[str, object]] = []

    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        del system_prompt
        decoded = json.loads(observation)
        self.observations.append(decoded)
        intent = "KITE" if decoded["team"] == "RED" else "EVADE"
        return json.dumps({"intent": intent})


class BrokenStrategyModel:
    def generate_strategy(self, *, system_prompt: str, observation: str) -> str:
        del system_prompt, observation
        return json.dumps({"intent": "SET_HP_TO_99"})


def test_agent_accepts_only_closed_high_level_intent() -> None:
    state = initial_state()
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()
    agent = IsolatedStrategyAgent(Team.RED, FixedStrategyModel("KITE"))

    decision = agent.decide(state, engine, rule=None, histories=histories)

    assert decision.status is StrategyDecisionStatus.ACCEPTED
    assert decision.intent is StrategyIntent.KITE
    assert len(agent.private_memory) == 1


def test_invalid_strategy_output_falls_back_without_game_mutation_authority() -> None:
    state = initial_state()
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()
    before = state
    agent = IsolatedStrategyAgent(Team.RED, BrokenStrategyModel())

    decision = agent.decide(state, engine, rule=None, histories=histories)

    assert decision.status is StrategyDecisionStatus.FALLBACK_PROTOCOL_ERROR
    assert decision.intent is StrategyIntent.PRESSURE
    assert state == before


def test_red_and_blue_private_memories_are_isolated() -> None:
    state = initial_state()
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()
    model = TeamAwareSpyModel()
    red = IsolatedStrategyAgent(Team.RED, model)
    blue = IsolatedStrategyAgent(Team.BLUE, model)

    red.decide(state, engine, rule=None, histories=histories)
    blue.decide(state, engine, rule=None, histories=histories)
    red.decide(state, engine, rule=None, histories=histories)
    blue.decide(state, engine, rule=None, histories=histories)

    red_second = model.observations[2]
    blue_second = model.observations[3]
    red_memory = red_second["private_memory"]
    blue_memory = blue_second["private_memory"]

    assert [entry["intent"] for entry in red_memory] == ["KITE"]
    assert [entry["intent"] for entry in blue_memory] == ["EVADE"]
    assert all(entry["intent"] != "EVADE" for entry in red_memory)
    assert all(entry["intent"] != "KITE" for entry in blue_memory)
    assert red.private_memory is not blue.private_memory


def test_deterministic_planner_maps_intents_to_different_legal_shapes() -> None:
    state = initial_state()
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()
    planner = DeterministicIntentPlanner()

    pressure = planner.choose_action(
        state,
        Team.RED,
        engine,
        rule=None,
        histories=histories,
        intent=StrategyIntent.PRESSURE,
    )
    hold = planner.choose_action(
        state,
        Team.RED,
        engine,
        rule=None,
        histories=histories,
        intent=StrategyIntent.HOLD,
    )
    evade = planner.choose_action(
        state,
        Team.RED,
        engine,
        rule=None,
        histories=histories,
        intent=StrategyIntent.EVADE,
    )

    assert len(pressure.move_path) == 1
    assert pressure.attack is Weapon.BOW
    assert hold.move_path == ()
    assert hold.attack is None
    assert len(evade.move_path) == 1
    assert evade.attack is None
    assert evade != pressure


def test_planner_reads_public_rule_effects_without_model_action_control() -> None:
    state = initial_state()
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()
    planner = DeterministicIntentPlanner()
    rule = bow_range_plus_one_rule()

    action = planner.choose_action(
        state,
        Team.RED,
        engine,
        rule=rule,
        histories=histories,
        intent=StrategyIntent.HOLD,
    )

    assert action.move_path == ()
    assert action.attack is Weapon.BOW


def test_pressure_planners_resolve_center_contest_without_invalid_attack_loop() -> None:
    state = GameState(
        round_no=1,
        units={
            Team.RED: UnitState(Team.RED, Position(3, 2), 4),
            Team.BLUE: UnitState(Team.BLUE, Position(3, 4), 4),
        },
    )
    engine = RuleAwareGameEngine()
    histories = initial_public_rule_histories()
    planner = DeterministicIntentPlanner()
    actions = {
        team: planner.choose_action(
            state,
            team,
            engine,
            rule=None,
            histories=histories,
            intent=StrategyIntent.PRESSURE,
        )
        for team in (Team.RED, Team.BLUE)
    }

    resolution = engine.resolve_rule_round(
        state,
        actions,
        rule=None,
        histories=histories,
        match_seed=1,
    )

    assert actions[Team.RED].attack is Weapon.KNIFE
    assert actions[Team.BLUE].attack is Weapon.KNIFE
    assert resolution.state.unit(Team.RED).position == Position(3, 3)
    assert resolution.state.unit(Team.BLUE).position == Position(3, 4)
    conflict = next(
        event for event in resolution.events if event.kind == "SAME_DESTINATION_CONFLICT"
    )
    assert conflict.details["winner"] == "RED"
    assert not any(event.kind == "INVALID_ATTACK" for event in resolution.events)
    assert {
        event.actor for event in resolution.events if event.kind == "ATTACK_RESOLVED"
    } == {Team.RED, Team.BLUE}
