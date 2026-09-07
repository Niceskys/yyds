# Handoff — Rule → Engine Integration V0.1

> 日期：2026-09-07  
> 分支：`feat/rule-engine-integration-v0.1`  
> 目的：给后续新窗口、其他 AI 或并行开发者快速继承上下文，减少重复实现和文件冲突。

## 1. 这次在做什么

把已经合并的：

```text
Rule DSL
→ Validator
→ Rule Evaluator
→ Public Rule History
```

第一次接到真实战斗结算中。

本分支新增：

```text
src/rules_beyond/rule_engine.py
```

核心类：

```text
RuleAwareGameEngine
```

它负责：

- 每回合开始按公开状态/历史求值公共规则；
- 对 RED / BLUE 分别生成有效属性；
- 让 move range / weapon range / damage / bow hit multiplier / cooldown 真正影响战斗；
- 保持 Hard Liveness 最终兜底不可被玩家规则关闭；
- 每回合结算后更新 PublicRuleHistory。

## 2. 为什么没有直接改 `engine.py`

这是有意的并行开发隔离，不是遗漏。

当前：

```text
GameEngine
= 无玩家规则的稳定 baseline

RuleAwareGameEngine
= 新的动态规则集成层
```

这样做的目的：

1. 保留此前 12,000 / 36,000 局 baseline 的可复现性；
2. 方便 A/B 比较“无规则 vs 有规则”；
3. 避免多人/多 AI 同时大改 `engine.py` 产生高冲突；
4. 如果规则集成有 bug，可以回退新层，而不是污染基础 Engine。

### 并行开发建议

在本 PR 合并前，其他开发者/AI：

- **不要重复实现第二套 Rule → Engine adapter**；
- 若必须修改 `engine.py`，尽量保持其公共行为兼容，并在 PR 中说明；
- 可以并行做与本分支低耦合的文档、比赛需求梳理、Replay 数据结构调研；
- 暂时不要开始 GLM 接入，因为动态规则行为还没通过 simulation 验证。

## 3. 本分支采用的组合语义

属性顺序：

```text
Base Stats
→ Player Rule Modifier
→ Ordinary Safety Clamp
→ System Anti-Stall Minimum / Override
→ Final Safety
```

关键解释：

> Anti-stall 作为最低保障值，不与玩家增益重复做额外加法。

例如基础 Bow Range=3：

```text
玩家规则 +1 → 4
Level 1 anti-stall 也要求至少 4
最终仍为 4，不是 5
```

Level 2 / 3 / Hard Liveness 仍可由系统层超过普通玩家 Bow Range 上限，因为这是系统 liveness override，不是玩家能力。

## 4. Cooldown 与 Hard Liveness

普通玩家 cooldown 先正常生效。

若已经进入 Hard Liveness：

```text
普通 Bow 因 cooldown 判非法
→ attack = null
→ 系统生成 FORCED_BOW
→ FORCED_BOW 忽略玩家 cooldown，命中率 100%
```

不是“所有 Hard Liveness 中提交的 Bow 都自动免 cooldown”。

## 5. 当前测试覆盖

新增：

```text
tests/test_rule_engine.py
```

至少检查：

- `rule=None` 时与原 GameEngine 单回合结果一致；
- Bow Range +1 真正让 4 格 Bow 攻击合法；
- 同一公共条件可以只在低 HP 一方触发；
- Move Range +1 允许两步移动；
- Bow Hit Multiplier 真正进入命中率公式；
- Weapon Cooldown 阻止普通攻击；
- Hard Liveness 将被 cooldown 阻止的 Bow 替换为 FORCED_BOW；
- anti-stall floor 不与玩家 range bonus 重复加成；
- 手工构造的非法 RuleAST 不能绕过 Validator 直接进入 RuleAwareGameEngine。

## 6. 明确没有完成的内容

本分支当前不包含：

- 动态规则批量 simulation；
- Bot 对规则的策略适应层；
- 多条规则同时存在；
- 玩家每 3 回合替换规则的完整 match controller；
- GLM 自然语言 → RuleAST；
- 正式 Planner / Agent；
- UI / Replay 展示。

## 7. 合并后的下一步

如果 CI 全部通过：

```text
RuleAwareGameEngine
→ rule-aware simple bots / planner probe
→ paired-seed dynamic rule simulation
```

第一轮目标不是找最强规则，而是回答：

> 在同样的 seed 和基础策略下，合法公共规则是否能稳定、可解释地改变动作选择、武器使用、战斗时长和结果分布？

如果答案是否定的，应回到核心玩法，而不是继续接 GLM。
