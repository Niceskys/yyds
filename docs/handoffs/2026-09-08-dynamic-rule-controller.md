# Handoff — Deterministic Dynamic Public-Rule Controller

> 日期：2026-09-08  
> 分支：`feat/dynamic-rule-controller`  
> 状态：**Controller / tests / 4×500 paired experiment PASS；等待最终 PR CI 后合并。**

## 1. 前置状态

PR #13 已通过全部 CI 并合并，正式 V0.1 Engine 当前包含：

```text
no_damage_streak 3/6/9/12 escalation
+
Round >= 24 -> Hard Liveness
```

因此此前被 liveness blocker 阻塞的动态规则替换可以继续。

## 2. 当前实现

新增：

```text
src/rules_beyond/dynamic_rule_controller.py
tests/test_dynamic_rule_controller.py
src/rules_beyond/dynamic_rule_experiment.py
.github/workflows/dynamic-rule-replacement.yml
docs/experiments/DYNAMIC_RULE_REPLACEMENT_2026-09-08.md
```

并在 `src/rules_beyond/__init__.py` 暴露 Controller API。

## 3. V0.1 规则阶段语义

严格按照当前 `GAME_DESIGN_V0.1.md`：

```text
开局前：phase 0
Round 1-3
Round 3 后：phase 1
Round 4-6
Round 6 后：phase 2
...
```

注意：

```text
规则阶段间隔 = 3 回合
!=
规则 TTL = 3 回合
```

当前规则仍是 `UNTIL_REPLACED`。

没有新合法规则时，旧规则继续存在。

## 4. Controller 状态与强制 Gate

`DynamicMatchState` 保存：

```text
game_state
histories
active_rule
last_phase_index
pending_rule_phase_after_round
```

如果第 3/6/9... 回合结束后比赛仍未终局：

```text
pending_rule_phase_after_round != None
```

在处理该规则阶段前，Controller 拒绝继续 resolve 下一回合。

如果该边界回合已经终局，则**不会**再打开规则阶段。

## 5. Rule phase 处理

### 有合法提交

```text
RuleValidator.accepted
→ 新 RuleAST 替换旧 active_rule
```

### 无提交

```text
旧 active_rule 保留
```

### 非法提交

```text
记录 validation issues
→ 拒绝新规则
→ 旧 active_rule 保留
```

### 开局 phase 0 无合法规则

因为不存在旧规则：

```text
active_rule = None
```

## 6. PublicRuleHistory 不随规则替换重置

`docs/PUBLIC_RULE_HISTORY_V0.1.md` 定义的是每方持续保存的、由 Engine 已结算公开事实构成的战斗历史。

因此 replacement 只改变：

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

已经增加回归测试：前三回合连续使用 Bow 后，在 Round 3 后发布基于 `CONSECUTIVE_SAME_WEAPON_USE_GTE(2)` 的 Bow cooldown，Round 4 会直接读取此前公开历史并生效。

## 7. 依赖配置一致性

Controller、RuleAwareGameEngine、RuleValidator 必须使用同一 `GameConfig`。

如果外部注入的 Engine / Validator 配置与 Controller 不一致，立即拒绝构造，避免一个模块按 HP=4/边界 A 验证，另一个模块按另一配置执行。

## 8. Controller-level events

新增：

```text
RULE_PHASE_OPENED
RULE_PHASE_DUE
PLAYER_RULE_REPLACED
PLAYER_RULE_REJECTED
PLAYER_RULE_CARRIED_FORWARD
```

这些事件用于后续 Replay / UI / 审计，不修改 combat semantics。

## 9. 单元测试覆盖

当前覆盖：

- 开局规则在 Round 1 前生效；
- Round 3 仍使用旧规则；
- Round 3 后新规则从 Round 4 生效；
- 无提交不会导致规则自动过期；
- 非法提交保留旧规则；
- due rule phase 不能被跳过；
- 非规则阶段不能任意替换规则；
- 非法开局规则不会产生 active_rule；
- Round 3 若已经终局，不再打开规则阶段；
- PublicRuleHistory 跨 replacement 连续；
- Validator config 必须与 Controller config 一致。

## 10. Dynamic paired experiment

固定 dynamic schedule：

```text
phase0 Bow Range +1
phase1 Move Range +1
phase2 Bow Hit x0.5 at Distance>=3
phase3 Low HP Bow Damage +1
phase4 Repeat Bow cooldown
```

对照：

```text
phase0 Bow Range +1
之后不提交，始终沿用 phase0
```

四种 Attack/Kite pairing，每组 500 paired seeds。

结果：

| Pairing | Outcome change | Mean replacements | Round4 action change | Static mean rounds | Dynamic mean rounds | TIMEOUT |
|---|---:|---:|---:|---:|---:|---:|
| Attack-first vs Attack-first | 49.6% | 3.888 | 58.0% | 22.364 | 11.188 | 0% |
| Attack-first vs Kite | 31.8% | 4.652 | 0% | 15.278 | 15.226 | 0% |
| Kite vs Attack-first | 28.8% | 4.656 | 0% | 15.586 | 15.396 | 0% |
| Kite vs Kite | 32.4% | 4.572 | 0% | 11.242 | 14.344 | 0% |

判定：

```text
Dynamic replacement gate = PASS
```

注意：固定 dynamic schedule 只是机制探针，不是正式平衡方案。它在不同 pairing 中既可能缩短也可能延长战斗。

## 11. 明确未做

- GLM / LLM；
- 自然语言；
- 20 秒 UI timer；
- 玩家分数 controller；
- 多规则并存；
- 规则自动 TTL；
- 前端。

## 12. 并行开发边界

本 PR 合并前，其他 AI / 开发者不要同时修改：

```text
dynamic_rule_controller.py
rule phase cadence
active_rule replacement semantics
```

可以并行：

- Replay/UI 所需事件字段 review；
- LLM -> Candidate RuleAST 的接口设计草案；
- 独立 PR code review；
- 比赛材料整理。

## 13. 下一步

只有本 PR 的最终 CI 全部通过并合并后，才进入：

```text
Natural Language input
→ LLM adapter
→ untrusted Candidate RuleAST
→ existing RuleValidator
→ DynamicRuleController
```

LLM 永远不能绕过 Validator 直接修改 active_rule 或 GameState。
