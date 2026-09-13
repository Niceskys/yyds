# Handoff — MatchApplicationService V0.2 (A1)

> 日期：2026-09-09
> 分支：`backend/match-service-v02`
> 对应 Issue：#49 / PR：#50（Draft）
> 基线：`main@2fcdedf7233cd321f4baff89e84e6632b53dacb3`
> 状态：**A1 IMPLEMENTED + review blocker 已修复；等待 PR CI 与 re-review。未合并、未 merge。**

## 1. 本轮目标

实现应用层 `MatchApplicationService`，把 A0 已完成的 V0.2 `DynamicRuleController`、公开
API DTO、隔离策略 Agent、确定性 Planner、Engine 与 Replay public projection 串起来。

本轮**不**实现：

```text
repository persistence
revision conflict / CAS
per-match lock
Idempotency-Key
FastAPI routes
WebSocket / Redis / Celery / DB
web/**
```

这些分别属于 A2 / A3。未重新引入 `pre-game phase 0`、`rounds 3/6/9` cadence、
`RULE_PHASE_INTERVAL`。

## 2. 核心文件

```text
src/rules_beyond/match_application_service.py    新增：A1 应用层
src/rules_beyond/strategy_agent.py               A1 review 最小修改：memory commit 边界
tests/test_match_application_service.py          28 个测试
docs/handoffs/2026-09-09-match-application-service-v02.md
```

未修改（保持冻结）：

```text
src/rules_beyond/api_contract.py          公开 schema 未改
src/rules_beyond/engine.py                未改
src/rules_beyond/rule_dsl.py              未改
src/rules_beyond/rule_validator.py        未改
src/rules_beyond/dynamic_rule_controller.py
docs/GAMEPLAY_FLOW_V0.2.md                normative gameplay 未改
web/**
历史 Gate PASS/FAIL 定义未改
```

## 3. 应用层 API

```text
create_match(*, seed=None, match_id=None) -> MatchSnapshot
get_match_snapshot()                      -> MatchSnapshot
submit_public_rule(player_text)           -> RuleSubmissionResult
advance_match()                           -> AdvanceResult
get_replay()                              -> ReplaySnapshot
```

### 3.1 A1 只拥有一个内存 aggregate

`MatchApplicationService` 内部只保存一个 `_MatchAggregate`：

```text
match_id
seed
state（DynamicMatchState）
revision（A1 占位：只在状态变化时 +1）
active_rule_view（RulePublicView）
latest_strategy（RED / BLUE 最近一次公开策略）
timeline（ReplayEntry 列表）
```

- `create_match` 每个 service 实例只能调用一次，否则 `MatchAlreadyExistsError`。
- 方法签名故意不含 `match_id`。A2 加 repository + `match_id` 解析，不触碰 gameplay /
  projection 逻辑。
- 未实现并发 map、lock table、revision CAS、idempotency cache。

### 3.2 create_match

不执行 Round 1、不调用 Agent、不调用 provider/model、不生成 Replay ROUND。

```text
active_rule = null
completed_rounds = 0
score_rounds = 0
rule_change_count = 0
lifecycle = RUNNING
after_round = null
can_submit_rule = false
rule_changed_this_intermission = false
can_advance = true
```

### 3.3 advance_match（A1 最关键）

一次 `advance_match()` 是一个完整原子业务动作：

```text
若 PLAYER_DECISION：controller.continue_match()（内部步骤）
→ RED strategy + BLUE strategy（各自独立 IsolatedStrategyAgent，remember=False）
→ DeterministicIntentPlanner → RED / BLUE concrete Action
→ controller.resolve_round() 一个完整回合
→ 构建 Replay INTERMISSION(CONTINUE) + ROUND 与返回 DTO
→ 一次性提交 aggregate
→ 最后提交 RED / BLUE strategy private memory
→ 非终局 PLAYER_DECISION；终局 TERMINAL
```

- 所有 aggregate 变更都在完整回合 resolve 之后一次性提交；异常不会留下半回合。
- **strategy private memory 也纳入该原子边界**：`decide(remember=False)` 只产生决策不写
  memory，只有完整回合成功后才调用 `commit_decision_memory`。失败 / 放弃的回合不会留下
  phantom memory。
- 第一次 advance 从 RUNNING 直接执行 Round 1，Round 1 前不存在 INTERMISSION。
- `continue_match()` 之后、下一回合尚未 resolve 的 RUNNING 中间态**不返回、不写入
  aggregate、也不作为任何 Replay `pre_round`**。
- `ReplayRoundEntry.pre_round` 使用**玩家看到的最后一个稳定状态**：
  Round 1 是创建快照（RUNNING），Round N≥2 是上一回合后的 PLAYER_DECISION 快照
  （`after_round = N-1`）。

### 3.4 submit_public_rule

允许条件：

```text
lifecycle == PLAYER_DECISION and can_submit_rule == true
```

流程复用现有 verified pipeline（不复制第二套逻辑）：

```text
VerifiedNaturalLanguageDynamicController.submit_rule()
  = Intent Guard → translator → RuleValidator → Faithfulness → DynamicRuleController
```

