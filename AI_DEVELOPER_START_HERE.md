# AI Developer Start Here

> **所有 AI / 新开发者开始非 trivial 工作前必须先读本文件。**

目的：进入当前正确上下文，避免继续实现已经被 V0.2 玩法取代的旧 cadence，或破坏已经验证过的安全边界。

---

# 1. 当前项目状态

项目：《规则之外》（暂定名）

当前阶段：

```text
正式 MVP 产品开发（GO WITH CONDITIONS）
```

当前最重要的规范顺序：

```text
1. docs/GAMEPLAY_FLOW_V0.2.md
2. docs/MVP_API_CONTRACT_V0.2.md
3. docs/MVP_FIRST_TASKS.md
4. docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
5. docs/AI_COLLABORATION_PROTOCOL.md
6. 与当前任务直接相关的最新 handoff
```

V0.1 API contract / Phase0 / 每3回合规则阶段文档保留为历史证据，但不再作为新产品实现依据。

---

# 2. 项目一句话定义

真人玩家不直接操控棋子。红方 AI 和蓝方 AI 各自以击败对方为目标，玩家在每个完整回合结束后观察战局，并决定是否替换一条同时约束双方的公共自然语言规则，目标是在有限生命值和“战局升温”压力下尽可能延长对局。

三个角色目标：

```text
RED AI  → 击败 BLUE
BLUE AI → 击败 RED
PLAYER  → 尽量延长完整回合数
```

---

# 3. V0.2 正式游玩流程

```text
点击开始游戏
↓
创建 Match
↓
第1回合无玩家规则自动进行
↓
RED / BLUE 各自独立思考
↓
Planner 生成双方具体动作
↓
Engine 同步结算一个完整回合
↓
如果终局 → 结算 / Replay
否则 → PLAYER_DECISION
↓
玩家：直接继续，或尝试提交一条公共规则
↓
规则被拒绝 → 可改写后重试
规则第一次成功 → 替换旧规则，rule_change_count +1，本 intermission 不再允许第二次成功替换
↓
玩家仍需点击“继续下一回合”
↓
下一回合
```

硬规则：

- Round 1 前不能制定规则；
- 不存在 pre-game Phase 0；
- 红蓝各行动一次合起来才算一个完整回合；
- AI/provider 的响应秒数不计入玩家成绩；
- 每个非终局完整回合后都暂停；
- 同一回合间最多成功替换一次规则；
- 始终最多一条 active rule；
- 规则成功后不自动推进下一回合；
- 规则被拒绝不增加 `rule_change_count`；
- 暂无回血；
- 玩家主成绩暂为 `score_rounds = completed_rounds`。

---

# 4. 当前最重要的开发顺序

A0 Controller cadence migration 已完成并合并。A1 MatchApplicationService 已实现，等待 PR 审核。

当前固定顺序：

```text
Gameplay Flow V0.2                         [DONE]
↓
API / Replay Contract V0.2                 [DONE]
↓
DynamicRuleController cadence migration    [A0 DONE]
↓
controller regression tests                [A0 DONE]
↓
MatchApplicationService                    [A1 IMPLEMENTED — PR 审核中]
↓
in-memory repository / revision / per-match lock / idempotency   [A2]
↓
real FastAPI five-route vertical slice     [A3]
↓
Developer B B4 real API integration
↓
Replay / 追逃/软死局实验 + Agent A/B/C
↓
真人试玩
```

Developer B 可以继续用 fixture 开发，直接使用：

```text
contracts/fixtures/mvp-v0.2/
```

A3 完成后进入 B4 真实 API 联调。

---

# 5. 当前 Controller 状态：必须注意

`DynamicRuleController` 已完成 A0 V0.2 回合间迁移（Issue #37）：

```text
start_match()                -> active_rule = null，Round 1 直接执行
每个非终局完整回合            -> 进入 intermission / PLAYER_DECISION
submit_rule()                -> rejected 可重试；同一 intermission 最多成功替换 1 次
continue_match()             -> 显式 continue 后才执行下一完整回合
terminal                     -> 不再进入 intermission
```

