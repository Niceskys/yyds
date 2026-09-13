# 《规则之外》深度研究审计决策记录（2026-09-07）

> 状态：**Accepted as project review baseline / 非最终游戏规则**  
> 目的：把外部深度研究报告中的结论分成“应立即吸收”“需要验证”“暂不采用”，防止团队把研究意见误当成已经证明的设计事实。  
> 适用范围：V0.1 规则冻结、Engine、Rule DSL、Validator、Agent、Planner、Replay 的下一阶段设计与实现。

---

## 1. 当前证据基线

截至本记录创建时，仓库 `main` 只有：

- `README.md`
- `docs/GAME_DESIGN_V0.1.md`

当前没有：

- 可运行 Game Engine；
- Planner / Agent 实现；
- Rule DSL schema；
- Validator 实现；
- Prompt 文件；
- 自动化测试；
- Simulation Harness；
- Replay 实现；
- 前端或后端代码。

因此，现阶段所有“平衡性”“AI 会采取什么策略”“某机制一定能结束对局”等判断都只能是**设计推理或待验证假设**，不能作为实现已经成立的证据。

---

# 2. 审计结论的处理原则

本项目不因为某条意见来自深度研究报告就自动接受。

采用标准只有三个：

1. 是否指出了会导致不同开发者产生不同实现的规范缺口；
2. 是否能通过数学、状态转移或现有文档直接证明，而不是依赖主观体验；
3. 是否能降低 V0.1 的核心技术或竞赛演示风险。

如果一条结论需要大量模拟、真人测试或比赛官方文件才能确认，则将其标记为 **待验证**，而不是直接写成正式设计结论。

---

# 3. 立即接受：V0.1 的 P0 级问题

以下结论证据充分，必须在正式实现冻结前处理。

## P0-1：Agent 的终局效用没有完整定义

当前设计只定义：

1. 最大化获胜概率；
2. 胜率接近时更快获胜；
3. 再接近时保留更多 HP；
4. 不得故意拖延。

但 Planner 在比较以下终局时仍缺少唯一规范：

```text
WIN
DRAW_MUTUAL_DEATH
TIMEOUT
LOSS
```

例如，若 AI 判断自己大概率会输，它是否应主动争取超时？当前文档没有可以直接交给 Planner 的形式化答案。

### 决策

在 Planner 开发前，必须冻结一份**显式终局效用规范**。

可以使用：

- 词典序效用；或
- 标量效用；

但必须能够对任意两个 terminal result 给出稳定排序。

### 注意

深度研究报告中举出的：

```text
WIN > DRAW > LOSS > TIMEOUT
```

或：

```text
WIN > DRAW > TIMEOUT > LOSS
```

都只是候选，不在本记录中直接采纳。

这项顺序必须由项目的行为目标和模拟结果共同决定。

---

## P0-2：当前 anti-stall 不能证明终局可达

当前 V0.1：

```text
地图最大曼哈顿距离 = 8
基础弓射程 = 3
anti-stall 触发时弓射程 = 4
```

因此双方若处于距离 `D >= 5`，即使 anti-stall 触发，也可能仍然没有合法攻击。

这说明当前机制最多能增加接触概率，不能作为“对局一定会恢复交战”的形式保证。

### 决策

正式 Engine 规则冻结前，必须定义一个**系统级 liveness invariant**。

最低要求：

> 在玩家规则合法、双方单位仍存活的前提下，系统机制不得允许一个可以无限保持、且永远无法重新产生有效伤害机会的稳定状态。

### 当前不直接决定的内容

以下都只是候选方案：

- 累积射程 escalation；
- 命中率 floor；
- shrinking arena；
- 强制接近；
- 某种超时前 sudden death。

具体采用哪一种，必须经过 simulation，而不是因为报告推荐就直接落地。

---

## P0-3：同步移动的占位语义必须补全

当前设计已经定义：

- 同一步双方进入同一格 → 双方失败；
- 同一步双方交换位置 → 双方失败。

但仍缺少至少以下明确语义：

