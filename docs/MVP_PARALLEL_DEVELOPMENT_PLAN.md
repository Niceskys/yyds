# 《规则之外》MVP 双人 + AI 并行开发计划

状态：正式 MVP 开发（**GO WITH CONDITIONS**）  
当前玩法基线：`docs/GAMEPLAY_FLOW_V0.2.md`  
公共契约：`docs/MVP_API_CONTRACT_V0.2.md`

本计划适用于两名开发者各自使用 AI 辅助开发。核心目标不是“同时写最多代码”，而是：**并行时不互相制造返工。**

---

# 一、当前最重要的并行边界

V0.2 已经修改产品状态机：

旧：

```text
Phase0 before Round1
Round3 / 6 / 9 ... rule phase
```

新：

```text
Round1 无玩家规则自动开始
每个非终局完整回合后进入 PLAYER_DECISION
玩家可直接继续或尝试换规则
同一 intermission 最多成功换一次
规则成功后仍需点击继续下一回合
```

因此：

```text
Developer A 当前先迁 Controller cadence
Developer B 当前直接按 V0.2 fixture 做 UI
```

不要让 A 继续按旧 Controller 写 MatchApplicationService，也不要让 B 使用 V0.1 fixture。

---

# 二、唯一共享合同

以下内容只能有一份定义：

```text
MatchSnapshot
PlayerDecisionSnapshot
BattleEscalationSnapshot
RuleSubmissionResult
PublicStrategyDecision
ReplaySnapshot
ErrorEnvelope
schema / replay / plan version
enum / error code
```

唯一规范：

```text
docs/MVP_API_CONTRACT_V0.2.md
```

Canonical source：

```text
src/rules_beyond/api_contract.py
```

Developer A 维护 Pydantic/OpenAPI 生成源；Developer B 使用生成/验证后的 TypeScript 类型和 fixture。

禁止 A/B 各自长期维护两套类型。

---

# 三、责任域

## Developer A — 后端 / AI / 核心集成

```text
Python
Engine integration
DynamicRuleController cadence V0.2 migration
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

```text
React
TypeScript
Vite
初始页
5×5 board
HP / completed rounds / score
rule_change_count
current public rule
battle escalation
rule input UX
rule rejection / rephrase UX
public strategy visualization
concrete action visualization
event feed
replay timeline
frontend tests
```

## Shared — 必须双人 review

```text
GAMEPLAY_FLOW_V0.2
MVP_API_CONTRACT_V0.2
OpenAPI canonical schema
Replay schema/version
PublicStrategyDecision
privacy boundary
battle escalation public semantics
product-level A/B metrics
```

---

# 四、热点文件与禁止并行区

默认不要让两个 AI/开发者同时修改：

```text
src/rules_beyond/engine.py
src/rules_beyond/rule_engine.py
src/rules_beyond/dynamic_rule_controller.py
src/rules_beyond/strategy_agent.py
src/rules_beyond/rule_dsl.py
src/rules_beyond/rule_validator.py
src/rules_beyond/api_contract.py
replay event mapping
OpenAPI generated source
```

Developer B 不为了 UI 方便修改 Engine 语义。

如果 UI 缺字段：

```text
提出 contract 变更
→ shared review
→ A 修改 schema/backend
→ regenerate types/fixtures
→ B 使用新合同
```

---

# 五、当前并行 Sprint

## Developer A — A0 Controller cadence migration【当前第一优先级】

迁移目标：

```text
start_match
→ active_rule = null
→ Round1 可直接 resolve

每个非终局 round resolve 后
→ PLAYER_DECISION/intermission open

rule attempt rejected
→ intermission 保持打开
→ 允许重试

rule accepted once
→ 替换 active rule
→ 同一 intermission 不再允许第二次成功替换

continue
→ 关闭 intermission
→ 下一 round
```

必须保持：

```text
rule replacement 不重置 PublicRuleHistory
rule replacement 不重置 no_damage_streak
只有实际伤害重置 no_damage_streak
terminal 不再打开 intermission
```

A0 完成前，不实现真实 MatchApplicationService orchestration。

## Developer B — B0/B1 V0.2 Mock UI【可立即并行】

直接使用：

```text
contracts/fixtures/mvp-v0.2/
```

实现：

```text
初始页：游戏名 + 开始游戏
GameBoard
RED/BLUE status
PublicStrategy panel
Concrete Action panel
Current Rule panel
Battle Escalation panel
Player Decision controls
Event feed
Terminal summary
```

B 不需要等待完整 FastAPI。

---

# 六、前端 V0.2 交互硬规则

## 初始页

```text
《规则之外》
[开始游戏]
```

不做：登录、设置、排行榜、模式选择。

## 第1回合

```text
开始游戏
→ create match
→ frontend immediately calls first advance
```

用户体验表现为：

```text
第1回合自动开始
```

第1回合前规则输入不可用。

## 每个回合后

```text
PLAYER_DECISION
```

玩家：

```text
A. 直接继续下一回合
B. 尝试提交公共规则
```

规则成功：

```text
rule_change_count + 1
输入区锁定
仍需点击继续下一回合
```

规则拒绝：

```text
rule_change_count 不变
允许改写后重试
```

---

# 七、中文 UI 原则

普通玩家尽量不看到工程英文。

至少映射：

```text
PRESSURE → 逼近进攻
KITE → 保持距离
EVADE → 躲避保命
HOLD → 原地应对
RED → 红方
BLUE → 蓝方
BOW → 弓箭
KNIFE → 刀
```

不要直接显示：

```text
Hard Liveness
conflict_level
schema_version
provider
chain-of-thought
private memory
```

内部 `BattleEscalationSnapshot` 在 UI 统一叫：

```text
战局升温
```

---

# 八、战局升温是共享产品能力

当前系统阈值保留：

```text
3 / 6 / 9 / 12 连续无实际伤害回合
```

产品展示至少告诉玩家：

```text
当前等级
连续无伤害回合
距离下一等级还有几回合
当前是否进入强制破局
```

Developer B 不自己计算阈值；后端通过 `BattleEscalationSnapshot` 返回 authoritative state。

规则替换不能重置它。

---

# 九、Public Strategy：兼容四分类，不永久锁死

当前：

```text
PRESSURE
KITE
EVADE
HOLD
```

前端禁止只按一个 intent 字符串设计永久 UI。

公共结构保留：

```text
plan_version
status
intent
optional richer-plan fields
degraded
```

当前可选字段为空也能渲染。

Sprint 1 richer-plan 有证据后再开始填充。

---

# 十、A0 完成后的 Developer A 主线

## A1 — MatchApplicationService

负责：

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
DynamicRuleController V0.2
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
completed_rounds
score_rounds
rule_change_count
battle escalation projection
```

