# 《规则之外》MVP API / Replay 公共契约 V0.1

状态：**Sprint 0 冻结规范（Normative）**  
日期：2026-09-08  
适用范围：第一条真人可玩 MVP 纵向切片  
维护责任：Developer A 维护生成源；A/B 对公共字段共同 review

> 这份文件的目的很简单：前端和后端从现在开始使用同一套“语言”。
>
> 前端不得自己猜字段，后端不得随意改变字段。实现代码、Pydantic schema、OpenAPI、TypeScript 类型和 fixture 都必须与本文件保持一致。

---

## 1. 为什么现在必须先冻结这份契约

当前 Engine、动态规则和 Agent/Planner 已经可以运行，但 Web/API/Replay 还没有正式产品边界。

如果前端先按四个 `StrategyIntent` 自己建模、后端又在后续把 Agent 改成更丰富的 StrategyPlan，双方会发生大面积返工。

因此 V0.1 采用以下原则：

1. **当前实现兼容**：现有 Agent 仍然只产生 `PRESSURE/KITE/EVADE/HOLD`。
2. **公共合同不把未来锁死**：公共策略对象包含 `plan_version`，并为后续 richer plan 预留可选字段。
3. **Engine 仍是最终权威**：API 只暴露 Engine/Controller 已确认的状态，不让前端重算规则。
4. **Replay 是正式产品合同**：不是调试日志；不得依赖再次调用 LLM 才能回放。
5. **公开信息与私有信息严格分开**：hidden reasoning、private memory、provider secret 永不进入 public DTO。

---

# 2. 版本与兼容规则

所有顶层公共响应必须包含：

```json
{
  "schema_version": "mvp-v0.1"
}
```

规则：

- V0.1 内新增**可选字段**允许；
- 删除字段、重命名字段、改变 enum 值、改变字段含义属于 breaking change；
- breaking change 必须升版本，不允许静默修改；
- TypeScript 类型必须从 OpenAPI/Pydantic 生成或经过 contract test 验证，禁止长期手写两套定义；
- fixture 必须通过同一 schema 校验。

---

# 3. Match 生命周期

公共生命周期固定为：

```text
AWAITING_INITIAL_RULE
RUNNING
AWAITING_RULE
TERMINAL
FAILED_RECOVERABLE
```

含义：

- `AWAITING_INITIAL_RULE`：新对局已创建，Round 1 尚未开始，等待 Phase 0 规则提交；
- `RUNNING`：可以推进下一回合；
- `AWAITING_RULE`：规则阶段已到，必须先处理规则提交，禁止直接 advance；
- `TERMINAL`：比赛结束，不允许再提交规则或推进；
- `FAILED_RECOVERABLE`：应用层发生可恢复故障，例如策略模型故障后的服务异常；第一版应尽量通过 deterministic fallback 避免进入该状态。

> Natural-language 规则被拒绝并不意味着 Match 失败。被拒绝时旧 active rule 保留，生命周期仍根据 Controller 状态决定。

---

# 4. 公共 DTO

## 4.1 PositionSnapshot

```json
{
  "row": 3,
  "col": 1
}
```

坐标继续沿用 domain 的 1-based 语义。

## 4.2 UnitSnapshot

```json
{
  "team": "RED",
  "hp": 4,
  "position": {"row": 3, "col": 1}
}
```

`team`：`RED | BLUE`。

## 4.3 EffectiveStatsPublicView

前端只展示后端计算完成的最终有效属性，不自行套规则。

```json
{
  "move_range": 1,
  "knife_range": 1,
  "bow_range": 3,
  "knife_damage": 2,
  "bow_damage": 1,
  "bow_hit_multiplier": 1.0,
  "bow_hit_floor": 0.0,
  "cooldown_weapons": [],
  "conflict_level": 0,
  "hard_liveness": false
}
```

## 4.4 RulePublicView

```json
{
  "rule_id": "rule_01J...",
  "player_text": "双方移动距离增加1格",
  "ast": {
    "version": "0.1",
    "target": "ALL_UNITS",
    "conditions": [],
    "effect": {"type": "MOVE_RANGE_DELTA", "delta": 1},
    "duration": "UNTIL_REPLACED"
  }
}
```

说明：

- `player_text` 可以公开回放；
- `ast` 是已通过 Validator/Controller 的可执行 RuleAST 公共投影；
- 未接受的候选 AST 不得伪装成 active rule。

## 4.5 PublicStrategyDecision

这是本次 Sprint 0 最重要的防返工设计。

```json
{
  "plan_version": "intent-v0.1",
  "status": "ACCEPTED",
  "intent": "PRESSURE",
  "target_distance": null,
  "weapon_preference": null,
  "risk_budget": null,
  "short_term_goal": null,
  "horizon_rounds": null,
  "contingency": null,
  "degraded": false
}
```