```text
Red 计划进入 Blue 当前格
Blue 选择 STAY
```

以及：

```text
双方 move_range 不同
多子步路径在中途发生交叉或占位冲突
```

### 决策

Engine 实现前必须补一份完整的 **joint movement transition table**。

至少明确：

- `STAY` 是否产生占位意图；
- 任意子步结束后是否允许敌我共占一格；
- 多步路径长度不同如何同步推进；
- 某一步失败后剩余路径是否全部停止；
- 非法路径和冲突路径对随后攻击阶段的影响。

### 推荐但尚未升格为最终规范

默认应把 `STAY` 视为对当前格的占位，否则可能产生重叠状态。

---

## P0-4：Rule DSL 必须从“建议结构”升级为“可执行规格”

当前文档已经有正确方向：

```text
自然语言
→ LLM 结构化
→ Rule DSL
→ Validator
→ Game Engine
```

但现有 DSL 仍缺少足够精确的执行语义。

正式实现前至少必须回答：

- condition 是否允许 `AND / OR / NOT`；
- 一个规则最多包含几个 condition；
- 是否允许比较双方属性；
- 连续历史条件保存多少回合；
- effect value 是否允许负数；
- multiplier 是作用于基础值还是最终值；
- clamp 顺序；
- cooldown 的对象、范围和上限；
- condition 在哪个 phase 取样；
- 同一回合内状态变化后是否重新触发规则；
- duration 的精确定义；
- 无实际效果的规则是否接受。

### 决策

在 GLM Rule Interpreter 开发前，必须先冻结 Rule AST schema、evaluation semantics 和 Validator error taxonomy。

LLM 只负责：

> “把玩家表达解析成候选 AST。”

LLM 不拥有：

- 规则合法性最终裁决权；
- 数值越界豁免权；
- 对称性裁决权；
- Engine 状态写权限。

---

## P0-5：规则“对称”不能只检查有没有 RED / BLUE

当前“规则同时作用于双方”只解决了最显式的阵营偏置。

例如：

> “站在第 1 列的单位伤害 +1。”

没有出现 `RED`，但在当前初始布局下可能稳定偏向一方。

### 决策

至少区分两种约束：

### Faction Neutrality

AST 不允许直接引用阵营身份、固定 unit id 或等价的阵营标签。

### Ex-Ante Symmetry

在交换红蓝身份并对棋盘做约定对称变换后，规则结果应保持对应交换。

### 推荐测试方式

使用 metamorphic test：

```text
effect(rule, state)
==
swap_back(effect(rule, swap_and_mirror(state)))
```

具体允许哪些绝对坐标条件，应由 DSL 规范明确，不交给 LLM 自由判断“公平不公平”。

---

# 4. 接受为 P1：必须验证，但不能直接视为事实

## P1-1：基础 1v1 空图可能出现策略退化

风险包括：

- 状态主要退化成 Manhattan distance；
- D=1 时刀可能严格优于弓；
- 对称状态下近战可能容易形成双杀；
- 中央同格冲突可能重复；
- 远距离弓战的随机性可能掩盖策略差异。

### 决策

不因为这些风险立即增加：

- 障碍；
- 地形；
- 职业；
- 多单位；
- 新武器。

先通过简单机器人和批量 simulation 验证。

---

## P1-2：玩家策略可能退化成“前期减速，后期加速”

这是合理风险，但目前没有实际玩家数据或 Planner 数据证明它已经成为 dominant strategy。

### 决策

V0.1 仍保留“尽量延长但避免超时”的核心目标，用它验证机制。

同时 simulation 和试玩必须记录：

- 玩家规则对预计击杀时间的影响；
- 每个 rule window 的边际价值；
- 是否出现稳定的“只降低伤害效率即可最优”的行为；
- 末期是否必然需要一次加速规则。

若被数据证明退化，再考虑：

- 规则预算；
- 目标区间；
- 条件式关卡；
- 其他评分方式。

不要提前加系统掩盖问题。

---

