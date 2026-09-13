# Public Rule Core Signal — 第一轮成对实验结果

> 日期：2026-09-07  
> 状态：Experimental evidence / 非最终玩法结论  
> CI：`rule-core-signal`  
> 设计：5 条合法规则 × 4 组 probe pairing × 每格 1,000 paired seeds。每个 seed 同时跑无规则 baseline 与固定规则整局。

## 1. 本轮回答的问题

> 合法公共规则是否真的能稳定、可解释地改变战斗，而不只是“数值结构上可以修改”？

答案：

> **是。已经出现明确的 core signal。**

但同时发现：

> **现有 liveness 机制面对“偶尔造成一点伤害、但整体战斗非常慢”的规则时不够强，TIMEOUT 可显著升高。**

因此本轮不是无条件 Go，而是：

```text
Core mechanic signal: GO
Liveness robustness: BLOCKER before dynamic rule replacement
```

---

## 2. 总体信号

下面把 4 个策略配对等权汇总，仅用于观察方向，不代表未来正式 Agent 分布。

| 规则 | 平均回合变化 | 平均 outcome change rate | 主要可解释变化 | 风险 |
|---|---:|---:|---|---|
| Bow Range +1 | +4.34 | 26.2% | Attack-first 从接近敌人改为原地远射 | 某镜像配对 TIMEOUT 33% |
| Move Range +1 | -0.59 | 8.3% | 混合配对移动距离增加、战斗略加速 | 某些镜像局几乎无实际结果变化 |
| Distance>=3, Bow Hit ×0.5 | +6.68 | 38.2% | 远程战斗显著变慢、Bow 次数增加 | 最高 TIMEOUT 31.6% |
| HP<=2, Bow Damage +1 | -1.66 | 34.3% | 残血阶段更快收束、双杀明显增加 | 会提高 DRAW_MUTUAL_DEATH |
| 连续同武器>=2, Bow cooldown | -0.33（配对方向差异大） | 40.5% | Bow 使用下降、移动/Knife 使用增加 | 对不同策略的节奏方向不一致 |

最重要的不是均值，而是存在多个**不同性质、能解释原因的响应**。

---

## 3. 规则确实能改变动作策略

### 3.1 Bow Range +1：最直接的动作改变

Attack-first vs Attack-first：

```text
baseline:
平均 8.024 回合
平均移动距离 2

Bow Range +1:
平均 25.442 回合
平均移动距离 0
first-action change rate = 100%
```

解释：

基础 Bow Range=3 时，两边开局距离4，Attack-first 必须先接近。

规则把 range 提到4后，两边开局就认为“可以攻击”，因此改为原地远射。

这证明：

> Rule 不只是改变命中公式，而是能改变 probe bot 的动作选择。

但这条规则同时暴露了严重的拖延风险，见第6节。

### 3.2 Move Range +1：规则不保证在所有策略下都有价值

Attack-first 镜像中：

```text
first-action change rate = 100%
但：
outcome change rate = 0%
平均回合变化 = 0
```

说明：

> “动作变了”不等于“战略结果一定变了”。

在 Attack-first vs Kite / Kite vs Attack-first 中则：

```text
平均移动距离约 3 → 5
outcome change rate 约 15.8% / 17.4%
平均回合减少约 1.0 / 1.3
```

这属于合理的策略依赖性，而不是规则必须对每个 matchup 都产生相同效果。

---

## 4. 条件规则能在中后期改变结果，而不需要改第一步

### HP<=2 → Bow Damage +1

四个 pairing：

```text
first-action change rate = 0%
```

符合预期，因为开局 HP=5，不触发条件。

但 outcome change rate：

```text
26.9% ~ 39.7%
```

平均回合减少：

```text
约 1.0 ~ 1.9 回合
```

且多个 pairing 的 `DRAW_MUTUAL_DEATH` 明显增加。

因此：

> 状态条件规则可以在后期改变终局分布，即使完全不改变开局行为。

这对“玩家观察局势后制定规则”的核心玩法是正向证据。

---

## 5. 历史条件 + Cooldown 能产生明显的行为重构

规则：

