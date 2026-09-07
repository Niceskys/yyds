# 《规则之外》V0.1 P0 规则冻结规范

> **状态：Normative / Engine MVP 实现基线**  
> **版本：V0.1-P0-Freeze**  
> **日期：2026-09-07**  
> **目的：消除 Engine、Planner、Rule DSL、Validator 在核心语义上的歧义。**

---

## 0. 文档优先级

本文件只冻结此前深度审计确认的五个 P0 问题：

1. Agent terminal utility；
2. anti-stall / liveness；
3. 同步移动 occupancy；
4. Rule DSL V0.1 可执行语义；
5. 规则对称性。

如果本文件与 `docs/GAME_DESIGN_V0.1.md` 在上述五个范围内冲突：

> **以本文件为准。**

其他未覆盖设计仍以 `GAME_DESIGN_V0.1.md` 为草案基线。

本次冻结的目标不是声称“这些数值已经平衡”，而是让所有开发者实现同一套可测试规则。

以下仍属于实验参数，可被后续 simulation 修改：

- 5×5 地图；
- HP=4；
- 刀/弓基础数值；
- 30 回合上限；
- anti-stall 的触发阈值；
- Rule DSL 中具体数值边界。

任何实验参数修改都必须保持本文件定义的状态转移语义、信息边界和安全不变量，除非另开设计变更。

---

# 1. Agent Terminal Utility

## 1.1 为什么必须形式化

“最大化胜率、尽快获胜、不得故意拖延”不足以直接交给 Planner。

Planner 必须能够稳定比较：

```text
WIN
DRAW_MUTUAL_DEATH
LOSS
TIMEOUT
```

因此 V0.1 不使用一句 Prompt 代替效用定义。

## 1.2 V0.1 决策目标

每个 Agent 都最大化以下词典序效用向量：

```text
U = (
  P_WIN,
  P_DRAW,
  -P_TIMEOUT,
  -E_WIN_ROUND,
  E_OWN_HP
)
```

按从左到右严格词典序比较。

含义：

1. **首先最大化最终获胜概率 `P_WIN`；**
2. 获胜概率相同时，最大化同归于尽概率 `P_DRAW`；
3. 前两项相同时，最小化超时概率 `P_TIMEOUT`；
4. 前三项相同时，如果存在获胜分支，优先更早获胜；
5. 仍相同时，优先保留更多己方 HP。

因此单个确定终局的顺序为：

```text
WIN > DRAW_MUTUAL_DEATH > LOSS > TIMEOUT
```

## 1.3 为什么 TIMEOUT 低于 LOSS

这是 V0.1 的行为约束，不是现实价值判断。

如果 `TIMEOUT >= LOSS`，一个预期处于劣势的 Agent 可能理性选择永久逃跑，把超时当作优于失败的结果。

将 TIMEOUT 放在最低位，是为了使“主动维持无意义停滞”不会成为合理最优策略。

## 1.4 禁止额外隐含目标

Planner / Prompt 不得擅自加入：

- 帮助真人获得更高分；
- 延长比赛；
- 让比赛更精彩；
- 避免伤害；
- 偏好某种武器；
- 偏好中央区域；
- 与对手形成默契。

除本效用函数和公开规则外，Agent 不拥有其他游戏目标。

## 1.5 后续允许修改的范围

上述效用是 V0.1 实现冻结值，但不是永久产品结论。

Simulation 必须至少统计：

- TIMEOUT 率；
- 明显自杀式进攻比例；
- 劣势方在 `LOSS > TIMEOUT` 下是否产生异常行为；
- DRAW 比例；
- 平均胜利回合。

若数据表明终局排序产生明显退化，可通过新的设计变更调整，禁止程序员本地私改。

---

# 2. Anti-Stall 与 Liveness

## 2.1 设计不变量

系统必须满足：

> 只要双方仍存活，系统级规则就不能允许一个可以永久保持、且永远无法重新产生有效伤害机会的稳定状态。

玩家规则不得覆盖系统 liveness 机制。

## 2.2 `no_damage_streak`

引擎维护：

```text
no_damage_streak: integer >= 0
```

每个完整回合攻击结算后：

```text
if total_applied_damage_this_round > 0:
    no_damage_streak = 0
else:
    no_damage_streak += 1
```

只有**实际扣除 HP 的伤害**才能清零。

以下情况都不清零：

