# 规则之外（暂定名）

> 一个以“自然语言动态公共规则 + 双 AI 独立对抗”为核心机制的策略游戏。

## 立即试玩

Windows PowerShell（需要 Python 3.11+、Node.js 20+ 和一个兼容 OpenAI Chat Completions 的模型 API）：

```powershell
git clone https://github.com/Niceskys/yyds.git
cd yyds
.\scripts\start-local-playtest.ps1
```

脚本会询问 API 地址、模型名并隐藏输入 key，按需安装依赖、启动本地后端和前端，然后打开游戏。GLM、OpenAI 兼容中转服务及本地兼容服务均可接入。按 `Ctrl+C` 可停止它启动的两个服务。其他平台、兼容选项、端口覆盖和故障排查见 [`docs/PLAYTEST_QUICKSTART.md`](docs/PLAYTEST_QUICKSTART.md)。

> Developer A 可以使用此入口试玩和记录反馈；这不会解除 `DEVELOPER_A_GATE.md` 中的后端开发暂停状态。

## 项目一句话说明

真人玩家不直接操控角色，而是观察两个各自以获胜为目标的独立 AI，在**每个完整回合结束后**决定是否替换一条同时约束红蓝双方的公共规则。玩家的当前目标不是帮助红方或蓝方，而是在有限生命值和不断升高的“战局升温”压力下，尽量让对局持续更多回合。

当前核心体验：

```text
开始游戏
→ 第1回合无玩家规则自动进行
→ 两个独立 AI 同时适应当前战局并决策
→ 确定性 Planner 生成具体动作
→ Engine 同步结算一个完整回合
→ 游戏暂停
→ 玩家观察双方策略 / 行动 / 属性 / 战局升温
→ 直接继续，或尝试替换一条公共规则
→ 玩家点击“继续下一回合”
→ 终局
→ Replay
```

这不是“玩家操控棋子打 AI”，也不是“两个大模型自由聊天式对战”。

---

# 当前阶段

**状态：可真实试玩的 MVP 纵向闭环已完成；B5A 核心因果反馈进行中。**

第二轮独立审计后的行动基线：

**[`docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md`](docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md)**

当前最新玩法基线：

**[`docs/GAMEPLAY_FLOW_V0.2.md`](docs/GAMEPLAY_FLOW_V0.2.md)**

当前唯一公共 API / Replay 规范：

**[`docs/MVP_API_CONTRACT_V0.2.md`](docs/MVP_API_CONTRACT_V0.2.md)**

V0.1 合同和旧 cadence 文档保留为历史证据，但不再作为新产品实现依据。

当前工程状态：

```text
A0–A3 后端 V0.2 纵向切片              DONE
B0–B4 React / HTTP / Replay            DONE
M1 Chromium + live MiMo 可玩验收       PASSED
B5A.1 回合因果过渡                     DONE
B5A.2 规则结果反馈                     DONE
B5A.3 战局升温反馈                     DONE
B5A Replay before/after 过渡            REMAINING
```

当前 LLM Agent 的产品必要性仍需后续 A/B/C 实验证明；可连通、可完成对局不等于已经证明它优于确定性策略。

---

# 当前 V0.2 产品基线

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

## 一个完整回合

```text
RED AI 读取同一回合开始状态
BLUE AI 读取同一回合开始状态
↓
双方分别产生公开策略
↓
Planner 分别生成具体动作
↓
Engine 同步结算
↓
这一回合完成
```

红方一次行动 + 蓝方一次行动，合起来才算一个回合。

AI/provider 的真实响应秒数**不计入玩家成绩**。

---

# 当前正式游玩流程

## 第 1 回合

```text
开始游戏
↓
active_rule = null
↓
第 1 回合自动开始
```

第 1 回合前：

- 玩家不能制定规则；
- 不存在旧设计中的 Phase 0；
- 玩家先观察一次没有玩家规则干预的基线战斗。

## 第 1 回合之后

每个非终局完整回合结束后：

```text
游戏暂停
↓
进入玩家决策阶段
↓
玩家选择：
A. 不修改规则
B. 尝试提交新规则
↓
玩家点击“继续下一回合”
```

游戏不会自动连续跑下一回合。

## 规则替换

```text
每个回合间允许尝试提交
被拒绝 → 可以改写后重试
首次成功 → 替换旧规则
            rule_change_count + 1
            本回合间不再允许第二次成功替换
            仍需点击“继续下一回合”
```

同一时刻最多一条 active rule：

```text
UNTIL_REPLACED
```

V0.2 不做规则叠加。

---

# 当前玩家目标

V0.2 第一版主目标：

> **让战斗持续尽可能多的完整回合。**

```text
score_rounds = completed_rounds
```

AI 对局结果和玩家成绩分开：

```text
红方胜利

本局持续：14回合
规则制定：4次
```

如果达到 `max_rounds = 30`，即使 AI 对局结果记为 `TIMEOUT`，玩家 UI 应表达为：

