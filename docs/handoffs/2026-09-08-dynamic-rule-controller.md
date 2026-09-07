# Handoff — Deterministic Dynamic Public-Rule Controller

> 日期：2026-09-08  
> 分支：`feat/dynamic-rule-controller`  
> 状态：实现完成；等待 PR CI / dynamic regression。

## 1. 前置状态

PR #13 已通过全部 CI 并合并，正式 V0.1 Engine 当前包含：

```text
no_damage_streak 3/6/9/12 escalation
+
Round >= 24 -> Hard Liveness
```

因此可以进入此前被 liveness blocker 阻塞的动态规则替换阶段。

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

当前规则是 `UNTIL_REPLACED`。

没有新合法规则时，旧规则继续存在。

## 4. Controller 状态

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

## 6. 事件

新增 Controller-level events：

```text
RULE_PHASE_OPENED
RULE_PHASE_DUE
PLAYER_RULE_REPLACED
PLAYER_RULE_REJECTED
PLAYER_RULE_CARRIED_FORWARD
```

这些事件用于后续 Replay / UI / 审计，但不改变 Engine combat semantics。

## 7. 关键测试

覆盖：

- 开局规则在 Round 1 前生效；
- Round 3 仍使用旧规则；
- Round 3 后替换的新规则从 Round 4 生效；
- 无提交不会导致规则自动过期；
- 非法提交保留旧规则；
- due rule phase 不能被跳过；
- 非规则阶段不能任意替换规则；
- 非法开局规则不会产生 active_rule。

## 8. Dynamic paired experiment

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

Gate：

```text
Dynamic TIMEOUT = 0
有比赛经历 >1 replacement
Round4 有 paired comparable matches
第一次 replacement 后存在可观察 action change
pytest PASS
```

## 9. 明确未做

- GLM / LLM；
- 自然语言；
- 20 秒 UI timer；
- 玩家分数 controller；
- 多规则并存；
- 规则自动 TTL；
- 前端。

## 10. 并行开发边界

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

## 11. 下一步

只有本 PR 的 pytest 和 dynamic regression 都通过后，才进入：

```text
Natural Language input
→ LLM adapter
→ untrusted Candidate RuleAST
→ existing RuleValidator
→ DynamicRuleController
```

LLM 永远不能绕过 Validator 直接修改 active_rule 或 GameState。
