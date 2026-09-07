# Handoff — Public Rule Core Signal Experiment

> 日期：2026-09-07  
> 分支：`experiment/dynamic-rule-core-signal`  
> 状态：实验已跑完；core signal 通过，但发现新的 liveness blocker。

## 1. 本分支回答的问题

> 在同一 seed、同一基础策略下，一条合法公共规则是否能稳定、可解释地改变动作选择、武器使用、战斗时长或结果分布？

答案：**能。**

但本轮同时发现：合法低 DPS / 远程规则能显著提高 TIMEOUT，因此不能直接进入“每3回合换规则”。

详细数据：

```text
docs/experiments/PUBLIC_RULE_CORE_SIGNAL_2026-09-07.md
```

## 2. 实验方式

第一轮采用：

```text
整局无规则
vs
整局固定一条合法公共规则
```

并使用相同 seed 成对比较。

本轮仍没有测试自然语言，也没有测试正式 Agent。

## 3. 新增测试机器人

```text
RuleAwareAttackFirstBot
RuleAwareKiteBot
```

文件：

```text
src/rules_beyond/rule_bots.py
```

它们每回合通过 `RuleAwareGameEngine.effective_stats_for_team()` 读取规则后的真实有效属性。

因此：

- move_range=2 时真的会搜索两步可达位置；
- Bow cooldown 时不会继续把普通 Bow 当合法动作；
- Bow range / Knife range 变化会改变可攻击判断。

它们仍然只是测试探针，不是正式 Planner。

## 4. 实验参数

本轮使用上一轮节奏实验的**候选值**：

```text
HP = 5
Knife Damage = 2
```

这只是实验参数，没有修改正式 `GameConfig` 默认值。

## 5. 五条规则

全部通过 V0.1 Validator：

```text
1. ALWAYS → BOW_RANGE_ADD(+1)
2. ALWAYS → MOVE_RANGE_ADD(+1)
3. DISTANCE >= 3 → BOW_HIT_MULTIPLIER(0.5)
4. SELF_HP <= 2 → BOW_DAMAGE_ADD(+1)
5. CONSECUTIVE_SAME_WEAPON_USE >= 2 → BOW cooldown 1 round
```

它们不是推荐规则，只是覆盖：射程、移动、概率、条件性伤害、历史条件/cooldown。

## 6. 已确认的正向 core signal

### Bow Range +1

Attack-first 镜像的 first-action change rate = 100%，并从“先接近”变成“原地远射”。

### HP<=2 → Bow Damage +1

开局动作完全不变，但四个 pairing 的 outcome change rate 约 26.9%~39.7%，证明中后期条件规则能改变终局。

### Repeat Bow cooldown

混合 pairing 中：

```text
Bow 使用显著下降
Knife 使用从 0 上升
移动距离约 3 → 11+
outcome change rate 约 37%~39%
```

说明历史条件可以迫使 probe bot 改变行为结构，而不只是改一个伤害数字。

## 7. 新发现的阻断项：稀疏伤害规避 Hard Liveness

现有 liveness 依赖：

```text
连续无伤害回合数
```

只要偶尔造成一点伤害，`no_damage_streak` 就会归零。

因此可能出现：

```text
低命中率
→ 多回合 miss
→ 偶尔命中
→ streak 清零
→ 重复
→ 长期不进入 Hard Liveness
→ 最终 TIMEOUT
```

真实数据：

```text
Bow Range +1
Attack-first vs Attack-first:
TIMEOUT 0% → 33.0%

DISTANCE>=3, Bow Hit ×0.5
Attack-first vs Kite:
0.5% → 26.2%

Kite vs Attack-first:
0.8% → 31.6%

Kite vs Kite:
0% → 11.0%
```

因为真人玩家目标本身就是延长战斗，这个漏洞与玩家激励方向一致，不能忽略。

## 8. 当前涉及文件

新增：

```text
src/rules_beyond/rule_bots.py
src/rules_beyond/rule_experiment.py
tests/test_rule_experiment.py
.github/workflows/rule-core-signal.yml
docs/experiments/PUBLIC_RULE_CORE_SIGNAL_2026-09-07.md
```

以及通用协作约定：

```text
docs/AI_COLLABORATION_PROTOCOL.md
```

## 9. 并行开发注意

其他 AI / 开发者暂时不要：

- 再实现第二套 paired-seed rule simulation；
- 把 probe bots 当正式 Planner；
- 根据本实验直接改默认 HP；
- 开始 GLM Prompt 定稿；
- 直接开始“每3回合换规则” controller。

可以低冲突并行：

- 比赛提交要求整理；
- Replay/日志需求分析（不改 Engine 行为）；
- 独立 code review；
- adversarial liveness 方案研究或实验设计，但不要直接改 normative anti-stall，除非有数据支持。

## 10. 修正后的下一步 Gate

原计划：

```text
core signal A
→ 每3回合规则替换
```

已被实验结果修正。

现在应为：

```text
Core signal: PASS
↓
Adversarial liveness / stall exploit experiment
↓
修正或重新定义 anti-stall
↓
回归 paired rule simulation
↓
确认 TIMEOUT exploit 被压住
↓
再进入每3回合规则替换 controller
```

原因：玩家目标与当前 timeout exploit 的激励高度一致，这是产品级阻断项。
