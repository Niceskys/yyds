# MiMo V2.5 Pro Natural-Language Holdout V0.1 — FAIL

> Date: 2026-09-08  
> Provider: MiMo China Token Plan  
> Model: `mimo-v2.5-pro`  
> Workflow run: `34174980570`  
> Head: `0a5bd66c17549ecffd5729ff7de11c728fe49fba`  
> Corpus: `evals/natural_language_rule_holdout_v0.1.json`

## Frozen gate

The pass/fail thresholds were frozen before this live run:

```text
false_accepts = 0
wrong_legal_candidates = 0
legal_semantic_correct >= 18/20
no_candidate_decision_correct >= 19/20
```

## Actual result

```text
total                         40
exact_correct                 27/40 = 67.5%
decision_correct              33/40 = 82.5%
legal_semantic_correct        17/20 = 85%
no_candidate_decision_correct 16/20 = 80%
no_candidate_reason_correct   10/20
false_accepts                  1
false_rejects                  3
wrong_legal_candidates         0
```

Verdict:

```text
FAIL
```

The frozen gate is not relaxed after seeing this result.

## Most important failure: silent semantic loss

Input:

```text
生命值不高于2或者距离至少4格时，弓射程增加1格。
```

Expected:

```text
NO_CANDIDATE
```

because V0.1 does not support OR.

Actual accepted candidate:

```json
{
  "version": "v0.1",
  "target": "ALL_UNITS",
  "conditions": [
    {"type": "SELF_HP_LTE", "value": 2}
  ],
  "effect": {"type": "BOW_RANGE_ADD", "delta": 1},
  "duration": "UNTIL_REPLACED"
}
```

The model silently dropped the `距离至少4格` branch and converted `A OR B` into `A`.

This candidate is syntactically and numerically legal, so `RuleValidator` correctly accepts it. Therefore this failure demonstrates a real architectural gap:

> Deterministic validation can prove that the produced AST is legal, but it cannot prove that the AST faithfully preserves the player's full original intent.

This is a zero-tolerance semantic safety failure under the frozen holdout gate.

## Safe failures caught by RuleValidator

Three unsupported/out-of-bounds inputs were converted into candidates, but deterministic validation rejected them:

- three conditions -> `CONDITION_COUNT`;
- bow range +2 -> `NUMERIC_BOUNDS`;
- HP >= 10 condition -> `NUMERIC_BOUNDS`.

These are model-decision failures for the holdout benchmark, but they did not become executable rules. They reinforce the value of the deterministic Validator.

## Legal rules over-rejected by the model

Three legal inputs were rejected by MiMo:

- bow range -1;
- last-round BOW -> one-round BOW cooldown;
- distance <= 1 -> knife damage -1.

This reduced legal semantic correctness to `17/20`.

## Conclusion

The original pipeline:

```text
Natural Language
-> LLM candidate
-> RuleValidator
-> Controller
```

is not sufficient, because the Validator sees only the candidate and cannot detect semantic information the LLM silently removed.

The next architecture experiment adds a fail-closed semantic faithfulness gate after deterministic validation:

```text
Natural Language
-> Translator LLM
-> RuleValidator
-> Faithfulness Verifier
-> Controller
```

The verifier must not repair or rewrite candidates. Any uncertainty or semantic mismatch rejects the rule.

Holdout V0.1 is now a known-result regression corpus. It must not be reused as an unseen holdout after architecture changes. A new V0.2 holdout is required for the next generalization claim.
