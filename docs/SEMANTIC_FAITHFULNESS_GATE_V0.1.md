# Semantic Faithfulness Gate V0.1

## Problem

`RuleValidator` proves whether a generated RuleAST is legal. It cannot prove that the LLM preserved every semantic fragment from the player's original text.

Observed holdout failure:

```text
A OR B -> A
```

The resulting `A` rule was legal and therefore passed deterministic validation even though the player's intent had been weakened.

## V0.1 boundary

Add a second, independent semantic verification step after deterministic validation:

```text
player_text
-> translator model
-> candidate
-> RuleValidator
-> faithfulness verifier
-> downstream Controller
```

Only a candidate passing both gates may be exposed as executable.

## Verifier authority

The verifier may only return:

```json
{"decision":"FAITHFUL"}
```

or:

```json
{
  "decision":"REJECT",
  "reason_code":"DROPPED_INTENT|ALTERED_INTENT|ADDED_INTENT|AMBIGUOUS_COVERAGE"
}
```

It may not:

- repair the candidate;
- generate a replacement candidate;
- mutate GameState;
- call the Engine;
- modify Validator limits;
- change the player's text;
- reinterpret an unsupported rule into a nearby legal rule.

Any model error, malformed output, oversized output, or uncertainty fails closed.

## Semantic requirements

Reject if the candidate omits, changes, adds, or approximates any material fragment, including:

- OR / NOT logic;
- third or additional conditions;
- multiple effects;
- temporary duration;
- faction restrictions;
- explicit numbers;
- weapon identity;
- thresholds;
- direction of comparison;
- modifiers such as increase vs decrease;
- any unsupported capability that the translator silently drops.

The verifier is not a replacement for `RuleValidator`; the two gates answer different questions:

```text
RuleValidator: Is this AST legal?
Faithfulness:  Is this legal AST actually what the player said?
```

## Evaluation rule

The failed V0.1 holdout becomes a regression corpus and may be used to verify that known failures are addressed.

It may not be reused as an unseen holdout for a new generalization claim.

After this architecture is implemented and regression-tested, create a fresh V0.2 holdout before any claim that natural-language mapping is ready for end-to-end gameplay.
