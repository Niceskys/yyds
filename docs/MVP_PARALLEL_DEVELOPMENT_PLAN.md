# 《规则之外》MVP 双人 + AI 并行开发计划

状态：正式 MVP 开发（**GO WITH CONDITIONS**）  
当前行动基线：`docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md`  
公共契约：`docs/MVP_API_CONTRACT_V0.1.md`

本计划适用于两名开发者各自使用 AI 辅助开发。核心目标不是“让两个人同时写最多代码”，而是：**让两个人并行时不互相制造返工。**

---

# 一、先说最重要的规则

在任何真实前后端集成之前，以下内容只能有一份定义：

```text
MatchSnapshot
RuleSubmissionResult
PublicStrategyDecision
ReplaySnapshot
ErrorEnvelope
schema version / enum / error code
```

唯一规范：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

Developer A 维护 Pydantic/OpenAPI 生成源；Developer B 使用生成/验证后的 TypeScript 类型和 fixture。

**禁止 A/B 各自手写一套长期并存的接口类型。**

---

# 二、责任域

## Developer A — 后端 / AI / 核心集成

主要责任：

```text
Python
Engine integration
DynamicRuleController
Natural Language pipeline
Strategy Agent / Planner
Pydantic / OpenAPI
MatchApplicationService
MatchRepository
FastAPI
Replay public projection
backend tests
provider telemetry / fallback
```

## Developer B — 前端 / 交互 / 可视化

主要责任：

```text
React
TypeScript
Vite
5×5 board
HP / round / lifecycle
rule input UX
rule rejection / rephrase UX
effective modifier visualization
public strategy visualization
event feed
replay timeline
frontend tests
```

## Shared — 必须双人 review

```text
docs/MVP_API_CONTRACT_V0.1.md
OpenAPI canonical schema
Replay schema/version
PublicStrategyDecision
privacy boundary
product-level A/B metrics
```

这些不是“谁写后端谁说了算”的纯实现细节，因为会直接决定产品展示和前端结构。

---

# 三、热点文件与禁止并行区

默认不要让两个 AI/开发者同时修改：

```text
src/rules_beyond/engine.py
src/rules_beyond/rule_engine.py
src/rules_beyond/dynamic_rule_controller.py
src/rules_beyond/strategy_agent.py
src/rules_beyond/rule_dsl.py
src/rules_beyond/rule_validator.py
未来 canonical schemas.py
未来 replay event mapping
OpenAPI generated source
```

Developer B 不为了 UI 方便修改 Engine 语义。

如果 UI 缺字段：

```text
提出 contract 变更
→ shared review
→ A 修改 schema/backend
→ regenerated types/fixtures
→ B 使用新合同
```

---

# 四、Sprint 0 — 先冻结和实现 Contract

这是当前第一件事。

## S0.1 Public Contract

规范已建立：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

当前冻结：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

以及：

```text
Match lifecycle
MatchSnapshot
RuleSubmissionResult
PublicStrategyDecision
ReplaySnapshot
revision
Idempotency-Key
public/private projection
schema/replay/plan version
```

## S0.2 Developer A — Schema implementation

A 先实现：

- Pydantic DTO；
- OpenAPI；
- contract tests；
- schema-validated fixtures；
- private-field exclusion tests。

完成后，B 的 TypeScript 类型从 OpenAPI 生成或自动验证。

## S0.3 Developer B — Mock Shell

B 不需要等完整 FastAPI。

可以基于**已通过 contract schema 的 fixture**完成：

```text
GameBoard
StatusPanel
RulePanel
StrategyPanel
EventFeed
ReplayTimeline
MatchControls
```

B0 完成标准：

- 5×5 棋盘渲染；
- RED/BLUE、HP、round 显示；
- lifecycle 显示；
- active rule / effective stats 显示；
- accepted/rejected/rephrase 三类规则体验可模拟；
- public strategy 可渲染；
- replay timeline 可渲染；
- 不包含任何规则裁判逻辑。

---

# 五、Public Strategy：当前兼容，不永久锁死

当前生产代码仍使用：

```text
PRESSURE
KITE
EVADE
HOLD
```

但是第二轮审计明确指出：现有证据只证明连通性，不能证明这四个标签足以体现 LLM 价值。

因此前端禁止把 UI/类型永久建模成“只有一个 intent 字符串”。

公共结构使用：

```text
plan_version
status
intent
optional richer-plan fields
degraded
```

具体见 `MVP_API_CONTRACT_V0.1.md`。

当前四分类 Agent 运行时，可选字段为 `null`。

Sprint 1 的 richer-plan 实验通过后，再开始填充这些字段，而不是破坏 V0.1 前端。

---

# 六、Sprint 1 — 第一条可玩纵向切片

## Developer A — Match Application Service

FastAPI route 不得直接操作 Engine 内部对象。

Application Service 负责：

```text
create_match()
get_match_snapshot()
submit_public_rule()
advance_match()
get_replay()
```

组合：

```text
MatchRepository
DynamicRuleController
NaturalLanguageVerifiedAdapter
RED/BLUE StrategyAgent
Deterministic Planner
Engine
Replay projection
```

第一版 repository：

```text
in-memory
```

必须实现：

```text
per-match lock
revision
Idempotency-Key
atomic update
public/private projection
```

不要先上 SQLite。第一条纵向切片稳定后，再判断是否需要为了重启恢复加入 SQLite。

