# MVP API Contract V0.1 — Implementation Notes

状态：**Normative implementation clarification**  
日期：2026-09-08

本文件记录把 `docs/MVP_API_CONTRACT_V0.1.md` 落成 Pydantic/OpenAPI 时发现的两处文字不一致。它们都是文档修正，**不改变 V0.1 游戏规则或 Engine 语义**。

## 1. RuleEffect 示例名修正

原合同 `RulePublicView` 示例中曾写：

```text
MOVE_RANGE_DELTA
```

真实冻结 Rule DSL 与代码中的枚举是：

```text
MOVE_RANGE_ADD
```

因此从 API canonical source、OpenAPI 与 fixture 开始，统一使用：

```text
MOVE_RANGE_ADD
```

不得为了匹配旧示例而新增 `MOVE_RANGE_DELTA` DSL effect。

## 2. `RULE_PHASE_REQUIRED` 的归属

`POST /api/v1/matches/{match_id}/advance` 在 Match 处于 `AWAITING_RULE` 时使用：

```text
RULE_PHASE_REQUIRED
```

它属于通用 `ErrorEnvelope.error.code`，不是 `RuleSubmissionResult.public_code`。

当前 Pydantic `ErrorCode` 至少包含：

```text
REVISION_CONFLICT
RULE_PHASE_REQUIRED
RULE_PHASE_NOT_DUE
MATCH_TERMINAL
MATCH_NOT_FOUND
IDEMPOTENCY_KEY_REQUIRED
INVALID_REQUEST
MODEL_UNAVAILABLE
INTERNAL_ERROR
```

## 3. Canonical source

从本实现开始，公共结构的代码生成源是：

```text
src/rules_beyond/api_contract.py
```

路由/OpenAPI 生成源：

```text
src/rules_beyond/openapi_contract.py
```

fixture 生成源：

```text
src/rules_beyond/contract_fixtures.py
```

合同文档解释产品语义；Pydantic schema + contract tests 防止代码值与真实 domain enum 漂移。

## 4. 本次明确没有改变

没有改变：

- Engine；
- RuleValidator；
- Rule DSL 的 effect 集；
- DynamicRuleController；
- 当前四个 StrategyIntent；
- Hard Liveness；
- rule cadence；
- Agent / Planner 实现。
