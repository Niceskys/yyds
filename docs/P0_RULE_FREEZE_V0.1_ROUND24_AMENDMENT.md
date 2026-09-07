# 《规则之外》V0.1 P0 Anti-Stall Normative Amendment — Round 24

> **状态：Normative Amendment / Engine MVP 实现基线修订**  
> **日期：2026-09-08**  
> **覆盖范围：仅修订 `docs/P0_RULE_FREEZE_V0.1.md` 第 2 章 Anti-Stall / Liveness**

## 0. 优先级

本文件不是新玩法草案，而是对已冻结 P0 规范的有证据修订。

在以下唯一范围发生冲突时：

```text
Absolute late-game Hard Liveness fallback
```

优先级为：

```text
本 Amendment
>
docs/P0_RULE_FREEZE_V0.1.md
>
docs/GAME_DESIGN_V0.1.md
```

除此之外，原 P0 Freeze 的所有语义保持不变。

---

## 1. 为什么修订

原 V0.1 只通过 `no_damage_streak` 进入 Hard Liveness：

```text
有实际伤害 → streak 清零
无实际伤害 → streak +1
streak >= 12 → Hard Liveness
```

paired-seed public-rule 实验发现，合法规则可以形成：

```text
长期低 DPS
+
偶尔造成一次伤害
```

从而周期性把 streak 清零，在不停止战斗的情况下绕过 Hard Liveness。

已知场景的 TIMEOUT 曾达到约：

```text
11.0% ~ 32.4%
```

随后 1,000 paired seeds / cell 的 adversarial liveness 实验比较了 Pressure、Rolling Window、Round-24 和 Hybrid。Round-24 在四类已知 exploit 中均把 TIMEOUT 压到 0%，且 healthy distortion 较低；Hybrid 没有额外收益，反而增加部分正常局干扰。

证据见：

```text
docs/experiments/ADVERSARIAL_LIVENESS_2026-09-07.md
docs/experiments/HYBRID_LIVENESS_2026-09-08.md
```

---

## 2. 新增冻结规则：Absolute Late-Game Fallback

V0.1 产品默认：

```text
late_game_hard_round = 24
```

### Round-Start 语义

每回合开始，在 Agent/Planner 查询有效属性以及 Engine 结算动作之前，系统判断：

```text
if round_no >= late_game_hard_round:
    hard_liveness_active = True
```

因此默认情况下：

```text
Round 23：不会仅因为绝对回合数进入 Hard Liveness
Round 24：在移动与攻击结算前进入 Hard Liveness
```

这条触发条件与 `no_damage_streak` **并列**，不是替代原 anti-stall 阶梯：

```text
Hard Liveness active
=
previously_latched_hard_liveness
OR
no_damage_streak >= 12
OR
round_no >= late_game_hard_round
```

---

## 3. Hard Liveness 的既有语义完全复用

由 Round-24 触发后，不创建第二套终局规则。

仍使用原 P0 Freeze 定义的 Level 4：

```text
bow_range = MAP_MAX_MANHATTAN_DISTANCE
bow_hit_probability = 100%
bow_damage >= 1
```

移动结算后，任何未提交合法攻击的存活单位继续由 Engine 生成：

```text
FORCED_BOW
```

玩家规则仍不能：

- 关闭该系统 Bow；
- 用 cooldown 阻止 `FORCED_BOW`；
- 把该 Bow 伤害降为 0；
- 降低其 100% 命中率。

一旦进入 Hard Liveness，状态继续锁存；后续造成伤害把 `no_damage_streak` 清零，也不会退出 Hard Liveness。

---

## 4. Planner / Rule-Aware Query 一致性

Round-24 不是只在最终 Engine 执行时偷偷生效。

任何供 Planner/Bot 查询本回合有效属性的接口必须在 Round 24 同样返回：

```text
hard_liveness = True
conflict_level = 4
```

这样 Planner 看到的动作空间与 Engine 最终执行语义一致。

---

## 5. 参数与可调性

`24` 是 V0.1 当前冻结参数，不宣称为永久平衡值。

Engine 配置暴露：

```text
GameConfig.late_game_hard_round
```

产品默认值为 24。

历史实验为了可复现，可以显式设置到回合上限之后，例如：

```text
late_game_hard_round = 31
max_rounds = 30
```

这只允许用于实验复现，不能被玩家公共规则修改，也不能作为产品运行时绕过系统 liveness 的入口。

---

## 6. 保持不变

本修订**不改变**：

- `no_damage_streak` 的更新方式；
- 3/6/9/12 conflict-level 阶梯；
- Hard Liveness 的 Bow / FORCED_BOW 语义；
- 玩家规则优先级；
- Agent terminal utility；
- 30 回合 TIMEOUT 最终安全上限；
- Rule DSL；
- 同步移动规则。

---

## 7. 后续 Gate

本修订进入 Engine 后仍必须继续监测：

- Round-24 实际触发率；
- 正常对局 outcome distortion；
- 是否出现新的 Round-24 可利用策略；
- 是否需要将 24 调整为其他值。

在动态规则替换机制加入后，必须再次做 paired regression；如果新的玩家规则重新制造终局漏洞，再通过新的设计变更修订，不允许程序员或 AI 本地私改。
