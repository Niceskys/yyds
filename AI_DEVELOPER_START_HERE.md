# AI Developer Start Here

> **所有 AI / 新开发者开始非 trivial 工作前必须先读本文件。**
>
> 目的：让新的 ChatGPT / Codex / MiMo / DeepSeek / 其他 AI 或人类开发者快速进入当前正确上下文，避免重复实现、覆盖核心语义、接口漂移、把实验结论当成产品事实，或绕过已经验证过的安全边界。

---

# 1. 当前项目状态

项目：《规则之外》（暂定名）

当前阶段：

```text
正式 MVP 产品开发（GO WITH CONDITIONS）
```

第二轮独立审计后的当前行动基线：

```text
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
```

当前 Sprint 0 公共契约：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

这表示：Engine、规则权限边界、动态规则生命周期和 provider/Agent 基本连通性已经足以开始真人可玩的 MVP。

这**不表示**：

- 游戏已经被证明好玩；
- 当前 Planner 是最终策略系统；
- 当前四分类 LLM Agent 已被证明有产品价值；
- MiMo 是最终模型选择；
- 自然语言体验已经完全稳定；
- 当前 UI / API 可以随意各自设计；
- 项目已经具备竞赛获奖保证。

---

# 2. 现在最重要的开发顺序

不要继续把“增加功能”当成第一目标。

当前固定顺序：

```text
MVP API / Replay / PublicStrategy Contract
↓
Pydantic / OpenAPI + schema-validated fixtures
↓
MatchApplicationService 与 React Mock Shell 并行
↓
revision / per-match lock / idempotency
↓
FastAPI five-route vertical slice
↓
Frontend real API integration
↓
Replay public projection
↓
Agent A/B/C
↓
真人试玩
```

如果一个新任务不在这条链上，默认先判断它是否真的比当前 P0 更重要。

---

# 3. 项目一句话定义

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

---

# 4. 当前核心架构

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

当前 StrategyIntent：

```text
PRESSURE
KITE
EVADE
HOLD
```

注意：这是**当前代码兼容结构**，不是最终产品公共合同。

公共 API 使用版本化 `PublicStrategyDecision`，为后续 richer plan 预留可选字段。不要让前端永久锁死在“四个词”。

---

# 5. LLM 的权限边界

LLM 可以：

- 把玩家自然语言翻译成候选 RuleAST；
- 对候选 RuleAST 做语义忠实性判断；
- 为 RED / BLUE 分别输出闭合的高层策略信息。

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
- 输出自由代码并执行；
- 把 hidden reasoning 交给前端作为游戏数据。

最终裁判永远是确定性代码。

---

# 6. 开工前最低读取顺序

### 所有人 / AI 都必须先读

