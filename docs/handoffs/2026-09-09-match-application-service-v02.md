# Handoff — MatchApplicationService V0.2 (A1)

> 日期：2026-09-09
> 分支：`backend/match-service-v02`
> 对应 Issue：#49
> 基线：`main@2fcdedf7233cd321f4baff89e84e6632b53dacb3`
> 状态：**A1 IMPLEMENTED；等待 PR CI。未合并、未自动 merge。**

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
tests/test_match_application_service.py          新增：20 个测试
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
→ RED strategy + BLUE strategy（各自独立 IsolatedStrategyAgent）
→ DeterministicIntentPlanner → RED / BLUE concrete Action
→ controller.resolve_round() 一个完整回合
→ Replay INTERMISSION(CONTINUE) + Replay ROUND
→ completed_rounds / score_rounds / battle escalation / effective_stats
→ 非终局 PLAYER_DECISION；终局 TERMINAL
```

- 所有 aggregate 变更都在完整回合 resolve 之后一次性提交；异常不会留下半回合。
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
返回前对每个 entry 做 deep copy，防止调用方修改内部记录。

## 4. 投影规则（不复制权威计算）

- `effective_stats`：`RuleAwareGameEngine.effective_stats_for_team()`，service 不手写
  bow range / knife range / hit floor / damage / cooldown 公式。
- `battle_escalation`：`level` / `hard_liveness` 来自上述权威 stats；
  `next_level_at_no_damage` 通过**探测** `GameEngine.conflict_level()` 得到，未复制
  3/6/9/12 阈值；`hard` 时 `next_level_at_no_damage = null`。
- 换规则只替换 `active_rule`，不触碰 `PublicRuleHistory` 与 `no_damage_streak`。
- `MatchSnapshot` 严格使用现有 `mvp-v0.2` schema，未新增 lifecycle 值。
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
  （`FALLBACK_MODEL_ERROR` / degraded=true），回合仍完整结算。
- strategy/planner/resolve 阶段意外异常包装为 `RecoverableMatchFailure`，aggregate 不变。

## 6. 测试

```text
tests/test_match_application_service.py   20 tests
```

覆盖：

```text
create：RUNNING / completed_rounds=0 / no rule / 零 provider 调用
create 两次拒绝；未创建时 not found
create 后第一次 advance 前 submit 被拒且零模型调用
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
get_replay 返回 defensive copy
换规则保留 PublicRuleHistory 与 no_damage_streak
timeline 顺序与 active_rule_before/after 事实一致
provider 失败走 fallback、不产生半回合
agent 异常时 aggregate 不变
```

所有测试使用 deterministic fake provider / counting fake，禁止真实网络。

## 7. 验证

```text
pytest                                                              215 passed
python -m rules_beyond.dynamic_rule_experiment_v02 --matches-per-pair 500   PASS
python -m rules_beyond.diagnostics --matches-per-pair 2000                  PASS
```

（基线为 195 passed；本 PR 新增 20 个测试。）

## 8. 未完成 / 下一步

留给 A2：

```text
in-memory repository + match_id 解析
revision CAS / revision conflict
per-match lock
Idempotency-Key
public/private projection 的应用层缓存
```

留给 A3：

```text
FastAPI 五路由
ErrorEnvelope mapping
```

留给 B4：真实 API 联调。

## 9. 需要审核的设计决定

1. `advance_match()` 返回冻结契约的 `AdvanceResult(round=..., match=...)`，其中
   `match` 是**新的稳定 MatchSnapshot**。没有暴露 `continue_match()` 之后、Round 未 resolve
   的中间态。若要求只返回裸 `MatchSnapshot`，需要 A3 层再裁剪。
2. `rule_id` 采用确定性 `rule_{match_id}_{rule_change_count}`；A1 未引入随机 id。
3. 提供只读诊断属性 `controller_state`（不进入公共 DTO），仅用于测试 / 诊断；
   如认为应完全隐藏，可移除并改用其他方式验证历史连续性。
4. 单一 aggregate 的 A1 限制：一个 service 实例只服务一个 match；A2 必须改造成
   repository + `match_id` 参数，这是计划内的 API 变更。