- 发起攻击但 Miss；
- 提交攻击但非法；
- 攻击被 cooldown 阻止；
- 只移动或发生移动冲突。

## 2.3 Conflict Level

下一回合开始时，根据 `no_damage_streak` 计算系统冲突等级：

| 连续无伤害回合 | conflict_level |
|---:|---:|
| 0–2 | 0 |
| 3–5 | 1 |
| 6–8 | 2 |
| 9–11 | 3 |
| ≥12 | 4（Hard Liveness） |

### Level 0

无额外效果。

### Level 1

```text
knife_range += 1
bow_range += 1
```

### Level 2

```text
knife_range += 1
bow_range += 2
bow_hit_probability >= 25%
```

### Level 3

```text
knife_range += 1
bow_range += 3
bow_hit_probability >= 50%
```

### Level 4：Hard Liveness

这是系统安全模式，不是普通玩家规则。

```text
bow_range = MAP_MAX_MANHATTAN_DISTANCE
bow_hit_probability = 100%
bow_damage >= 1
```

并增加：

> **攻击强制规则：** 移动结算后，只要双方仍存活，任何未提交合法攻击的单位由 Engine 自动替换为对敌方的 `FORCED_BOW` 攻击。

Hard Liveness 下：

- 玩家规则不能关闭 Bow；
- 玩家 cooldown 不能阻止 `FORCED_BOW`；
- 玩家规则不能把 Bow 伤害降到 0；
- 玩家规则不能降低该次强制 Bow 的命中率；
- Agent 仍可决定移动，但不能通过 `attack = null` 继续停战。

在当前 5×5、HP=4、Bow 最低伤害=1 的实验参数下，进入 Hard Liveness 后最多经过 4 个完整攻击结算回合就会出现死亡事件。

## 2.4 系统层优先级

有效属性计算顺序固定为：

```text
Base Stats
↓
Player Rule Modifier
↓
Normal Numeric Clamp
↓
System Anti-Stall Modifier / Override
↓
Final Safety Clamp
```

因此玩家规则不能抵消系统 liveness。

## 2.5 当前阈值不是平衡结论

`3/6/9/12` 只是 V0.1 首轮 simulation 参数。

必须用批量模拟检查：

- Hard Liveness 触发率；
- 是否过早干预正常策略；
- 触发后平均剩余回合；
- 是否导致过多确定性双杀；
- 玩家是否可以故意利用 Hard Liveness 获得更高分。

如果触发过多或严重破坏玩法，可以调阈值，但必须保留“最终进入不可被玩家取消的 Hard Liveness”这一系统不变量。

---

# 3. 同步移动与 Occupancy

## 3.1 基本不变量

任意移动子步结算结束后：

```text
Red.position != Blue.position
```

V0.1 永远不允许双方共占一格。

`STAY` 等价于：

```text
OCCUPY(current_position)
```

而不是“没有移动意图所以不占格”。

## 3.2 移动路径预验证

在双方联合移动结算前，Engine 对每个单位独立检查其完整 `move_path`：

- 方向必须属于 `UP / DOWN / LEFT / RIGHT`；
- 路径长度不得超过有效移动距离；
- 单独按该路径移动时不得越界。

若某单位路径预验证失败：

```text
该单位整段 move_path 替换为 []
记录 INVALID_MOVE_PATH
```

攻击字段不因此自动取消；攻击在移动结束后独立验证。

## 3.3 子步同步算法

设：

```text
steps = max(len(red_path), len(blue_path))
```

对 `i = 0 .. steps-1` 逐子步同步处理。

如果某单位：

- 已没有剩余移动；或
- 此前因冲突停止；

则该子步意图为：

```text
intent_destination = current_position
```

即 STAY/占位。

## 3.4 冲突类型 A：进入同一目标格

若：

```text
red_destination == blue_destination
```

则：

- 两方本子步位置均不改变；
- 两方停止本回合剩余移动；
- 记录 `SAME_DESTINATION_CONFLICT`。

这也覆盖：

```text
Red 想进入 Blue 当前格
Blue 已经没有剩余移动 / STAY
```

因为 Blue 的 destination 就是自己的当前格。

## 3.5 冲突类型 B：直接交换位置

若：

```text
red_destination == blue_current
AND
blue_destination == red_current
```

则：

- 双方本子步均失败；
- 双方停止本回合剩余移动；
- 记录 `SWAP_CONFLICT`。

## 3.6 允许进入“同一子步正在被对方离开的格”