```text
达到本局最高回合数
本局成绩：30
```

而不是“玩家失败”。

未来可以增加不同关卡目标，但当前 MVP 不提前扩展。

---

# 暂无回血

当前明确：

```text
没有基础回血
Rule DSL 不支持回血
自然语言规则不能创建回血
```

HP 一旦因伤害下降，不会自然恢复。

原因：有限 HP 是当前玩法的重要资源约束。稳定回血极易让“延长战斗”退化成恢复循环。

---

# 战局升温（原 Hard Liveness / conflict level 的产品化表达）

玩家既不能让双方太快互杀，也不能让双方无限不造成伤害。

当前继续保留已验证的防死局阈值：

| 连续无实际伤害回合 | 战局升温 | 当前系统效果 |
|---:|---|---|
| 0–2 | 0级 | 无额外破局加成 |
| 3–5 | 1级 | 提高攻击距离下限 |
| 6–8 | 2级 | 弓射程继续提高，最低命中率 25% |
| 9–11 | 3级 | 弓射程继续提高，最低命中率 50% |
| ≥12 | 4级 | 强制破局：全图弓射程、100%最低命中，并可强制弓攻击 |

现有 Round24 hard-liveness 兜底继续保留，直到新的节奏实验提供证据再修改。

规则替换**不能**重置连续无伤害计数。

只有实际产生伤害时：

```text
no_damage_streak → 0
```

普通玩家 UI 统一显示“战局升温”，不要直接显示 `Hard Liveness` 或 `conflict_level`。

---

# AI 信息展示

当前 Agent 代码的闭合 StrategyIntent：

```text
PRESSURE
KITE
EVADE
HOLD
```

它们是当前实现兼容结构，不是最终产品合同。

玩家 UI 使用中文：

| 内部值 | 玩家界面 |
|---|---|
| PRESSURE | 逼近进攻 |
| KITE | 保持距离 |
| EVADE | 躲避保命 |
| HOLD | 原地应对 |
| RED | 红方 |
| BLUE | 蓝方 |
| BOW | 弓箭 |
| KNIFE | 刀 |

玩家可以看双方的**公开策略摘要**，但不显示完整模型内部思维过程。

区分：

```text
当前策略
≠
Planner 具体动作
≠
Engine 最终结果
```

公共 API 的 `PublicStrategyDecision` 继续为 richer-plan 预留可选字段。

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

当前 main 的 `DynamicRuleController`、`MatchApplicationService` 与 FastAPI 五路由已迁移到 V0.2 cadence，并由真实 Chromium + live MiMo 闭环验证。

---

# 当前公共 API Contract V0.2

当前 `schema_version`：

```text
mvp-v0.2
```

Replay：

```text
replay-v0.2
```

五个最小路由仍保持：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
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

关键字段：

```text
completed_rounds
score_rounds
rule_change_count
player_decision.can_submit_rule
player_decision.rule_changed_this_intermission
player_decision.can_advance
battle_escalation
```

继续保留：

```text
revision
Idempotency-Key
per-match lock
public/private projection
Replay no-model-call
```

详细规范：

**[`docs/MVP_API_CONTRACT_V0.2.md`](docs/MVP_API_CONTRACT_V0.2.md)**

---

# 关键安全 / 语义原则

1. **Engine 是最终裁判。** LLM 不能直接写 HP、位置、伤害、随机数、胜负或 GameState。
2. **Open Language, Closed Semantics。** 自然语言可以开放，可执行规则必须落入封闭 Rule DSL。
3. **Prompt 不是安全边界。** 候选规则必须经过 deterministic Validator；语义忠实性另有 verifier。
4. **非法/不可表达规则宁可拒绝，也不能偷偷改成另一条合法规则。**
5. **两个 Agent 私有记忆隔离。** 只能共享公开棋盘、规则和公开历史。
6. **当前 LLM 只输出高层 StrategyIntent。** 具体动作由确定性 Planner 生成。
7. **战局升温系统兜底不能被玩家规则关闭。**
8. **Public Replay 不记录 chain-of-thought / hidden reasoning / private Agent memory。**
9. **规则翻译失败不修改 active rule，也不增加 rule_change_count。**
10. **策略模型失败必须允许 deterministic fallback，而不是让整局卡死。**
11. **规则替换不能重置 no_damage_streak。**
12. **同一玩家决策阶段最多成功替换一次规则。**

P0 冻结规则语义：

**[`docs/P0_RULE_FREEZE_V0.1.md`](docs/P0_RULE_FREEZE_V0.1.md)**

Round24 amendment：

**[`docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md`](docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md)**

---

# 历史 Agent Gate 的正式解释

历史 `live-agent-planner-match` 首次真实 PASS：

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

它仍然是：

```text
connectivity evidence
```

即证明真实 provider、两个隔离 Agent、Planner、Controller 和 Engine 可以连通并完成终局。

