# AI Developer Start Here

> **所有 AI / 新开发者开始非 trivial 工作前必须先读本文件。**
>
> 目的：让新的 ChatGPT / Codex / MiMo / DeepSeek / 其他 AI 或人类开发者快速进入当前正确上下文，避免重复实现、覆盖核心语义、把实验结论当成产品默认，或绕过已经验证过的安全边界。

## 1. 当前项目状态

项目：《规则之外》（暂定名）

当前阶段：

```text
正式 MVP 产品开发
```

阶段切换依据见：

```text
docs/MVP_DEVELOPMENT_START_2026-09-08.md
```

这表示核心工程架构已经达到“可以开始做真人可玩的 MVP”的水平，**不表示**：

- 游戏已经被证明好玩；
- 当前平衡数值已经最终确定；
- 当前 Planner 已经是最终策略系统；
- 当前自然语言体验已经完全稳定；
- 项目已经具备竞赛获奖保证。

## 2. 项目一句话定义

真人玩家不直接操控棋子，而是在战斗过程中为红蓝双方制定**对称的公共自然语言规则**；两个独立 AI 在相同公开规则下各自以获胜为目标进行对抗，玩家通过改变规则观察并影响双方策略与战局。

核心循环：

```text
制定公共规则
→ 两个独立 AI 适应规则
→ 确定性 Planner 生成动作
→ Engine 同步结算
→ 玩家观察变化
→ 下一规则阶段再次修改
→ 终局
→ Replay
```

## 3. 当前核心架构

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

### LLM 的权限边界

LLM 可以：

- 把玩家自然语言翻译成候选 RuleAST；
- 对候选 RuleAST 做语义忠实性判断；
- 为 RED / BLUE 分别输出闭合的高层 StrategyIntent。

LLM **不能**：

- 直接修改 HP；
- 直接修改位置；
- 直接决定伤害；
- 直接决定随机数；
- 直接决定胜负；
- 直接写 active rule；
- 绕过 RuleValidator；
- 绕过 DynamicRuleController；
- 让 RED / BLUE 共享 private memory；
- 输出动作坐标或移动路径后直接执行。

最终裁判永远是确定性代码。

## 4. 开工前最低读取顺序

### 所有人 / AI 都必须先读

```text
1. AI_DEVELOPER_START_HERE.md                 ← 本文件
2. README.md
3. docs/MVP_DEVELOPMENT_START_2026-09-08.md
4. docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
5. docs/MVP_FIRST_TASKS.md
6. docs/AI_COLLABORATION_PROTOCOL.md
7. 与当前任务直接相关的最新 handoff
```

### 如果任务会碰规则 / Engine / Agent，再读

```text
docs/P0_RULE_FREEZE_V0.1.md
docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md
docs/RULE_DSL_VALIDATOR_IMPLEMENTATION_V0.1.md
docs/PUBLIC_RULE_HISTORY_V0.1.md
docs/SEMANTIC_FAITHFULNESS_GATE_V0.1.md
docs/VALIDATION_HISTORY.md
```

### 如果任务会碰 API / 前后端契约

先读：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

如果该文件尚未存在，则 **Developer A 的第一责任是先冻结它**；Developer B 可以先用 fixture/mock 开发，但不得自行发明另一套契约。

## 5. Source of Truth 优先级

发生冲突时，不要凭聊天记录或旧 README 猜。

优先级：

```text
1. 最新 normative / freeze 文档
2. 最新 main 上的实现与测试
3. 最新 handoff / MVP phase 文档
4. experiment / validation 记录
5. README
6. 旧设计草案 / 旧聊天上下文
```

其中，V0.1 以下语义以 `docs/P0_RULE_FREEZE_V0.1.md` 及其 amendment 为准：

- terminal utility；
- anti-stall / Hard Liveness；
- movement occupancy；
- Rule DSL；
- symmetry。

## 6. 当前不可擅自改变的基线

### 产品基线

```text
board = 5×5
units = RED 1 vs BLUE 1
product initial_hp = 4
knife_damage = 2
max_rounds = 30
rule cadence = phase0 before Round1, then after Round3/6/9/...
rule duration = UNTIL_REPLACED
```

注意：

```text
HP5/K2
```

曾用于部分工程实验 / Gate，只是为了稳定跨越多个阶段，**不是产品默认**。

### Hard Liveness

当前系统 Hard Liveness 包含：

```text
previous latch
OR no_damage_streak >= 12
OR round_no >= 24
```

一旦触发，保持到终局。

不要为了“更自然”或“更好玩”在没有实验和规范变更的情况下自行删掉。

### Rule DSL

V0.1 是 **Open Language, Closed Semantics**：

自然语言可以开放，但可执行语义必须落入封闭 DSL。

不要：

- 临时增加新的 effect/condition；
- 前端自行解析规则；
- 为了让 LLM 更容易通过而放松 Validator；
- 自动把非法规则“改成差不多合法的规则”。

## 7. 当前已知的重要实验结论

详细证据链见：

```text
docs/VALIDATION_HISTORY.md
```

新开发者至少要知道以下几点：

