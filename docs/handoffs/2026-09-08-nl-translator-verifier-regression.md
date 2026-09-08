# Handoff — Natural-language translator/verifier regression fixes

## 当前状态

已知 V0.1 verified regression 已证明：

```text
false_accepts: 1 -> 0
legal_semantic_correct: 12/20
```

安全回归改善，但可用性过低。

## 本分支做了什么

- 新增 `GuidedRuleCandidateModel`，只给 translator 追加 V0.1 已支持语义说明；
- 不修改原历史 `SYSTEM_PROMPT_V0_1`，保留旧 baseline 可解释性；
- verifier 补充固定 DSL scaffolding 与等价表达规则；
- verified benchmark 改为按 RuleAST 语义比较，AND 条件顺序不再影响结果；
- 保存 run `34175838599` 的 verified regression 结论。

## 明确没做什么

没有修改：

```text
Rule DSL
RuleValidator
Engine
DynamicRuleController
anti-stall
MiMo provider protocol
```

没有创建 V0.2 holdout。

## 为什么还不能创建 V0.2

必须先用已经暴露的 V0.1 holdout 验证本次修正是否：

```text
false_accepts 仍为 0
wrong_legal_candidates 仍为 0
合法规则可用率明显恢复
```

如果这一已知回归仍差，就应继续修已知问题；过早创建 V0.2 会浪费一份未见测试集。

## 其他 AI 不应做什么

- 不要放宽 RuleValidator 来提高模型分数；
- 不要修改 V0.1 holdout 题目；
- 不要把 V0.1 回归结果称为泛化 PASS；
- 不要让 verifier 自动修 Candidate；
- 不要开始前端/MVP 产品开发。

## 下一步

CI 全绿后合并，然后手动运行：

```text
provider=mimo
model=mimo-v2.5-pro
suite=holdout
pipeline=verified
```

若已知 V0.1 regression 达到安全 0 false accept 且合法可用率恢复到至少 18/20，再冻结并创建全新 V0.2 unseen holdout。
