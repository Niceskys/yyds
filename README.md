# 规则之外（暂定名）

> 一个以“自然语言动态公共规则 + 双 AI 独立对抗”为核心机制的策略游戏。

## 项目一句话说明

真人玩家不直接操控角色，而是在战斗过程中为**红蓝双方共同颁布公开规则**；红方 AI 与蓝方 AI 在**私有策略记忆隔离**的条件下，各自以赢得对局为目标自主决策。玩家通过不断改变双方共同遵守的规则，观察规则如何改变 AI 策略、行动和战局。

核心体验：

```text
制定公共规则
→ 两个独立 AI 适应规则
→ 确定性 Planner 生成具体动作
→ Engine 同步结算
→ 玩家观察变化
→ 下一规则阶段再次修改
→ 终局
→ Replay
```

这不是“玩家操控棋子打 AI”，也不是“两个大模型自由聊天式对战”。

---

# 当前阶段

**状态：正式 MVP 产品开发（GO WITH CONDITIONS）。**

第二轮独立审计后的当前行动基线：

**[`docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md`](docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md)**

当前 Sprint 0 唯一公共接口/Replay 规范：

**[`docs/MVP_API_CONTRACT_V0.1.md`](docs/MVP_API_CONTRACT_V0.1.md)**

最重要的当前结论：

```text
Engine / RuleValidator / DynamicRuleController 基础已经足以支持 MVP 纵向切片

但：
当前 LLM Agent 的“产品必要性”尚未被证明
```

历史 `live-agent-planner-match` 首次真实 PASS 仍然保留：

```text
model = mimo-v2.5-pro
seed = 1270000
result = RED_WIN
rounds = 5
gate_passed = true
gate_failures = []
planner_snapshot_errors = 0
PLAYER_RULE_REPLACED = 2
```

后续对这项结果的正式解释是：

```text
connectivity evidence
```

即它证明真实 provider、两个隔离 Agent、Planner、Controller 和 Engine 可以连通并完成终局。

它**不证明**：

- LLM 比 deterministic heuristic 更好；
- 四个 StrategyIntent 是最终策略结构；
- private memory 已经形成真正学习；
- 游戏已经好玩；
- MiMo 应永久成为默认模型；
- 当前 Agent 架构已经可以冻结。

Sprint 1 必须用 A/B/C 继续验证这些问题。

---

# AI / 新开发者必读

如果你是新的 AI、ChatGPT/Codex/MiMo/DeepSeek 会话或新开发者，先读：

**[`AI_DEVELOPER_START_HERE.md`](AI_DEVELOPER_START_HERE.md)**

然后优先读：

```text
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
docs/MVP_API_CONTRACT_V0.1.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/MVP_FIRST_TASKS.md
docs/AI_COLLABORATION_PROTOCOL.md
```

验证证据总索引：

**[`docs/VALIDATION_HISTORY.md`](docs/VALIDATION_HISTORY.md)**

不要只根据旧聊天、旧 README 或单个 experiment 猜当前设计。

---

# 当前 V0.1 产品基线

```text
board = 5×5
units = RED 1 vs BLUE 1
initial_hp = 4
base_move_range = 1
knife_range = 1
knife_damage = 2
bow_base_range = 3
bow_damage = 1
max_rounds = 30
```

弓命中率基础模型：

```text
P(hit) = 1 * 0.5^(distance - 1)
```

双方同步决策、同步结算。

玩家规则阶段：

```text
phase 0：Round 1 前
phase 1：Round 3 结算后
phase 2：Round 6 结算后
...
```

规则持续时间：

```text
UNTIL_REPLACED
```

没有自动“三回合 TTL”。规则阶段频率和规则寿命是两件事。

> 注意：部分工程 Gate 使用过 `HP5/K2`，只是为了稳定跨越多个阶段，**不是产品默认**。

---

# 当前核心架构

