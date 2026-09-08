# MVP 第一批任务板

本文件只列“现在立刻做什么”。完整边界见：

```text
docs/MVP_API_CONTRACT_V0.1.md
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
```

> 第二轮审计后的核心顺序：**先统一合同，再写后端/前端；先做可玩闭环，再证明 LLM Agent 价值。**

---

## Sprint 0 — Shared Contract（第一优先级）

### S0 — API / Replay / PublicStrategy Contract V0.1

规范源：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

已经冻结的内容：

- `/api/v1` 五个最小路由；
- `MatchSnapshot`；
- Match lifecycle；
- `RuleSubmissionResult`；
- `PublicStrategyDecision`；
- `ReplaySnapshot`；
- public/private projection；
- `schema_version` / `plan_version` / `replay_version`；
- `revision`；
- `Idempotency-Key`；
- per-match lock；
- Replay 禁止再次调用模型。

注意：

```text
PRESSURE / KITE / EVADE / HOLD
```

仍然是**当前实现兼容值**，但前端不得把它们写死成永久策略模型。公共策略对象已经预留 richer-plan 可选字段。

Sprint 0 真正完成还需要：

- Pydantic schema；
- OpenAPI；
- generated/validated TypeScript types；
- accepted/rejected/terminal/revision-conflict fixtures；
- contract tests；
- 私有字段泄漏测试。

---

# Developer A — Backend / AI

## A0 — Pydantic / OpenAPI Contract Source

分支建议：

```text
contract/v0.1
```

实现 `docs/MVP_API_CONTRACT_V0.1.md` 对应的 Python schema。

完成标准：

- OpenAPI 可生成；
- schema_version 固定；
- enum 与文档一致；
- fixture 能通过 schema validation；
- hidden reasoning / private memory / secret 不存在于 public schema。

## A1 — Match Application Service

分支建议：

```text
backend/match-service
```

在 HTTP 层与 Engine 之间增加 service，不让 route 直接操作 Engine 内部对象。

必须支持：

```text
create_match()
get_match_snapshot()
submit_public_rule()
advance_match()
get_replay()
```

同时实现：

```text
in-memory repository
revision
per-match lock
idempotency
public/private projection
```

## A2 — FastAPI Vertical Slice

分支建议：

```text
backend/fastapi-shell
```

严格按 V0.1 contract 实现：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

第一版不做 WebSocket、Redis、Celery、微服务。

---

# Developer B — Frontend

## B0 — React/Vite App Shell

分支建议：

```text
frontend/app-shell
```

新建 `web/`，搭建 React + TypeScript + Vite。

B 可以在 A 完成完整 FastAPI 前开工，但只能使用**通过 Contract schema 校验的 fixture**，不得自行定义另一套接口。

## B1 — Game Board + Status

分支建议：

```text
frontend/game-board
```

实现：

- 5×5 棋盘；
- RED / BLUE unit；
- HP；
- round；
- Match lifecycle；
- active rule；
- rule phase due；
- effective stats；
- `PublicStrategyDecision`。

前端不计算规则效果。

## B2 — Rule Panel

分支建议：

```text
frontend/rule-panel
```

实现：

- 中文规则输入；
- accepted；
- NO_CANDIDATE；
- RULE_REJECTED；
- FAITHFULNESS_REJECTED；
- MODEL_UNAVAILABLE；
- suggested rephrase；
- 只在对应 lifecycle 时允许提交。

建议改写必须由玩家确认后重新提交，前端不得自动执行。

## B3 — Replay / Explainability Shell

分支建议：

```text
frontend/replay-timeline
```

根据 Replay fixture 渲染：

```text
玩家规则
→ 规则接受/拒绝
→ 双方有效属性
→ RED/BLUE public strategy
→ concrete action
→ engine events
→ HP/position 变化
```

不展示 chain-of-thought / private memory。

---

# 两人第一个同步点

现在不再是“等 A 把整个后端写完”。

唯一同步合同是：

```text
MVP_API_CONTRACT_V0.1
+ OpenAPI generated source
```

在此基础上：

```text
A：MatchApplicationService / FastAPI
B：React shell / board / rule / replay fixtures
```

可以并行。

---

# Sprint 1 必做实验 — Agent A/B/C

当前 live Agent Gate 只算：

```text
connectivity evidence
```

不算 LLM value evidence。

Sprint 1 必须比较：

```text
A deterministic heuristic
B current four-intent LLM
C richer-plan LLM + deterministic short rollout
```

如果 C 或 B 无法在客观指标或玩家感知上优于 A，不得为了“AI 项目”叙事强行宣称 LLM Agent 必要。

---

# 现在不要做

```text
扩 Rule DSL
OR / NOT / multi-effect
WebSocket
复杂数据库
Redis / Celery
微服务
多人系统
MCTS
多单位
地形 / 技能 / 装备
账号 / 排行 / 商城
```

这些不是当前 P0。
