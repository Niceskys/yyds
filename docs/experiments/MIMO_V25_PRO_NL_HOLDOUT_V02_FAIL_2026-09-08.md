# MiMo V2.5 Pro Natural-Language Verified Holdout V0.2 — FAIL

> Date: 2026-09-08  
> Provider: MiMo China Token Plan  
> Model: `mimo-v2.5-pro`  
> Workflow run: `34178489427`  
> Head: `943d0a7ed92283bc4e2bbb086a24a76fb58dffbd`

## Frozen gate

Before the first live V0.2 run, the gate was frozen as:

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 23/25
```

## Actual result

```text
total                    50
legal_total              25
legal_semantic_correct   24
legal_blocked             1
no_candidate_total       25
no_candidate_blocked     24
false_accepts             1
wrong_legal_candidates    0
semantic_rejections       3
verifier_errors           0
```

Result: **FAIL**, because `false_accepts` must be zero.

## Critical failure

Case `v02_reject_03`:

```text
生命值不超过2或者上一回合没移动时，弓射程增加1格。
```

V0.1 supports at most two conditions combined with AND only. The player used OR, so the intent must be rejected.

The translator produced both conditions in the RuleAST condition list:

```text
SELF_HP_LTE(2)
DID_NOT_MOVE_LAST_ROUND
```

but that list means AND. The faithfulness verifier returned `FAITHFUL`, so the system incorrectly accepted an OR -> AND semantic rewrite.

This is different from the earlier V0.1 failure where one branch of OR was dropped. V0.2 shows that merely checking whether every condition appears is insufficient; the logical connective itself is part of the player's meaning.

## Legal false reject

Case `v02_legal_13` was safely blocked by the verifier:

```text
上一轮使用了弓的单位，本轮弓需要冷却1回合。
```

The translator candidate was validator-legal, but the verifier returned `DROPPED_INTENT`. This reduced legal usability to 24/25, which still met the frozen usability threshold. It is not the reason V0.2 failed.

## Decision

The fix must not relax RuleValidator or lower the gate. Instead, because V0.1 is structurally AND-only, explicit boolean disjunction should be rejected deterministically before relying on an LLM faithfulness verdict.

V0.2 is now exposed and may only be used as a regression set. A future generalization claim requires a new unseen holdout after the fix is validated.