### 当前必须支持

`plan_version`：

```text
intent-v0.1
```

`intent`：

```text
PRESSURE
KITE
EVADE
HOLD
```

`status` 至少：

```text
ACCEPTED
FALLBACK_MODEL_ERROR
FALLBACK_PROTOCOL_ERROR
```

### V0.1 预留但当前允许为 null 的 richer-plan 字段

```text
target_distance: integer | null
weapon_preference: KNIFE | BOW | ADAPTIVE | null
risk_budget: LOW | MEDIUM | HIGH | null
short_term_goal: DAMAGE | SURVIVE | TRIGGER_RULE | DENY_RULE | null
horizon_rounds: 1..3 | null
contingency: object | null
```

为什么现在就预留：

- 当前四分类 Agent 只填 `intent`；
- 后续如果 A/B/C 实验证明 richer plan 有价值，可以把 `plan_version` 升为例如 `strategy-plan-v0.2`，同时开始填这些字段；
- 前端不应把“只有四个词”写死成永久产品结构。

### `degraded`

当策略模型失败并使用 deterministic fallback 时：

```json
"degraded": true
```

前端可显示“AI 本回合使用降级策略”，但不得显示内部异常、stack trace 或原始 provider body。

## 4.6 MatchSnapshot

```json
{
  "schema_version": "mvp-v0.1",
  "match_id": "match_01J...",
  "revision": 7,
  "lifecycle": "RUNNING",
  "seed": 1270000,
  "round_no": 2,
  "board": {"rows": 5, "cols": 5},
  "units": {
    "RED": {"team": "RED", "hp": 4, "position": {"row": 3, "col": 2}},
    "BLUE": {"team": "BLUE", "hp": 3, "position": {"row": 3, "col": 5}}
  },
  "active_rule": null,
  "rule_phase": {
    "phase_index": 0,
    "due": false,
    "next_due_after_round": 3
  },
  "effective_stats": {
    "RED": {},
    "BLUE": {}
  },
  "latest_strategy": {
    "RED": null,
    "BLUE": null
  },
  "no_damage_streak": 0,
  "hard_liveness_active": false,
  "result": null
}
```

### `revision`

每次成功改变 Match 的操作后递增。

作用：阻止两个请求同时推进同一局，或者用户连续点两次按钮导致一回合被执行两次。

客户端写请求必须携带 `expected_revision`。

### `result`

终局时使用现有 domain enum：

```text
RED_WIN
BLUE_WIN
DRAW_MUTUAL_DEATH
TIMEOUT
```

非终局为 `null`。

---

# 5. 规则提交 DTO

## 5.1 RuleSubmissionRequest

```json
{
  "expected_revision": 4,
  "player_text": "双方移动距离增加1格"
}
```

同时必须通过 HTTP Header 提供：

```text
Idempotency-Key: <client-generated-unique-key>
```

同一个 key 重试不得重复执行或重复扣费。

## 5.2 RuleSubmissionResult

统一结构：

```json
{
  "schema_version": "mvp-v0.1",
  "accepted": true,
  "public_code": "ACCEPTED",
  "message": "规则已生效。",
  "suggested_rephrase": null,
  "candidate_preview": null,
  "rule_id": "rule_01J...",
  "match": {}
}
```

### `public_code` 冻结集合

至少支持：

```text
ACCEPTED
NO_CANDIDATE
RULE_REJECTED
FAITHFULNESS_REJECTED
MODEL_UNAVAILABLE
RULE_PHASE_NOT_DUE
MATCH_TERMINAL
REVISION_CONFLICT
```

说明：

- provider timeout、HTTP 429/5xx、协议损坏不得全部伪装成“你的规则不合法”；
- `MODEL_UNAVAILABLE` 表示系统暂时不能可靠翻译/验证；
- `NO_CANDIDATE` 表示系统认为该自然语言无法安全表达为当前 DSL；
- `RULE_REJECTED` 表示 deterministic validator/controller 拒绝；
- `FAITHFULNESS_REJECTED` 表示候选 AST 未通过语义忠实检查；
- 语义拒绝不自动偷偷改写并执行。

### `suggested_rephrase`

只允许是**给玩家看的建议句子**，不得自动提交。

例如：

```json
{
  "accepted": false,
  "public_code": "NO_CANDIDATE",
  "suggested_rephrase": "双方的移动距离增加1格"
}
```

玩家确认后重新提交，才形成新的规则请求。

---

# 6. Action / Event 公共投影

## 6.1 ActionPublicView

```json
{
  "move_path": ["RIGHT"],
  "attack": "BOW"
}
```

