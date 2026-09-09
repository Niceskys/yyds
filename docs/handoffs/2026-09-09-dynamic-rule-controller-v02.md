# Handoff — DynamicRuleController V0.2 Intermission Migration (A0)

> 日期：2026-09-09
> 分支：`backend/controller-v02-intermission`
> 对应 Issue：#37
> 基线：`main@6a930d7ae67dbc5d703bae15d669545fc272fc4e`
> 状态：**A0 COMPLETED；review blocker 已修复；等待最终 PR CI。**

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

### 2.1 continue_match 不是对外状态

`continue_match()` **只是 Controller 内部关闭 intermission**。

V0.2 HTTP `/advance` 必须在应用层一个原子操作内完成：

```text
intermission close
→ RED / BLUE strategy
→ Planner
→ resolve one complete round
→ Replay
→ public MatchSnapshot
```

A1 不得把 `continue_match()` 之后、下一回合尚未 resolve 的中间状态作为正常对外
`PLAYER_DECISION` 结果持久化/返回。

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

## 5. Review 修复：历史 Gate identity 不再被污染

PR #48 第一次 CI（`tests` / `behavior-diagnostics` / `dynamic-rule-replacement`）已全绿，
但 review 发现一个治理 blocker：为了适配新 cadence，直接在**已冻结且已有 PASS/FAIL 证据**
的旧 Gate 模块名下改写了实验定义。

### 5.1 已冻结的历史身份

```text
Natural-Language Dynamic Match Gate V0.1
  FAIL, head 9239cfa876f5a7fb3d050ad960ceacf851e43324
  workflow: live-natural-language-dynamic-match
  evidence: docs/experiments/MIMO_V25_PRO_NL_DYNAMIC_MATCH_V01_FAIL_2026-09-08.md

Natural-Language Dynamic Match Gate V0.2
  FAIL, head 62a1ec52899ab16e47fcf957ab9a246b0452c658
  workflow: live-natural-language-dynamic-match-v02
  evidence: docs/experiments/MIMO_V25_PRO_NL_DYNAMIC_MATCH_V02_FAIL_2026-09-08.md

Agent / Planner Integration Gate V0.1
  PASS, head 5c1aeccc7d9ef1727c01f416695415f5a9c9477f
  workflow: live-agent-planner-match
  evidence: docs/experiments/LIVE_AGENT_PLANNER_GATE_PASS_2026-09-08.md

V0.1 Dynamic Public-Rule Replacement Experiment
  PASS, results commit d8e5ec00f9e4116bc43d8e05ffdc674dcb064a27
  workflow: dynamic-rule-replacement
  evidence: docs/experiments/DYNAMIC_RULE_REPLACEMENT_2026-09-08.md
```

### 5.2 分版方案

历史 workflow 全部改为 **historical-only + 明确 pin 到冻结 head**，只复现历史代码，不再执行
当前 cadence 定义：

```text
.github/workflows/live-natural-language-dynamic-match.yml      -> pin 9239cfa...
.github/workflows/live-natural-language-dynamic-match-v02.yml  -> pin 62a1ec5...
.github/workflows/live-agent-planner-match.yml                 -> pin 5c1aecc...
.github/workflows/dynamic-rule-replacement.yml                 -> pin d8e5ec0... + workflow_dispatch only
```

当前 cadence 使用新版本名 / 新模块 / 新 workflow：

```text
src/rules_beyond/live_natural_language_dynamic_match_v03.py
  workflow: live-natural-language-dynamic-match-v03 (workflow_dispatch)

src/rules_beyond/live_agent_planner_match_v02.py
  workflow: live-agent-planner-match-v02 (workflow_dispatch)

src/rules_beyond/dynamic_rule_experiment_v02.py
  workflow: dynamic-rule-replacement-v02 (pull_request + workflow_dispatch)
```

新版本定义文档：

```text
docs/experiments/NATURAL_LANGUAGE_DYNAMIC_MATCH_GATE_V0.3.md
docs/experiments/AGENT_PLANNER_INTEGRATION_GATE_V0.2.md
docs/experiments/DYNAMIC_RULE_REPLACEMENT_V0.2.md
```

三份新文档与模块 docstring 都明确写明：这是 cadence migration 后的新 smoke/gate，
**不是**历史 V0.1 / V0.2 FAIL 或 Agent V0.1 PASS 的 rerun。

历史 PASS/FAIL 文档本身未做任何修改。

历史 cadence 的旧模块（`live_agent_planner_match.py`、
`live_natural_language_dynamic_match.py`、`live_natural_language_dynamic_match_v02.py`、
`dynamic_rule_experiment.py`）及其专属测试已从当前 HEAD 移除；其可复现入口是上面的 pinned
historical workflows，代码可从冻结 head 完整检出。

### 5.3 当前 cadence 与历史观测点差异

```text
Round 1 在 V0.2 中必须无玩家规则，因此不可能被规则改变。
第一次可观测的 planner 行为改变发生在第 1 个 intermission 之后，即 Round 2。
```

V0.3 NL Gate 的第一个 intermission 使用 `KNIFE_RANGE_ADD +1`，使 Round 2 的武器选择变化可观测。

## 6. Active baseline 文档已同步

以下 active source-of-truth 已从“Controller 仍是 V0.1 / A0 未完成”更新为 A0 COMPLETED：

```text
AI_DEVELOPER_START_HERE.md
docs/MVP_FIRST_TASKS.md
docs/MVP_API_CONTRACT_V0.2.md §14（仅 implementation/current-status，不改 normative gameplay）
```

当前后端顺序：

```text
A1 MatchApplicationService
-> A2 in-memory repository + revision / per-match lock / idempotency
-> A3 real FastAPI five-route vertical slice
-> Developer B B4 real API integration
```

## 7. 测试

```text
tests/test_dynamic_rule_controller.py
tests/test_natural_language_dynamic_controller.py
tests/test_natural_language_rule_adapter.py
tests/test_live_agent_planner_match_v02.py          (current cadence)
tests/test_live_natural_language_dynamic_match_v03.py (current cadence)
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

## 8. 验证

```text
pytest                                                                 195 passed
python -m rules_beyond.dynamic_rule_experiment_v02 --matches-per-pair 500   PASS
python -m rules_beyond.diagnostics --matches-per-pair 2000                  PASS
```

## 9. 未完成 / 下一步

- A1 `MatchApplicationService`（create / snapshot / submit_rule / advance / replay）**尚未开始**。
- A2 in-memory repository + revision / per-match lock / Idempotency-Key。
- A3 real FastAPI 五路由 vertical slice。
- A3 之后 Developer B B4 real API integration。
- Controller 目前仍不负责 Replay entry 组装；A1 需要把 `INTERMISSION_OPENED` /
  `PLAYER_RULE_REJECTED` / `PLAYER_RULE_REPLACED` / `PLAYER_CONTINUED` 映射到
  `ReplayIntermissionEntry`。
- `live-natural-language-benchmark.yml` 等与本轮无关的历史 workflow 未改动。
