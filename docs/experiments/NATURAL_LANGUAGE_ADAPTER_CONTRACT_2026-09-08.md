# Natural Language Adapter Contract Checks — 2026-09-08

> 状态：静态 / adversarial contract checks；不包含真实 LLM 语义评测。

## 1. 本轮能证明什么

本轮只证明：

```text
不可信模型输出
→ 严格 JSON envelope
→ CANDIDATE / NO_CANDIDATE
→ Candidate 才进入 RuleValidator
→ DynamicRuleController 再验证
```

不会因为模型输出格式、越权字段或 Prompt Injection 型内容而直接修改游戏状态。

同时给模型提供一个明确安全出口：

```text
NO_CANDIDATE
```

避免协议强迫模型把不合法玩家意图改写成另一条合法规则。

## 2. 本轮不能证明什么

本轮**不能证明**：

- GLM 能正确理解中文规则；
- 真实模型结构化成功率足够高；
- 模糊自然语言能稳定映射到正确 DSL；
- 模型一定不会语义误映射；
- 玩家体验已经成立。

因为当前只使用测试 Stub，不调用真实 Provider。

## 3. adversarial contract cases

自动测试覆盖：

```text
合法 CANDIDATE envelope             -> Validator accepted
合法 NO_CANDIDATE                  -> 不生成 RuleAST
非法 NO_CANDIDATE reason           -> MODEL_PROTOCOL_ERROR
envelope extra fields              -> MODEL_PROTOCOL_ERROR
unknown decision                   -> MODEL_PROTOCOL_ERROR
空输入                              -> 不调用模型
Provider exception                  -> MODEL_ERROR
Provider 非字符串                   -> MODEL_PROTOCOL_ERROR
Markdown fenced JSON               -> JSON_DECODE_ERROR
JSON array                          -> MODEL_PROTOCOL_ERROR
target=RED                          -> FACTION_NEUTRALITY
winner=RED unknown field            -> SCHEMA_UNKNOWN_FIELD
BOW_RANGE_ADD +99                   -> NUMERIC_BOUNDS
candidate 非 object                 -> CANDIDATE_NOT_OBJECT
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

## 4. 真实 Provider 前的新增 Gate

固定语料集必须特别包含：

```text
“只给红方伤害+1”
“让双方回血”
“把比赛延长到60回合”
“残血时更灵活”
```

分别检查模型是否选择：

```text
DISALLOWED_INTENT
UNSUPPORTED_CAPABILITY
AMBIGUOUS
```

而不是自行把玩家原意改成一条合法但不同的规则。

## 5. 结论 Gate

本阶段成功条件不是自然语言准确率，而是：

> **模型接入之前，格式权限边界与显式拒绝路径已经 deterministic + testable。**

只有这些 contract tests 全部通过，才允许真实 Provider 进入下一阶段。
