# MiMo V2.5 Pro Natural-Language Dynamic Match Gate V0.2 — FAIL

Date: 2026-09-08

## Verdict

**FAIL. Do not reclassify this run as PASS.**

This failure is a **safe usability false reject**, not an unsafe rule acceptance and not an Engine / DynamicRuleController failure.

## Run identity

```text
workflow: live-natural-language-dynamic-match-v02
run id: 34185343863
head: 62a1ec52899ab16e47fcf957ab9a246b0452c658
model: mimo-v2.5-pro
```

V0.2 intentionally memoized identical semantic requests across the three combat seeds. A player text was evaluated once by the provider path, and that frozen semantic result was reused for deterministic combat variation.

Observed model accounting:

```text
semantic_model_calls = 5
semantic_cache_hits = 10
```

## Match outcomes

```text
seed 1260000 -> RED_WIN, 18 rounds
seed 1260001 -> BLUE_WIN, 19 rounds
seed 1260002 -> DRAW_MUTUAL_DEATH, 20 rounds
TIMEOUT = 0
```

All three matches completed and all three reused the same semantic decisions.

## Phase results

### Phase 0 — legal

```text
双方弓的最大射程增加1格。
```

Result:

```text
translator = ACCEPTED
faithfulness = FAITHFUL
controller = replaced
```

The rule reached the deterministic Planner/Engine path and changed round-1 behavior relative to the no-rule baseline.

### Phase 1 — legal, but false rejected

```text
双方移动距离增加1格。
```

Expected:

```text
CANDIDATE -> MOVE_RANGE_ADD(+1)
```

Observed frozen result:

```text
verified status = BASE_REJECTED
base status = NO_CANDIDATE
controller replaced = false
```

The active previous legal rule was safely carried forward.

This is the reason V0.2 fails its original live Gate.

### Phase 2 — unsupported OR

```text
生命值不超过2或者上一回合没移动时，弓射程增加1格。
```

Result in every combat seed:

```text
INTENT_GUARD_REJECTED
controller replaced = false
previous legal rule carried forward
```

This is the expected fail-closed behavior.

### Phase 3 — legal recovery after rejection

```text
双方相距至少3格时，弓箭命中率按原来的一半计算。
```

Result:

```text
translator = ACCEPTED
faithfulness = FAITHFUL
controller = replaced
```

Therefore the dynamic path successfully recovered from a rejected rule phase and later accepted a new legal rule.

## Interpretation

Evidence supported by this run:

- one real natural-language semantic decision can be frozen and reused across combat seeds;
- legal natural-language rules can reach `DynamicRuleController` and affect combat behavior;
- explicit unsupported OR is rejected before unsafe compilation;
- rejected submissions preserve the previous legal rule;
- a later legal replacement still succeeds;
- three different deterministic combat seeds all terminate without TIMEOUT.

Evidence **not** supported:

- every simple legal player rule is accepted on the first MiMo call;
- the V0.2 live Gate as originally frozen passed.

## Project decision

Do not repeatedly rerun this fixed Gate until random model variation happens to produce green. That would select a favorable sample rather than evaluate the observed failure.

The remaining failure is a user-facing false-reject problem: a legal request may occasionally be conservatively rejected. Because rejected text does not create an unsafe RuleAST and does not mutate GameState, this issue remains on the product reliability track (feedback, rephrase UX, carefully designed retry policy, or provider/model comparison).

It is **not** treated as a blocker to the separate Agent/Planner architecture Gate.

The Agent/Planner Gate must be decoupled from natural-language translation and use fixed validated public rules so it measures the new question directly: whether two isolated high-level Agents can safely drive deterministic concrete actions through the Engine.
