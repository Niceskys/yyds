# Semantic Connective Guard V0.1

> Status: active safety boundary candidate

## Purpose

The V0.1 Rule DSL permits zero to two conditions combined with logical AND only. It cannot represent OR semantics.

A validator can prove that a generated RuleAST is legal, but it cannot prove that a model preserved the player's original logical connective. Therefore the verified natural-language path requires an additional deterministic guard for explicit disjunction.

## Rule

If the player text contains a clear disjunction form that requires OR semantics, the verified pipeline must reject the rule before the LLM faithfulness verifier can approve it.

The guard is conservative and only matches explicit forms. It does not treat every occurrence of the Chinese character `或` as boolean OR, because comparison phrases such as `1点或更少` can faithfully map to `SELF_HP_LTE(1)`.

## Authority

This guard:

- cannot generate or repair RuleAST;
- cannot alter GameState;
- cannot bypass RuleValidator;
- can only fail closed by preventing a candidate from becoming executable.

## Rationale

The first unseen V0.2 holdout demonstrated an OR -> AND false accept even when all individual conditions were retained. This proves that condition coverage alone is insufficient; connective semantics must also be preserved.