## P1-3：LLM 的价值必须在运行闭环中被证明

理论上，有限 DSL 可以用表单、受控语法或传统 parser 完成。

因此项目不能把“调用了 GLM”本身当作 AI 创新证据。

### 决策

V0.1 中 GLM 的核心职责限定为：

1. **开放自然语言 → 候选 Rule AST**；
2. 在规则变化或重大事件时进行**高层策略重规划 / 规则战略影响解释**；
3. 输出玩家可理解的简短策略说明。

具体坐标动作、概率计算、合法动作枚举、伤害和结算仍由确定性模块负责。

不建议每回合都调用 LLM 决定一步移动。

---

## P1-4：真人能看到多少 Agent 信息必须单独定义

当前文档同时存在：

- private strategy memory；
- `AIIntentPanel` 类似展示设想。

若真人能看到真实未执行计划，而两个 Agent 彼此看不到，会改变游戏的信息结构。

### 决策

V0.1 必须明确 Human-visible information policy。

默认建议：

- 不展示 private memory；
- 不展示隐藏 CoT；
- 不展示尚未锁定的下一步动作；
- 可在双方动作锁定或结算后展示短策略标签和事后解释；
- 任何展示给玩家的 Agent 信息不得重新注入另一方 Agent 上下文。

---

# 5. 暂不采纳为正式结论

以下观点有分析价值，但目前证据不足，不应直接进入正式规则。

## 5.1 “5×5 太小 / 太大”

暂不下结论。

5×5 既可能让战术维度不足，也可能让当前 anti-stall 覆盖不足。尺寸问题必须和移动、射程、liveness 一起模拟。

## 5.2 “累计 escalation 就是最终 anti-stall 方案”

不采纳为最终方案。

它只是候选。

## 5.3 “必须使用 MCTS / Opponent Model / 模型检查”

暂不作为 V0.1 必需项。

当前状态空间很小，优先使用：

- 可单测的合法动作生成；
- joint-action evaluator；
- 概率期望；
- 有限深度搜索；
- 简单 opponent policy。

只有在数据证明需要时再引入复杂算法。

## 5.4 “现在立刻拆成很多规范文档”

不立即执行。

报告指出单个设计文档职责过多，这个问题成立；但 P0 语义尚未冻结时就拆分，会增加重复和漂移。

### 决策

在 Rule Freeze Gate 通过后再拆成至少：

```text
docs/GAME_RULES.md
docs/RULE_DSL.md
docs/AGENT_SPEC.md
docs/ARCHITECTURE.md
```

其中代码可生成的 API / schema 不再额外维护第二套手写事实来源。

---

# 6. 新的 V0.1 实现门禁

从本记录开始，V0.1 不按“写完文档就进入 Agent/UI”推进，而按以下门禁推进。

## Gate A — Rule Freeze

必须冻结：

- terminal result 与 Agent utility；
- 完整同步移动语义；
- 攻击/死亡/双杀/timeout；
- anti-stall/liveness；
- 玩家规则权限边界。

未通过前：

> 不开发正式 Agent，不做高成本前端。

---

## Gate B — Deterministic Engine

要求：

- 不调用任何 LLM 也能完整跑完一局；
- Engine 是唯一状态拥有者；
- 所有边界条件有单测；
- RNG 可注入 seed；
- Event Log 可完整记录结算。

---

## Gate C — Simulation & Liveness

使用最简单机器人先跑批量对局。

最低建议：

```text
>= 1000 baseline matches
```

记录：

- unique win rate；
- mutual death rate；
- timeout rate；
- mean / median duration；
- distance distribution；
- weapon usage；
- no-damage streak；
- deterministic loop 频率；
- Red/Blue symmetry 偏差。

阈值暂不在本记录中硬编码，由实际数据后冻结。

---

## Gate D — Rule DSL & Validator

必须具备：

- versioned JSON Schema / equivalent typed AST；
- static semantic validator；
- numeric bounds；
- faction neutrality；
- symmetry/metamorphic tests；
- liveness-risk checks；
- prompt injection / illegal rule corpus；
- ambiguous rule clarification path。