旧 V0.1 cadence 已从产品路径删除：

```text
RULE_PHASE_INTERVAL = 3
phase 0 before Round 1
rounds 3 / 6 / 9 ... rule phase
```

任何新 AI 不得把产品文档改回旧 cadence，也不得在 `MatchApplicationService` 中重新引入
每 3 回合一次或 Round 1 前制定规则。

迁移细节见：

```text
docs/handoffs/2026-09-09-dynamic-rule-controller-v02.md
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_FIRST_TASKS.md
```

下一步固定为：

```text
A1 MatchApplicationService                          [IMPLEMENTED — PR 审核中]
-> A2 in-memory repository + revision / lock / idempotency
-> A3 real FastAPI five-route vertical slice
-> Developer B B4 real API integration
```

---

# 6. 当前公共 API Contract

Canonical source：

```text
src/rules_beyond/api_contract.py
```

当前：

```text
schema_version = mvp-v0.2
replay_version = replay-v0.2
```

五个路由保持：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

关键公共对象：

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

Developer B 不得自行发明另一套类型。

---

# 7. “战局升温”不是可随意删除的隐藏机制

当前 Engine 已实现基于连续无实际伤害回合的 anti-stall：

```text
0-2  → level 0
3-5  → level 1
6-8  → level 2, bow hit floor 25%
9-11 → level 3, bow hit floor 50%
>=12 → level 4, hard liveness
```

另外保留 Round24 hard-liveness 兜底。

V0.2 产品层把它统一称为：

```text
战局升温
```

硬约束：

```text
rule replacement ≠ damage
```

因此：

- 换规则不能重置 `no_damage_streak`；
- 只有实际应用伤害才能把连续无伤害计数归零；
- 玩家规则不能关闭系统破局兜底。

普通玩家 UI 不直接显示 `Hard Liveness / conflict_level` 英文工程名。

---

# 8. 暂无回血

V0.2 明确：

```text
没有基础回血
Rule DSL 不支持回血
自然语言规则不能创建回血
```

不要为了“增加玩法”临时加入恢复类 effect。

原因：有限 HP 是当前延长对局玩法的重要约束，稳定回血可能直接制造循环最优策略。

---

# 9. 当前核心架构

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

它们是当前代码兼容结构，不是最终策略产品合同。

---

# 10. UI / 玩家可见信息原则

普通玩家界面尽量中文。

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

玩家可以看到：

```text
当前策略
本回合目标
武器倾向
风险倾向
实际动作
Engine 结果
```

不要展示：

```text
chain-of-thought
hidden reasoning
private memory
raw provider body
完整 system prompt
secret
stack trace
```

“AI 公开策略摘要”和“完整模型思维过程”不是一回事。

---

# 11. LLM 权限边界

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

# 12. Rule DSL / 安全语义

当前规则仍坚持：

```text
Open Language, Closed Semantics
```

必须读：

```text
docs/P0_RULE_FREEZE_V0.1.md
docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md
docs/RULE_DSL_VALIDATOR_IMPLEMENTATION_V0.1.md
docs/PUBLIC_RULE_HISTORY_V0.1.md
docs/SEMANTIC_FAITHFULNESS_GATE_V0.1.md
```

不要：

- 临时增加新 effect/condition；
- 前端自行解析规则；
- 因 false reject 放松 Validator；
- 自动把非法规则改成“差不多合法”后直接执行；
- 现在扩 OR / NOT / multi-effect；
- 现在加回血。

---

# 13. 第二轮审计后的证据口径

历史 `live-agent-planner-match` PASS 只称为：

```text
connectivity evidence
```

它证明 provider / Agent / Planner / Controller / Engine 能连通并完成终局。

它不证明：

