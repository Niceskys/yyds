# Bot 行为缺陷 vs 游戏规则缺陷：第一轮诊断

> 日期：2026-09-07  
> 状态：Diagnostic evidence / 非平衡结论  
> 数据：6 组 × 2,000 局，共 12,000 局，GitHub Actions 实际执行。

## 1. 要回答的问题

第一批 baseline 出现：

```text
AggressiveBot vs AggressiveBot
2000 / 2000 = DRAW_MUTUAL_DEATH
same-destination conflicts = 15498（首批 baseline）
```

不能直接据此修改正式游戏规则，因为 `AggressiveBot` 本身只是一个极简测试策略。

因此本轮只改变 Bot 行为，不改变 Engine、地图、HP、武器或同步移动规则。

新增对照策略：

```text
AttackFirstAggressiveBot

如果当前已经能合法攻击：原地攻击
否则：向对手靠近
```

## 2. 诊断结果

| Red | Blue | Red Win | Blue Win | Draw | Timeout | 平均回合 | Same-destination |
|---|---|---:|---:|---:|---:|---:|---:|
| Aggressive | Aggressive | 0 | 0 | 2000 | 0 | 8.747 | 15494 |
| Attack-first | Attack-first | 831 | 897 | 272 | 0 | 6.319 | 0 |
| Aggressive | Attack-first | 987 | 0 | 1013 | 0 | 3.000 | 2000 |
| Attack-first | Aggressive | 0 | 989 | 1011 | 0 | 3.000 | 2000 |
| Attack-first | Kite | 918 | 996 | 84 | 2 | 11.1405 | 0 |
| Kite | Attack-first | 989 | 925 | 86 | 0 | 11.241 | 0 |

## 3. 可以得出的结论

### 结论 A：Aggressive vs Aggressive 的 100% 双杀不是游戏规则不变量

只改变一个非常简单的 Bot 行为：

```text
能打到 -> 先攻击，不继续往中心硬挤
```

在完全相同游戏规则下：

```text
same-destination conflicts:
15494 -> 0

mutual death:
100% -> 13.6%（272 / 2000）
```

因此：

> 第一批 `Aggressive vs Aggressive` 的极端退化主要由 naive heuristic 与同步规则发生耦合造成，不能把它直接解释为“同步移动规则必须修改”。

当前没有证据支持仅因为这一现象修改地图、取消同步行动或改变同格冲突规则。

### 结论 B：基础规则能对不同策略产生明显不同结果

已有简单策略表现：

- Kite 对原始 Aggressive 有明显优势（来自 baseline）；
- 原始 Aggressive 对 Attack-first 有明显优势；
- Attack-first 与 Kite 大致接近，平均约 11 回合；
- Attack-first 镜像对局不再固定双杀。

这只能证明：

> 当前规则至少没有立刻退化成“所有简单策略都产生同一个结果”。

不能据此证明正式 Planner 会产生丰富策略，也不能证明游戏已经好玩。

### 结论 C：当前更值得怀疑的是战斗节奏，而不是同步移动规则

本轮出现：

```text
Aggressive vs Attack-first: 平均 3 回合
Attack-first vs Attack-first: 平均 6.319 回合
Attack-first vs Kite: 约 11.1 回合
```

而玩家规则窗口当前暂定每 3 回合一次。

如果正式 Agent 的一部分对局经常只持续 3–6 回合，玩家可能只有 1–2 次真正干预机会，核心循环：

```text
制定规则 -> 观察适应 -> 再改规则
```

可能来不及展开。

这不是已经证明的产品缺陷，但它比“100% 双杀”更值得下一轮实验。

## 4. 下一步

不修改正式规则，先做参数敏感性实验：

```text
HP
Knife Damage
（必要时再测 Bow 数值）
```

目标不是寻找“最好玩的参数”，而是先回答：

1. 当前 HP=4 / Knife Damage=2 是否让大量对局过快结束；
2. 稍微提高 HP 或降低近战爆发后，平均回合是否进入更适合玩家多次改规则的范围；
3. 调整是否会引入大量 Timeout / Hard Liveness / Draw。

在这一轮完成前，仍不接 GLM、不做复杂 Planner、不因 Bot 行为直接修改同步规则。
