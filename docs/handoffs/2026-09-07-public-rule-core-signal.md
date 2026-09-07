# Handoff — Public Rule Core Signal Experiment

> 日期：2026-09-07  
> 分支：`experiment/dynamic-rule-core-signal`  
> 状态：实验分支，尚未形成最终玩法结论。

## 1. 本分支要回答的唯一问题

> 在同一 seed、同一基础策略下，一条合法公共规则是否能稳定、可解释地改变动作选择、武器使用、战斗时长或结果分布？

现在仍不测试自然语言，也不测试正式 Agent。

## 2. 为什么暂时不做“每 3 回合换规则”

控制变量。

第一轮采用：

```text
整局无规则
vs
整局固定一条合法公共规则
```

并使用相同 seed 成对比较。

如果第一层都没有明确行为信号，就没有理由继续叠加规则替换、GLM 和复杂 Planner。

## 3. 新增测试机器人

```text
RuleAwareAttackFirstBot
RuleAwareKiteBot
```

文件：

```text
src/rules_beyond/rule_bots.py
```

它们与旧 baseline bot 的关键区别：

> 每回合通过 `RuleAwareGameEngine.effective_stats_for_team()` 读取规则后的真实有效属性。

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

这只是实验参数，不修改正式 `GameConfig` 默认值。

## 5. 第一轮五条规则

全部先通过 V0.1 Validator：

```text
1. ALWAYS → BOW_RANGE_ADD(+1)
2. ALWAYS → MOVE_RANGE_ADD(+1)
3. DISTANCE >= 3 → BOW_HIT_MULTIPLIER(0.5)
4. SELF_HP <= 2 → BOW_DAMAGE_ADD(+1)
5. CONSECUTIVE_SAME_WEAPON_USE >= 2 → BOW cooldown 1 round
```

选择目的不是“这些规则最好玩”，而是覆盖：

- 射程；
- 移动；
- 概率；
- 条件性伤害；
- 历史条件 + cooldown。

## 6. 策略配对

```text
Attack-first vs Attack-first
Attack-first vs Kite
Kite vs Attack-first
Kite vs Kite
```

每个规则 × 每个配对使用相同 seed 跑：

```text
baseline: rule=None
ruled:    当前规则
```

## 7. 主要指标

- outcome change rate；
- mean round delta；
- first-action change rate；
- move distance；
- Bow / Knife 使用次数；
- rule activation 次数；
- Timeout 变化。

第一轮不使用“好玩分数”，因为 simple bots 不能证明主观体验。

## 8. 当前涉及文件

新增：

```text
src/rules_beyond/rule_bots.py
src/rules_beyond/rule_experiment.py
tests/test_rule_experiment.py
.github/workflows/rule-core-signal.yml
```

以及通用协作约定：

```text
docs/AI_COLLABORATION_PROTOCOL.md
```

### 并行开发注意

其他 AI / 开发者暂时不要：

- 再实现第二套 paired-seed rule simulation；
- 把这批 probe bots 当正式 Planner；
- 根据尚未跑完的数据改默认 HP；
- 开始 GLM Prompt 定稿。

可以低冲突并行：

- 比赛提交要求整理；
- Replay/日志需求分析（不改 Engine 行为）；
- 文档审阅；
- 独立代码 review。

## 9. 下一步 Gate

只有 CI 和完整实验成功后，才根据真实结果决定：

```text
A. 有明显且可解释的规则信号
→ 进入“每 3 回合规则替换”控制器实验

B. 有数值变化但策略几乎不变化
→ 优先改测试 Planner / 动作选择模型，再验证

C. 合法规则普遍几乎无影响
→ 回到 DSL / 基础玩法，不接 GLM
```
