# Handoff — Natural-Language V0.2 Logical-Connective Safety Fix

> Date: 2026-09-08

## Why this exists

The first unseen V0.2 verified holdout failed its frozen gate with:

```text
legal_semantic_correct 24/25
false_accepts 1
wrong_legal_candidates 0
verifier_errors 0
```

The critical false accept was an explicit OR rule being represented as the V0.1 condition list, whose semantics are AND-only.

## What changed

`src/rules_beyond/verified_natural_language_rule_adapter.py` now performs a deterministic precheck for clear disjunction forms before calling the LLM faithfulness verifier.

Examples currently covered include:

```text
或者
或是
满足任一
任一条件
任意一个条件
任意一项
二者之一
English either ... or ...
```

Important: the guard intentionally does **not** reject every Chinese `或`, because phrases such as `1点或更少` are valid threshold language equivalent to `<= 1`.

If the precheck finds explicit disjunction:

```text
pipeline status = SEMANTIC_REJECTED
candidate/rule are hidden downstream
faithfulness LLM is not called
```

This is a system-level safety guard derived from the frozen DSL fact that V0.1 conditions are AND-only. It is not a special-case whitelist for one benchmark sentence.

## What did not change

```text
Rule DSL
RuleValidator
Engine
DynamicRuleController
anti-stall
translator prompt/guidance
MiMo provider protocol
V0.2 corpus
V0.2 frozen gate
```

The V0.2 legal false reject for a previous-bow + bow-cooldown rule was **not** tuned here because legal usability already met the frozen 23/25 threshold. Avoid overfitting exposed V0.2 cases.

## Evidence

The failed unseen run is preserved at:

```text
docs/experiments/MIMO_V25_PRO_NL_HOLDOUT_V02_FAIL_2026-09-08.md
```

Tests added/updated in `tests/test_rule_faithfulness.py` require:

1. explicit OR is blocked even if translator keeps both conditions;
2. semantic verifier is not called after deterministic OR rejection;
3. `1点或更少` is not misclassified as boolean OR.

## Concurrency boundary

Until this PR is merged, other developers/AIs should avoid modifying:

```text
src/rules_beyond/verified_natural_language_rule_adapter.py
tests/test_rule_faithfulness.py
```

Do not modify V0.2 corpus or its frozen gate after exposure.

## Next step

1. Offline CI passes.
2. Merge this fix.
3. Rerun exposed V0.2 only as a regression:

```text
provider=mimo
model=mimo-v2.5-pro
suite=holdout-v02
pipeline=verified
```

Expected regression requirement:

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 23/25
```

4. If regression passes, create a fresh unseen V0.3 corpus and freeze its gate before any live call.

Formal MVP development remains blocked.