- rejected：`active_rule` / `rule_change_count` 不变，intermission 保持打开，可重试；
- accepted：替换 `active_rule`、`rule_change_count += 1`、`rule_changed_this_intermission = true`、
  `can_submit_rule = false`，仍停留 `PLAYER_DECISION`，**不自动 advance**；
- 每次尝试都写一条 `ReplayIntermissionEntry(choice=RULE_ATTEMPT)`，rejected 重试不会被覆盖。

公开 code 映射（不泄露 provider raw / error 细节）：

```text
outcome.accepted                         -> ACCEPTED
INTENT_GUARD_REJECTED                    -> RULE_REJECTED
BASE_REJECTED + base NO_CANDIDATE        -> NO_CANDIDATE
BASE_REJECTED + base MODEL_ERROR         -> MODEL_UNAVAILABLE
BASE_REJECTED + 其他 base 失败           -> RULE_REJECTED
SEMANTIC_REJECTED                        -> FAITHFULNESS_REJECTED
VERIFIER_ERROR                           -> MODEL_UNAVAILABLE
```

### 3.5 get_replay

只读取已保存的 timeline；不调用 Agent / translator / provider / Engine，也不重新模拟。
返回前经统一的 defensive-copy 边界。

### 3.6 public response defensive-copy 边界

`ContractModel` 故意不是 frozen。所有 public 返回值都经单一 helper：

```text
_public_copy(model) -> model.model_copy(deep=True)
```

覆盖：

```text
create_match()
get_match_snapshot()
submit_public_rule()
advance_match()
get_replay()
```

调用方修改返回 DTO（含 nested model / list）不会反向污染
`aggregate.active_rule_view` / `aggregate.latest_strategy` / `aggregate.timeline`，
也不会污染后续 snapshot / replay。

## 4. 投影规则（不复制权威计算）

- `effective_stats`：`RuleAwareGameEngine.effective_stats_for_team()`，service 不手写
  bow range / knife range / hit floor / damage / cooldown 公式。
- `battle_escalation`：`level` / `hard_liveness` 来自上述权威 stats；
  `next_level_at_no_damage` 通过**探测** `GameEngine.conflict_level()` 得到，未复制
  3/6/9/12 阈值；`hard` 时 `next_level_at_no_damage = null`。
- 换规则只替换 `active_rule`，不触碰 `PublicRuleHistory` 与 `no_damage_streak`。
- `MatchSnapshot` 严格使用现有 `mvp-v0.2` schema，未新增 lifecycle 值。
- **不提供 production accessor 暴露 `DynamicMatchState` / `PublicRuleHistory`**；
  continuity 验证使用 public `battle_escalation.no_damage_streak` + 测试内明确 private 路径。
- `PlayerDecisionSnapshot`：
  - 创建 / RUNNING：`after_round=null`、`can_submit_rule=false`、`can_advance=true`；
  - 非终局回合后：`after_round=completed_rounds`、`can_submit_rule=true`；
  - 本 intermission accepted 后：`can_submit_rule=false`、`rule_changed_this_intermission=true`；
  - 终局：`can_submit_rule=false`、`can_advance=false`、`after_round=completed_rounds`。

### 4.1 Replay ROUND / INTERMISSION

`ReplayRoundEntry`：`round_no`、`pre_round`（稳定公开快照）、双方公开 strategy、双方
concrete action、Engine public events、`post_round_units`、`battle_escalation`、
`effective_stats`、`result`。

`ReplayIntermissionEntry`：`after_round`、`choice`、`submitted_player_text`、
`submission_public_code`、`accepted_rule`、`active_rule_before/after`、
`rule_change_count_after`。

时间线示例：

```text
ROUND 1
INTERMISSION RULE_ATTEMPT rejected
INTERMISSION RULE_ATTEMPT accepted
INTERMISSION CONTINUE
ROUND 2
```

- `CONTINUE` 独立成一条 entry，不与 accepted attempt 压缩合并。
- ROUND entry 的 `events` 只含 Engine 事实；controller 的 `INTERMISSION_OPENED` 由后续
  INTERMISSION entry 表达。
- 事件 `details` 经 JSON-safe 归一化（tuple/frozenset/enum → list/str），满足
  `RoundEventPublicView.details: dict[str, JsonValue]`。

## 5. 错误处理

A1 定义类型化异常（携带冻结 `ErrorCode`，A3 再映射 HTTP ErrorEnvelope）：

```text
MatchNotFoundError              -> MATCH_NOT_FOUND
MatchAlreadyExistsError         -> INVALID_REQUEST
MatchTerminalError              -> MATCH_TERMINAL
RuleSubmissionNotAllowedError   -> RULE_SUBMISSION_NOT_ALLOWED
AdvanceNotAllowedError          -> ADVANCE_NOT_ALLOWED
RecoverableMatchFailure         -> INTERNAL_ERROR (retryable)
```

- strategy model 失败由 `IsolatedStrategyAgent` 现有 fallback 处理
  （`FALLBACK_MODEL_ERROR` / degraded=true），回合仍完整结算；