```text
玩家自然语言
      ↓
Deterministic Intent Guard
      ↓
LLM Rule Translator
      ↓
RuleValidator
      ↓
Faithfulness Verifier
      ↓
DynamicRuleController
      ↓
┌──────────────────────┬──────────────────────┐
│ RED Isolated Agent   │ BLUE Isolated Agent  │
│ private strategy mem │ private strategy mem │
└──────────┬───────────┴──────────┬───────────┘
           ↓                      ↓
      StrategyIntent         StrategyIntent
           └──────────┬───────────┘
                      ↓
          DeterministicIntentPlanner
                      ↓
                    Action
                      ↓
               Game Engine
```

当前 Agent 代码的闭合 StrategyIntent：

```text
PRESSURE
KITE
EVADE
HOLD
```

它是**当前实现兼容结构，不是最终产品合同**。

公共 API 使用带版本号的 `PublicStrategyDecision`，为后续 richer strategy plan 预留可选字段，避免前端被四分类永久锁死。

---

# 当前 Sprint 0：先统一“前后端语言”

正式开发第一优先级不是继续扩功能，而是让前端和后端使用同一份公共合同。

当前冻结路由：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

当前必须统一的对象：

```text
MatchSnapshot
RuleSubmissionResult
PublicStrategyDecision
ReplaySnapshot
ErrorEnvelope
```

并且从第一版就加入：

```text
schema_version
revision
Idempotency-Key
per-match lock
public/private projection
Replay no-model-call
```

详细规范：

**[`docs/MVP_API_CONTRACT_V0.1.md`](docs/MVP_API_CONTRACT_V0.1.md)**

---

# 关键安全 / 语义原则

1. **Engine 是最终裁判。** LLM 不能直接写 HP、位置、伤害、随机数、胜负或 GameState。
2. **Open Language, Closed Semantics。** 自然语言可以开放，可执行规则必须落入封闭 Rule DSL。
3. **Prompt 不是安全边界。** 候选规则必须经过 deterministic Validator；语义忠实性另有 verifier。
4. **非法/不可表达规则宁可拒绝，也不能偷偷改成另一条合法规则。**
5. **两个 Agent 私有记忆隔离。** 只能共享公开棋盘、规则和公开历史。
6. **当前 LLM 只输出高层 StrategyIntent。** 具体动作由确定性 Planner 生成；后续 richer plan 仍必须保持 closed/verifiable。
7. **Hard Liveness 是系统兜底。** 玩家规则不能关闭。
8. **Public Replay 不记录 chain-of-thought / hidden reasoning / private Agent memory。**
9. **规则翻译失败不修改 active rule。**
10. **策略模型失败必须允许 deterministic fallback，而不是让整局卡死。**

P0 唯一冻结规则规范：

**[`docs/P0_RULE_FREEZE_V0.1.md`](docs/P0_RULE_FREEZE_V0.1.md)**

Round24 amendment：

**[`docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md`](docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md)**

---

# 已验证的重要结论

当前工程证据支持：

- deterministic Engine 可运行、可通过 seed 重现；
- Rule DSL / Validator / Evaluator 可执行；
- PublicRuleHistory 可确定性更新；
- 动态公共规则可在对局中替换并持续生效；
- Hard Liveness 可避免已知拖延策略无限拖局；
- 自然语言 verified pipeline 已建立；
- MiMo `mimo-v2.5-pro` 在第一次 V0.3 unseen verified holdout 上达到：

```text
LEGAL semantic correct = 24/25
NO_CANDIDATE blocked = 25/25
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
```

- RED / BLUE 私有 Agent session 与 memory 已隔离；
- live MiMo Agent + deterministic Planner + Controller + Engine 已完成真实终局对战。

这些证据不能自动推出“LLM Agent 有必要”“游戏好玩”或“比赛有竞争力”。

完整证据链：

**[`docs/VALIDATION_HISTORY.md`](docs/VALIDATION_HISTORY.md)**

---

# 当前仍未解决的问题

## 1. LLM Agent 是否真的有价值

这是当前最大 AI 风险。

Sprint 1 必须比较：

```text
A deterministic heuristic
B current four-intent LLM
C richer-plan LLM + deterministic short rollout
```

