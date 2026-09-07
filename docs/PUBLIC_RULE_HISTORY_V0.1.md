# Public Rule History V0.1

> **状态：Normative clarification / Rule Evaluator 实现基线**  
> **日期：2026-09-07**  
> **原因：** `P0_RULE_FREEZE_V0.1.md` 已列出历史型 Condition，但没有完整定义其运行时历史状态。本文补全该缺口。

## 1. 总原则

规则历史只记录：

> **Game Engine 已经公开结算完成的事实。**

不记录：

- Agent 原本想做什么；
- 未执行计划；
- private memory；
- hidden reasoning；
- 对方尚未提交的动作。

因此 Rule Evaluator 永远基于“实际发生了什么”，而不是“AI 打算做什么”。

---

## 2. 每方公开历史状态

每个阵营保存：

```text
PublicRuleHistory {
  has_previous_round: bool
  moved_last_round: bool
  last_attack_weapon: KNIFE | BOW | NONE
  consecutive_bow_miss: int
  consecutive_same_weapon_use: int
}
```

初始：

```text
has_previous_round = false
moved_last_round = false
last_attack_weapon = NONE
consecutive_bow_miss = 0
consecutive_same_weapon_use = 0
```

注意：第一回合不存在“上一回合”，因此所有引用上一回合的 Condition 都返回 false。不能因为初始字段是 `NONE/false` 就把不存在的历史当成真实上一回合。

---

## 3. DID_NOT_MOVE_LAST_ROUND

定义：

```text
has_previous_round == true
AND
本方单位上一回合结束位置 == 上一回合开始位置
```

即只看**实际位移结果**。

因此：

- 主动 STAY → true；
- 想移动但发生 same-destination conflict → true；
- 想交换位置而冲突失败 → true；
- 提交非法 move path，被 Engine 转为 STAY → true；
- 成功移动至少一个格 → false。

不根据“是否提交了 move intent”判断。

---

## 4. LAST_ATTACK_WEAPON_IS

定义为上一回合**真正进入 `ATTACK_RESOLVED` 的武器**。

```text
实际 Knife 攻击结算 -> KNIFE
实际 Bow 攻击结算 -> BOW
没有任何合法/强制攻击被结算 -> NONE
```

特殊情况：

- 提交非法攻击并被 Engine 拒绝，没有替代攻击 → NONE；
- Hard Liveness 生成 `FORCED_BOW` → BOW；
- Bow Miss 仍然是 BOW，因为攻击真实发生了；
- 第一回合开始时该 Condition 一律 false，因为没有上一回合。

---

## 5. CONSECUTIVE_BOW_MISS_GTE

这是“连续完整回合都以 Bow Miss 结束”的计数。

上一回合若实际发生：

```text
ATTACK_RESOLVED
weapon = BOW
hit = false
```

则：

```text
consecutive_bow_miss += 1
```

否则统一：

```text
consecutive_bow_miss = 0
```

因此以下都会打断连续 Miss：

- Bow Hit；
- Knife 攻击；
- 没有攻击；
- 非法攻击未执行；
- `FORCED_BOW` 命中。

V0.1 Validator 已限制该阈值为 `1..3`。

---

## 6. CONSECUTIVE_SAME_WEAPON_USE_GTE

统计连续完整回合实际使用同一种**非 NONE**武器的次数。

示例：

```text
Round 1: BOW -> 1
Round 2: BOW -> 2
Round 3: BOW -> 3
Round 4: KNIFE -> 1
Round 5: NONE -> 0
Round 6: KNIFE -> 1
```

计算必须基于实际 `ATTACK_RESOLVED`，而不是提交动作。

如果上一回合没有实际攻击：

```text
consecutive_same_weapon_use = 0
```

为了计算下一回合，需要同时参考上一轮的 `last_attack_weapon`。

---

## 7. Round Start 求值关系

玩家规则仍按 P0 Freeze 规定：

```text
Round Start Public Snapshot
```

只求值一次。

顺序固定：

```text
上一回合 Engine 完成结算
→ 更新 PublicRuleHistory
→ 下一回合开始
→ 对当前 RuleAST 求值
→ 得到本回合固定 Rule Modifier
→ 双方 Agent / Bot 基于同一公开状态决策
→ Engine 执行
```

因此本回合发生的移动、命中、Miss 不会让本回合 Rule 条件中途重新触发。

---

## 8. 公平与信息边界

Red 与 Blue 使用完全相同的历史更新算法和 Rule Evaluator。

每方历史字段都属于公开事实，因此两边都可以看到：

- 对方上一回合是否实际移动；
- 对方上一回合实际用了哪种武器；
- 对方公开的连续 Bow Miss 次数；
- 对方公开的连续同武器使用次数。

这不包含任何隐藏思考。

---

## 9. 测试要求

必须覆盖：

- 第一回合所有 history-based Condition 为 false；
- STAY -> DID_NOT_MOVE=true；
- 移动冲突 -> DID_NOT_MOVE=true；
- 成功移动 -> DID_NOT_MOVE=false；
- 非法攻击 -> LAST_ATTACK=NONE；
- Bow Miss -> LAST_ATTACK=BOW 且 bow_miss streak +1；
- Bow Hit -> bow_miss streak 清零；
- Bow/Bow 连续使用 -> same_weapon 1,2,...；
- Bow -> Knife -> same_weapon 重置为1；
- 无攻击 -> same_weapon=0；
- FORCED_BOW 计为实际 BOW 使用。

---

## 10. 设计边界

这份定义的目标不是制造更复杂的玩法，而是消除实现歧义。

未来如果认为：

- “跳过一回合是否应该打断 Bow Miss streak”；
- “冲突失败是否应该算主动不移动”；

需要不同玩法，可以另开规则版本。

V0.1 中不允许不同模块自行采用不同解释。
