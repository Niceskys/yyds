# 《规则之外》MVP API / Replay 公共契约 V0.2

状态：**当前公共合同（Normative）**  
日期：2026-09-08  
玩法基线：[`GAMEPLAY_FLOW_V0.2.md`](GAMEPLAY_FLOW_V0.2.md)

> 本文取代 V0.1 中与“开局规则阶段 / 每3回合规则阶段”有关的合同语义。
> V0.1 保留为历史证据，不再作为新代码生成依据。

---

# 1. 版本

所有顶层公共响应：

```json
{"schema_version":"mvp-v0.2"}
```

Replay：

```text
replay-v0.2
```

Event 继续使用：

```text
event-v0.1
```

HTTP 路由仍保持 `/api/v1`，因为项目尚无对外稳定消费者；本次通过 `schema_version` 明确标记 breaking contract change。

---

# 2. 对局生命周期

V0.2 公共生命周期：

```text
RUNNING
PLAYER_DECISION
TERMINAL
FAILED_RECOVERABLE
```

含义：

- `RUNNING`：正在等待/执行下一完整回合，不允许玩家在回合中途改规则；
- `PLAYER_DECISION`：一个非终局回合已经完整结算，游戏暂停，玩家可直接继续或尝试替换公共规则；
- `TERMINAL`：AI 对局结束；
- `FAILED_RECOVERABLE`：应用层可恢复故障。

不再存在：

```text
AWAITING_INITIAL_RULE
AWAITING_RULE
```

第 1 回合开始前没有规则阶段。

---

# 3. MatchSnapshot V0.2

核心结构：

```json
{
  "schema_version": "mvp-v0.2",
  "match_id": "match_...",
  "revision": 5,
  "lifecycle": "PLAYER_DECISION",
  "seed": 1270000,
  "round_no": 2,
  "completed_rounds": 1,
  "score_rounds": 1,
  "rule_change_count": 0,
  "board": {"rows":5,"cols":5},
  "units": {},
  "active_rule": null,
  "player_decision": {
    "after_round": 1,
    "can_submit_rule": true,
    "rule_changed_this_intermission": false,
    "can_advance": true
  },
  "effective_stats": {},
  "latest_strategy": {},
  "battle_escalation": {
    "level": 0,
    "no_damage_streak": 1,
    "next_level_at_no_damage": 3,
    "rounds_until_next_level": 2,
    "hard_liveness_active": false
  },
  "result": null
}
```

## 3.1 `round_no`

保持与 Engine 当前语义兼容：表示**下一次将要解析的 Engine round number**。

因此 UI 不应仅靠它显示玩家成绩。

## 3.2 `completed_rounds`

已经完整结算的回合数。

玩家主界面和结算页面优先使用它。

## 3.3 `score_rounds`

V0.2 暂等于：

```text
score_rounds = completed_rounds
```

单独暴露是为了未来关卡评分不必破坏 MatchSnapshot。

## 3.4 `rule_change_count`

只统计成功生效的公共规则替换。

拒绝、模型不可用、幂等重试不增加。

---

# 4. PlayerDecisionSnapshot

```json
{
  "after_round": 4,
  "can_submit_rule": true,
  "rule_changed_this_intermission": false,
  "can_advance": true
}
```

规则：

### 新对局 / 第1回合开始前

```text
after_round = null
can_submit_rule = false
rule_changed_this_intermission = false
can_advance = true
```

### 非终局回合刚结束

```text
after_round = completed_rounds
can_submit_rule = true
rule_changed_this_intermission = false
can_advance = true
```

### 本决策阶段已有一条规则成功生效

```text
can_submit_rule = false
rule_changed_this_intermission = true
can_advance = true
```

### 终局

```text
can_submit_rule = false
can_advance = false
```

客户端按钮状态应以这些公共字段为准，不自行推测。

---

# 5. 战局升温公共状态

内部 `no_damage_streak / conflict_level / hard_liveness` 对玩家产品化为“战局升温”。

公共 DTO：

```json
{
  "level": 2,
  "no_damage_streak": 7,
  "next_level_at_no_damage": 9,
  "rounds_until_next_level": 2,
  "hard_liveness_active": false
}
```

当前阈值：

```text
3 / 6 / 9 / 12
```

`level`：0..4。

4级或 Round24 硬兜底生效时：

```text
hard_liveness_active = true
```

规则替换不得重置该对象；只有实际造成伤害才重置连续无伤害计数。

前端显示中文“战局升温”，不要直接显示 `hard_liveness`。

---

# 6. 规则提交

路由不变：

```text
POST /api/v1/matches/{match_id}/rules
```

请求：

```json
{
  "expected_revision": 5,
  "player_text": "双方移动距离增加1格"
}
```

Header：

```text
Idempotency-Key: <unique-key>
```

允许条件：

```text
lifecycle == PLAYER_DECISION
and player_decision.can_submit_rule == true
```

规则被拒绝：

- active rule 不变；
- rule_change_count 不变；
- can_submit_rule 仍为 true；
- 玩家可以改写后重试。

规则成功：

- 新规则替换旧 active rule；
- `rule_change_count += 1`；
- `rule_changed_this_intermission = true`；
- `can_submit_rule = false`；
- **不自动推进下一回合**。

V0.2 `RuleSubmissionCode` 至少：

```text
ACCEPTED
NO_CANDIDATE
RULE_REJECTED
FAITHFULNESS_REJECTED
MODEL_UNAVAILABLE
RULE_SUBMISSION_NOT_ALLOWED
MATCH_TERMINAL
REVISION_CONFLICT
```