`attack`：`KNIFE | BOW | null`。

## 6.2 RoundEventPublicView

当前 domain `Event.kind` 仍是字符串。API 层 V0.1 必须把它包在版本化对象里：

```json
{
  "event_version": "event-v0.1",
  "kind": "BOW_HIT",
  "actor": "RED",
  "details": {}
}
```

在 `event-v0.1` 内：

- 已公开的 `kind` 不可悄悄改含义；
- 新增 kind 可以；
- `details` 只允许 JSON-safe、已清洗字段；
- provider raw output、exception object、private memory 不得进入 `details`。

---

# 7. ReplaySnapshot

Replay 是不可变的 public projection。

```json
{
  "schema_version": "mvp-v0.1",
  "replay_version": "replay-v0.1",
  "match_id": "match_01J...",
  "seed": 1270000,
  "initial_config": {},
  "timeline": [],
  "terminal_result": "RED_WIN"
}
```

## 7.1 每个规则阶段至少保存

```text
phase_index
submitted_player_text
submission_public_code
accepted_rule_id
accepted RuleAST public projection（若有）
active rule before/after
```

## 7.2 每个回合至少保存

```text
round_no
pre_round MatchSnapshot 的必要状态
RED PublicStrategyDecision
BLUE PublicStrategyDecision
RED ActionPublicView
BLUE ActionPublicView
Engine public events
post_round units / HP / positions
no_damage_streak
hard_liveness_active
effective stats / modifiers
result
```

## 7.3 Replay 的硬规则

1. `GET replay` **绝不能再次调用 LLM**；
2. Replay 必须依赖已保存的 public plan/action/event/state；
3. 同一 Replay 多次读取必须得到相同公共内容；
4. Replay 不记录 chain-of-thought；
5. Replay 不记录 opponent private memory；
6. Replay 不记录 provider key、完整 system prompt、未经清洗的 provider error/body、内部 stack trace；
7. raw model output 若将来为调试保存，只能进入独立受控调试日志，不能进入 public replay。

---

# 8. API 路由 V0.1

统一 URL 前缀：

```text
/api/v1
```

## 8.1 创建对局

```text
POST /api/v1/matches
```

请求：

```json
{
  "seed": 1270000
}
```

`seed` 可选；若服务端生成，必须在响应和 Replay 固化。

返回：`201 MatchSnapshot`

第一版创建后默认：

```text
lifecycle = AWAITING_INITIAL_RULE
```

## 8.2 查看当前状态

```text
GET /api/v1/matches/{match_id}
```

返回：`200 MatchSnapshot`

GET 不得改变任何 Match 状态。

## 8.3 提交规则

```text
POST /api/v1/matches/{match_id}/rules
```

要求：

- Body: `RuleSubmissionRequest`；
- Header: `Idempotency-Key`；
- 仅在 `AWAITING_INITIAL_RULE` 或 `AWAITING_RULE` 时允许。

成功/安全拒绝均返回可解析的 `RuleSubmissionResult`。是否使用 200/422 由 FastAPI 实现统一决定，但 public_code 必须保持稳定。

## 8.4 推进一个回合

```text
POST /api/v1/matches/{match_id}/advance
```

请求：

```json
{
  "expected_revision": 5
}
```

Header：

```text
Idempotency-Key: ...
```

规则：

- `AWAITING_RULE` 时禁止推进，返回 `RULE_PHASE_REQUIRED`；
- `TERMINAL` 时禁止推进；
- 同一 match 同一时刻只允许一次 advance 进入临界区；
- RED/BLUE 策略调用、Planner、Engine 结算必须由 application service 统一编排；
- route 不直接持有或修改 Engine state。

返回建议：

```json
{
  "schema_version": "mvp-v0.1",
  "round": {
    "round_no": 2,
    "strategies": {},
    "actions": {},
    "events": []
  },
  "match": {}
}
```

## 8.5 获取 Replay

```text
GET /api/v1/matches/{match_id}/replay
```

返回：`200 ReplaySnapshot`

不得触发模型调用或改变 match revision。

---

# 9. 并发、重复请求和原子性

这是 MVP 也必须做的，不是“以后上云再做”。

Application Service 必须满足：

```text
per-match lock
+ revision check
+ idempotency
```

最小行为：

- 请求 `expected_revision != current revision`：返回 HTTP 409 + `REVISION_CONFLICT`；
- 相同 Idempotency-Key 重发：返回第一次的已保存结果，不重复推进/重复调用模型；
- 同一 match 的两个 advance 不得并发执行；
- 模型失败不得留下“只移动了 RED、BLUE 还没决策”这种半提交状态；
- 应在 service 中形成完整的新状态和 replay event 后再原子替换当前 match record。