- fallback 策略在回合成功提交后同样写入 private memory；
- strategy/planner/resolve 阶段意外异常包装为 `RecoverableMatchFailure`，aggregate、
  Replay、RED/BLUE private memory 全部不变。

## 6. PR #50 review 修复记录

第一次 A1 实现 CI 为 **215 passed**（195 基线 + 20 新增）。review 判定 merge blocked：

### 6.1 Blocker 1 — advance 原子性未覆盖 agent private memory

问题：`IsolatedStrategyAgent.decide()` 会立即写 `_private_memory`，而 `advance_match()` 在
RED/BLUE decide 之后才提交 aggregate。若 RED 成功、BLUE / Planner / resolve 之后失败，
aggregate 与 Replay 停留在上一回合，但 private memory 已包含未提交回合 → phantom memory。

修复（最小兼容）：

```text
IsolatedStrategyAgent.decide(..., remember: bool = True)   默认行为不变
IsolatedStrategyAgent.commit_decision_memory(decision, *, round_no, rule)
MatchApplicationService.advance_match():
    decide(..., remember=False) x2
    → planner → resolve_round
    → aggregate commit
    → commit_decision_memory x2（最后一步）
```

- 现有普通调用方（harness / tests）继续使用默认 `remember=True`，行为不变。
- private memory 仍只存 `round_no` / `active_rule_signature` / `intent`。
- failed / abandoned round 不写 memory；retry 不产生重复 Round N。
- 未通过跨类访问私有字段实现。

### 6.2 Blocker 2 — public DTO 与内部 aggregate 对象别名

问题：aggregate 的 `active_rule_view` / `latest_strategy` / `timeline` Pydantic 实例被直接
嵌入返回 DTO；`ContractModel` 非 frozen，调用方可反向污染内部状态。

修复：`_public_copy()` 统一 deep copy 边界，覆盖全部五个 public method；
未修改 `api_contract.ContractModel`。

### 6.3 封装 — 移除 `controller_state`

删除 production accessor `MatchApplicationService.controller_state`；测试改为：

- `no_damage_streak` → public `battle_escalation.no_damage_streak`；
- `PublicRuleHistory` continuity → `tests/**` 内明确 private 路径。

## 7. 测试

```text
tests/test_match_application_service.py   28 tests
```

覆盖（原 20 + review 新增 8）：

```text
create：RUNNING / completed_rounds=0 / no rule / 零 provider 调用
first advance：Round 1 完整执行、completed_rounds=1、PLAYER_DECISION
Round 1 前不存在 Replay INTERMISSION
advance 生成 RED/BLUE strategy + action + ROUND entry + Engine events
rejected rule 可重试、计数不变、Replay 保留每次 RULE_ATTEMPT
accepted rule：rule_change_count+1、can_submit_rule=false、不推进
accepted 后再次 submit 被拒
accepted → advance → CONTINUE + Round N + 新稳定 snapshot
不改规则直接 advance → CONTINUE entry
terminal：TERMINAL / 不可 submit / 不可 advance
get_replay + get_match_snapshot 零模型调用（counting fake）
public projection 不含 private_memory / raw_model_output / system_prompt 等
换规则保留 PublicRuleHistory 与 no_damage_streak
timeline 顺序与 active_rule_before/after 事实一致
provider 失败走 fallback、不产生半回合
BLUE 在 RED decide 后失败：aggregate / Replay / RED+BLUE memory 不变
Planner 在双方 decide 后失败：RED+BLUE memory 不变
失败后 retry：Round N memory 只出现一次，无 phantom duplicate
fallback 策略在成功回合后写入 memory
defensive copy：create / snapshot / accepted rule / advance 返回对象被篡改不污染内部
get_replay defensive copy
```

所有测试使用 deterministic fake provider / counting fake，禁止真实网络。

## 8. 验证

```text
pytest -o addopts="" -q                                                 223 passed
python -m rules_beyond.dynamic_rule_experiment_v02 --matches-per-pair 500   PASS
python -m rules_beyond.diagnostics --matches-per-pair 2000                  PASS
```

（第一次 A1 CI 为 215 passed；review 修复后为 223 passed。未删除测试、未放松断言。）

## 9. 未完成 / 下一步

留给 A2：

```text
in-memory repository + match_id 解析
revision CAS / revision conflict
per-match lock
Idempotency-Key
public/private projection 的应用层缓存
```

A2 必须注意：

```text
- 保证 match_id 全局唯一，rule_id = rule_{match_id}_{rule_change_count} 才安全；
- 幂等重试不得生成新的 rule_id，也不得重复 rule_change_count。
```

留给 A3：

```text
FastAPI 五路由
ErrorEnvelope mapping
```

留给 B4：真实 API 联调。

## 10. 需要审核

1. `advance_match()` 返回冻结契约的 `AdvanceResult(round, match)`；review 已确认正确，不改。
2. `rule_id = rule_{match_id}_{rule_change_count}` A1 保留；A2 必须保证唯一性与幂等语义。
3. 单一 aggregate 的 A1 边界：review 已确认可接受，A2 再引入 repository + `match_id`。
4. `controller_state` production accessor 已移除。
