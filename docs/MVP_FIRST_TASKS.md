# MVP 第一批任务板

本文件只列“现在立刻做什么”。当前唯一产品/合同基线：

```text
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_API_CONTRACT_V0.2.md
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
```

> 当前顺序：**先把新玩法状态机迁干净，再写 MatchApplicationService；前端可以同时按 V0.2 fixture 开工。**

---

# 当前已完成

## S0-A — V0.2 Gameplay Flow Freeze

已冻结：

- 第 1 回合前不允许制定规则；
- 第 1 回合无玩家规则自动开始；
- 红蓝双方各思考/行动一次，合起来算一个完整回合；
- 每个非终局完整回合后游戏暂停；
- 玩家每个回合间可以直接继续或尝试提交规则；
- 同一回合间最多成功替换一次规则；
- 规则成功后仍需点击“继续下一回合”；
- 始终最多一条 active rule；
- `rule_change_count` 只统计成功生效规则；
- 暂无回血；
- 防死局机制产品化为“战局升温”；
- 规则修改不重置连续无伤害计数；
- 普通玩家 UI 尽量中文，不展示完整模型内部思维。

规范：

```text
docs/GAMEPLAY_FLOW_V0.2.md
```

## S0-B — API / Replay Contract V0.2

已升级公共合同：

```text
schema_version = mvp-v0.2
replay_version = replay-v0.2
```

V0.2 关键公共对象：

```text
MatchSnapshot
PlayerDecisionSnapshot
BattleEscalationSnapshot
RuleSubmissionResult
PublicStrategyDecision
ReplaySnapshot
ErrorEnvelope
```

路由仍固定为：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

---

# Developer A — Backend / AI

## A0 — DynamicRuleController Cadence Migration【当前第一优先级】

建议分支：

```text
backend/controller-v02-intermission
```

当前 Controller 仍是旧 V0.1：

```text
pre-game phase 0
rounds 3 / 6 / 9 ... rule phase
```

必须迁移为：

```text
start_match()
→ active_rule = null
→ Round 1 直接可执行

每个非终局 round resolved
→ 打开玩家决策阶段
→ 允许 0 或多次失败的规则尝试
→ 最多 1 次成功规则替换
→ continue 后关闭本轮玩家决策阶段
→ 下一回合
```

硬约束：

- rule change 不清空 PublicRuleHistory；
- rule change 不清空 `no_damage_streak`；
- 只有实际伤害才能重置连续无伤害；
- rejected submission 不消耗成功规则次数；
- terminal match 不再进入玩家决策阶段；
- 原有 Engine / RuleValidator 语义不因 cadence 迁移改变。

完成标准：

- 删除产品路径中的 Phase 0；
- 每个非终局回合后均可进入 intermission；
- 同一 intermission 最多接受一次新规则；
- 新 controller tests 覆盖 Round1 / reject retry / accept lock / continue / terminal；
- 原 Engine / Rule tests 全绿。

## A1 — Match Application Service

**只有 A0 完成后才开始。**

建议分支：

```text
backend/match-service-v02
```

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
rule_change_count
completed_rounds / score_rounds
battle escalation public projection
```

关键行为：

- create 后第 1 回合前 `can_submit_rule = false`；
- 前端随后调用第一次 advance，形成“第 1 回合自动开始”的体验；
- 非终局 advance 完成后进入 `PLAYER_DECISION`；
- rule accepted 后仍停在 `PLAYER_DECISION`；
- 下一次 advance 才开始下一回合。

## A2 — FastAPI Vertical Slice

严格按 V0.2 contract 实现五个路由。

第一版继续不做：

```text
WebSocket
Redis
Celery
微服务
复杂数据库
```

---

# Developer B — Frontend

Developer B **不需要等待 A0/A1 完成**，可直接使用：

```text
contracts/fixtures/mvp-v0.2/
```

## B0 — React/Vite App Shell

建议分支：

```text
frontend/app-shell-v02
```

初始页面：

```text
《规则之外》
[开始游戏]
```

点击后进入游玩界面，不做登录/设置/排行榜。

## B1 — Game Board + Status

主界面三栏：

```text
红方 | 5×5棋盘 | 蓝方
```

顶部至少显示：

```text
已完成回合
规则制定次数
当前公共规则
战局升温
```

红蓝两侧至少显示：

```text
生命值
当前策略
实际行动
当前有效属性
```

前端不自行计算规则效果或弓命中率。

## B2 — Player Decision / Rule Panel

只根据 `PlayerDecisionSnapshot` 控制按钮。

```text
can_submit_rule = true
→ 显示可用规则输入

rule accepted
→ 输入区锁定
→ 仍显示“继续下一回合”

rule rejected
→ 不增加规则制定次数
→ 允许修改后重试
```

中文文案优先。

内部值映射：

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

不要展示：

```text
chain-of-thought
private memory
Hard Liveness
conflict_level
provider raw error
```

`BattleEscalationSnapshot` 在 UI 统一叫“战局升温”。

## B3 — Event Feed + Replay

本回合结果需要解释：

```text
移动
攻击
命中/未命中
伤害
HP变化
规则效果
战局升温变化
```

Replay V0.2 时间线：

```text
ROUND
INTERMISSION
ROUND
INTERMISSION
...
```

第 1 个 entry 必须是 Round 1，而不是旧 Phase 0。

---

# 两人当前同步点

唯一同步合同：

```text
GAMEPLAY_FLOW_V0.2
+
MVP_API_CONTRACT_V0.2
+
Pydantic/OpenAPI canonical source
+
contracts/fixtures/mvp-v0.2
```

当前可以并行：

```text
A：Controller cadence V0.2 migration
B：React/Vite + V0.2 fixture UI
```

A0 完成后：

```text
A：MatchApplicationService
B：继续 Board / Rule / Replay UI
```

---

# Sprint 1 必做玩法实验

## 1. 追逃 / 软死局实验

至少测试：

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
重复位置/重复策略
强制弓攻击次数
```

重点验证现有 `3 / 6 / 9 / 12` 阈值在“每回合人工暂停”的新节奏下是否太慢。

## 2. Agent A/B/C

当前 live Agent Gate 仍只算：

```text
connectivity evidence
```

必须比较：

```text
A deterministic heuristic
B current four-intent LLM
C richer-plan LLM + deterministic short rollout
```

如果 LLM 无客观或玩家可感知增益，允许简化/重构。

## 3. 真人试玩重点

必须观察：

- 玩家是不是每回合都必改规则；
- “继续下一回合”是不是伪选择；
- 是否很快出现固定拖延套路；
- 玩家是否理解战局升温；
- 玩家是否理解同一公共规则对红蓝不同状态产生的不同效果。

---

# 当前明确不要做

```text
回血
规则叠加
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

除非后续实验提供证据，否则这些都不是当前 P0。