---

# 10. 错误 Envelope

非业务型错误统一：

```json
{
  "schema_version": "mvp-v0.1",
  "error": {
    "code": "REVISION_CONFLICT",
    "message": "对局状态已经变化，请刷新后重试。",
    "retryable": true
  }
}
```

禁止返回给前端：

```text
Python stack trace
provider response body
provider key
system prompt
private memory
raw chain-of-thought
```

---

# 11. Public / Private 数据边界

## 可以进入 API / Replay

- match id / seed / revision / lifecycle；
- board、HP、position；
- active public rule 与 accepted RuleAST public projection；
- effective stats；
- public rule history（若产品需要）；
- public strategy decision；
- concrete action；
- Engine public events；
- Hard Liveness 状态；
- public rejection code 与用户可理解 message。

## 永远不进入 Public DTO

- `MIMO_API_KEY` / 其他 secret；
- raw chain-of-thought；
- hidden reasoning；
- RED/BLUE private strategy memory；
- 对手未公开的内部策略状态；
- 完整 system prompt；
- 未经清洗的 provider error/body；
- stack trace；
- 内部对象 repr。

---

# 12. 前端实现约束

Developer B 只做“展示 + 用户输入”，不实现业务裁判。

前端不得：

- 自己判断 RuleAST 合法性；
- 自己计算弓命中率；
- 自己计算 effective stats；
- 自己决定 rule phase 是否 due；
- 自己重放 Engine；
- 根据四个 intent 猜具体行动；
- 把 private/hidden 字段加进 UI。

前端应该：

- 根据 MatchSnapshot 渲染棋盘；
- 根据 lifecycle 控制按钮状态；
- 根据 RuleSubmissionResult 显示接受/拒绝/改写建议；
- 根据 PublicStrategyDecision 展示 AI 公开策略；
- 根据 ReplaySnapshot 做 timeline。

---

# 13. Backend 实现约束

推荐最小依赖方向：

```text
FastAPI routes
    ↓
MatchApplicationService
    ↓
MatchRepository protocol (in-memory first)
    ↓
DynamicRuleController / NL adapter / Agents / Planner / Engine
```

Routes 只负责：

```text
HTTP DTO validation
Idempotency-Key 读取
expected_revision 读取
错误映射
调用 service
返回 public DTO
```

Routes 不得：

- 直接推进 Engine；
- 自己保存 mutable GameState；
- 直接调用 provider；
- 重新解释规则。

---

# 14. Contract Test / Definition of Done

Sprint 0 只有满足以下条件才算真正完成，而不是“写完一份文档”：

1. 建立 Pydantic schema，字段与本文件一致；
2. FastAPI OpenAPI 可生成；
3. 前端 TypeScript 类型由 OpenAPI 生成或自动验证；
4. accepted/rejected/terminal/revision-conflict 至少各有一个 fixture；
5. fixture 经过 schema validation；
6. contract test 证明私有字段不出现在 JSON；
7. Replay fixture 证明读取 Replay 不需要调用 model；
8. A/B 都以这份 contract 为唯一接口依据。

---

# 15. 本版本明确不解决

本合同 V0.1 不引入：

```text
WebSocket
数据库强依赖
Redis
Celery
Event Bus
微服务
多人房间
账号系统
OR/NOT/multi-effect DSL 扩展
MCTS
自由代码规则
```

第一版 REST + in-memory store 足够完成 Demo 纵向切片。

---

# 16. 对当前四分类 Agent 的正式定位

当前 `live-agent-planner-match` PASS 从本规范开始只应被称为：

```text
Agent / Planner / provider / Controller / Engine 的真实连通性证据
```

它**不是**：

```text
LLM Agent 必要性证据
策略质量证据
玩家价值证据
最终 Agent schema 冻结依据
```

因此：

- 当前代码继续兼容，不因为审计直接重写 Agent；
- 前端不把四分类永久锁死；
- Sprint 1 必须做 heuristic vs 当前 LLM vs richer-plan LLM+rollout 的 A/B/C；
- 如果 LLM 没有可测或可感知增益，应允许降级/重构，而不是为了叙事强留。

---

# 17. Sprint 0 完成后的下一步

顺序固定：

```text
1. Pydantic/OpenAPI 生成源
2. schema-validated fixtures
3. MatchApplicationService
4. in-memory MatchRepository
5. revision + lock + idempotency
6. FastAPI five routes
7. React mock shell 接 generated types
8. real API integration
9. Replay public projection
10. Sprint 1 A/B/C Agent experiment
```

在 1–9 跑通之前，不扩 Rule DSL，不上复杂基础设施，不为 UI 重写 Engine。
