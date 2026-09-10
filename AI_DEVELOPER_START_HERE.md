# AI Developer Start Here

> **所有 AI / 新开发者开始非 trivial 工作前必须先读本文件。**
>
> 目的：进入当前正确上下文，避免重新实现已经完成的 A0–A3 / B0–B4，避免恢复 V0.1 cadence，也避免在缺乏证据时继续堆功能。

---

# 1. 当前项目状态

项目：《规则之外》（暂定名）

当前阶段：

```text
MVP 工程纵向切片已完成
→ 进入 Integrated Playable Acceptance / AI value validation 阶段
```

当前最重要的规范顺序：

```text
1. docs/MVP_NEXT_MILESTONE_2026-09-10.md
2. docs/GAMEPLAY_FLOW_V0.2.md
3. docs/MVP_API_CONTRACT_V0.2.md
4. DEVELOPER_A_GATE.md
5. web/DEVELOPMENT_HANDOFF.md
6. docs/AI_COLLABORATION_PROTOCOL.md
7. 与当前任务直接相关的最新 Issue / handoff
8. docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md（历史审计行动依据）
```

注意：README 和旧审计/开发文档中可能仍保留“尚未有 FastAPI / React”“A3/B4 未完成”“Phase 0 / 每 3 回合规则阶段”等历史描述。**当前执行状态以本文件 + `MVP_NEXT_MILESTONE_2026-09-10.md` + 最新 main 为准。**

---

# 2. 当前已完成的工程主线

```text
Gameplay Flow V0.2                          DONE
API / Replay Contract V0.2                 DONE
A0 DynamicRuleController V0.2              DONE
A1 MatchApplicationService                 DONE
A2 repository / revision / lock / idempotency DONE
A3 FastAPI five-route vertical slice       DONE — PR #59

B0 React/Vite App Shell                    DONE
B1 fixture-driven product UI               DONE
B3 Replay UI                               DONE
OpenAPI generated TypeScript + API seam    DONE
B4 real HTTP frontend integration          DONE — PR #61
```

B4 merge：

```text
8769649cf587862b72f241fc64b531e5fdbbdbe6
```

Developer B V0.2 umbrella Issue #38 已按 completed 关闭。

**任何 AI 不得再把 A3 / B4 当成“当前待实现任务”。**

---

# 3. 当前唯一第一任务

```text
M1 — Integrated Playable Acceptance
```

详见：

```text
docs/MVP_NEXT_MILESTONE_2026-09-10.md
```

目标不是加功能，而是证明当前仓库可以真实完成：

```text
backend 启动
+ frontend 启动
+ browser
→ create match
→ Round 1
→ PLAYER_DECISION
→ rejected / MODEL_UNAVAILABLE 可恢复
→ accepted rule
→ continue
→ 后续 round
→ terminal
→ Replay
```

M1 通过前，默认不要做：

```text
新 DSL
回血
多单位
地形
richer-plan Agent
数据库
WebSocket
账号 / 排行
UI 大改版
```

---

# 4. Developer A Gate

Developer A 在任何非 trivial backend 工作前必须先读：

```text
DEVELOPER_A_GATE.md
```

当前：

```text
DEVELOPER_A_GATE = PAUSED_BY_OWNER
CURRENT_APPROVED_BACKEND_TASK = NONE
DO_NOT_START = true
DO_NOT_START_NEW_TASK = true
```

A0/A1/A2/A3 已完成。没有新的批准 Issue 前，Developer A 只能做只读分析 / 状态汇报 / 方案评估。

旧聊天、旧 Day 4/Day 5、旧 Issue 中的 READY 文案都不能绕过 gate。

---

# 5. Developer B 状态

B0–B4 已完成。当前正式 runtime：

```text
FastAPI V0.2
→ HttpMatchApiAdapter
→ generated TypeScript DTO aliases
→ ViewModel
→ React
```

Developer B 新工作必须建立新的 Issue。

当前可以参与：

- M1 integration smoke；
- 修复 M1 发现的真实 integration bug；
- 记录可复现 smoke 证据。

不得借 M1 顺手加入新玩法。

最新前端 handoff：

```text
web/DEVELOPMENT_HANDOFF.md
```

---

# 6. V0.2 正式游玩流程

```text
点击开始游戏
↓
create Match
↓
Round 1 前 active_rule = null
↓
玩家不能制定规则
↓
RED / BLUE 各自独立决策
↓
Deterministic Planner 生成具体 Action
↓
Engine 同步结算完整 Round
↓
terminal ?
  YES → 结算 / Replay
  NO  → PLAYER_DECISION
↓
玩家：直接继续，或尝试提交一条公共规则
↓
rejected / MODEL_UNAVAILABLE → 可再次提交
accepted → 替换旧规则；本 intermission 不再允许第二次成功替换
↓
玩家仍需点击“继续下一回合”
↓
下一完整 Round
```

硬规则：

