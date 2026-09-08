# Handoff — V0.2 OR→AND semantic-safety fix

> 日期：2026-09-08

## 为什么做

第一次 unseen V0.2 verified holdout（workflow `34178489427`）FAIL：

```text
legal_semantic_correct = 24/25
false_accepts = 1
wrong_legal_candidates = 0
verifier_errors = 0
```

关键失败：

```text
原文 A OR B
-> translator 生成 A AND B
-> RuleValidator 接受
-> faithfulness verifier 错误判 FAITHFUL
-> 错误规则进入 executable pipeline
```

## 本分支做什么

### 1. Deterministic intent guard

新增：

```text
src/rules_beyond/rule_intent_guard.py
```

当前 V0.1 guard 只处理显式 OR：

```text
或者
或是
要么
English standalone word: or
```

这些输入在任何模型调用前直接安全拒绝。

边界：

- 不做通用中文解析；
- 不生成/修复 RuleAST；
- 不替代 RuleValidator；
- 不替代 faithfulness verifier；
- 不扩展 DSL。

### 2. Verified pipeline integration

`VerifiedNaturalLanguageRuleAdapter` 新增状态：

```text
INTENT_GUARD_REJECTED
```

Guard 拒绝时：

- translator 不调用；
- verifier 不调用；
- candidate/rule 不向 downstream 暴露；
- 以 `CANNOT_MAP_SAFELY` 表示安全拒绝。

### 3. Faithfulness contract clarification

明确：

```text
same atomic conditions != same logic
OR -> AND = ALTERED_INTENT
```

同时明确 conditional cooldown：

```text
Rule duration UNTIL_REPLACED
!=
WEAPON_COOLDOWN rounds=1 duration
```

修复 V0.2 唯一合法 false reject 的已知语义混淆。

### 4. Benchmark observability

Verified benchmark 新增：

```text
intent_guard_rejections
intent_guard_decision
intent_guard_reason
```

以后可以区分：

```text
deterministic guard
base translator/validator rejection
semantic verifier rejection
verifier error
```

## 明确没有改

```text
Rule DSL
RuleValidator bounds
Engine
DynamicRuleController
anti-stall
MiMo provider protocol
V0.2 corpus
```

## 并发热点

在本 PR 合并前，其他 AI/开发者不要并行修改：

```text
src/rules_beyond/verified_natural_language_rule_adapter.py
src/rules_beyond/rule_faithfulness.py
src/rules_beyond/verified_natural_language_benchmark.py
```

Engine / rule runtime / bots 等低耦合区域可继续独立工作，但当前仍不建议正式双人产品开发。

## Merge Gate

必须：

```text
pytest PASS
behavior-diagnostics PASS
dynamic-rule-replacement PASS
```

合并后先重跑**已知 V0.2**：

```text
provider=mimo
model=mimo-v2.5-pro
suite=holdout-v02
pipeline=verified
```

该重跑只验证修复，不是新的泛化证明。

若：

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 24/25
```

则停止针对 V0.2 调整，并创建新的 V0.3 unseen Gate。

正式 MVP 开发仍未开始。
