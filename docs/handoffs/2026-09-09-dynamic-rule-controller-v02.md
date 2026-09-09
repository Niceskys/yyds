# Handoff — DynamicRuleController V0.2 Intermission Migration (A0)

> 日期：2026-09-09
> 分支：`backend/controller-v02-intermission`
> 对应 Issue：#37
> 基线：`main@6a930d7ae67dbc5d703bae15d669545fc272fc4e`
> 状态：**Controller cadence migration + controller/NL tests PASS；等待 PR CI。**

## 1. 本轮目标

把 `DynamicRuleController` 从 V0.1 cadence 迁移到 V0.2 回合间状态机：

```text
旧：Round 1 前 phase 0 + 每 3 回合 rule phase
新：Round 1 无玩家规则直接执行
    每个非终局完整回合后进入 intermission / PLAYER_DECISION
    同一 intermission 可多次 rejected 重试、最多 1 次成功替换
    accepted 后仍需显式 continue
    terminal 不再开放 intermission
```

本轮不实现 `MatchApplicationService`、repository、revision/lock/idempotency、FastAPI。

## 2. 新的 Controller 状态机

`DynamicMatchState` 关键字段：

```text
game_state
histories
active_rule
rule_change_count
pending_intermission_after_round
rule_changed_this_intermission
```

关键只读属性：

```text
in_intermission
completed_rounds
can_submit_rule
can_advance
```

Controller API：

```text
start_match()                                  -> DynamicStartResult
resolve_round(state, actions, match_seed=...)  -> DynamicRoundResult
submit_rule(state, candidate=None)             -> DynamicRuleSubmissionResult
continue_match(state)                          -> DynamicContinueResult
```

行为约定：

- `start_match()` 不接受任何初始规则；`active_rule = None`，Round 1 直接可执行。
- `resolve_round()` 在每个非终局回合结束后打开 intermission，并写入
  `pending_intermission_after_round = 已结算回合`。
- intermission 未关闭前再次 `resolve_round()` 会被拒绝。
- `submit_rule(state, None)` 表示“玩家提交了但没有产生候选规则”，是 rejected attempt，
  不是静默 continue。
- rejected：`active_rule` 不变、`rule_change_count` 不变、intermission 保持打开、可重试。
- accepted：替换 `active_rule`、`rule_change_count += 1`、
  `rule_changed_this_intermission = True`、本 intermission 禁止第二次成功替换、**不推进回合**。
- `continue_match()` 关闭 intermission；只有 continue 之后才允许解析下一完整回合。
- terminal 回合不产生 intermission，`can_submit_rule = False`、`can_advance = False`。

## 3. 删除的 V0.1 产品逻辑

```text
RULE_PHASE_INTERVAL = 3
phase 0 before Round 1
rounds 3 / 6 / 9 ... rule phase
DynamicMatchState.rule_phase_due
DynamicMatchState.pending_rule_phase_after_round
DynamicMatchState.last_phase_index
RulePhaseOutcome / DynamicRulePhaseResult
DynamicRuleController.apply_due_rule_phase()
DynamicRuleController.start_match(initial_submission)
```

`RulePhaseOutcome` 被 `IntermissionOutcome` 取代；`DynamicRulePhaseResult` 被
`DynamicRuleSubmissionResult` + `DynamicContinueResult` 取代。

## 4. 历史状态连续性

- 换规则只替换 `active_rule`，不触碰 `histories`（`PublicRuleHistory`）。
- 换规则不触碰 `GameState.no_damage_streak`。
- 只有 Engine 实际应用伤害才会重置 `no_damage_streak`。
- Engine / RuleValidator / Rule DSL / bow 命中率 / HP / damage 均未修改。

## 5. 受影响的调用方

Controller cadence 变化会传导到以下 V0.1 实验/连通性 harness，本轮一并迁移到 V0.2
回合间 cadence：

```text
src/rules_beyond/natural_language_dynamic_controller.py
src/rules_beyond/dynamic_rule_experiment.py
src/rules_beyond/live_agent_planner_match.py
src/rules_beyond/live_natural_language_dynamic_match.py
src/rules_beyond/live_natural_language_dynamic_match_v02.py
```

这些 harness 的 schedule 现在以“已结算回合”为 key（例如 `1:` 表示第 1 回合结束后的
intermission），不再以 phase index 为 key。

`live_natural_language_dynamic_match*` 的“行为改变”观测点从 Round 1 改为 Round 2：

```text
Round 1 在 V0.2 中必须无玩家规则，因此不可能被规则改变。
第一次可观测的 planner 行为改变发生在第 1 个 intermission 之后，即 Round 2。
```

为了让该断言仍然可观测，第一个 intermission 的规则改为 `KNIFE_RANGE_ADD +1`
（改变 Round 2 的武器选择），其余 schedule 文本保持不变。

## 6. 测试

重写/迁移：

```text
tests/test_dynamic_rule_controller.py
tests/test_natural_language_dynamic_controller.py
tests/test_live_natural_language_dynamic_match.py
tests/test_live_natural_language_dynamic_match_v02.py
tests/test_natural_language_rule_adapter.py
```

新增覆盖：

```text
start → Round 1 无规则直接执行
Round 1 → intermission
每个非终局回合都进入 intermission（不是每 3 回合）
reject → 同一 intermission 重试
no-candidate submission 是 rejected attempt 而非 continue
accept → 同一 intermission 锁定
accept → 仍需显式 continue
continue → 下一回合
直接 continue（不提交规则）→ 下一回合
terminal → 无 intermission、不可提交/推进
换规则保留 PublicRuleHistory
换规则保留 no_damage_streak
RULE_PHASE_INTERVAL 已从模块删除
```

移除的旧 cadence 断言（已被 V0.2 正式规范取代，不是为了让测试通过而保留两套逻辑）：

```text
pre-game phase 0 接受初始规则
round 3/6/9 才开放规则阶段
no-submission carry-forward 作为 phase 语义
due rule phase 必须在下一回合前处理
```

## 7. 验证

```text
pytest                                     196 passed
python -m rules_beyond.dynamic_rule_experiment --matches-per-pair 500   PASS
python -m rules_beyond.diagnostics --matches-per-pair 2000               PASS
```

## 8. 未完成 / 下一步

- A1 `MatchApplicationService`（create / snapshot / submit_rule / advance / replay）
- A2 in-memory repository + revision / per-match lock / Idempotency-Key
- A3 FastAPI 五路由 vertical slice
- Controller 目前仍不负责 Replay entry 组装；A1 需要把 `INTERMISSION_OPENED` /
  `PLAYER_RULE_REJECTED` / `PLAYER_RULE_REPLACED` / `PLAYER_CONTINUED` 映射到
  `ReplayIntermissionEntry`。