旧的 `RULE_PHASE_NOT_DUE` 不再作为新产品语义。

---

# 7. 推进回合

```text
POST /api/v1/matches/{match_id}/advance
```

请求：

```json
{"expected_revision":5}
```

Header：

```text
Idempotency-Key: ...
```

允许：

- 新对局创建后：用于自动开始第 1 回合；
- `PLAYER_DECISION`：玩家点击“继续下一回合”。

禁止：

- `TERMINAL`；
- 已有另一个 advance 正在同一 match 临界区执行；
- revision 不匹配。

一次 advance 必须原子完成：

```text
RED strategy
BLUE strategy
→ Planner actions
→ Engine one complete round
→ Replay round entry
→ completed_rounds +1
→ score_rounds 更新
→ battle_escalation 更新
→ 若非终局进入 PLAYER_DECISION
```

不得只提交红方半个回合。

---

# 8. 创建对局

```text
POST /api/v1/matches
```

创建后：

```text
active_rule = null
completed_rounds = 0
rule_change_count = 0
lifecycle = RUNNING
can_submit_rule = false
can_advance = true
```

前端点击“开始游戏”后，应立即触发第一次 `advance`，从用户体验上表现为第 1 回合自动开始。

创建接口本身不偷偷执行 AI/provider，避免一个 HTTP create 同时承担过多副作用。

---

# 9. AI 公开策略

`PublicStrategyDecision` 继续兼容当前四枚举：

```text
PRESSURE
KITE
EVADE
HOLD
```

但前端中文映射：

```text
PRESSURE → 逼近进攻
KITE     → 保持距离
EVADE    → 躲避保命
HOLD     → 原地应对
```

不得公开：

```text
chain-of-thought
hidden reasoning
private memory
raw provider body
完整 system prompt
```

UI 用“当前策略”，不要用“完整思考过程”。

---

# 10. Replay V0.2

Replay 顶层：

```json
{
  "schema_version":"mvp-v0.2",
  "replay_version":"replay-v0.2",
  "match_id":"...",
  "seed":1270000,
  "initial_config":{},
  "timeline":[],
  "terminal_result":"RED_WIN",
  "score_rounds":14,
  "rule_change_count":4
}
```

时间线两类 entry：

## ROUND

记录完整回合：

```text
round_no
pre_round public state
RED/BLUE public strategy
RED/BLUE concrete action
Engine public events
post-round units
battle escalation
result
```

## INTERMISSION

记录回合间玩家操作：

```text
after_round
choice = CONTINUE | RULE_ATTEMPT
submitted_player_text
submission_public_code
accepted_rule
active_rule_before/after
rule_change_count_after
```

第 1 回合之前不存在 INTERMISSION 规则提交。

同一个 after_round 可以有多个被拒绝的 `RULE_ATTEMPT`，最终再出现一次成功尝试或 `CONTINUE`。

Replay 读取绝不再次调用模型。

---

# 11. 路由集合

仍固定为五个：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

V0.2 不新增“结束玩家决策阶段”专用路由：

- 不改规则时，玩家直接调用 `advance`；
- 改规则成功后，玩家仍调用 `advance`。

这样保持接口最小。

---

# 12. 并发 / 幂等 / 隐私

V0.1 的这些硬约束全部继续：

```text
per-match lock
revision check
Idempotency-Key
public/private projection
Replay no-model-call
```

相同 Idempotency-Key 重发不得：

- 重复调用模型；
- 重复推进回合；
- 重复增加 rule_change_count。

---

# 13. 前端中文化原则

API 内部 enum 可以保持英文稳定值，但普通玩家 UI 尽量中文。

至少映射：

```text
RED → 红方
BLUE → 蓝方
BOW → 弓箭
KNIFE → 刀
PRESSURE → 逼近进攻
KITE → 保持距离
EVADE → 躲避保命
HOLD → 原地应对
```

工程术语 `Hard Liveness / conflict_level / provider / schema` 不直接展示给普通玩家。

---

# 14. 当前实现迁移状态

A0 已完成（Issue #37，分支 `backend/controller-v02-intermission`）：

```text
DynamicRuleController = V0.2 intermission cadence
- start_match() 不再接受初始规则，active_rule = null
- Round 1 无玩家规则直接执行
- 每个非终局完整回合后进入 intermission / PLAYER_DECISION
- rejected submission 可重试、不计数、不关闭 intermission
- 同一 intermission 最多成功替换一次规则
- accepted 后仍需显式 continue 才执行下一回合
- terminal 不再进入 intermission
- 换规则不重置 PublicRuleHistory / no_damage_streak
```

旧 V0.1 cadence（pre-game phase 0 / rounds 3/6/9...）已从产品路径删除，仅作为历史证据保留。

当前后端顺序：

```text
V0.2 gameplay contract
→ V0.2 Pydantic/OpenAPI/fixtures
→ DynamicRuleController cadence migration        [DONE]
→ controller regression tests                     [DONE]
→ MatchApplicationService                        [当前第一优先级]
→ in-memory repository / revision / lock / idempotency
→ real FastAPI five-route vertical slice
→ Developer B B4 real API integration
```

`continue_match()` 只是 Controller 内部关闭 intermission。HTTP `/advance` 必须在应用层
一个原子操作内完成：

```text
intermission close
→ RED / BLUE strategy
→ Planner
→ resolve one complete round
→ Replay
→ public MatchSnapshot
```

不得把 `continue_match()` 之后、下一回合尚未 resolve 的中间状态作为正常对外
PLAYER_DECISION 结果持久化/返回。
