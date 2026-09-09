# Dynamic Public-Rule Replacement Experiment V0.2

> 日期：2026-09-09
> 状态：**current-cadence experiment definition（不是历史 V0.1 PASS 的 rerun）**

## 1. 身份

本实验是 `DynamicRuleController` 迁移到 V0.2 intermission cadence 之后的新版本。

它**不是**、也不得被当作以下历史冻结实验的 rerun：

```text
docs/experiments/DYNAMIC_RULE_REPLACEMENT_2026-09-08.md
```

历史 V0.1 实验定义（pre-game phase 0 + 每 3 回合 rule phase）永久保留，并可通过
`.github/workflows/dynamic-rule-replacement.yml`（pin `d8e5ec00f9e4116bc43d8e05ffdc674dcb064a27`）
复现。

## 2. 当前 cadence

```text
start_match() -> active_rule = null
Round 1 无玩家规则直接执行
每个非终局完整回合后进入 intermission
schedule key = 已结算回合（第 N 回合结束后的 intermission）
每个 intermission 提交后显式 continue_match()，再执行下一回合
```

## 3. 固定配置

```text
GameConfig(initial_hp=5, knife_damage=2)
red/blue bots = RuleAwareAttackFirstBot / RuleAwareKiteBot 四种 pairing
matches_per_pair = 500
```

## 4. Gate

```text
dynamic TIMEOUT = 0
至少部分比赛经历 >1 replacement
paired runs 有 Round-4 comparable
至少一个 pairing 在 Round 4 观测到 action change
```

## 5. 运行

```text
.github/workflows/dynamic-rule-replacement-v02.yml
python -m rules_beyond.dynamic_rule_experiment_v02 --matches-per-pair 500
```

## 6. 明确未做

```text
不修改 Engine combat semantics
不修改 Rule DSL / Validator
不修改 gameplay balance
不修改历史 V0.1 PASS 结论
```
