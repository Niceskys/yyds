# Handoff — Gameplay Flow / API Contract V0.2

日期：2026-09-08  
分支：`product/gameplay-flow-v02`

## 1. 为什么有这次变更

产品讨论确认旧流程不再适用：

```text
旧：Round1 前 Phase0 + 每3回合规则阶段
新：Round1 无规则自动开始 + 每个完整回合后玩家决策
```

如果继续直接实现旧 MatchApplicationService，会把新 MVP 建在错误状态机上，因此先做 breaking contract migration。

---

## 2. 已确认的玩法

- 第 1 回合前不允许玩家制定规则；
- 第 1 回合无玩家规则自动开始；
- 红蓝双方各思考、各行动一次，合起来算一个完整回合；
- AI/provider 响应秒数不计入玩家成绩；
- 每个非终局完整回合后暂停；
- 玩家可直接继续或尝试提交规则；
- 被拒绝可以改写后重试；
- 同一 intermission 最多成功替换一次规则；
- accepted 后仍需点击“继续下一回合”；
- 始终最多一条 active rule；
- `rule_change_count` 只统计成功生效规则；
- 暂无回血；
- 玩家第一版主成绩为 `completed_rounds`；
- 防死局机制在产品 UI 中称为“战局升温”；
- 规则替换不重置 `no_damage_streak`；
- 普通玩家界面尽量中文；
- 不展示完整模型 chain-of-thought / private memory。

---

## 3. 本分支修改

新增：

```text
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_API_CONTRACT_V0.2.md
docs/handoffs/2026-09-08-gameplay-flow-v02.md
contracts/fixtures/mvp-v0.2/*
```

更新：

```text
README.md
AI_DEVELOPER_START_HERE.md
docs/MVP_FIRST_TASKS.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/AI_COLLABORATION_PROTOCOL.md
contracts/README.md
src/rules_beyond/api_contract.py
src/rules_beyond/openapi_contract.py
src/rules_beyond/contract_fixtures.py
tests/test_api_contract.py
tests/test_contract_fixture_files.py
```

---

## 4. Contract breaking change

```text
schema_version: mvp-v0.1 → mvp-v0.2
replay_version: replay-v0.1 → replay-v0.2
```

移除公共 lifecycle：

```text
AWAITING_INITIAL_RULE
AWAITING_RULE
```

加入：

```text
PLAYER_DECISION
PlayerDecisionSnapshot
BattleEscalationSnapshot
completed_rounds
score_rounds
rule_change_count
```

Replay 从旧：

```text
RULE_PHASE + ROUND
```

改为：

```text
ROUND + INTERMISSION
```

第一个 replay entry 必须是 Round 1，不存在 pre-game phase 0。

五个 HTTP 路由不变。

---

## 5. 明确没有改什么

本分支**没有**修改：

```text
Engine combat semantics
Rule DSL
RuleValidator
RuleEvaluator
Natural-language provider/prompt
StrategyAgent
Planner
DynamicRuleController cadence implementation
```

尤其：`DynamicRuleController` 目前仍是旧 V0.1 cadence。

这是有意保留的下一任务，不是遗漏。

---

## 6. 下一步唯一后端 P0

```text
DynamicRuleController cadence migration
```

目标：

```text
no Phase0
Round1 directly playable
每个非终局 round 后 intermission open
reject 可 retry
accept once 后本 intermission lock
continue 后进入下一 round
terminal 不再开 intermission
rule change 不重置 PublicRuleHistory / no_damage_streak
```

Controller 迁移完成并回归测试全绿后，才继续：

```text
MatchApplicationService
```

---

## 7. 前端可以立即做什么

Developer B 可以直接使用：

```text
contracts/fixtures/mvp-v0.2/
```

开始：

```text
初始页
5×5棋盘
红蓝状态
规则制定次数
当前公共规则
战局升温
公开策略 / 实际行动
规则输入 / 拒绝 / suggested rephrase
继续下一回合
终局摘要
Replay shell
```

不要继续使用 `mvp-v0.1` fixture 开新 UI。

---

## 8. 后续必须验证的玩法风险

- 玩家是不是每回合都必改规则；
- “继续”是不是伪选择；
- 是否存在固定拖延套路稳定 30 回合；
- 3/6/9/12 战局升温阈值在每回合暂停后是否太慢；
- PRESSURE/KITE/EVADE 等组合是否有无聊软死局；
- LLM 四分类策略是否有真正玩家可感知价值。

这些仍然是实验问题，不得在文档里提前宣布已解决。