```text
1. AI_DEVELOPER_START_HERE.md
2. README.md
3. docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
4. docs/MVP_API_CONTRACT_V0.1.md
5. docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
6. docs/MVP_FIRST_TASKS.md
7. docs/AI_COLLABORATION_PROTOCOL.md
8. 与当前任务直接相关的最新 handoff
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

### 如果任务会碰 API / 前后端契约 / Replay

必须读：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

Developer B 不得自行发明另一套 `MatchSnapshot/ReplaySnapshot/PublicStrategyDecision`。

---

# 7. Source of Truth 优先级

发生冲突时，不要凭聊天记录或旧 README 猜。

优先级：

```text
1. 最新 normative / freeze / contract 文档
2. 最新 main 上的实现与测试
3. 最新 action plan / handoff / MVP phase 文档
4. experiment / validation 记录
5. README
6. 旧设计草案 / 旧聊天上下文
```

其中 V0.1 以下语义仍以 `docs/P0_RULE_FREEZE_V0.1.md` 及 amendment 为准：

- terminal utility；
- anti-stall / Hard Liveness；
- movement occupancy；
- Rule DSL；
- symmetry。

公共 Web/API/Replay 语义以：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

为准。

---

# 8. 当前不可擅自改变的产品基线

```text
board = 5×5
units = RED 1 vs BLUE 1
product initial_hp = 4
knife_damage = 2
max_rounds = 30
rule cadence = phase0 before Round1, then after Round3/6/9/...
rule duration = UNTIL_REPLACED
```

`HP5/K2` 曾用于部分 Gate，只是为了稳定跨越多个阶段，**不是产品默认**。

### Hard Liveness

当前系统包含：

```text
previous latch
OR no_damage_streak >= 12
OR round_no >= 24
```

一旦触发，保持到终局。

不要在没有实验和规范变更的情况下自行删掉。

### Rule DSL

V0.1 是：

```text
Open Language, Closed Semantics
```

不要：

- 临时增加新 effect/condition；
- 前端自行解析规则；
- 因 false reject 放松 Validator；
- 自动把非法规则“改成差不多合法的规则”后直接执行；
- 现在扩 OR / NOT / multi-effect。

---

# 9. 第二轮审计后的证据口径

历史 `live-agent-planner-match` PASS 保留，但从现在开始正式称为：

```text
connectivity evidence
```

它证明：

- 真实 provider 可调用；
- RED/BLUE 两个 Agent 实例与 private memory 可隔离；
- Planner 可把 StrategyIntent 映射为 Action；
- Controller / Engine 可完成动态规则终局对战。

它不证明：

- LLM 比 heuristic 更聪明；
- 四分类就是最佳策略结构；
- private memory 已形成学习；
- 当前 Agent 对玩家有明显可感知价值。

因此 Sprint 1 必须比较：

```text
A deterministic heuristic
B current four-intent LLM
C richer-plan LLM + deterministic short rollout
```

在没有 A/B/C 证据前，禁止在新文档/PR 里声称“LLM Agent 必要性已经证明”。

---

# 10. 当前已知的重要实验结论

详细证据链：

```text
docs/VALIDATION_HISTORY.md
```

新开发者至少知道：

1. Prompt **不是安全边界**；
2. 曾出现非法阵营规则被 semantic laundering 成合法规则，因此引入 `NO_CANDIDATE`；
3. 曾出现 `OR → 单条件`、`OR → AND` 语义篡改，因此引入 Faithfulness Verifier 和 Deterministic Intent Guard；
4. V0.3 unseen verified holdout 达到冻结阈值；
5. Dynamic Natural-Language Match V0.2 **永久记为 FAIL**，因为一个合法简单规则被 MiMo 安全误拒；
6. false reject 是可用性债务，不能靠放松 deterministic safety 解决；
7. Agent/Planner live Gate 证明真实集成可连通，但不是 LLM value evidence。

---

# 11. 双人 + AI 责任边界

### Developer A：后端 / AI / 核心集成

默认拥有：

```text
src/rules_beyond/**
Python tests
Pydantic / OpenAPI source
MatchApplicationService
MatchRepository
FastAPI
Replay public projection
LLM provider integration
contract tests
```

### Developer B：前端 / 交互 / 可视化

默认拥有：

```text
web/**
React
TypeScript
Vite
5×5 board
Rule input / rejection / rephrase UX
Effective stats visualization
Public strategy display
Event feed
Replay timeline
frontend tests
```

### Shared review

```text
MVP_API_CONTRACT_V0.1
OpenAPI canonical schema
PublicStrategyDecision
Replay schema/version
privacy boundary
Agent A/B/C product metrics
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
canonical API schemas
replay event mapping
```

Developer B **不得把游戏规则逻辑复制到 TypeScript**。前端只渲染后端 authoritative state。

---

# 12. Sprint 0 Contract 硬约束

公共 API 必须至少包含：

```text
schema_version
match revision
Match lifecycle
RuleSubmissionResult
PublicStrategyDecision
ReplaySnapshot
ErrorEnvelope
```

写操作必须考虑：

```text
expected_revision
Idempotency-Key
per-match lock
atomic state update
```

Replay：

```text
不得再次调用模型
不得记录 chain-of-thought
不得记录 private memory
不得记录 secret / raw provider body / stack trace
```

具体字段全部以：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

为准。

---

# 13. 测试要求

### 修改核心逻辑

至少：

- 单元测试；
- 旧行为回归；
- 相关 experiment/gate 回归（若适用）；
- CI 全绿。

### 修改 API contract

至少：

- Pydantic/OpenAPI 一致；
- generated/validated frontend types；
- fixture schema validation；
- accepted/rejected/terminal/revision-conflict 样例；
- private-field exclusion test；
- breaking change version check。

### 修改 LLM Prompt / provider / semantic gate

必须区分：

```text
已暴露 regression set
vs
真正 unseen holdout
```

禁止：

- 改 Prompt 后继续把同一题库叫 unseen；
- 看到结果后临时降低 Gate；
- 删除失败实验记录；
- 只汇报最好的一次运行。

---

# 14. 明确禁止 AI 擅自做的事

禁止：

- 把 HP5 实验值设成产品默认；
- 擅自改变 3 回合 rule cadence；
- 给规则自动加 TTL；
- 绕过 RuleValidator / Faithfulness Verifier / DynamicRuleController；
- 让 LLM 直接控制 GameState；
- 让两个 Agent 共用 private strategy memory；
- 把 Dynamic NL Match V0.2 FAIL 改写成 PASS；
- 因 false reject 放宽安全 Validator；
- 展示 chain-of-thought；
- 在 Replay/API 中保存 hidden reasoning/private memory；
- 把四个 StrategyIntent 固化成永久前端合同；
- 没有 A/B/C 证据时声称 LLM Agent 已证明必要；
- 未经协调在 `main` 做大范围修改；
- 现在引入 WebSocket、Redis、Celery、微服务；
- 擅自扩展 OR/NOT/multi-effect、多单位、职业、地形、装备、账号、排行榜等 Non-goals。

---

# 15. 当前 MVP 第一目标

当前不是继续证明“系统能不能运行”，而是做出真人能从浏览器完成的纵向闭环：

```text
创建对局
→ 看到棋盘
→ 输入中文规则
→ 看见规则被接受/拒绝
→ 两个 Agent 对战
→ 看见有效属性 / public strategy / action / event
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
WebSocket
3D
移动 App
商城
```

---

# 16. Handoff 规则

以下情况必须在 PR Body 明确交接，必要时新增 `docs/handoffs/`：

- 修改架构；
- 修改 normative 规则；
- 修改 API/OpenAPI contract；
- 修改 Replay schema/version；
- 修改 PublicStrategyDecision；
- 涉及多个核心模块；
- 新实验结论影响后续路线；
- 与另一位开发者/AI 可能冲突；
- 当前工作未完成，需要下一窗口接手。

---

## 最后一条

**不要因为 AI 能快速写代码，就跳过职责边界、公共合同和证据等级。**

当前最重要的资产是：

```text
规则语义边界
+ deterministic authority
+ Agent isolation
+ 可追溯实验记录
+ 版本化公共 contract
+ 可被多人 / 多 AI 继承的协作协议
```

任何新实现都应建立在这些资产之上，而不是重新发明一套系统。
