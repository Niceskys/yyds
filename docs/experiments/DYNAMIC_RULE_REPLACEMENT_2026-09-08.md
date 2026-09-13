# Dynamic Public-Rule Replacement Experiment — 2026-09-08

> 状态：**PASS — 4×500 paired seeds 已完成；等待最终 PR CI 后合并。**

## 1. 目标

本轮只验证“真人公共规则按 V0.1 节奏被替换”这一机制，不接 GLM，不引入自然语言，不修改 Rule DSL。

现行节奏来自 `docs/GAME_DESIGN_V0.1.md`：

```text
开局前：规则阶段 0
Round 1-3：使用 phase 0 的 active_rule
Round 3 结束后：规则阶段 1
Round 4-6：使用 phase 1 之后的 active_rule
Round 6 结束后：规则阶段 2
...
```

关键语义：

- 一个规则阶段最多接受一条新规则；
- 新合法规则替换旧规则；
- 无提交时旧规则继续；
- 非法提交被拒绝，旧规则继续；
- 规则**不会因为经过 3 回合自动失效**；
- 系统级 anti-stall / Round-24 不属于真人规则，不被替换。

## 2. Controller 边界

新增：

```text
src/rules_beyond/dynamic_rule_controller.py
```

Controller 只负责：

```text
规则阶段时机
→ RuleValidator
→ active_rule 替换/保留
→ RuleAwareGameEngine
```

它不负责：

- 红蓝 AI 策略；
- LLM/GLM；
- 自然语言解析；
- UI 倒计时；
- 玩家计分；
- 多条真人规则并存。

## 3. Off-by-one 约束

```text
Round 3 本身仍使用旧规则；
Round 3 结算完成且比赛未终局后，才进入下一规则阶段；
新规则从 Round 4 开始生效。
```

同理：Round 6 使用当前旧规则，新规则从 Round 7 开始。

如果 Round 3/6/9... 结束后比赛仍未终局，Controller 标记：

```text
rule_phase_due = true
```

该阶段未处理前禁止直接结算下一回合。

## 4. PublicRuleHistory 连续性

`docs/PUBLIC_RULE_HISTORY_V0.1.md` 已把历史定义为每方持续保存的、由 Engine 已结算公开事实构成的战斗历史。

因此规则替换只改变：

```text
active_rule
```

不会重置：

```text
moved_last_round
last_attack_weapon
consecutive_bow_miss
consecutive_same_weapon_use
```

这意味着新发布的 history-based 规则可以读取发布前已经公开发生的战斗事实。

例如前三回合连续使用 Bow 后，在 Round 3 后发布：

```text
CONSECUTIVE_SAME_WEAPON_USE_GTE(2)
→ Bow cooldown 1 round
```

Round 4 可以立即满足条件。

## 5. 确定性实验

Dynamic schedule：

```text
phase 0: Bow Range +1
phase 1: Move Range +1
phase 2: Distance>=3, Bow Hit x0.5
phase 3: Low HP, Bow Damage +1
phase 4: Repeat Bow cooldown
```

Static paired baseline：

```text
phase 0: Bow Range +1
后续阶段不提交新规则，持续沿用 phase 0
```

实验配置：

```text
HP = 5
Knife Damage = 2
Round-24 Hard Liveness = 产品当前默认
```

HP=5 只用于让更多比赛进入多个规则阶段，不修改产品默认 HP=4。

## 6. 4×500 paired-seed 结果

| Pairing | Outcome change | Mean dynamic replacements | Round-4 action change | Static mean rounds | Dynamic mean rounds | Dynamic TIMEOUT |
|---|---:|---:|---:|---:|---:|---:|
| Attack-first vs Attack-first | 49.6% | 3.888 | 58.0% | 22.364 | 11.188 | 0% |
| Attack-first vs Kite | 31.8% | 4.652 | 0% | 15.278 | 15.226 | 0% |
| Kite vs Attack-first | 28.8% | 4.656 | 0% | 15.586 | 15.396 | 0% |
| Kite vs Kite | 32.4% | 4.572 | 0% | 11.242 | 14.344 | 0% |

每个 pairing 都有 500/500 static + dynamic 对局同时进入 Round 4。

## 7. 解释

### 7.1 Replacement plumbing 有明确策略信号

四个 pairing 的 outcome change 均达到约 28.8%~49.6%，说明动态规则序列不是只在日志层“替换成功”，而是能够传播到 Bot 决策和终局。

### 7.2 Round-4 立即动作变化不是所有 pairing 都发生

第一次 replacement 为：

```text
Bow Range +1
→
Move Range +1
```

Attack-first mirror 在 Round 4 有 58% paired action change；其余三个 pairing 在 Round 4 本身没有变化。

这不构成失败：它说明“某条新规则是否立刻改变当前动作”取决于局面与 Bot 策略。后续多次替换仍使这三类 pairing 的最终 outcome change 达到 28.8%~32.4%。

因此后续 UI/分析不能把“规则已替换”错误等同于“下一回合动作必然改变”。

### 7.3 Liveness 未回退

四个 dynamic pairing：

```text
TIMEOUT = 0%
```

说明当前这组动态规则在 Round-24 正式 liveness 下没有重新打开此前的 timeout blocker。

### 7.4 当前固定序列不是平衡方案

例如 Attack-first mirror：

```text
22.364 rounds
→ 11.188 rounds
```

而 Kite mirror：

```text
11.242 rounds
→ 14.344 rounds
```

这证明规则序列能显著改变比赛长度，但不能据此把该固定序列当作玩家最优规则或正式关卡设计。

本轮只验证动态 replacement mechanism，不优化玩家得分。

## 8. Gate 判定

要求：

1. dynamic TIMEOUT = 0；
2. 至少部分比赛经历 >1 replacement；
3. paired runs 有 Round-4 comparable；
4. 至少一个 pairing 在第一次 replacement 后出现 Round-4 action change；
5. pytest PASS。

当前结果：

```text
Dynamic replacement gate = PASS
```

## 9. 本轮不做

- 不调用 GLM；
- 不实现 20 秒倒计时；
- 不让每条规则自动 3 回合失效；
- 不允许多条真人规则累积；
- 不改变 Rule DSL；
- 不改变 Round-24；
- 不开始前端。

## 10. 下一 Gate

```text
Dynamic controller + regression PASS
↓
Natural Language input
→ LLM adapter
→ untrusted Candidate RuleAST
→ RuleValidator
→ DynamicRuleController
```

下一阶段仍必须保持：LLM 不能直接修改 active_rule、GameState 或 Engine 参数。
