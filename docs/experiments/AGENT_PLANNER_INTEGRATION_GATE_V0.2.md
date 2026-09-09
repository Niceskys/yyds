# Agent / Planner Integration Gate V0.2

> 日期：2026-09-09
> 状态：**current-cadence Gate definition（不是历史 V0.1 PASS 的 rerun）**

## 1. 身份

本 Gate 是 `DynamicRuleController` 迁移到 V0.2 intermission cadence 之后的新版本。

它**不是**、也不得被当作以下历史冻结 Gate 的 rerun：

```text
docs/experiments/AGENT_PLANNER_INTEGRATION_GATE_V0.1.md
docs/experiments/LIVE_AGENT_PLANNER_GATE_PASS_2026-09-08.md
```

历史 Agent / Planner Integration Gate V0.1 PASS（head
`5c1aeccc7d9ef1727c01f416695415f5a9c9477f`）永久保留，并可通过
`.github/workflows/live-agent-planner-match.yml` 复现。

## 2. 与 V0.1 的差异

```text
V0.1: pre-game phase 0 rule schedule
V0.2: Round 1 无玩家规则；schedule key = 已结算回合；
      每个 intermission 提交后显式 continue_match() 再执行下一回合
```

规则 schedule：

```text
after round 1: BOW_RANGE_ADD(+1)
after round 2: MOVE_RANGE_ADD(+1)
after round 3: DISTANCE >= 3 -> BOW_HIT_MULTIPLIER(0.5)
```

## 3. Gate

```text
match result != TIMEOUT
planner_snapshot_errors = 0
INVALID_MOVE_PATH = 0
PLAYER_RULE_REPLACED >= 2
RED / BLUE 各至少 2 次 ACCEPTED strategy decision
初始 no-rule decision ACCEPTED
规则变化后各至少 1 次 ACCEPTED decision
```

## 4. 运行

```text
.github/workflows/live-agent-planner-match-v02.yml
python -m rules_beyond.live_agent_planner_match_v02 --model mimo-v2.5-pro
```

## 5. 边界

本 Gate 仍只证明 Agent/Planner/Controller/Engine 的接线与职责边界，不证明最终平衡、乐趣或
LLM 相对 heuristic 的价值。不得修改历史 V0.1 PASS 结论。