- Round 1 前不能制定规则；
- 不存在 pre-game Phase 0；
- 不存在每 3 回合一次规则阶段；
- 红蓝各行动一次合起来才算一个完整回合；
- 每个非终局完整回合后进入玩家决策；
- 同一 intermission 最多成功替换一次规则；
- 始终最多一条 active rule；
- accepted 后不自动推进；
- rejected / MODEL_UNAVAILABLE 不增加 `rule_change_count`；
- 暂无回血；
- 当前玩家主成绩 `score_rounds = completed_rounds`。

---

# 7. 当前公共 API Contract

Canonical source：

```text
src/rules_beyond/api_contract.py
```

派生链：

```text
api_contract.py
→ openapi_contract.py
→ contracts/openapi/mvp-v0.2.json
→ openapi-typescript
→ web/src/contract/generated/api.ts
→ thin aliases
```

版本：

```text
schema_version = mvp-v0.2
replay_version = replay-v0.2
```

五个正式路由：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

不得自行定义第二套 DTO。若真实需求需要 public contract 新字段：

```text
CONTRACT CHANGE REQUIRED
```

先停止自行实现并报告最小缺口。

---

# 8. Revision / Idempotency / 并发

冻结语义：

- authoritative revision 来自服务端 snapshot；
- mutation 必须带 `expected_revision`；
- 新用户意图 → 新 Idempotency-Key；
- 同一次未知结果重试 → 复用原 key；
- 409 `REVISION_CONFLICT` → GET authoritative snapshot，不自动重放旧 mutation；
- per-match lock 保护同一 match；
- 不在全局锁中执行 provider / planner / engine；
- public response / cached response 必须避免 mutable alias 泄漏。

不要在新任务中悄悄重写这些语义。

---

# 9. Provider failure 语义

## Strategy provider/model failure

```text
HTTP 200 AdvanceResult
round 正常完成
public strategy degraded = true
status = public fallback status
```

不是 503；前端显示非阻断降级提示。

## Rule provider/model failure

```text
HTTP 200 RuleSubmissionResult
accepted = false
public_code = MODEL_UNAVAILABLE
revision 不增加
rule_change_count 不增加
仍可再次提交
```

不是 503。

## RecoverableMatchFailure

```text
HTTP 503
INTERNAL_ERROR
retryable = true
```

前端保留原 authoritative snapshot；同一次未知结果 retry 复用同 key。

---

# 10. 安全边界

1. **Engine 是最终裁判。** LLM 不直接写 HP、位置、伤害、随机数、胜负或 GameState。
2. **Open Language, Closed Semantics。** 自然语言规则最终必须落入封闭 Rule DSL。
3. Prompt 不是安全边界；候选规则必须经过 deterministic Validator。
4. 非法/不可表达规则宁可拒绝，也不能偷偷改成另一条合法规则。
5. RED / BLUE 私有记忆隔离。
6. 具体 Action 由 deterministic Planner 生成。
7. 战局升温兜底不能被玩家规则关闭。
8. Public Replay 不记录 chain-of-thought / hidden reasoning / private memory。
9. server raw provider error / stack / API key 不得进入普通玩家 UI。
10. 规则替换不能重置 `no_damage_streak`。

---

# 11. 当前 AI 证据级别

历史 live Agent Gate 只能解释为：

```text
connectivity evidence
```

它证明 provider + isolated agents + planner + controller + engine 能完成对局。

它**不证明**：

- LLM 比 deterministic heuristic 更好；
- 四个 StrategyIntent 是最终设计；
- private memory 已形成真正学习；
- 玩家能感知 AI 对规则的理解；
- 游戏已经好玩。

因此 M1 后必须做 M2 Agent A/B/C evidence，再进入真人试玩。

---

# 12. 下一阶段顺序

```text
M1 Integrated Playable Acceptance   [CURRENT]
↓
M2 Agent A/B/C Evidence              [NEXT]
↓
M3 Human Playtest                    [NEXT]
↓
依据证据决定 Agent / 玩法 / UI 下一轮改动
```

A/B/C 未出结果前，不因为“这是 AI 比赛”就默认继续增加 LLM 复杂度。

---

# 13. 默认 Non-goals

当前继续推迟：

```text
OR / NOT / multi-effect DSL
回血
WebSocket
Redis
Celery
Event Bus
微服务
复杂数据库
多人房间
账号 / 排行 / 商城
MCTS
多单位
地形
职业 / 技能
自由代码规则
移动 App
3D
```

任何新功能如果不直接解决当前 M1/M2/M3 风险，默认先不做。

---

# 14. 开工前最小检查

任何 AI 准备写代码前必须回答：

1. 最新 remote `main` SHA 是什么？
2. 当前任务对应哪个新 Issue？
3. Developer A 是否受 gate 限制？
4. 是否影响 public contract？
5. 是否会改变 gameplay / Engine / Rule DSL？
6. 是否把历史 V0.1 cadence 错当当前产品？
7. 最低验证命令 / hosted CI 是什么？
8. 是否有 handoff / remaining 需要同步？

回答不清楚，不应开始非 trivial 实现。
