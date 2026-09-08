# Handoff — Natural-Language Semantic Faithfulness Gate

## Why this exists

The first unseen holdout V0.1 failed. Most importantly, MiMo converted:

```text
A OR B
```

into a legal candidate containing only:

```text
A
```

`RuleValidator` could not detect this because the produced AST itself was legal.

## This branch adds

```text
src/rules_beyond/rule_faithfulness.py
src/rules_beyond/verified_natural_language_rule_adapter.py
src/rules_beyond/verified_natural_language_benchmark.py
tests/test_rule_faithfulness.py
tests/test_verified_natural_language_benchmark.py
```

and adds `pipeline = translator | verified` to the manual live benchmark workflow.

## New trust chain

```text
Natural Language
-> translator LLM
-> deterministic RuleValidator
-> semantic faithfulness verifier
-> Controller
```

Only the final verified adapter may expose an executable candidate/rule.

## Critical constraints

The faithfulness verifier:

- must NOT repair a candidate;
- must NOT generate a replacement candidate;
- must NOT call Engine or mutate GameState;
- must reject on uncertainty;
- must reject dropped OR/NOT/additional conditions/effects/duration/faction/numeric/weapon semantics;
- is a second safety gate, not a replacement for `RuleValidator`.

## What was NOT changed

This branch does not change:

```text
Rule DSL
RuleValidator bounds
Engine
DynamicRuleController
anti-stall
existing translator prompt
MiMo Provider protocol
```

## Evaluation status

Known live holdout V0.1 result is permanently recorded as FAIL:

```text
false_accepts = 1
legal_semantic_correct = 17/20
no_candidate_decision_correct = 16/20
```

V0.1 is now a regression corpus only. Do not claim it is unseen again.

## Next steps after CI

1. Merge this branch only if offline CI passes.
2. Manually run:

```text
provider = mimo
model = mimo-v2.5-pro
suite = holdout
pipeline = verified
```

This run is a **known-failure regression**, not a new holdout.
3. Confirm the prior OR false accept is blocked and inspect any new verifier false rejects.
4. Only after the regression behavior is understood, create a fresh holdout V0.2 with acceptance thresholds frozen before its first live run.
5. End-to-end natural-language gameplay remains blocked until V0.2 passes.
6. Formal MVP development has NOT started.

## Parallel-development warning

Other AI/developers should not simultaneously redesign:

```text
natural_language_rule_adapter.py
rule_faithfulness.py
verified_natural_language_rule_adapter.py
verified_natural_language_benchmark.py
live-natural-language-benchmark.yml
```

without coordinating through a separate PR, because these files define the natural-language trust boundary.
