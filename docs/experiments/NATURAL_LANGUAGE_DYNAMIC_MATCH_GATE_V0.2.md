# Natural-Language Dynamic Match Gate V0.2

> 日期：2026-09-08  
> 状态：第一次 live V0.2 运行前冻结

## 目的

V0.1 live Gate 已暴露并 FAIL。V0.2 不修改生产自然语言安全链，而是修正评测职责混叠：一次玩家语义提交只做一次真实 LLM 编译；多个 combat seed 只用于验证后续确定性 Planner/Engine 行为。

## 固定配置

```text
provider = MiMo China Token Plan
model = mimo-v2.5-pro
GameConfig(initial_hp=5, knife_damage=2)
seeds = 1260000, 1260001, 1260002
red = RuleAwareAttackFirstBot
blue = RuleAwareAttackFirstBot
```

HP5 仅为工程 Gate 配置，产品默认仍为 HP4/K2。

## 固定自然语言阶段

```text
phase 0: 双方弓的最大射程增加1格。
phase 1: 双方移动距离增加1格。
phase 2: 生命值不超过2或者上一回合没移动时，弓射程增加1格。
phase 3: 双方相距至少3格时，弓箭命中率按原来的一半计算。
```

Phase 2 必须由 deterministic Intent Guard 拒绝。

## V0.2 编译语义

Evaluation-only `MemoizedRuleCandidateModel` 以：

```text
(system_prompt, player_text)
```

为键缓存第一次 Provider 返回。

因此：

- 同一个玩家语义请求只产生一次真实模型判定；
- translator 与 faithfulness verifier 仍是不同 system prompt，因此分别调用；
- Provider/network exception 不缓存；
- 不改变产品 adapter、Controller 或 Engine 行为；
- 不把 cache 引入正式产品设计。

## PASS Gate

必须全部满足：

```text
3 seeds 均完成终局
TIMEOUT = 0
每个 seed 的 phase 0 ACCEPTED + controller replaced
每个 seed 的 phase 1 ACCEPTED + controller replaced
每个 seed 的 phase 2 INTENT_GUARD_REJECTED
phase 2 不替换 active_rule，并沿用上一合法规则
至少一个 seed 到达 phase 3
所有到达 phase 3 的 seed 均 ACCEPTED + controller replaced
每个 seed 的 round-1 action 与无规则 baseline 不同
每个 seed 至少出现一次 RULE_MODIFIER_APPLIED
```

任何失败都判 FAIL。不得通过反复重跑挑选最好结果。

## 明确没有修改

```text
Rule DSL
RuleValidator
Engine
DynamicRuleController
anti-stall / Round24
translator prompt/guidance
faithfulness prompt
Intent Guard
MiMo provider protocol
final Agent/Planner design
```

## PASS 后

如果 V0.2 PASS：

```text
Natural Language -> verified compile -> DynamicRuleController -> deterministic bots -> Engine
```

端到端动态比赛 Gate 通过。

下一步进入真实 Agent/Planner Integration Gate。只有该 Gate 也通过后，才宣布：

```text
正式 MVP 开发开始
```
