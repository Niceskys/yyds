# Natural-Language Dynamic Match Gate V0.3

> 日期：2026-09-09
> 状态：**current-cadence Gate definition（不是历史 V0.1 / V0.2 FAIL 的 rerun）**

## 1. 身份

本 Gate 是 `DynamicRuleController` 迁移到 V0.2 intermission cadence 之后的新版本。

它**不是**、也不得被当作以下历史冻结 Gate 的 rerun：

```text
docs/experiments/NATURAL_LANGUAGE_DYNAMIC_MATCH_GATE_V0.1.md
docs/experiments/NATURAL_LANGUAGE_DYNAMIC_MATCH_GATE_V0.2.md
docs/experiments/MIMO_V25_PRO_NL_DYNAMIC_MATCH_V01_FAIL_2026-09-08.md
docs/experiments/MIMO_V25_PRO_NL_DYNAMIC_MATCH_V02_FAIL_2026-09-08.md
```

历史 V0.1 FAIL（head `9239cfa876f5a7fb3d050ad960ceacf851e43324`）与 V0.2 FAIL（head
`62a1ec52899ab16e47fcf957ab9a246b0452c658`）永久保留，并分别通过
`.github/workflows/live-natural-language-dynamic-match.yml` 与
`.github/workflows/live-natural-language-dynamic-match-v02.yml` 复现。

## 2. 固定配置

```text
provider = MiMo China Token Plan
model = mimo-v2.5-pro
GameConfig(initial_hp=5, knife_damage=2)
seeds = 1260000, 1260001, 1260002
red = blue = RuleAwareAttackFirstBot
evaluation-only memoization: 每个 (system_prompt, player_text) 只调用 Provider 一次
```

## 3. 当前 cadence 阶段

```text
after round 1: 双方刀的攻击距离增加1格。          (KNIFE_RANGE_ADD +1)
after round 2: 双方移动距离增加1格。              (MOVE_RANGE_ADD +1)
after round 3: 生命值不超过2或者上一回合没移动时，弓射程增加1格。  (INTENT_GUARD_REJECTED)
after round 4: 双方相距至少3格时，弓箭命中率按原来的一半计算。      (BOW_HIT_MULTIPLIER 0.5)
```

Round 1 必须无玩家规则。第一个可观测的 planner 行为改变发生在第一个 intermission 之后，
即 Round 2。

## 4. Gate

```text
3 seeds 均完成终局
TIMEOUT = 0
phase 0 ACCEPTED + replaced
phase 1 ACCEPTED + replaced
phase 2 INTENT_GUARD_REJECTED，不替换 active_rule，沿用上一合法规则
至少一个 seed 到达 phase 3，且 ACCEPTED + replaced
每个 seed 的 Round 2 action 与 no-rule baseline 不同
每个 seed 至少一次 RULE_MODIFIER_APPLIED
```

## 5. 运行

```text
.github/workflows/live-natural-language-dynamic-match-v03.yml
python -m rules_beyond.live_natural_language_dynamic_match_v03 --model mimo-v2.5-pro
```

## 6. 边界

不得修改历史 V0.1 / V0.2 FAIL 结论，不得用本 V0.3 结果改判历史 Gate。
