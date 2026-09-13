# Handoff — Natural Language Holdout Gate V0.1

> 日期：2026-09-08  
> 分支：`eval/nl-rule-holdout-v0.1`  
> 状态：holdout / Gate / workflow selector 已实现；等待 PR CI；尚未运行 live holdout。

## 1. 前置事实

`mimo-v2.5-pro` baseline 已运行两轮。

第一轮：

```text
legal semantic correct = 1/8
safe rejection         = 9/10
false_accepts           = 0
false_rejects           = 7
```

PR #20 只修 Prompt JSON shape 契约。

第二轮：

```text
legal semantic correct = 8/8
safe rejection         = 10/10
false_accepts           = 0
false_rejects           = 0
wrong_legal_candidates  = 0
```

第二轮 workflow run：

```text
34174271078
```

结果记录：

```text
docs/experiments/MIMO_V25_PRO_NL_LIVE_AFTER_PROMPT_FIX_2026-09-08.md
```

## 2. 为什么不能直接进入 E2E

原 18 条 baseline 已用于 Prompt 反馈，因此第二轮 100% decision accuracy 不能证明泛化。

本分支没有继续调 Prompt，而是新增独立 holdout：

```text
evals/natural_language_rule_holdout_v0.1.json
40 cases = 20 LEGAL + 20 NO_CANDIDATE
```

## 3. Gate 已在 live 前冻结

```text
docs/experiments/NATURAL_LANGUAGE_HOLDOUT_GATE_V0.1.md
```

硬性要求：

```text
false_accepts = 0
wrong_legal_candidates = 0
```

可用性最低要求：

```text
legal_semantic_correct >= 18/20
no_candidate_decision_correct >= 19/20
```

reason-code exact match 不是硬门槛。

## 4. 本分支明确没有修改

```text
SYSTEM_PROMPT_V0_1
Rule DSL
RuleValidator
NaturalLanguageRuleAdapter acceptance semantics
MiMo Provider request protocol
DynamicRuleController
Engine
anti-stall
```

这点非常重要：其他 AI 不要在 holdout live 之前“顺便优化 Prompt”。

## 5. Workflow 改动

手动 workflow 新增固定选择：

```text
suite = baseline | holdout
```

只映射到仓库内两个固定文件，不允许任意 corpus path 输入。

## 6. CI 检查

新增单元测试要求 holdout：

```text
40 unique cases
20 CANDIDATE
20 NO_CANDIDATE
所有 expected legal candidate 均通过当前 RuleValidator
```

## 7. 并行开发边界

在本 PR 合并并完成第一次 live holdout 之前，其他 AI / 开发者不要修改：

```text
SYSTEM_PROMPT_V0_1
evals/natural_language_rule_holdout_v0.1.json
NATURAL_LANGUAGE_HOLDOUT_GATE_V0.1.md
live-natural-language-benchmark.yml 的 suite 语义
```

低冲突可并行：

- UI 草图；
- Replay 需求分析；
- 只读安全 review；
- 正式 MVP 分工草案（不要开始实现产品层）。

## 8. 下一步

PR CI PASS + merge 后，仓库管理员手动运行：

```text
provider = mimo
model = mimo-v2.5-pro
suite = holdout
```

拿到 Artifact 后先按冻结 Gate 判断 PASS / FAIL，再决定是否进入真实自然语言驱动的动态完整比赛。

## 9. 正式开发状态

截至本 handoff：

```text
Formal MVP development = NOT STARTED
```

即使 holdout PASS，下一步仍先做自然语言端到端比赛 Gate；真实战斗 Agent Gate 通过后才宣布正式 MVP 开发开始并进行双人任务拆分。
