# Handoff — Agent / Planner Integration Gate

Date: 2026-09-08
Branch / PR: `feat/agent-planner-integration-gate` / PR #30

## Context

The project remains in core validation. Do not start UI/product parallelization yet and do not announce formal MVP development until the live Agent/Planner Gate passes.

The preceding natural-language Dynamic Match Gate V0.2 is permanently recorded as FAIL because MiMo safely false-rejected one simple legal rule (`双方移动距离增加1格。`). That is a usability/reliability issue, not an unsafe accept or Engine authority failure. Do not rewrite that history to PASS and do not rerun until a favorable sample appears.

The Agent/Planner Gate is intentionally decoupled from natural-language translation so it measures a new concern independently.

## New architecture in this PR

```text
RED IsolatedStrategyAgent       BLUE IsolatedStrategyAgent
           |                              |
      StrategyIntent                 StrategyIntent
           \                              /
            DeterministicIntentPlanner
                        |
                      Action
                        |
              DynamicRuleController
                        |
                     Engine
```

Closed intents:

```text
PRESSURE
KITE
EVADE
HOLD
```

The strategy model cannot emit concrete moves, coordinates, attack execution, HP, damage, winner, RNG or GameState mutations.

## Files

```text
src/rules_beyond/strategy_agent.py
src/rules_beyond/mimo_strategy_provider.py
src/rules_beyond/planner_audit.py
src/rules_beyond/live_agent_planner_match.py

tests/test_strategy_agent.py
tests/test_mimo_strategy_provider.py
tests/test_planner_audit.py
tests/test_live_agent_planner_match.py

docs/experiments/MIMO_V25_PRO_NL_DYNAMIC_MATCH_V02_FAIL_2026-09-08.md
docs/experiments/AGENT_PLANNER_INTEGRATION_GATE_V0.1.md
```

A manual live workflow is also part of this PR.

## Isolation rule

RED and BLUE must use separate `IsolatedStrategyAgent` instances and separate provider/session objects.

Each Agent gets public opponent state/history, but its serialized `private_memory` contains only that Agent's own previous high-level intents and public-rule signatures.

Do not add opponent Agent memory to the observation. Do not persist or expose chain-of-thought.

## Planner authority

`DeterministicIntentPlanner` is the only component that turns `StrategyIntent` into a concrete `Action`.

The LLM must never be given an escape hatch to directly submit an `Action` or modify GameState.

## Important simultaneous-action nuance

Initial offline Gate design incorrectly required:

```text
INVALID_ATTACK = 0
```

CI correctly exposed that this is not a valid Planner criterion. Engine attack legality is evaluated **after** joint movement resolution. An opponent can move away, or movement can conflict, making a previously reasonable attack out of range.

The corrected hard criterion is pre-settlement public-snapshot legality:

```text
planner_snapshot_errors = 0
INVALID_MOVE_PATH = 0
```

`planner_audit.py` independently checks path/range/cooldown against the snapshot available to the Planner when it submits the action.

Post-settlement `INVALID_ATTACK` remains diagnostic only.

Do not revert this distinction without changing the underlying simultaneous-movement semantics.

## Frozen live Gate

Engineering config only:

```text
HP=5
knife_damage=2
seed=1270000
model=mimo-v2.5-pro
```

Fixed validated public rules:

```text
phase0 BOW_RANGE_ADD(+1)
phase1 MOVE_RANGE_ADD(+1)
phase2 DISTANCE_GTE(3) -> BOW_HIT_MULTIPLIER(0.5)
```

Natural-language translation is bypassed intentionally.

PASS requires:

```text
non-TIMEOUT terminal match
planner_snapshot_errors = 0
INVALID_MOVE_PATH = 0
PLAYER_RULE_REPLACED >= 2
RED accepted strategy decisions >= 2
BLUE accepted strategy decisions >= 2
both sides accepted at phase0
both sides accepted again after at least one rule replacement
```

## What happens after live PASS

This is the promised final core architecture Gate.

If the first meaningful live Agent/Planner run passes, explicitly tell the user:

> **正式 MVP 开发开始。**

Then move to two-person + AI parallel development. Intended initial ownership:

### Developer A — backend/core

- Python service boundary
- Engine / Controller integration APIs
- Agent / Planner productionization
- LLM provider configuration
- FastAPI / Pydantic contracts
- replay/event backend

### Developer B — frontend

- React + TypeScript + Vite
- 5×5 board visualization
- public-rule input and validation feedback
- rule-phase UX
- match playback / event visualization
- Agent strategy/status display without chain-of-thought

Avoid both developers editing the same hot core files concurrently. Use one task -> one branch -> tests -> PR -> independent review -> CI -> handoff -> merge.

## If live Gate fails

Classify before changing anything:

- provider/model call failure;
- strategy JSON protocol failure/fallback;
- insufficient accepted decisions;
- memory isolation issue;
- Planner snapshot legality failure;
- dynamic rule replacement issue;
- Engine/timeout/liveness issue.

Do not weaken the Gate merely to obtain green. Do not mix natural-language compiler fixes into the Agent/Planner branch unless the failure actually comes from that subsystem (the current live Agent Gate bypasses it).
