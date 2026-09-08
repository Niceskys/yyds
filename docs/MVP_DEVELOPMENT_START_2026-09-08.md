# 《规则之外》正式 MVP 开发启动记录

日期：2026-09-08

## 结论

从本记录开始，项目状态由：

```text
核心机制 / 工程可行性验证
```

正式切换为：

```text
MVP 产品开发
```

这不是“核心玩法已经证明好玩”或“比赛一定有竞争力”的结论，而是表示：核心架构风险已经降低到足以开始构建可供真人完整操作的 MVP。

## 触发依据

最后一道核心架构 Gate：`live-agent-planner-match` 首次真实运行 PASS。

运行信息：

```text
workflow: live-agent-planner-match
run_number: 1
head_sha: 5c1aeccc7d9ef1727c01f416695415f5a9c9477f
model: mimo-v2.5-pro
seed: 1270000
result: RED_WIN
rounds: 5
gate_passed: true
gate_failures: []
planner_snapshot_errors: 0
PLAYER_RULE_REPLACED: 2
```

真实 Agent 决策：

```text
Phase 0:
RED  -> PRESSURE
BLUE -> KITE

Phase 1（公开规则替换后）:
RED  -> PRESSURE
BLUE -> HOLD
```

红蓝双方均通过独立 Agent session 作出真实模型决策；具体动作由确定性 Planner 产生，Engine 负责最终合法性与结算。

## 已验证到什么程度

当前已经有工程证据支持：

1. 5×5 同步战斗 Engine 可确定性运行与重放；
2. Rule DSL / Validator / Evaluator 可执行；
3. 动态公共规则可在固定规则阶段替换并持续生效；
4. anti-stall 与 Round24 Hard Liveness 可避免已知拖延策略无限拖局；
5. 自然语言规则可经过 Intent Guard、Translator、RuleValidator、Faithfulness Verifier 再进入 Controller；
6. 未见自然语言 V0.3 Gate 达到 `24/25 LEGAL`、`25/25 NO_CANDIDATE blocked`、`false_accepts=0`；
7. 两个 AI Agent 的私有策略记忆隔离；
8. LLM 只输出闭合的高层 StrategyIntent，不直接控制位置、动作、HP、伤害、随机数或胜负；
9. 确定性 Planner 根据公开状态与规则生成具体动作；
10. 真实 MiMo Agent + Planner + DynamicRuleController + Engine 已完成完整终局对战。

## 仍未解决的问题

进入 MVP 开发不代表这些问题消失：

### 1. 自然语言合法规则仍存在安全 false reject

Dynamic Natural-Language Match Gate V0.2 曾因：

```text
双方移动距离增加1格。
```

被 MiMo 单次误判为 `NO_CANDIDATE` 而 FAIL。

这是可用性问题，不是 unsafe accept：系统选择拒绝并沿用旧规则，没有错误 RuleAST 进入 Engine。

后续 MVP 必须提供清晰的规则拒绝反馈，并评估安全重试/重新措辞 UX；不得为了减少拒绝而放松 deterministic Validator 或 semantic faithfulness 边界。

### 2. 当前 Planner 只是 MVP 初版

闭合 StrategyIntent：

```text
PRESSURE
KITE
EVADE
HOLD
```

足以支撑 MVP，但不应视为最终策略系统。

### 3. 产品默认仍为 HP4/K2

Agent Gate 使用 `GameConfig(initial_hp=5, knife_damage=2)` 仅为了工程验证稳定跨越多个阶段；产品 baseline 不因此改成 HP5。

### 4. “好玩”尚未验证

下一阶段必须通过真人可玩的 MVP、回放和真实规则实验验证趣味性、可理解性、策略差异与比赛展示效果。

## MVP 的第一目标

不是继续增加规则种类，而是把当前已验证核心做成一个真人可以完成以下闭环的产品：

```text
开始对局
→ 看见棋盘与双方状态
→ 输入一条公开中文规则
→ 两个独立 AI 自主战斗
→ 到规则阶段再次修改规则
→ 看见 AI 策略与战局变化
→ 对局结束
→ 回看规则变化、关键事件与结果
```

只要这条闭环还不能稳定供真人操作，就不优先开发账号、排行榜、复杂关卡、多人联机、3D、美术系统或大量新 DSL 能力。
