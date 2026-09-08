# 规则之外（暂定名）

> 一个以“自然语言动态公共规则 + 双 AI 独立对抗”为核心机制的策略游戏。

## 项目一句话说明

真人玩家不直接操控角色，而是在战斗过程中为**红蓝双方共同颁布公开规则**；红方 AI 与蓝方 AI 在**私有策略记忆隔离**的条件下，各自以赢得对局为目标自主决策。玩家则通过不断改变双方共同遵守的规则，观察规则如何改变 AI 策略、行动和战局。

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

**状态：正式 MVP 产品开发。**

阶段切换记录：

**[`docs/MVP_DEVELOPMENT_START_2026-09-08.md`](docs/MVP_DEVELOPMENT_START_2026-09-08.md)**

最后一道核心架构 Gate `live-agent-planner-match` 已首次真实 PASS：

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

真实 Agent 策略变化：

```text
Phase 0:
RED  -> PRESSURE
BLUE -> KITE

Phase 1:
RED  -> PRESSURE
BLUE -> HOLD
```

这表示核心架构风险已经降低到足以开始构建真人可玩的 MVP，**不表示游戏已经被证明好玩、平衡已最终确定或比赛一定有竞争力**。

---

# AI / 新开发者必读

如果你是新的 AI、ChatGPT/Codex/MiMo/DeepSeek 会话或新开发者，**先读：**

**[`AI_DEVELOPER_START_HERE.md`](AI_DEVELOPER_START_HERE.md)**

该文件说明：

- 当前阶段；
- source of truth；
- 核心架构；
- 不可擅自修改的 V0.1 基线；
- Developer A / B 责任边界；
- 哪些文件是热点区；
- 哪些实验失败不能改写；
- 分支 / PR / CI / handoff 规则。

验证证据总索引：

**[`docs/VALIDATION_HISTORY.md`](docs/VALIDATION_HISTORY.md)**

不要只根据旧聊天、旧 README 或某一个 experiment 猜当前设计。

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

# 核心架构

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
                      ↓
          GameState / Events / Replay
```

当前闭合 StrategyIntent：

```text
PRESSURE
KITE
EVADE
HOLD
```

这是 MVP baseline，不是最终策略系统。

---

# 关键安全 / 语义原则

1. **Engine 是最终裁判。** LLM 不能直接写 HP、位置、伤害、随机数、胜负或 GameState。
2. **Open Language, Closed Semantics。** 自然语言可以开放，可执行规则必须落入封闭 Rule DSL。
3. **Prompt 不是安全边界。** 候选规则必须经过 deterministic Validator；语义忠实性另有 verifier。
4. **非法/不可表达规则宁可拒绝，也不能偷偷改成另一条合法规则。**
5. **两个 Agent 私有记忆隔离。** 只能共享公开棋盘、规则和公开历史。
6. **LLM 只输出高层 StrategyIntent。** 具体 move path / weapon 由确定性 Planner 生成。
7. **Hard Liveness 是系统兜底。** 玩家规则不能关闭。
8. **Replay 不记录 chain-of-thought / hidden reasoning。**

P0 唯一冻结规范：

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

完整证据链：

**[`docs/VALIDATION_HISTORY.md`](docs/VALIDATION_HISTORY.md)**

---

# 仍未解决的问题

### Natural-language safe false reject

Dynamic Natural-Language Match V0.2 仍永久记为 **FAIL**：一条合法的“双方移动距离增加1格”曾被 MiMo 单次误判为 `NO_CANDIDATE`。

这是可用性问题，不是 unsafe accept。后续通过：

- 清晰拒绝反馈；
- 重新措辞；
- 经过设计的安全 retry；

处理。

**不得为了减少 false reject 放松 RuleValidator / Faithfulness safety boundary。**

### “好玩”尚未验证

当前验证证明了系统可以工作，不等于玩家体验已经成立。MVP 阶段必须通过真人试玩、Replay、规则效果可视化和竞赛 Demo 继续验证。

---

# 双人 + AI 并行开发

正式分工：

### Developer A — 后端 / AI / 核心集成

```text
Python
Engine integration
DynamicRuleController
Natural Language pipeline
Agent / Planner
FastAPI
Pydantic schema
Match Service
Replay serialization
API contract
```

### Developer B — 前端 / 交互 / 可视化

```text
React
TypeScript
Vite
5×5 Board
HP / Round / Rule UI
Rule submission feedback
Strategy / Event display
Replay timeline
frontend tests
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
Developer A:
API Contract V0.1
→ Match Application Service
→ FastAPI vertical slice
→ Replay serialization

Developer B:
React/Vite Mock Shell
→ Board / Rule Panel / Status
→ Event / Strategy view
→ Replay timeline
→ 接真实 API
```

第一个真人可玩纵向切片必须让玩家无需手工改 JSON 或运行 CLI，就能完成：

```text
创建对局
→ 看见棋盘
→ 输入中文规则
→ 两个独立 AI 对战
→ 看见规则和策略变化
→ 下一规则阶段继续改规则
→ 终局
→ Replay
```

---

# 当前明确不做

MVP 范围外：

```text
账号系统
排行榜
匹配大厅
真人多人联机
商城
成就
复杂数据库
多单位
职业 / 技能树
地图障碍 / 地形
装备系统
大量新 DSL effect
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

docs/MVP_DEVELOPMENT_START_2026-09-08.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/MVP_FIRST_TASKS.md
docs/VALIDATION_HISTORY.md
docs/AI_COLLABORATION_PROTOCOL.md

docs/P0_RULE_FREEZE_V0.1.md
docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md
docs/RULE_DSL_VALIDATOR_IMPLEMENTATION_V0.1.md
docs/PUBLIC_RULE_HISTORY_V0.1.md
docs/SEMANTIC_FAITHFULNESS_GATE_V0.1.md

docs/experiments/
docs/handoffs/
```

旧设计草案仍有历史价值，但如果与最新 normative / MVP 文档冲突，应以后者为准。
