# Live Natural-Language Benchmark Runbook

> 目的：让不熟悉命令行的协作者通过 GitHub UI 安全运行真实模型语料测试。
>
> 当前 live provider：**MiMo China Token Plan**。智谱 Provider 保留，API 恢复后可用同一 corpus 比较。

## 1. 当前推荐配置

```text
provider = mimo
model = mimo-v2.5-pro
```

MiMo China Token Plan 默认 Base URL：

```text
https://token-plan-cn.xiaomimimo.com/v1
```

真实 Token Plan Key 不进入仓库。

## 2. GitHub Secret

在仓库：

```text
Settings
→ Secrets and variables
→ Actions
→ New repository secret
```

名称：

```text
MIMO_API_KEY
```

值填写 Token Plan 页面提供的专属 key。

不要把 Key 写进 Issue、PR、README、`.env` 或聊天文本。

## 3. Workflow 的两个 suite

进入：

```text
Actions
→ live-natural-language-benchmark
→ Run workflow
```

现在有固定 `suite` 选择：

```text
baseline
holdout
```

### baseline

```text
evals/natural_language_rule_corpus_v0.1.json
18 cases
```

这是开发过程中已经用于 Prompt 反馈的语料，适合回归，不再作为泛化证明。

### holdout

```text
evals/natural_language_rule_holdout_v0.1.json
40 cases = 20 LEGAL + 20 NO_CANDIDATE
```

这是在当前 Prompt 修复后创建的新测试集，用于判断自然语言映射是否真正泛化。

## 4. 当前推荐的下一次运行

保持：

```text
provider = mimo
model = mimo-v2.5-pro
suite = holdout
```

然后点击 Run workflow。

Workflow 只支持手动触发，不会因普通 push / PR 自动消耗 Token Plan 额度。

## 5. 查看结果

运行完成后，Artifact：

```text
natural-language-benchmark
└── result.json
```

重点指标：

```text
false_accepts
wrong_legal_candidates
legal_semantic_correct
no_candidate_decision_correct
false_rejects
decision_accuracy
```

不要只看 `exact_accuracy`。

## 6. Holdout Gate

详细标准见：

```text
docs/experiments/NATURAL_LANGUAGE_HOLDOUT_GATE_V0.1.md
```

硬性要求：

```text
false_accepts = 0
wrong_legal_candidates = 0
```

最低可用性：

```text
legal_semantic_correct >= 18/20
no_candidate_decision_correct >= 19/20
```

reason code 的精确分类不是硬性条件。

## 7. 已有 baseline 结果

第一轮 `mimo-v2.5-pro`：

```text
legal semantic correct = 1/8
safe rejection         = 9/10
false_accepts           = 0
```

Prompt JSON 契约修复后第二轮：

```text
legal semantic correct = 8/8
safe rejection         = 10/10
false_accepts           = 0
false_rejects           = 0
wrong_legal_candidates  = 0
```

第二轮结果说明 Prompt 修复有效，但因为 baseline 已参与调参，必须由 holdout 再验证泛化。

## 8. 可选模型比较

如果未来要比较：

```text
mimo-v2.5-pro
mimo-v2.5
glm-5.1
```

必须在相同 commit、相同 suite 下比较，不能为不同模型换题。

## 9. 当前阶段

在 holdout live 结果审核通过前：

```text
Natural-language baseline regression = PASS
Natural-language holdout generalization = 未验证
End-to-end natural-language match = 未开始
Formal MVP development = 未开始
```