不要先上 SQLite。

## A2 — Provider reliability

MVP 需要：

- 模型调用硬 timeout；
- 429/5xx/网络错误最多一次受控 retry；
- strategy failure deterministic fallback + `degraded=true`；
- 规则翻译失败不修改 active rule；
- usage / latency / status 最小遥测；
- secret 不进入 response/log/replay；
- Demo 准备 offline replay/fallback。

## A3 — FastAPI real routes

仍只实现五个路由。

不提前引入 WebSocket / Redis / Celery / 微服务。

---

# 十一、Replay V0.2

时间线核心：

```text
ROUND
INTERMISSION
ROUND
INTERMISSION
...
```

第一个 entry 必须是：

```text
ROUND 1
```

不存在旧 Phase0。

Replay 至少让玩家看懂：

```text
每回合双方公开策略
→ concrete action
→ Engine events
→ HP / position
→ battle escalation
→ 玩家是否继续或尝试规则
→ 规则接受/拒绝
→ active rule before/after
→ rule_change_count
→ 最终 AI 结果
→ 玩家 score_rounds
```

Replay：

- 不再次调用模型；
- 不展示 chain-of-thought；
- 不保存 private memory；
- 不输出 secret / raw provider body / stack trace。

---

# 十二、第一条真人可玩 MVP 验收

必须同时满足：

1. 初始页只有核心入口；
2. 点击开始后第1回合自动无规则进行；
3. 浏览器看到 5×5 棋盘和红蓝双方；
4. 红蓝一次共同构成一个完整回合；
5. 每个非终局回合后暂停；
6. 玩家可直接继续；
7. 玩家可提交中文公共规则；
8. accepted/rejected 清晰区分；
9. rejected 不消耗规则制定次数；
10. 同一 intermission 最多成功替换一次；
11. accepted 后不自动进入下一回合；
12. 页面持续显示 rule_change_count；
13. 页面可解释战局升温；
14. public strategy 与 concrete action 分开展示；
15. Engine 同步结算；
16. terminal 能正确结束；
17. 达到 30 回合时玩家 UI 视为达到最高回合；
18. Replay 可回看；
19. 重复请求不会重复推进/重复计数；
20. API/Replay 不泄露 private memory / hidden reasoning / secret。

---

# 十三、Sprint 1 必须并行做的玩法验证

## 追逃 / 软死局

至少：

```text
PRESSURE vs KITE
KITE vs KITE
EVADE vs EVADE
PRESSURE vs EVADE
HOLD vs KITE
```

记录：

```text
总回合数
最长连续无伤害
最高战局升温等级
重复位置
重复策略
强制弓次数
```

重点验证 `3/6/9/12` 在每回合人工暂停后的节奏是否太慢。

## Agent A/B/C

```text
A deterministic heuristic
B current four-intent LLM
C richer-plan LLM + deterministic 2–3 round rollout
```

比较：

- rule change 后 action divergence；
- legal rate；
- invalid settlement rate；
- strategy diversity；
- latency / cost；
- blind replay 玩家评分。

如果 B/C 没有足够增益，就简化或重构 Agent。

## 真人试玩

观察：

- 玩家是否每回合都必改规则；
- “继续”是否成为伪选择；
- 是否出现固定拖延套路；
- 玩家是否理解战局升温；
- 玩家是否理解同一公共规则对双方产生不同效果。

---

# 十四、分支建议

Developer A：

```text
backend/controller-v02-intermission
backend/match-service-v02
backend/fastapi-slice-v02
backend/replay-v02
backend/agent-ab-harness
```

Developer B：

```text
frontend/app-shell-v02
frontend/game-board-v02
frontend/player-decision-v02
frontend/replay-v02
```

合并顺序：

```text
V0.2 contract
→ Controller migration / Frontend mock 并行
→ MatchService
→ real API integration
→ Replay
→ gameplay experiments + Agent A/B/C
→ usability
```

---

# 十五、当前明确不做

```text
回血
规则叠加
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

如果某项不是完成 V0.2 真人闭环所必需，默认延后。

---

# 十六、两人每天只需对齐 8 项

```text
1. 我改了哪些路径
2. Gameplay contract 是否变化
3. API contract 是否变化
4. OpenAPI 是否重新生成
5. Replay schema/version 是否变化
6. shared enum 是否变化
7. tests/CI 是否通过
8. 下一分支会碰哪些热点文件
```

如果合同没变，A/B 应尽量独立推进。