如果 LLM 无明显可测/可感知增益，就允许简化或重构 Agent，而不是为了“AI 项目”叙事强留。

## 2. Natural-language safe false reject

Dynamic Natural-Language Match V0.2 仍永久记为 **FAIL**：一条合法的“双方移动距离增加1格”曾被 MiMo 单次误判为 `NO_CANDIDATE`。

这是可用性问题，不是 unsafe accept。

MVP 处理方式：

- 清晰拒绝反馈；
- suggested rephrase；
- 玩家确认后重新提交；
- 网络/协议错误才做受控 retry。

**不得为了减少 false reject 放松 RuleValidator / Faithfulness safety boundary。**

## 3. “好玩”尚未验证

当前验证证明系统可以工作，不等于玩家体验已经成立。

尤其需要验证：

- “延长战斗”是否退化成单一拖延套路；
- 玩家能否快速理解一条公共规则对双方不同的实际影响；
- Hard Liveness 是否让玩家感觉系统强行抢走控制权。

---

# 双人 + AI 并行开发

### Developer A — 后端 / AI / 核心集成

```text
Python
Engine integration
DynamicRuleController
Natural Language pipeline
Agent / Planner
Pydantic / OpenAPI
MatchApplicationService
FastAPI
Replay public projection
contract tests
```

### Developer B — 前端 / 交互 / 可视化

```text
React
TypeScript
Vite
5×5 Board
HP / Round / Lifecycle UI
Rule submission / rejection / rephrase
Effective modifier view
Public strategy view
Event feed
Replay timeline
```

详细计划：

**[`docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md`](docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md)**

第一批任务：

**[`docs/MVP_FIRST_TASKS.md`](docs/MVP_FIRST_TASKS.md)**

协作协议：

**[`docs/AI_COLLABORATION_PROTOCOL.md`](docs/AI_COLLABORATION_PROTOCOL.md)**

---

# 当前 MVP 主线

```text
Contract
↓
Pydantic/OpenAPI + schema-validated fixtures
↓
┌─────────────────────────┬──────────────────────────┐
│ MatchApplicationService │ React/Vite Mock Shell    │
│ in-memory repository    │ Board/Rule/Replay UI     │
└─────────────────────────┴──────────────────────────┘
↓
FastAPI five routes
↓
Frontend real API integration
↓
Replay public projection
↓
Agent A/B/C
↓
真人试玩
```

第一条真人可玩纵向切片必须让玩家无需手工改 JSON 或运行 CLI，就能完成：

```text
创建对局
→ 看见棋盘
→ 输入中文规则
→ 两个独立 AI 对战
→ 看见规则/有效属性/策略/行动变化
→ 下一规则阶段继续改规则
→ 终局
→ Replay
```

---

# 当前明确不做

```text
OR / NOT / multi-effect DSL
WebSocket
Redis
Celery
Event Bus
微服务
账号系统
排行榜
匹配大厅
真人多人联机
商城
成就
复杂数据库起步
多单位
职业 / 技能树
地图障碍 / 地形
装备系统
MCTS
Unity / Godot 客户端
3D
移动 App
高成本美术资产
```

如果某项不是完成“真人规则 → AI 对战 → 观察 → 再改规则 → 终局 → Replay”所必需，默认延后。

---

# 主要文档入口

```text
AI_DEVELOPER_START_HERE.md

docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
docs/MVP_API_CONTRACT_V0.1.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/MVP_FIRST_TASKS.md
docs/AI_COLLABORATION_PROTOCOL.md
docs/VALIDATION_HISTORY.md

docs/P0_RULE_FREEZE_V0.1.md
docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md
docs/RULE_DSL_VALIDATOR_IMPLEMENTATION_V0.1.md
docs/PUBLIC_RULE_HISTORY_V0.1.md
docs/SEMANTIC_FAITHFULNESS_GATE_V0.1.md

docs/experiments/
docs/handoffs/
```

旧设计草案仍有历史价值，但如果与最新 normative / action 文档冲突，应以后者为准。
