# Handoff — Zhipu Rule Provider + Fixed NL Corpus

> 日期：2026-09-08  
> 最新状态：PR #17 已合并；Provider / corpus / benchmark 已进入 `main`。当前正在补手动 live benchmark workflow；尚未产生真实模型 benchmark 数据。

## 1. 已完成

```text
NaturalLanguageRuleAdapter
+ NO_CANDIDATE envelope
+ ZhipuRuleCandidateModel
+ fixed 18-case corpus
+ benchmark scorer
+ secret ignore rules
```

真实 Provider 可以在不会直接触碰 Engine 的前提下调用智谱 API。

## 2. Provider 语义

默认官方端点：

```text
https://open.bigmodel.cn/api/paas/v4/chat/completions
```

默认模型：

```text
glm-5.1
```

请求使用：

```text
response_format = json_object
thinking = disabled
stream = false
```

模型名可配置，不把 GLM-5.2 自动升级成项目默认。

## 3. Secret 边界

```text
ZHIPU_API_KEY
```

只能来自环境变量 / GitHub Actions Secret / 运行时参数。

`.env` 已加入 `.gitignore`。

禁止：

- 提交真实 key；
- 把 key 写测试；
- 把 Authorization header 打日志；
- 把 key 放 README / Issue / PR / AI 普通聊天。

## 4. 固定语料

```text
evals/natural_language_rule_corpus_v0.1.json
18 cases = 8 LEGAL + 10 NO_CANDIDATE
```

比较 Prompt / GLM-5.1 / GLM-5.2 时必须使用同一 corpus。

## 5. Benchmark 指标

最高风险指标：

```text
false_accepts
```

即：本应拒绝的玩家意图，被模型擅自改写成合法 Candidate。

同时看：

```text
decision_accuracy
legal_semantic_correct
wrong_legal_candidates
false_rejects
exact_accuracy
```

NO_CANDIDATE 的 reason code 是否精确匹配属于次一级指标；安全拒绝本身更重要。

## 6. Live workflow

分支：

```text
chore/live-nl-benchmark-workflow
```

新增：

```text
.github/workflows/live-natural-language-benchmark.yml
docs/LIVE_NL_BENCHMARK_RUNBOOK.md
```

特点：

- 只允许 `workflow_dispatch` 手动运行；
- 普通 push / PR 不会调用模型；
- `ZHIPU_API_KEY` 从 GitHub repository secret 注入；
- model input 通过环境变量传给 shell，避免直接表达式拼接产生注入风险；
- 输出固定为 `benchmark-output/result.json`；
- 结果作为 `natural-language-benchmark` Artifact 保存 30 天。

## 7. 尚未完成

最重要：

> 仍没有真实 GLM-5.1 benchmark 数据。

因此不能描述成：

```text
“GLM-5.1 已验证可用”
```

只能描述成：

```text
“Provider + live benchmark infrastructure 已准备好”
```

## 8. 下一 Gate

手动 workflow PR 合并后，需要仓库管理员在 GitHub 配置：

```text
Repository Secret: ZHIPU_API_KEY
```

然后先跑：

```text
glm-5.1
```

必要时再用完全相同 corpus 跑：

```text
glm-5.2
```

拿到真实 `result.json` 后再决定 Prompt / model 是否合格。

在 live benchmark 通过前：

- 不做端到端自然语言动态 match；
- 不把玩家规则接真实线上 Session；
- 不宣布正式 MVP 开发开始。