1. 自然语言 Prompt **不是安全边界**；
2. 曾出现“非法阵营规则被偷偷洗成合法规则”的风险，因此引入 `NO_CANDIDATE`；
3. 曾出现 `OR → 单条件`、`OR → AND` 的语义篡改，因此引入 Faithfulness Verifier 和 Deterministic Intent Guard；
4. V0.3 unseen verified holdout 已通过；
5. Dynamic Natural-Language Match V0.2 **仍永久记为 FAIL**，原因是一个合法简单规则被 MiMo 安全误拒绝；
6. 该 false reject 是 MVP 可用性债务，**不得通过放松 deterministic safety 边界解决**；
7. live Agent / Planner Gate 已 PASS，因此正式进入 MVP 开发；
8. 当前 StrategyIntent 只有：

```text
PRESSURE
KITE
EVADE
HOLD
```

这是 MVP baseline，不是最终策略质量结论。

## 8. 双人 + AI 责任边界

### Developer A：后端 / AI / 核心集成

默认拥有：

```text
src/rules_beyond/**
Python tests
backend/server application layer
FastAPI
Pydantic schema
Match Service
Replay serialization
LLM provider integration
API contract
```

### Developer B：前端 / 交互 / 可视化

默认拥有：

```text
web/**
React
TypeScript
Vite
5×5 board
Rule input UI
Strategy display
Event feed
Replay timeline
frontend tests
```

### 热点文件

除非明确协调，不要并行修改：

```text
engine.py
rule_engine.py
dynamic_rule_controller.py
strategy_agent.py
rule_dsl.py
rule_validator.py
共享 API schema / contract
```

Developer B **不得把游戏规则逻辑复制到 TypeScript**。前端只渲染后端 authoritative state。

## 9. AI 工作协议

每个非 trivial 任务按：

```text
最新 main
→ 读取相关规范 / handoff
→ 一个任务一个 branch
→ 一个主要实现 AI
→ 测试
→ PR
→ 独立 review
→ CI
→ 必要时 handoff
→ merge
```

### 开工前必须回答

AI 在动代码前至少应能明确：

```text
1. 我正在解决什么问题？
2. 哪个模块拥有这个职责？
3. 哪些文件是 source of truth？
4. 哪些文件是热点区？
5. 我明确不改变什么？
6. 怎样用测试证明没有破坏旧语义？
```

如果答不出来，先读文档，不要直接改代码。

## 10. 测试要求

### 修改核心逻辑

至少需要：

- 单元测试；
- 旧行为回归；
- 相关 experiment / gate 回归（若适用）；
- CI 全绿。

### 修改 LLM Prompt / provider / semantic gate

必须区分：

```text
已暴露 regression set
vs
真正 unseen holdout
```

禁止：

- 改完 Prompt 后继续把同一题库叫 unseen；
- 看到结果后临时降低 Gate；
- 删除失败实验记录；
- 只汇报最好的一次随机运行。

### 修改前端

不得用前端 mock 的“看起来能跑”代替后端 contract 测试。Mock/fixture 必须与冻结 API contract 对齐。

## 11. 明确禁止 AI 擅自做的事

禁止：

- 把 HP5 实验值设成产品默认；
- 擅自改变 3 回合 rule cadence；
- 给规则自动加 TTL；
- 绕过 RuleValidator；
- 绕过 Faithfulness Verifier；
- 绕过 DynamicRuleController；
- 让 LLM 直接控制 GameState；
- 让两个 Agent 共用 private strategy memory；
- 把 Dynamic NL Match V0.2 FAIL 改写成 PASS；
- 因为 false reject 而放宽安全 Validator；
- 重新实现已经存在的 Engine / Agent / Planner，只因为没先搜索仓库；
- 展示 chain-of-thought；
- 在 Replay / API 中保存或暴露 hidden reasoning；
- 未经协调在 `main` 做大范围修改；
- 为了“顺手完善”擅自扩展职业、地形、道具、多单位、账号、排行榜等 Non-goals。

## 12. 当前 MVP 第一目标

当前不是继续证明“系统能不能运行”，而是做出真人能从浏览器完成的纵向闭环：

```text
创建对局
→ 看到棋盘
→ 输入中文规则
→ 两个独立 AI 对战
→ 看到回合状态 / StrategyIntent / 规则效果
→ Round3 后再次修改规则
→ 对局终局
→ Replay
```

在这条闭环稳定之前，不优先开发：

```text
账号系统
排行榜
多人大厅
复杂数据库
多单位
职业 / 技能
地形
装备
3D
Unity / Godot
移动 App
商城
```

## 13. 当前第一批任务

以以下文档为准：

```text
docs/MVP_FIRST_TASKS.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
```

总体顺序：

```text
Developer A:
API Contract V0.1
→ Match Application Service
→ FastAPI vertical slice
→ Replay serialization

Developer B:
React/Vite app shell + fixtures
→ Board / status / rule panel
→ Event / strategy view
→ Replay timeline
→ 接真实 API
```

## 14. Handoff 规则

以下情况必须在 PR Body 明确交接，必要时新增 `docs/handoffs/`：

- 修改架构；
- 修改 normative 规则；
- 修改 API contract；
- 涉及多个核心模块；
- 新实验结论将影响后续路线；
- 与另一位开发者 / AI 可能冲突；
- 当前工作未完成，需要下一窗口接手。

普通拼写、局部无行为重构、小型自解释测试无需制造 handoff 噪声。

---

## 最后一条

**不要因为 AI 能快速写代码，就跳过职责边界、规范和测试。**

这个项目目前最有价值的资产不是代码量，而是已经建立的：

```text
规则语义边界
+ deterministic authority
+ Agent isolation
+ 可追溯实验记录
+ 可以被多人 / 多 AI 继承的开发协议
```

任何新实现都应建立在这些资产之上，而不是重新发明一套系统。
