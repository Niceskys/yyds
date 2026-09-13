# Handoff — Natural-Language Verified Pipeline Holdout V0.2

## 当前状态

已知 V0.1 verified regression 在 PR #23 后达到：

```text
20/20 legal correct
20/20 NO_CANDIDATE blocked
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
```

这个结果只证明已知问题回归通过，不证明泛化。

## 本分支做了什么

新增从未用于 Prompt/guidance 调优的 V0.2 corpus：

```text
evals/natural_language_rule_holdout_v0.2.json
```

规模：

```text
25 LEGAL + 25 NO_CANDIDATE
```

新增离线机械一致性测试，并给手动 workflow 增加固定 suite：

```text
holdout-v02
```

新增并冻结第一次 live 前的验收门槛：

```text
docs/experiments/NATURAL_LANGUAGE_HOLDOUT_GATE_V0.2.md
```

## 不要并行修改

在第一次 V0.2 live run 前，不要为了这些题修改：

```text
translator guidance
SYSTEM_PROMPT_V0_1
FAITHFULNESS_PROMPT_V0_1
RuleValidator
Rule DSL
verified acceptance semantics
V0.2 corpus
Gate thresholds
```

如果发现 corpus 机械错误，只能在第一次 live 前修正，并记录原因。

## 第一次 live 的唯一推荐配置

```text
provider = mimo
model = mimo-v2.5-pro
suite = holdout-v02
pipeline = verified
```

## 冻结 PASS 标准

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 23/25
```

且不得存在真实 Provider/protocol failure。

## 下一步

- PASS：进入真实自然语言驱动的动态完整比赛；
- FAIL：保存结果并按失败类型判断，不得继续把 V0.2 当未见集；
- 正式 MVP 开发仍然没有开始；真实战斗 Agent Gate 仍在后面。
