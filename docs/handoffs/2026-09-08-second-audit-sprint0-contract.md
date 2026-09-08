# Handoff — Second Audit → Sprint 0 Contract

日期：2026-09-08  
分支：`contract/v0.1-audit-alignment`

## 1. 这次做了什么

根据第二轮深度审计的 `GO WITH CONDITIONS` 结论，把“下一步应该做什么”落成仓库规范，而不是继续写抽象研究。

新增：

```text
docs/MVP_API_CONTRACT_V0.1.md
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
```

更新：

```text
README.md
AI_DEVELOPER_START_HERE.md
docs/MVP_FIRST_TASKS.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/AI_COLLABORATION_PROTOCOL.md
```

## 2. 核心决定

### Agent Gate 证据降格

历史 `live-agent-planner-match` PASS 保留，不改写历史。

从当前开发口径起，它只算：

```text
connectivity evidence
```

不再被用作：

```text
LLM value evidence
最终 Agent schema 冻结依据
游戏趣味性证据
```

### Public Strategy 不永久锁死四分类

当前代码继续使用：

```text
PRESSURE / KITE / EVADE / HOLD
```

但公共 API 使用带 `plan_version` 的 `PublicStrategyDecision`，并预留 richer-plan 可选字段。

当前运行时这些字段可以为 `null`。

### Replay 升级为 shared product contract

Replay 必须保存足够的 public state/plan/action/event，且：

```text
GET replay 不再次调用 LLM
```

禁止 public replay 包含 chain-of-thought、private memory、secret、raw provider body、stack trace。

### 应用层必须从第一版支持

```text
revision
per-match lock
Idempotency-Key
atomic update
public/private projection
```

第一版仍使用 in-memory repository，不引入复杂数据库。

## 3. 明确没有做什么

本分支**没有修改产品实现代码**，尤其没有修改：

```text
Engine
Rule DSL
RuleValidator
DynamicRuleController
StrategyAgent implementation
Planner implementation
Prompt/provider implementation
```

没有扩 OR/NOT/multi-effect，没有加入 WebSocket/Redis/Celery/微服务。

## 4. 下一步 Developer A

实现：

```text
Pydantic public DTO
OpenAPI canonical source
contract tests
schema-validated fixtures
private-field exclusion tests
```

然后：

```text
MatchApplicationService
in-memory MatchRepository
revision/lock/idempotency
FastAPI five routes
Replay projection
```

## 5. 下一步 Developer B

不等完整 FastAPI。

基于通过 schema 验证的 fixtures 实现：

```text
React/Vite shell
5x5 Board
Status/Lifecycle
Rule panel
Effective stats
Public strategy
Event feed
Replay timeline
```

不得自行定义第二套 API 类型或实现游戏裁判逻辑。

## 6. Sprint 1 必须做

Agent A/B/C：

```text
A deterministic heuristic
B current four-intent LLM
C richer-plan LLM + deterministic short rollout
```

没有该证据前，不宣称 LLM Agent 已证明必要。

## 7. 冲突热点

后续尤其注意：

```text
canonical schemas
OpenAPI
PublicStrategyDecision
Replay event mapping
strategy_agent.py
```

不要让多个 AI 同时修改同一个 canonical model。