它**不证明**：

- LLM 比 deterministic heuristic 更好；
- 四个 StrategyIntent 是最终策略结构；
- private memory 已形成真正学习；
- 游戏已经好玩；
- 当前 Agent 架构已经可以冻结。

Sprint 1 仍必须用 A/B/C 验证。

---

# 已验证的重要结论

当前工程证据支持：

- deterministic Engine 可运行、可通过 seed 重现；
- Rule DSL / Validator / Evaluator 可执行；
- PublicRuleHistory 可确定性更新；
- 动态公共规则可在 V0.2 每回合玩家决策流程中替换并持续生效；
- Hard Liveness 能避免已知拖延策略无限拖局；
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

这些证据不能自动推出“LLM Agent 有必要”“V0.2 新玩法已经好玩”或“比赛有竞争力”。

完整证据链：

**[`docs/VALIDATION_HISTORY.md`](docs/VALIDATION_HISTORY.md)**

---

# 当前仍未解决的问题

## 1. B5A Replay before/after 过渡

回合、规则结果与战局升温的核心因果反馈已经合并。Issue #63 仍需完成 Replay 的 before/after 过渡，并保证只播放权威历史、不重新调用模型、不修改历史事实。

## 2. LLM Agent 是否真的有价值

Sprint 1 必须比较：

```text
A deterministic heuristic
B current four-intent LLM
C richer-plan LLM + deterministic short rollout
```

如果 LLM 无明显可测/可感知增益，就允许简化或重构 Agent。

## 3. Natural-language safe false reject

历史 Dynamic Natural-Language Match V0.2 曾出现一条合法规则被单次误判为 `NO_CANDIDATE`。

MVP 处理：

- 清晰拒绝反馈；
- suggested rephrase；
- 玩家确认后重新提交；
- 网络/协议错误才做受控 retry。

不得为了减少 false reject 放松 RuleValidator / Faithfulness safety boundary。

## 4. “好玩”尚未验证

V0.2 最关键的玩法风险：

- 玩家是否每回合都必改规则，导致“继续”成为伪选择；
- 是否存在固定规则套路稳定拖到 30 回合；
- 当前 3/6/9/12 战局升温阈值在每回合人工暂停后是否太慢；
- PRESSURE/KITE/EVADE 组合是否出现无聊软死局；
- 玩家是否理解公共规则对双方状态产生的不同实际效果。

---

# 双人 + AI 并行开发

### Developer A — 后端 / AI / 核心集成

当前顺序：

```text
DynamicRuleController V0.2 cadence migration
↓
MatchApplicationService
↓
in-memory repository / revision / lock / idempotency
↓
FastAPI real routes
↓
Replay public projection
```

### Developer B — 前端 / 交互 / 可视化

现在即可使用：

```text
contracts/fixtures/mvp-v0.2/
```

实现：

```text
初始页：游戏名 + 开始游戏
5×5 Board
红蓝 HP / 当前策略 / 实际动作 / 当前属性
当前公共规则
规则制定次数
战局升温
规则输入 / 拒绝 / 改写建议
继续下一回合
本回合事件
Replay timeline
```

玩家可见文案尽量中文。

详细任务：

**[`docs/MVP_FIRST_TASKS.md`](docs/MVP_FIRST_TASKS.md)**

---

# 当前 MVP 主线

```text
Gameplay Flow V0.2
↓
API Contract V0.2
↓
┌───────────────────────────────┬──────────────────────────┐
│ Controller cadence migration  │ React/Vite V0.2 Mock UI │
└───────────────────────────────┴──────────────────────────┘
↓
MatchApplicationService
↓
FastAPI five routes
↓
Frontend real API integration
↓
Replay
↓
追逃/软死局实验 + Agent A/B/C
↓
真人试玩
```

第一条真人可玩纵向切片必须让玩家无需手工改 JSON 或运行 CLI，就能完成：

```text
点击开始
→ 第1回合自动战斗
→ 每回合观察红蓝策略与结果
→ 选择继续或制定中文公共规则
→ 规则成功后仍手动继续
→ 观察战局升温
→ 终局
→ 查看回放与回合成绩
```

---

# 当前明确不做

```text
回血
规则叠加
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

如果某项不是完成 V0.2 真人可玩闭环所必需，默认延后。

---

# AI / 新开发者必读

先读：

```text
AI_DEVELOPER_START_HERE.md
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_API_CONTRACT_V0.2.md
docs/MVP_FIRST_TASKS.md
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
docs/AI_COLLABORATION_PROTOCOL.md
```

验证证据总索引：

**[`docs/VALIDATION_HISTORY.md`](docs/VALIDATION_HISTORY.md)**

旧设计、旧合同、旧实验仍有历史价值；如果与当前 `GAMEPLAY_FLOW_V0.2 / MVP_API_CONTRACT_V0.2` 冲突，以当前 V0.2 normative 文档为准。
