# Natural-Language Dynamic Match Gate V0.1

> 日期：2026-09-08  
> 状态：**第一次 live dynamic match 运行前冻结**

## 1. 目的

自然语言 verified pipeline 已在 unseen V0.3 holdout 上达到冻结 Gate。

下一步不再继续增加静态语料，而是验证真实中文规则是否能穿过完整系统并真正改变对局：

```text
玩家中文规则
-> MiMo
-> deterministic intent guard
-> NaturalLanguageRuleAdapter
-> RuleValidator
-> semantic faithfulness verifier
-> DynamicRuleController 再验证
-> RuleAware bots
-> RuleAwareGameEngine
-> 完整终局
```

本 Gate 主要验证跨模块接线、fail-closed 行为、动态替换、Planner 可观察变化和终局可达性。

它**不**验证最终平衡、最终 Agent、最终 UI 或玩法是否足够有趣。

## 2. 固定实验配置

为稳定覆盖多个规则阶段，Gate 使用：

```text
GameConfig(initial_hp=5, knife_damage=2)
```

固定 seeds：

```text
1260000
1260001
1260002
```

这是工程验证配置，不改变产品默认：

```text
initial_hp = 4
knife_damage = 2
```

## 3. 固定测试 Bot

红蓝双方均使用：

```text
RuleAwareAttackFirstBot
```

这是 deterministic probe bot，不是最终 Planner，也不是最终“AI Agent”。

选择它的原因：第一阶段规则可产生确定性的首回合行为差异，便于证明规则已经进入 Planner/Engine，而不是只改变日志。

## 4. 固定自然语言规则阶段

### Phase 0 — pre-game

```text
双方弓的最大射程增加1格。
```

期望：合法、verified ACCEPTED、Controller replaced。

初始双方 Manhattan distance=4：

```text
无规则：AttackFirst 需要先移动再用弓
有 BOW_RANGE_ADD(+1)：AttackFirst 应原地用弓
```

因此每个 seed 的 round-1 action signature 必须与 no-rule baseline 不同。

### Phase 1 — after Round 3

```text
双方移动距离增加1格。
```

期望：合法、verified ACCEPTED、替换 Phase 0 规则。

### Phase 2 — after Round 6

```text
生命值不超过2或者上一回合没移动时，弓射程增加1格。
```

期望：V0.1 不支持 OR，必须：

```text
INTENT_GUARD_REJECTED
```

并且：

```text
不替换 active_rule
沿用 Phase 1 的合法规则
```

### Phase 3 — after Round 9

```text
双方相距至少3格时，弓箭命中率按原来的一半计算。
```

若 match 到达该阶段，必须合法接受并替换。

至少一个固定 seed 必须到达 Phase 3，用于验证“先安全拒绝一个规则，之后仍能正常接受下一条合法规则”。

### Phase 4 — after Round 12

```text
连续2回合使用同一种武器后，弓冷却1回合。
```

若 match 到达该阶段，必须合法接受并替换。

Phase 4 是否到达不作为硬性 Gate，因为随机命中可能使对局更早终止。

后续 phase 没有文本提交，按 UNTIL_REPLACED 继续沿用最后合法规则。

## 5. 冻结 PASS 条件

第一次 live run 必须同时满足：

```text
3 个固定 seed 全部完成终局
TIMEOUT = 0
每个 seed Phase 0 ACCEPTED + replaced
每个 seed Phase 1 ACCEPTED + replaced
每个 seed Phase 2 INTENT_GUARD_REJECTED
每个 seed Phase 2 不替换 active_rule
每个 seed Phase 2 正确 carry forward 上一合法规则
至少一个 seed 到达 Phase 3 且 ACCEPTED + replaced
每个 seed round-1 action 与 no-rule baseline 不同
每个 seed 至少出现 1 个 RULE_MODIFIER_APPLIED Engine event
```

任何一项失败都判：

```text
FAIL
```

不能用总体比例抵消安全/接线失败。

## 6. Provider / transient failure

如果真实 MiMo 出现明确基础设施故障，例如 HTTP timeout、服务不可用或 protocol transport failure，结果会以 fail-closed 形式表现为未接受规则。

可以在以下全部内容都不变化时重跑一次：

```text
model
Prompt/guidance
intent guard
faithfulness verifier
Rule DSL
RuleValidator
schedule
seeds
Gate
```

不得因为语义失败挑最好的一次重跑。

## 7. 结果 Artifact

手动 workflow：

```text
live-natural-language-dynamic-match
```

输出 Artifact：

```text
live-natural-language-dynamic-match/result.json
```

即使 Gate FAIL，也应尽量保留：

- 每个 phase 的翻译状态；
- base translator 状态；
- faithfulness decision；
- Intent Guard 状态；
- Controller accepted/replaced/carry；
- 每回合红蓝 action；
- HP；
- active rule；
- Engine event kinds；
- gate failure reasons。

## 8. PASS 后的下一步

如果本 Gate PASS：

```text
Natural Language -> deterministic probe match = end-to-end wiring PASS
```

随后进入最后一个主要验证阶段之一：

```text
正式 Agent/Planner integration Gate
```

需要把当前 deterministic probe bots 替换/升级为明确职责的红蓝 Agent/Planner 系统，并证明：

- 红蓝思想/记忆隔离；
- 只能读取各自允许的公开/私有信息；
- LLM 负责高层策略而不是直接改 GameState；
- deterministic planner/validator 决定合法动作；
- 完整对局可回放、可复现、无越权。

只有该真实 Agent/Planner 端到端 Gate 通过后，才宣布：

```text
正式 MVP 开发开始
```