以下情况允许：

```text
Red: A -> B
Blue: C -> A
```

只要：

```text
B != A
B != Blue.destination
且不构成直接交换
```

则双方同时成功移动。

这是标准同步状态转移，不把子步错误地实现成“红先走、蓝后走”。

## 3.7 冲突后的攻击

移动冲突只影响移动。

移动阶段结束后：

- 使用最终位置；
- 分别验证双方 attack；
- 合法攻击继续执行；
- 不因移动冲突自动取消攻击。

## 3.8 非法攻击

若攻击字段非法：

```text
attack -> null
记录 INVALID_ATTACK
```

普通模式下不自动补一个替代攻击。

唯一例外是 `conflict_level = 4` 的 Hard Liveness，此时 Engine 可以按第 2 章生成 `FORCED_BOW`。

---

# 4. Rule DSL V0.1 最小可执行规格

## 4.1 总原则

V0.1 采用：

> **Open Language, Closed Semantics**

玩家可以自由使用自然语言表达，但最终只能被解析为本章定义的有限 AST。

GLM 负责：

```text
Natural Language -> Candidate RuleAST
```

GLM 不负责：

- 最终合法性；
- 数值越界豁免；
- 对称性豁免；
- liveness 豁免；
- 直接修改 GameState。

## 4.2 V0.1 RuleAST

规范结构：

```json
{
  "version": "v0.1",
  "target": "ALL_UNITS",
  "conditions": [],
  "effect": {},
  "duration": "UNTIL_REPLACED"
}
```

### 固定约束

```text
target 必须为 ALL_UNITS
conditions 数量：0..2
duration 必须为 UNTIL_REPLACED
每条规则只能有 1 个 effect
```

`conditions = []` 表示 ALWAYS。

多个 conditions 只允许：

```text
AND
```

V0.1 **不支持**：

```text
OR
NOT
嵌套布尔表达式
```

原因是优先保证可验证性和多人实现一致性，而不是最大化 DSL 表达能力。

## 4.3 Condition 允许列表

V0.1 只允许以下原子条件：

```text
SELF_HP_LTE(value)
SELF_HP_GTE(value)
SELF_HP_LT_OPPONENT
SELF_HP_GT_OPPONENT
DISTANCE_LTE(value)
DISTANCE_GTE(value)
ROUND_GTE(value)
DID_NOT_MOVE_LAST_ROUND
LAST_ATTACK_WEAPON_IS(KNIFE | BOW | NONE)
CONSECUTIVE_BOW_MISS_GTE(value)
CONSECUTIVE_SAME_WEAPON_USE_GTE(value)
```

所有条件都必须只依赖：

- 当前公开回合快照；
- 已结算的公开历史；
- 当前单位自身公共属性；
- 敌方公共属性。

不得读取任何 Agent private memory 或隐藏推理。

### 数值边界

```text
HP threshold: 1..CURRENT_MAX_HP
DISTANCE threshold: 1..MAP_MAX_MANHATTAN_DISTANCE
ROUND threshold: 1..MAX_ROUNDS
CONSECUTIVE_* threshold: 1..3
```

## 4.4 V0.1 明确禁止的 Condition

暂不允许：

```text
RED / BLUE / team id
unit id
绝对 row
绝对 col
第 N 行 / 第 N 列
左边 / 右边出生点
靠近红方出生点
靠近蓝方出生点
任意 private intent / private memory
未来随机数
对方尚未提交的动作
```

V0.1 也暂不开放“离中心多远”等绝对几何条件。

不是因为这些条件永远不公平，而是当前 MVP 没有必要为它们增加额外对称证明成本。

## 4.5 Effect 允许列表

V0.1 允许：

```text
MOVE_RANGE_ADD(delta)
KNIFE_RANGE_ADD(delta)
BOW_RANGE_ADD(delta)
KNIFE_DAMAGE_ADD(delta)
BOW_DAMAGE_ADD(delta)
BOW_HIT_MULTIPLIER(multiplier)
WEAPON_COOLDOWN(weapon, rounds=1)
```

### 最终普通模式数值边界

```text
move_range: 1..2
knife_range: 1..2
bow_range: 1..4
knife_damage: 1..3
bow_damage: 1..2
bow_hit_probability: 5%..100%
weapon_cooldown: 仅允许 1 回合
```

Validator 检查的是**应用玩家规则后的最终普通模式数值**，而不是只检查输入 delta。

