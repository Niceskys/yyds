# Agent / Planner Integration Gate V0.1

Date frozen: 2026-09-08

## Purpose

This Gate answers one narrow architectural question:

> Can two isolated AI strategy sessions independently choose high-level winning intents, while a deterministic Planner converts those intents into concrete actions and the deterministic Engine remains the only authority over movement, attacks, damage, RNG and terminal state?

It does **not** re-test natural-language rule translation. That subsystem already has separate static and dynamic evidence, including a recorded safe false reject in Dynamic Match Gate V0.2.

Passing this Gate is the final planned core-validation prerequisite before declaring formal MVP development.

## Authority boundary

```text
RED private Agent session              BLUE private Agent session
        |                                      |
        | closed StrategyIntent                | closed StrategyIntent
        v                                      v
                 DeterministicIntentPlanner
                            |
                     concrete Action
                            |
                 DynamicRuleController
                            |
                     Game Engine
```

The model may choose only one of:

```text
PRESSURE
KITE
EVADE
HOLD
```

The model cannot directly choose or write:

- coordinates;
- movement paths;
- attack weapon execution;
- hit probability / RNG result;
- damage;
- HP;
- winner;
- GameState;
- active public rule.

Malformed output or provider failure falls back to deterministic `PRESSURE` and is explicitly recorded. The live Gate nevertheless requires real accepted strategy decisions from both sides, so a match cannot pass solely because fallback kept it running.

## Agent isolation

RED and BLUE are separate `IsolatedStrategyAgent` instances with separate provider/session objects and separate private memory lists.

Each observation contains:

- own team;
- own and opponent public HP/position;
- public current round and no-damage state;
- current public rule;
- effective public combat stats;
- own and opponent **public** combat history;
- only that Agent's private strategy-memory summary.

It does not contain the other Agent's private strategy memory or hidden reasoning.

The implementation intentionally does not request or persist chain-of-thought. Private memory stores only bounded high-level facts:

```text
round
active-rule signature
chosen StrategyIntent
```

## Deterministic Planner

The Planner:

1. reads the current public GameState and validated public RuleAST;
2. asks the same Engine-derived effective-stat query used by combat semantics;
3. enumerates board-bounded movement paths up to current move range;
4. derives knife/bow availability from range and cooldown;
5. scores candidates according to the closed StrategyIntent;
6. deterministically chooses one `Action`.

No LLM call occurs in this process.

### Submission-snapshot legality

Because movement is simultaneous, an attack that is reasonable when submitted may become invalid after the opponent moves or a joint movement conflict changes final positions.

Therefore the Planner hard Gate is **not** `Engine INVALID_ATTACK == 0`.

Before settlement, each submitted action is audited against what the Planner actually knows:

- move length <= effective move range;
- every planned step remains on board;
- selected weapon is not on cooldown;
- selected attack is in range against the opponent's current public position after the Planner's own intended path.

The hard criterion is:

```text
planner_snapshot_errors = 0
INVALID_MOVE_PATH = 0
```

Post-settlement `INVALID_ATTACK` remains logged but may result from simultaneous opponent movement/conflict and is not by itself a Planner defect.

## Frozen live configuration

Engineering Gate only:

```text
GameConfig(initial_hp=5, knife_damage=2)
match_seed = 1270000
RED provider = independent MiMo strategy provider
BLUE provider = independent MiMo strategy provider
model = mimo-v2.5-pro (default)
```

Product default remains HP4/K2.

## Frozen public-rule schedule

These are fixed, already-closed candidates; natural-language compilation is intentionally bypassed in this Gate.

```text
phase 0: ALWAYS -> BOW_RANGE_ADD(+1)
phase 1: ALWAYS -> MOVE_RANGE_ADD(+1)
phase 2: DISTANCE >= 3 -> BOW_HIT_MULTIPLIER(0.5)
```

The schedule is only there to prove the Agents receive and react after public-rule changes while the deterministic Controller/Engine continue to own rule application.

## PASS criteria

All conditions below must hold in the first evaluated live run unless the run is invalid due to infrastructure/provider outage before a meaningful strategy result is produced:

```text
match result != TIMEOUT
combat rounds > 0
planner_snapshot_errors = 0
INVALID_MOVE_PATH = 0
PLAYER_RULE_REPLACED >= 2

RED accepted strategy decisions >= 2
BLUE accepted strategy decisions >= 2
RED phase-0 decision = ACCEPTED
BLUE phase-0 decision = ACCEPTED
RED has >=1 ACCEPTED decision after a rule change
BLUE has >=1 ACCEPTED decision after a rule change
```

`INVALID_ATTACK` is recorded but not a hard failure for the simultaneous-settlement reason described above.

## What PASS would prove

- two independent Agent sessions can operate without shared private memory;
- LLM output is confined to a tiny high-level intent space;
- deterministic Planner, not the LLM, owns concrete action generation;
- Planner submissions satisfy their public snapshot constraints;
- public rules can change while both Agents continue to make new strategy decisions;
- Engine/Controller remain authoritative;
- a complete terminal match can run through this architecture.

## What PASS would not prove

It would **not** prove:

- final game balance;
- final Agent intelligence or fun;
- optimal strategy quality;
- UI/UX quality;
- production latency/cost;
- that natural-language false rejects are solved;
- competition-winning quality.

It would be sufficient evidence to end the current core architecture validation phase and begin formal MVP engineering in parallel workstreams.