建议至少维护：

```text
>= 100 条规则测试语料
```

覆盖：

- 合法；
- 非法；
- 歧义；
- 数值越界；
- 阵营偏置；
- prompt injection；
- 无效果规则。

---

## Gate E — GLM + Agent Integration

只有在 Engine、Simulation、DSL 通过后接入。

要求：

- Rule Interpreter 使用 structured output；
- Validator 不信任模型的 `legal=true`；
- Red/Blue context 完全隔离；
- Planner 可以使用 fake/recorded model output 独立测试；
- 模型失败有有限重试和 deterministic fallback；
- Replay 不依赖重新调用 LLM 才能复现。

---

# 7. V0.1 推荐模块边界

```text
Player Rule Text
      ↓
GLM Rule Interpreter
      ↓
Candidate Rule AST
      ↓
Rule Validator
      ↓
Compiled Rule
      ↓
┌──────────────────────────────┐
│ Authoritative Game Engine    │
│ GameState / RNG / Resolver   │
└──────────────────────────────┘
      ↑                  ↑
 Red Action          Blue Action
      ↑                  ↑
 Red Planner         Blue Planner
      ↑                  ↑
 Red Strategy        Blue Strategy
      ↑                  ↑
 Red isolated ctx    Blue isolated ctx

Engine Events
      ↓
Append-only Event Log
      ↓
Replay / Frontend
```

核心权限原则：

| 模块 | 可以做 | 不可以做 |
|---|---|---|
| GLM Rule Interpreter | 生成候选 AST | 直接写 GameState |
| Validator | 接受/拒绝 AST | 自己决定战斗结果 |
| Strategy LLM | 生成高层策略参数/解释 | 直接扣 HP |
| Planner | 枚举并选择合法 ActionProposal | 修改 authoritative state |
| Game Engine | 验证与执行所有状态转移 | 依赖模型自然语言作为规则事实 |
| Replay | 回放记录 | 重新调用模型推测过去发生了什么 |

---

# 8. 下一次正式设计决策必须回答

以下问题必须在 Engine/DSL 开发前给出唯一答案：

1. `WIN / DRAW_MUTUAL_DEATH / TIMEOUT / LOSS` 的 Agent 排序是什么？
2. anti-stall 最终如何保证 liveness？
3. `STAY` 与敌方进入当前格如何结算？
4. 多步同步移动如何处理不同长度路径和中途冲突？
5. 玩家 effect 是否允许负数？
6. `WEAPON_COOLDOWN` 的对象、上限和 evaluation phase 是什么？
7. absolute position 条件是否全部禁止，还是允许通过 symmetry validator 的子集？
8. Rule DSL 是否支持 AND/OR/NOT？支持到什么复杂度？
9. 真人能看到哪些 Agent intent / explanation？
10. GLM 何时 replan：仅规则变化，还是重大状态变化也触发？

---

# 9. 当前项目判断

## 项目方向

**Conditional Go。**

核心概念值得继续验证：

> 玩家通过自然语言修改两个求胜 AI 共同遵守的公共规则，而不是直接控制任何一方。

## 当前实现状态

**No implementation evidence yet。**

现阶段不能声称：

- 已经平衡；
- anti-stall 已保证结束；
- 双 Agent 已真正隔离；
- GLM 已承担运行态核心功能；
- Replay 已可复现；
- 竞赛硬性要求已经满足。

这些必须由后续代码、测试、模拟和官方赛题规则证明。

## 当前最优先事项

```text
冻结 P0 规则
→ 写 Deterministic Engine
→ Simple Bots + Simulation
→ 验证 liveness / symmetry / balance
→ 冻结 Rule DSL
→ Validator
→ GLM Rule Interpreter
→ 双 Agent + Planner
→ Replay / UI / 比赛展示
```

在上述链路成立前，不增加职业、障碍、复杂地形、道具、多单位或复杂长期记忆来掩盖核心机制是否成立的问题。