Hard Liveness 可以在系统层超过普通玩家规则的 bow range 上限，因为它不是玩家规则。

## 4.6 Effect 值是否可以降低属性

V0.1 允许玩家规则降低某些普通模式属性，只要最终数值仍在安全边界内。

例如：

```text
BOW_RANGE_ADD(-1)
BOW_HIT_MULTIPLIER(0.5)
KNIFE_DAMAGE_ADD(-1)
```

可以合法。

但以下永远非法：

```text
最终 damage = 0
最终 hit probability = 0
最终 move range = 0
同时永久关闭全部攻击方式
```

允许负向规则的原因是：真人玩家的核心玩法本来就包含“改变战斗节奏”；若一律只允许增益，玩法空间会被人为锁死。

是否导致玩家形成单一“前期减速”策略，必须通过 simulation / playtest 判断，而不是先验禁止。

## 4.7 条件取样时机

所有玩家规则条件都在：

```text
Round Start Public Snapshot
```

统一求值一次。

得到的 effect 对该单位在整个当前回合固定。

本回合内即使发生：

- HP 改变；
- 移动；
- Miss；
- weapon use；

也**不会在同一回合重新计算玩家规则条件**。

下一回合开始时再重新求值。

这样避免 Engine 出现“移动前满足、移动后又不满足”的中途语义分叉。

## 4.8 命中率计算顺序

普通 Bow：

```text
base_probability = 1.0 * (0.5 ^ (distance - 1))
```

若玩家规则有 `BOW_HIT_MULTIPLIER(m)`：

```text
player_modified_probability = base_probability * m
```

然后：

```text
normal_probability = clamp(player_modified_probability, 0.05, 1.0)
```

之后再应用 system anti-stall floor / override。

即：

```text
Base Formula
→ Player Multiplier
→ Normal Clamp
→ Anti-Stall Floor/Override
→ Final Clamp
```

## 4.9 Cooldown

V0.1 cooldown 只允许：

```text
rounds = 1
```

含义：

> 若某单位在 Round Start 条件求值时命中 `WEAPON_COOLDOWN` effect，则指定武器在该完整回合不可用于普通攻击。

下一回合重新根据条件求值，不维护由玩家规则产生的多回合倒计时。

Hard Liveness 的 `FORCED_BOW` 忽略玩家 Bow cooldown。

## 4.10 无实际效果的规则

如果一条规则结构合法，但在当前基础参数与数值 clamp 下永远不可能改变任何最终数值：

```text
NO_EFFECT_RULE
```

Validator 应拒绝，而不是接受一个视觉上“成功”但实际上永远无效的规则。

---

# 5. 规则对称性

## 5.1 两层约束

V0.1 同时要求：

### Faction Neutrality

AST 不得引用：

```text
RED
BLUE
team id
unit id
spawn identity
```

### Ex-Ante Symmetry

同一 RuleAST 必须对红蓝使用完全相同的 evaluator。

规则效果只能因为**公开状态不同**而对两方产生不同实际结果，不能因为阵营身份不同而产生差异。

例如：

> “HP 比对手低的单位移动 +1”

合法。

因为条件对双方完全相同，只是当前状态可能只有一方满足。

## 5.2 V0.1 禁止绝对位置条件

V0.1 直接禁止 row/col/出生边等绝对位置谓词。

因此：

> “第 1 列单位伤害 +1”

无论文本是否出现 RED，都必须拒绝。

这样可以在 MVP 中避免大量隐式阵营偏置，而不依赖 LLM 判断“这句话公平不公平”。

## 5.3 Metamorphic Test

Rule Engine 必须支持以下对称测试。

对 5×5 当前地图定义变换 `S`：

```text
RED <-> BLUE
(row, col) -> (row, 6 - col)
```

对任意合法 RuleAST 和任意可达公开状态：

```text
effect(rule, state)
==
S^-1(effect(rule, S(state)))
```

如果该性质失败：

```text
SYMMETRY_VIOLATION
```

规则不得进入游戏。

由于 V0.1 已禁止绝对位置条件，绝大多数合法 AST 应天然满足这一性质；该测试仍必须保留，用于防止实现层出现阵营分支。

---

# 6. Rule Validator 最小职责

Validator 至少按以下顺序检查：

```text
1. JSON / Schema
2. Enum / Type
3. Condition Count
4. Allowed Condition
5. Allowed Effect
6. Numeric Bounds
7. Faction Neutrality
8. Ex-Ante Symmetry
9. No-Effect
10. Capability Safety
11. Liveness Compatibility
```