```text
CONSECUTIVE_SAME_WEAPON_USE >= 2
→ Bow cooldown 1 round
```

在 Attack-first vs Kite：

```text
Bow attacks: 29.572 → 16.844
Knife attacks: 0 → 1.744
Move distance: 3 → 11.439
Outcome changed: 37.3%
```

反向 pairing：

```text
Bow attacks: 29.736 → 16.645
Knife attacks: 0 → 1.769
Move distance: 3 → 11.352
Outcome changed: 38.6%
```

这是当前最有价值的 core signal 之一：

> 规则不是简单让数字更大/更小，而是迫使测试策略改变“移动还是射击、继续用弓还是接近后换刀”的行为结构。

仍不能据此证明正式 Planner 会产生足够复杂的适应，但已经证明规则系统具备产生适应压力的能力。

---

## 6. 新发现的高优先级风险：稀疏伤害可以绕开现有 Hard Liveness 触发逻辑

当前普通 anti-stall 计数核心是：

```text
连续无伤害回合数
```

一旦有实际伤害：

```text
no_damage_streak = 0
```

这对“完全停战”有效，但对下面这种情况不够：

```text
远距离
低命中率
偶尔命中一次
→ streak 清零
→ 又连续多回合 miss
→ 偶尔再命中
→ 始终可能达不到连续12回合无伤害
```

### 实际数据 A：Bow Range +1

Attack-first vs Attack-first：

```text
baseline TIMEOUT = 0%
rule TIMEOUT = 33.0%

平均回合：
8.024 → 25.442
```

规则让双方开局原地进行低概率远射。

偶发命中足以重置 no-damage streak，但不足以保证在 30 回合前结束。

### 实际数据 B：Distance>=3 → Bow Hit ×0.5

Attack-first vs Kite：

```text
TIMEOUT: 0.5% → 26.2%
平均回合: 14.730 → 23.984
```

Kite vs Attack-first：

```text
TIMEOUT: 0.8% → 31.6%
平均回合: 15.035 → 24.426
```

Kite vs Kite：

```text
TIMEOUT: 0% → 11.0%
平均回合: 13.157 → 20.841
```

这不是小幅平衡波动，而是结构性信号。

### 为什么对本项目尤其危险

真人玩家的目标就是延长战斗。

因此玩家有动力寻找：

```text
伤害不完全归零
但足够稀疏
→ 经常重置 no_damage_streak
→ 尽量拖到 MAX_ROUNDS
```

如果这种规则成为稳定最优策略，玩家核心玩法可能退化成“寻找最稳定的低 DPS 规则”。

---

## 7. 对之前 liveness 结论的修正

此前可以证明的是：

> **一旦连续 12 回合无实际伤害并进入已锁存 Hard Liveness，系统能够强制交战。**

现在不能再把它表述成：

> “合法规则下系统普遍能避免 TIMEOUT。”

后者已经被实验数据否定。

因此需要把 liveness 问题拆成：

```text
A. Hard Liveness 触发后是否能终局？
当前：基本成立。

B. 合法规则/策略是否能长期避免触发 Hard Liveness，同时把比赛拖到 TIMEOUT？
当前：明确可以。
```

B 是下一阶段的高优先级问题。

---

## 8. 当前客观判断

### 已得到正向证据

- 合法公共规则确实能改变动作；
- 条件规则确实能改变后期结果；
- 历史条件/cooldown 能改变武器使用和移动结构；
- 不同规则对不同策略产生不同响应，而不是所有规则只有一个统一效果。

### 尚未证明

- 正式 Planner 会有同样丰富的适应；
- 玩家长期不会找到单一最优拖延模板；
- 每3回合换规则会更有趣；
- GLM 增加了必要价值；
- 当前 liveness 足够健壮。

### 当前 Gate

不是直接进入动态规则 controller。

建议：

```text
先做 adversarial liveness / stall exploit 实验
→ 修正或重新定义 anti-stall
→ 再回归 paired rule simulation
→ 通过后再做每3回合规则替换
```

原因：玩家目标与当前发现的 timeout exploit 在激励上高度一致，不能推迟到 UI/LLM 阶段再处理。
