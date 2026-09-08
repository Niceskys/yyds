# 《规则之外》MVP 双人 + AI 并行开发计划

状态：正式 MVP 开发

本计划适用于两名开发者各自使用 AI 辅助开发的场景。目标是最大化并行效率，同时避免两个 AI 同时改核心热点文件导致冲突或语义漂移。

---

## 一、总原则

### 开发者 A：后端 / AI / 核心集成

主要责任域：

```text
Python
Game Engine integration
DynamicRuleController
Natural Language rule pipeline
Strategy Agent / Planner
FastAPI
API schema
match service
replay/log serialization
backend tests
```

### 开发者 B：前端 / 交互 / 可视化

主要责任域：

```text
React
TypeScript
Vite
5x5 board UI
unit / HP / round visualization
public-rule input UI
rule rejection feedback
strategy/event display
replay timeline
frontend tests
```

### 禁止的并行方式

不要让 A、B 或两个 AI：

- 同时修改 `engine.py`；
- 同时修改 `dynamic_rule_controller.py`；
- 同时修改 `strategy_agent.py`；
- 同时修改 Rule DSL / Validator；
- 在没有 API contract 的情况下各自猜测请求/响应结构；
- 为了前端方便直接把游戏规则逻辑复制到 TypeScript；
- 让前端自行判断规则是否合法；
- 让 LLM 直接修改 GameState。

---

# 二、目录责任边界

## 开发者 A 默认拥有

```text
src/rules_beyond/**
tests/**（Python）
server/** 或后续确定的后端应用目录
pyproject.toml
backend migration / persistence files
```

注意：核心文件属于热点区，A 自己也应一任务一分支，不要同时让多个 AI 修改同一热点文件。

## 开发者 B 默认拥有

建议新建：

```text
web/
  src/
  public/
  tests/
  package.json
  vite.config.*
  tsconfig.*
```

B 不直接修改 Python Engine 来“配合 UI”。如果接口不足，提出 API contract 变更，由 A 负责后端实现。

## 共享区

```text
docs/MVP_API_CONTRACT_V0.1.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
README.md
.github/workflows/**
```

共享区变更需要在 PR 中明确说明，避免两个分支同时编辑。

---

# 三、Sprint 0：先冻结前后端契约

这是正式 MVP 开发的第一件事。

## A0 — API Contract V0.1

负责人：开发者 A

先定义，不急着做完整服务器实现。

至少覆盖：

```text
POST /api/matches
GET  /api/matches/{match_id}
POST /api/matches/{match_id}/rules
POST /api/matches/{match_id}/advance
GET  /api/matches/{match_id}/replay
```

V0.1 可以先用显式“advance”推进回合，避免第一版就引入 WebSocket / 实时房间复杂度。后续如果产品体验需要，再增加流式推送。

需要冻结的主要 DTO：

```text
MatchSnapshot
UnitSnapshot
RulePhaseSnapshot
RuleSubmissionRequest
RuleSubmissionResult
RoundEvent
StrategyDecisionPublicView
ReplaySnapshot
ErrorEnvelope
```

API contract 必须说明：

- 哪些字段是 authoritative；
- 哪些是纯展示字段；
- enum 值；
- nullable 语义；
- rule phase due 时能否 advance；
- invalid/NO_CANDIDATE/faithfulness rejection 的返回形式；
- Agent 私有 memory / hidden reasoning 永不通过 API 暴露。

## B0 — 前端骨架 + Mock Contract

负责人：开发者 B

A0 contract 草案出来后，B 可以立即使用固定 fixture 开工，不需要等 FastAPI 完成。

第一批页面只需要：

```text
/           MVP 单页入口
```

组件建议：

```text
GameBoard
UnitToken
StatusPanel
RulePanel
StrategyPanel
EventFeed
ReplayTimeline
MatchControls
```

B0 完成标准：

- 5×5 棋盘能根据 fixture 渲染；
- 红蓝单位、HP、回合数可显示；
- active rule 可显示；
- rule phase due 与普通战斗阶段视觉上可区分；
- 能输入中文规则并模拟 accepted/rejected 两种结果；
- 能渲染回合事件与 strategy intent；
- 不实现任何游戏规则判断。

---

# 四、Sprint 1：形成第一个可玩的纵向切片

## 开发者 A — Backend Vertical Slice

### A1. Match Application Service

不要让 FastAPI route 直接操作 Engine 内部对象。

新增 application/service 层，大致职责：

```text
create_match()
get_match_snapshot()
submit_public_rule()
advance_match()
get_replay()
```

service 层负责把：

```text
DynamicRuleController
NaturalLanguageVerifiedAdapter
RED/BLUE IsolatedStrategyAgent
DeterministicIntentPlanner
```

