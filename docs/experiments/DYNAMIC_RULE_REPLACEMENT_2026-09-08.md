# Dynamic Public-Rule Replacement Experiment — 2026-09-08

> 状态：实验设计已实现，等待 PR CI 结果。

## 1. 目标

本轮只验证“真人公共规则按 V0.1 节奏被替换”这一机制，不接 GLM，不引入自然语言，不修改 Rule DSL。

现行节奏来自 `docs/GAME_DESIGN_V0.1.md`：

```text
开局前：规则阶段 0
Round 1-3：使用 phase 0 的 active_rule
Round 3 结束后：规则阶段 1
Round 4-6：使用 phase 1 之后的 active_rule
Round 6 结束后：规则阶段 2
...
```

关键语义：

- 一个规则阶段最多接受一条新规则；
- 新合法规则替换旧规则；
- 无提交时旧规则继续；
- 非法提交被拒绝，旧规则继续；
- 规则**不会因为经过 3 回合自动失效**；
- 系统级 anti-stall / Round-24 不属于真人规则，不被替换。

## 2. Controller 边界

新增：

```text
src/rules_beyond/dynamic_rule_controller.py
```

Controller 只负责：

```text
规则阶段时机
→ RuleValidator
→ active_rule 替换/保留
→ RuleAwareGameEngine
```

它不负责：

- 红蓝 AI 策略；
- LLM/GLM；
- 自然语言解析；
- UI 倒计时；
- 玩家计分；
- 多条真人规则并存。

## 3. Off-by-one 约束

这是本轮最重要的实现不变量之一：

```text
Round 3 本身仍使用旧规则；
Round 3 结算完成且比赛未终局后，才进入下一规则阶段；
新规则从 Round 4 开始生效。
```

同理：Round 6 使用当前旧规则，新规则从 Round 7 开始。

## 4. 强制阶段处理

如果 Round 3/6/9... 结束后比赛仍未终局，Controller 会标记：

```text
rule_phase_due = true
```

在该阶段被处理前，禁止直接结算下一回合。

目的是避免上层 UI / Agent orchestration 因集成 Bug 跳过玩家规则阶段。

## 5. 确定性实验

新增：

```text
src/rules_beyond/dynamic_rule_experiment.py
.github/workflows/dynamic-rule-replacement.yml
```

使用固定规则序列：

```text
phase 0: Bow Range +1
phase 1: Move Range +1
phase 2: Distance>=3, Bow Hit x0.5
phase 3: Low HP, Bow Damage +1
phase 4: Repeat Bow cooldown
```

与同 seed 下的 static baseline 比较：

```text
phase 0: Bow Range +1
后续阶段：不提交新规则，因此一直沿用 phase 0
```

这样可以把差异归因于“替换机制”，而不是有没有规则。

## 6. 场景

Bot pairings：

```text
Attack-first vs Attack-first
Attack-first vs Kite
Kite vs Attack-first
Kite vs Kite
```

每组 500 paired seeds。

实验配置：

```text
HP = 5
Knife Damage = 2
Round-24 Hard Liveness = 产品当前默认
```

HP=5 仅用于让更多比赛进入多个规则阶段，不修改产品默认 HP=4。

## 7. Gate

动态实验至少必须满足：

1. dynamic schedule 不重新引入 TIMEOUT；
2. 至少部分比赛实际经历超过一次规则替换；
3. static / dynamic paired runs 中至少有比赛同时进入 Round 4；
4. 第一次替换后，至少一个 pairing 的 Round-4 动作出现可观察变化；
5. 普通 pytest 全部通过。

这里暂不设置“结果变化率越高越好”的硬阈值，因为本轮目标是验证 replacement plumbing 与策略可见性，不是做最终平衡结论。

## 8. 本轮不做

- 不调用 GLM；
- 不实现 20 秒倒计时；
- 不让每条规则自动 3 回合失效；
- 不允许多条真人规则累积；
- 不改变 Rule DSL；
- 不改变 Round-24；
- 不开始前端。

## 9. 下一 Gate

```text
Dynamic controller + regression PASS
↓
检查替换时序、策略变化和 liveness
↓
通过后再进入 Natural Language -> Candidate RuleAST 接口层
```

如果动态替换本身没有稳定通过，就不接 LLM。
