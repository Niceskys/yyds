# Handoff — Zhipu Rule Provider + Fixed NL Corpus

> 日期：2026-09-08  
> 分支：`feat/zhipu-rule-provider`  
> 状态：Provider / corpus / benchmark 实现完成；等待 PR CI；尚未 live API benchmark。

## 1. 前置状态

PR #15：NaturalLanguageRuleAdapter 已合并。  
PR #16：显式 `NO_CANDIDATE` envelope 已合并。

因此真实 Provider 可以在不会直接触碰 Engine 的前提下接入。

## 2. 新增

```text
src/rules_beyond/zhipu_rule_provider.py
src/rules_beyond/natural_language_benchmark.py
tests/test_zhipu_rule_provider.py
tests/test_natural_language_benchmark.py
evals/natural_language_rule_corpus_v0.1.json
docs/ZHIPU_RULE_PROVIDER_V0.1.md
.env.example
.gitignore
```

并更新 `src/rules_beyond/__init__.py`。

## 3. Provider 语义

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

## 4. 为什么使用标准库 HTTP

当前接口只需要一次 POST + JSON response；暂不增加 `zai-sdk` 依赖。

HTTP transport 已抽象，可在 tests 中完全替换，因此 CI 不访问外网、不消耗 token。

## 5. Secret 边界

```text
ZHIPU_API_KEY
```

只能来自环境变量或运行时参数。

`.env` 已加入 `.gitignore`。

不要在后续 PR：

- 提交真实 key；
- 把 key 写测试；
- 把 Authorization header 打到日志；
- 为了方便把 key 放到 README。

## 6. 固定语料

`evals/natural_language_rule_corpus_v0.1.json`：

```text
18 cases
= 8 LEGAL
+ 10 NO_CANDIDATE
```

后续比较 Prompt / GLM-5.1 / GLM-5.2 必须使用同一 corpus，不允许为某个模型临时换题后比较分数。

## 7. 指标

重点：

```text
false_accepts
```

即：本应拒绝的输入，被模型擅自改写为可通过 Validator 的合法 Candidate。

同时看：

```text
decision_accuracy
legal_semantic_correct
wrong_legal_candidates
false_rejects
exact_accuracy
```

拒绝 reason code 的精确分类属于次一级指标；安全拒绝本身更重要。

## 8. 当前测试范围

CI tests 只测试：

- 官方请求 payload 结构；
- Authorization 不进入 payload；
- JSON mode / thinking disabled；
- model 可配置；
- env key；
- malformed provider response；
- provider error 被 Adapter 隔离；
- Provider → Adapter mock end-to-end；
- corpus schema；
- corpus 中所有 expected legal candidate 都通过当前 Validator；
- benchmark 统计逻辑；
- silent sanitization 被计为 false_accept。

## 9. 尚未完成

最重要：

> 还没有真实 `ZHIPU_API_KEY`，因此没有真实 GLM-5.1 benchmark 数据。

所以不要把本 PR 描述成：

```text
“GLM-5.1 已验证可用”
```

只能描述成：

```text
“真实 Provider 接口已实现，并具备固定 live benchmark 工具”
```

## 10. 下一步

PR CI 通过合并后，下一 Gate 是运行 live corpus。

如果开发环境获得 `ZHIPU_API_KEY`：

```bash
python -m rules_beyond.natural_language_benchmark --model glm-5.1
python -m rules_beyond.natural_language_benchmark --model glm-5.2
```

先比较真实数据，再决定项目默认模型。

在 live benchmark 通过前：

- 不做端到端自然语言动态 match；
- 不把玩家规则接到真实线上 Session；
- 不宣布正式 MVP 开发开始。