## Developer A — Provider reliability

MVP 需要：

- 每次模型调用硬 timeout；
- 429/5xx/网络错误最多一次受控 retry；
- strategy failure 使用 deterministic fallback，并设置 public `degraded=true`；
- 规则翻译失败不修改 active rule；
- usage / latency / status 最小遥测；
- secret 不进入 response/log/replay；
- Demo 准备 offline replay/fallback。

## Developer B — Real API integration

接真实 API 后，前端必须以 authoritative snapshot 为准。

前端不计算：

```text
rule legality
effective stats
bow probability
rule phase due
terminal
Engine replay
```

这些全部由后端返回。

---

# 七、Replay 是共享产品能力，不只是后端日志

Replay 至少要让用户看懂：

```text
玩家提交了什么规则
→ 被接受还是拒绝
→ active rule 变成什么
→ 双方有效属性如何变化
→ RED/BLUE 的公开策略是什么
→ Planner 给了什么具体 Action
→ Engine 发生了什么事件
→ HP/位置如何变化
→ Hard Liveness 是否触发
→ 最终结果
```

Replay 规则：

- 不再次调用模型；
- 不展示 chain-of-thought；
- 不保存 opponent private memory；
- 不输出 secret / raw provider body / stack trace；
- 使用版本号；
- B 对“哪些字段足够解释行为”有验收权。

---

# 八、第一条真人可玩 MVP 的验收条件

必须同时满足：

1. 浏览器创建新对局；
2. 看到 5×5 棋盘和红蓝双方；
3. Phase 0 输入中文规则；
4. 后端真正经过 verified NL pipeline；
5. accepted/rejected 有清晰区分；
6. rejected 不破坏 active rule / match；
7. 两个 Agent/或其 fallback 能完成决策；
8. Planner 生成具体动作；
9. Engine 同步结算；
10. 前端看到每回合状态变化；
11. Round 3 后进入下一规则阶段；
12. 新规则可替换旧规则；
13. 对局能进入 terminal；
14. Replay 可回看；
15. 重复请求不会重复推进；
16. public API/replay 不泄露 private memory / hidden reasoning / secret；
17. 不需要手工改 JSON 或运行 CLI 才能玩完整局。

---

# 九、Sprint 1 必须并行做的 Agent A/B/C

第二轮审计后，`live-agent-planner-match` 的后续定位统一为：

```text
connectivity evidence
```

不再作为 LLM value evidence。

必须比较：

```text
A: deterministic heuristic
B: current four-intent LLM
C: richer-plan LLM + 2–3 round deterministic rollout/ranking
```

冻结场景后比较：

- action divergence after rule change；
- legal rate；
- settlement invalid rate；
- strategy diversity；
- utility / win rate（在适当对局设计下）；
- latency；
- token/cost；
- blind replay 玩家评分。

如果 B/C 没有足够增益，就重构/简化 Agent，不允许只靠“用了大模型”作为价值证明。

---

# 十、分支 / PR 建议

Shared contract：

```text
contract/v0.1
```

Developer A：

```text
backend/match-service
backend/fastapi-slice
backend/replay-projection
backend/agent-ab-harness
```

Developer B：

```text
frontend/app-shell
frontend/board-rule-panel
frontend/replay-timeline
frontend/rule-influence-view
```

合并顺序：

```text
contract
→ schema fixtures + mock shell / service tests 并行
→ real API integration
→ replay
→ A/B/C Agent evidence
→ usability
```

---

# 十一、AI 不应并行修改的任务

同一时间不要让多个 AI 同时：

- 改 Engine semantics；
- 改 canonical API schema；
- 改 Replay event version；
- 改 prompt 同时又改 holdout Gate；
- 改同一个 Pydantic model；
- 改 StrategyAgent schema 同时让前端自行猜新字段。

---

# 十二、当前明确不做

```text
OR / NOT / multi-effect DSL
WebSocket
Redis
Celery
Event Bus
微服务
多人真人联机
账号/排行榜/商城
复杂数据库起步
MCTS
多单位
职业/技能
地形
装备
3D
移动 App
```

如果某项不是完成：

```text
真人规则
→ AI 对战
→ 观察
→ 再改规则
→ 终局
→ Replay
```

所必需，默认延后。

---

# 十三、两人每天只需对齐 7 项

```text
1. 我改了哪些路径
2. API contract 是否变化
3. OpenAPI 是否重新生成
4. Replay schema/version 是否变化
5. shared enum 是否变化
6. tests/CI 是否通过
7. 下一分支会碰哪些热点文件
```

如果 contract 没变，A/B 应尽量独立推进。

---

# 十四、当前优先级

```text
P0  MVP_API_CONTRACT_V0.1
P0  Pydantic/OpenAPI + generated/validated fixtures
P0  Frontend Mock Shell
P0  MatchApplicationService + in-memory repository
P0  revision/lock/idempotency
P0  FastAPI five-route vertical slice
P0  Frontend real API integration
P0  Replay public projection
P0  Agent A/B/C harness
P1  rule rejection/rephrase UX
P1  rule influence / strategy visualization
P1  real-user playtest instrumentation
P1  optional SQLite after vertical slice
P2  polish / animation / competition packaging
```

除非出现核心 blocker，不重新扩 DSL，不用更多静态 holdout 代替产品验证。
