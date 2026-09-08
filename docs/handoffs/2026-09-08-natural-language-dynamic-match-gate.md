# Handoff — Natural-Language Dynamic Match Gate V0.1

> 日期：2026-09-08

## 1. 当前结论

MiMo `mimo-v2.5-pro` 已在第一次 unseen V0.3 verified holdout 上达到冻结 Gate：

```text
legal_semantic_correct = 24/25
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
NO_CANDIDATE blocked = 25/25
```

因此停止继续创建静态 V0.4 corpus，进入真实动态对局接线验证。

## 2. 本分支新增什么

### A. 自然语言 -> DynamicRuleController 编排层

新增：

```text
src/rules_beyond/natural_language_dynamic_controller.py
```

职责：

```text
player text
-> VerifiedNaturalLanguageRuleAdapter
-> accepted candidate or safe rejection
-> DynamicRuleController
```

关键边界：

- accepted candidate 仍由 `DynamicRuleController` 内部 `RuleValidator` 再验证；
- rejected/model-error/verifier-error 不生成可执行 candidate；
- 失败时按“没有有效新规则”处理，保留上一合法 `active_rule`；
- 编排层不直接修改 `GameState`；
- Controller 仍拥有 rule cadence 和 `active_rule`。

### B. Live dynamic match runner

新增：

```text
src/rules_beyond/live_natural_language_dynamic_match.py
```

固定使用 3 个 seed + `RuleAwareAttackFirstBot` mirror，对中文规则 schedule 做完整终局验证。

Phase 2 故意提供一条 OR 规则，必须被 Intent Guard 拦截并 carry forward。

Gate 同时比较 no-rule baseline 与 live phase-0 round-1 actions，证明规则实际影响 planner behavior。

### C. Manual GitHub Action

新增：

```text
.github/workflows/live-natural-language-dynamic-match.yml
```

只允许 `workflow_dispatch`，不会在普通 PR/push 自动消耗 Token Plan。

使用：

```text
MIMO_API_KEY
model=mimo-v2.5-pro
```

失败时仍上传 `result.json`，便于分析具体 phase / round。

### D. Tests

新增：

```text
tests/test_natural_language_dynamic_controller.py
tests/test_live_natural_language_dynamic_match.py
```

离线测试使用 scripted/oracle model，不调用真实 MiMo。

## 3. 明确没有改什么

```text
Rule DSL
RuleValidator 规则边界
Game Engine
DynamicRuleController cadence
anti-stall / Round24
MiMo provider protocol
translator Prompt/guidance
faithfulness Prompt
intent guard
product default HP4
```

Live Gate 使用 `HP5/K2` 仅为了稳定覆盖多个阶段，是实验配置，不是产品默认调整。

## 4. 并发热点

本分支主要是新增低耦合文件。

其他开发者/AI 在本 PR 合并前不要重复实现：

```text
Natural Language -> DynamicRuleController orchestration
live natural-language dynamic match workflow
同一套 phase0/1/2/3/4 Gate
```

当前仍不建议两个人正式并行做产品功能；这一阶段之后还有 Agent/Planner integration Gate。

## 5. Merge Gate

必须至少：

```text
pytest PASS
dynamic-rule-replacement PASS
behavior-diagnostics PASS（若被 workflow 触发）
```

离线 oracle full-match test 必须证明：

- 3 seeds 能完成；
- Phase 0/1 replacement 工作；
- Phase 2 OR 被 guard 拒绝并 carry；
- 至少一个 seed 能在拒绝后继续到 Phase 3；
- phase-0 规则改变首回合动作；
- Engine 产生 `RULE_MODIFIER_APPLIED`。

## 6. 合并后的唯一下一步

手动运行：

```text
Actions
-> live-natural-language-dynamic-match
-> Run workflow
-> model = mimo-v2.5-pro
```

第一次真实 run 前不再修改 schedule / seeds / Gate。

详细 Gate：

```text
docs/experiments/NATURAL_LANGUAGE_DYNAMIC_MATCH_GATE_V0.1.md
```

## 7. 如果 Live Gate PASS

不要继续做更多静态 corpus，也不要立刻开始前端。

下一步：

```text
Agent/Planner integration Gate
```

目标是把 probe bots 之后的真实红蓝 Agent 边界、私有记忆隔离、LLM 高层策略、deterministic action planner、replay 可复现性做成正式工程接口和端到端验证。

只有该 Gate 也通过后，才向用户明确宣布：

```text
正式 MVP 开发开始，可以双人 + AI 并行分工
```