组合起来。

### A2. FastAPI

第一版只要求：

- Pydantic schema；
- 明确错误码；
- CORS 仅开发环境；
- `MIMO_API_KEY` 从环境读取；
- secret 不进入响应/log/replay；
- API 与 Engine 分层。

### A3. Match State

MVP 第一阶段允许：

```text
进程内 MatchStore
```

但接口设计必须允许后续替换 SQLite。

当第一条纵向切片跑通后再加 SQLite；不要一开始花大量时间设计复杂数据库。

### A4. Replay Serialization

Replay 至少记录：

```text
match seed
initial config
每个 rule phase 的玩家文本
translation / rejection public status
accepted RuleAST（若有）
每回合双方公开 StrategyIntent
具体 Action
Engine events
round-end GameState
terminal result
```

禁止记录模型 chain-of-thought 或私有 hidden reasoning。

## 开发者 B — Frontend Vertical Slice

### B1. Board

- 固定 5×5；
- 红蓝单位；
- 当前 HP；
- 当前回合；
- 当前 active public rule；
- rule phase due 提示。

### B2. Rule Input

只有在 rule phase due 时允许提交。

至少区分：

```text
ACCEPTED
NO_CANDIDATE
RULE_REJECTED
MODEL_ERROR
FAITHFULNESS_REJECTED / 等价公开错误分类
```

产品上不要把内部 Validator stack trace 暴露给玩家。

### B3. Agent Strategy Display

只展示：

```text
PRESSURE
KITE
EVADE
HOLD
```

以及必要的简短产品文案。

不要展示 chain-of-thought。

### B4. Replay

第一版允许简单 timeline：

```text
Round 1
Round 2
Rule Phase 1
Round 4
...
```

点击某节点恢复该节点的棋盘/HP/规则/事件快照。

---

# 五、第一条可玩 MVP 的验收条件

只有满足以下全部条件，才算完成“第一条真人可玩纵向切片”：

1. 浏览器能创建新对局；
2. 能看到 5×5 棋盘和红蓝双方；
3. Phase 0 能输入中文公共规则；
4. 后端真正经过 verified NL pipeline；
5. 两个独立 Agent 真正调用策略模型；
6. Planner 生成具体动作；
7. Engine 完成同步结算；
8. 前端能看到每回合状态变化；
9. Round 3 后进入下一规则阶段；
10. 新规则可替换旧规则；
11. 非法/不可表达规则有清晰反馈且不会破坏对局；
12. 对局能进入 terminal；
13. Replay 可以回看整局关键状态；
14. 不需要开发者手动改 JSON 或运行 CLI 才能完成上述流程。

---

# 六、当前明确不做

正式 MVP 已开始，但范围仍严格控制。

当前不做：

```text
账号系统
排行榜
匹配大厅
多人真人联机
云存档
复杂权限系统
商城
成就
多单位
职业/技能树
地图障碍/地形
装备系统
大量新 DSL effect
Unity/Godot 客户端
3D
高成本美术资产
移动 App
```

如果某项不是完成“真人输入规则 → AI 对战 → 观察 → 再改规则 → 终局 → Replay”所必需，默认放到后面。

---

# 七、分支与 PR 规则

每人 + AI 都按：

```text
一个任务
→ 一个 branch
→ 一个主要实现 AI
→ 本地/CI 测试
→ PR
→ 独立 review
→ merge
```

建议分支前缀：

开发者 A：

```text
backend/api-contract-v01
backend/match-service
backend/fastapi-shell
backend/replay-serialization
```

开发者 B：

```text
frontend/app-shell
frontend/game-board
frontend/rule-panel
frontend/replay-timeline
```

不要建立类似：

```text
dev-all
mvp-big-update
ai-work
```

这种长期混合分支。

---

# 八、两人每天对齐的最小信息

每次准备合并前，只需要同步 5 项：

```text
1. 我改了哪些路径
2. API contract 有没有变化
3. 是否改了 shared enum / schema
4. CI 是否全绿
5. 下一分支会碰哪些文件
```

如果 API contract 没变，A/B 应尽量独立推进，不需要频繁等待对方。

---

# 九、当前优先级

从现在开始顺序固定为：

```text
P0  API Contract V0.1
P0  Frontend Mock Shell
P0  Backend Match Service
P0  FastAPI vertical slice
P0  Frontend real API integration
P0  Replay
P1  natural-language rejection UX
P1  Agent strategy visualization
P1  basic SQLite persistence
P1  E2E test
P2  polish / animation / competition demo packaging
```

除非出现核心 blocker，不应重新回到大规模静态 benchmark 或继续扩充 Rule DSL。
