# Natural Language Adapter Contract Checks — 2026-09-08

> 状态：静态 / adversarial contract checks；不包含真实 LLM 语义评测。

## 1. 本轮能证明什么

本轮只证明：

```text
不可信模型输出
→ 严格 JSON 边界
→ RuleValidator
→ DynamicRuleController 再验证
```

不会因为模型输出格式、越权字段或 Prompt Injection 型内容而直接修改游戏状态。

## 2. 本轮不能证明什么

本轮**不能证明**：

- GLM 能正确理解中文规则；
- 真实模型结构化成功率足够高；
- 模糊自然语言能稳定映射到正确 DSL；
- 玩家体验已经成立。

因为当前只使用测试 Stub，不调用真实 Provider。

## 3. adversarial contract cases

自动测试覆盖：

```text
合法 exact JSON                    -> Validator accepted
空输入                              -> 不调用模型
Provider exception                  -> MODEL_ERROR
Provider 非字符串                   -> MODEL_PROTOCOL_ERROR
Markdown fenced JSON               -> JSON_DECODE_ERROR
JSON array                          -> CANDIDATE_NOT_OBJECT
target=RED                          -> FACTION_NEUTRALITY
winner=RED unknown field            -> SCHEMA_UNKNOWN_FIELD
BOW_RANGE_ADD +99                   -> NUMERIC_BOUNDS
超大模型输出                         -> OUTPUT_TOO_LARGE
```

并额外验证 defense-in-depth：

```text
Adapter accepted candidate
→ DynamicRuleController 再验证
→ 才能成为 active_rule
```

以及：

```text
Adapter 已拒绝的 RED-target candidate
即使调用方错误地继续 forward
→ Controller 自己仍然拒绝
```

## 4. 结论 Gate

本阶段成功条件不是自然语言准确率，而是：

> **模型接入之前，权限边界已经是 deterministic + testable。**

只有这些 contract tests 全部通过，才允许下一阶段增加真实 Provider。