- LLM 比 heuristic 更聪明；
- 四分类就是最佳策略结构；
- private memory 已形成学习；
- 当前 Agent 对玩家有明显价值；
- V0.2 新玩法已经好玩。

Sprint 1 必须比较：

```text
A deterministic heuristic
B current four-intent LLM
C richer-plan LLM + deterministic short rollout
```

没有 A/B/C 证据前，不得声称 LLM Agent 必要性已证明。

---

# 14. 当前已知实验事实

完整证据链：

```text
docs/VALIDATION_HISTORY.md
```

至少知道：

1. Prompt 不是安全边界；
2. 曾出现 semantic laundering，因此引入 `NO_CANDIDATE`；
3. 曾出现 `OR → 单条件` / `OR → AND`，因此引入 Faithfulness Verifier 和 Intent Guard；
4. V0.3 unseen verified holdout 达到冻结阈值；
5. Dynamic Natural-Language Match V0.2 有过安全 false reject，永久作为 FAIL 证据保留；
6. false reject 是可用性债务，不能靠放松 deterministic safety 解决；
7. Agent live Gate 是 connectivity evidence，不是 LLM value evidence。

---

# 15. 双人 + AI 责任边界

### Developer A

```text
src/rules_beyond/**
Python tests
DynamicRuleController cadence migration
Pydantic / OpenAPI
MatchApplicationService
MatchRepository
FastAPI
Replay public projection
provider integration
```

### Developer B

```text
web/**
React
TypeScript
Vite
5×5 board
中文 Rule UX
规则制定次数
战局升温
Public strategy display
Event feed
Replay timeline
```

### Shared review

```text
GAMEPLAY_FLOW_V0.2
MVP_API_CONTRACT_V0.2
OpenAPI canonical source
PublicStrategyDecision
Replay schema/version
privacy boundary
Agent A/B/C metrics
```

热点文件不要未经协调并行修改：

```text
engine.py
rule_engine.py
dynamic_rule_controller.py
strategy_agent.py
rule_dsl.py
rule_validator.py
api_contract.py
replay event mapping
```

---

# 16. 测试要求

### 修改 Controller cadence

必须覆盖：

```text
Round1 before-rule forbidden
Round1 resolved → PLAYER_DECISION
reject → retry allowed
accept → same intermission locked
continue → next round
rule change does not reset history/no_damage_streak
terminal → no next player decision
```

并确保原 Engine / Rule tests 不被破坏。

### 修改 API contract

至少：

- Pydantic/OpenAPI 一致；
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

禁止改 Prompt 后继续把同一题库叫 unseen。

---

# 17. 当前禁止擅自做的事

禁止：

- 把旧 Phase0 + 3回合 cadence 当当前产品规则；
- Round1 前允许玩家制定规则；
- 提交规则成功后自动开始下一回合；
- 同一 intermission 成功替换多次规则；
- 规则替换重置 no_damage_streak；
- 加回血；
- 给规则自动加 TTL；
- 绕过 Validator / Verifier / Controller；
- 让 LLM 直接控制 GameState；
- 让两个 Agent 共用 private memory；
- 因 false reject 放宽安全边界；
- 展示 chain-of-thought；
- 把四个 StrategyIntent 固化成永久前端合同；
- 没有 A/B/C 证据时声称 LLM Agent 必要；
- 现在引入 WebSocket、Redis、Celery、微服务；
- 擅自扩 OR/NOT/multi-effect、多单位、地形、装备、账号、排行榜等 Non-goals。

---

# 18. 当前第一目标

不是继续加功能，而是做出浏览器真人可玩闭环：

```text
游戏名 + 开始游戏
→ 第1回合自动战斗
→ 每回合暂停
→ 玩家看红蓝生命 / 当前策略 / 实际动作 / 属性 / 战局升温
→ 直接继续或提交中文公共规则
→ 规则成功后手动继续
→ 终局
→ 回合成绩 / 规则制定次数
→ Replay
```

如果一个任务不能直接帮助完成这条链，默认延后。