### Capability Safety 永久拒绝

```text
修改 winner
修改 max_rounds
直接写 HP
直接造成事件伤害
治疗
复活
修改 Agent utility
读取 private memory
读取未来 RNG
永久关闭全部攻击
```

### Liveness Compatibility

任何玩家 RuleAST 都不能：

- 修改 `conflict_level`；
- 清零 `no_damage_streak`；
- 禁用 Hard Liveness；
- 降低 `FORCED_BOW` 的系统命中率；
- 禁止 `FORCED_BOW`；
- 把其伤害降到 0。

---

# 7. Engine MVP 必须通过的 P0 测试

在进入 Simple Bots / Simulation 前，至少必须有以下自动测试。

## 7.1 Terminal Utility

- WIN 始终优于 DRAW；
- DRAW 始终优于 LOSS；
- LOSS 始终优于 TIMEOUT；
- 相同 P_WIN/P_DRAW/P_TIMEOUT 时更早胜利优先；
- 前四项相同时更高 HP 优先。

## 7.2 Movement

- 同目标格冲突；
- 直接交换冲突；
- Red 进入 Blue 的 STAY 格失败；
- Blue 进入 Red 的 STAY 格失败；
- 进入对方同子步刚离开的格可以成功；
- move_range=2 的第二子步冲突；
- 一方路径提前结束时继续占位；
- 非法路径整体转为 STAY；
- 移动冲突后合法攻击仍执行；
- 任意结算后双方不能重叠。

## 7.3 Liveness

- 3 回合无伤害进入 Level 1；
- 6 回合进入 Level 2；
- 9 回合进入 Level 3；
- 12 回合进入 Hard Liveness；
- 实际伤害后 streak 清零；
- Miss 不清零；
- Hard Liveness Bow 覆盖地图最大距离；
- Hard Liveness 忽略玩家 Bow cooldown；
- Hard Liveness 下 `attack=null` 被替换为 `FORCED_BOW`；
- 当前 HP/伤害参数下 Hard Liveness 不会无限持续。

## 7.4 DSL / Validator

- 0 condition 合法；
- 1/2 condition AND 合法；
- 3 condition 拒绝；
- OR/NOT 拒绝；
- RED/BLUE 引用拒绝；
- row/col 条件拒绝；
- 修改 winner 拒绝；
- damage=0 拒绝；
- hit=0 拒绝；
- no-effect rule 拒绝；
- 合法负向 modifier 在安全边界内可通过；
- Hard Liveness 不可被玩家规则覆盖。

## 7.5 Symmetry

对一组生成状态执行：

```text
swap team + mirror board
```

要求 RuleEvaluator 输出对应交换。

---

# 8. 本次明确不冻结的内容

本文件不决定：

- 哪种 Planner 最优；
- 是否使用 Minimax / Expectimax / MCTS；
- GLM 每几回合调用一次；
- UI 如何显示策略；
- 真人是否看到多少 Agent intent；
- 5×5 是否最终保留；
- HP=4 是否平衡；
- 刀/弓数值是否平衡；
- 30 回合是否合理；
- 玩家最终计分是否需要更多目标；
- 是否需要长期记忆；
- 是否需要复杂 opponent model。

这些都必须等待 Engine + Simple Bots + Simulation 提供证据。

---

# 9. Rule Freeze Gate

满足以下条件后，P0 Rule Freeze 才算完成：

- [x] Terminal utility 有唯一可编码定义；
- [x] liveness 有不可被玩家规则取消的系统兜底；
- [x] occupancy / STAY / 多子步移动有唯一语义；
- [x] Rule DSL 有 V0.1 封闭语义；
- [x] symmetry 有结构约束与测试定义；
- [ ] 团队审阅本文件；
- [ ] 合并后由 Engine 测试证明实现与规范一致。

Rule Freeze 完成后，下一阶段不是接 GLM，而是：

```text
Deterministic Engine
→ Unit Tests
→ Simple Bots
→ Simulation Harness
```

---

# 10. 下一阶段的唯一目标

下一阶段只回答一个问题：

> **在完全不调用 LLM 的情况下，这套基础规则能否被确定性、可测试、可批量模拟地完整执行？**

如果答案还不是“能”，则不进入 Agent、Prompt、UI 或竞赛演示开发。
