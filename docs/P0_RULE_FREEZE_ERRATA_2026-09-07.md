# P0 Rule Freeze Errata — Hard Liveness 锁存修正

> **状态：Normative correction**  
> **日期：2026-09-07**  
> **作用范围：仅修正 `docs/P0_RULE_FREEZE_V0.1.md` 第 2 章 Hard Liveness 的状态保持语义。**

## 发现的问题

原冻结规范定义：

```text
发生实际伤害 -> no_damage_streak = 0
```

同时又定义：

```text
no_damage_streak >= 12 -> Hard Liveness
```

如果 Hard Liveness 只由当前 `no_damage_streak` 推导，则第一次强制攻击造成伤害后：

```text
Hard Liveness
→ FORCED_BOW 命中
→ no_damage_streak 清零
→ 下一回合退出 Hard Liveness
```

这样无法成立原规范中的：

> “进入 Hard Liveness 后，在当前 HP=4 / Bow damage>=1 参数下最多 4 个完整攻击结算回合出现死亡事件。”

这是状态机错误，不是平衡参数问题。

## 修正后的唯一语义

GameState 增加：

```text
hard_liveness_active: boolean
```

初始：

```text
false
```

当某回合开始时满足：

```text
no_damage_streak >= 12
```

则：

```text
hard_liveness_active = true
```

一旦变为 `true`：

> **直到本局进入 terminal result 前都不得恢复为 false。**

发生实际伤害仍然正常执行：

```text
no_damage_streak = 0
```

但这只重置普通 anti-stall 计数，不取消已经锁存的 Hard Liveness。

因此之后每一回合都继续应用：

```text
bow_range = MAP_MAX_MANHATTAN_DISTANCE
bow_hit_probability = 100%
bow_damage >= 1
缺失/非法攻击 -> FORCED_BOW
```

直到：

```text
RED_WIN
BLUE_WIN
DRAW_MUTUAL_DEATH
TIMEOUT
```

之一发生。

## 为什么采用锁存而不是“命中后重新计 12 回合”

后者仍允许：

```text
12 回合无伤害
→ 强制打 1 点
→ 再等 12 回合
→ 再强制打 1 点
```

在 30 回合上限下仍可能 TIMEOUT，不能满足 liveness 兜底的原设计目的。

## 测试要求

必须新增至少以下回归测试：

1. `no_damage_streak=12` 时进入 Hard Liveness；
2. 第一次 `FORCED_BOW` 造成伤害后 `no_damage_streak` 清零；
3. 下一回合 `hard_liveness_active` 仍为 true；
4. 下一回合继续强制攻击；
5. Passive vs Passive 在当前 HP=4 参数下应在首次进入 Hard Liveness 后连续攻击直至终局，而不是重新等待 12 回合。

## 文档优先级

在 `P0_RULE_FREEZE_V0.1.md` 正文后续被整理前：

> 本 Errata 对 Hard Liveness 的“是否持续”问题具有更高优先级。

其他 P0 冻结内容不变。
