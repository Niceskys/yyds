# Handoff — MiMo China Token Plan Rule Provider

> 日期：2026-09-08  
> 分支：`feat/mimo-token-plan-rule-provider`  
> 状态：Provider / benchmark / manual workflow 适配完成；等待 PR CI；尚未 live 调用。

## 1. 为什么有这个分支

当前 GLM API Key 暂不可用，但用户已有 Xiaomi MiMo China Token Plan。

因此当前验证策略改为：

```text
先用 MiMo 完成 live natural-language benchmark
GLM Provider 保留
GLM API 恢复后再用同一 corpus 横向比较
```

这不是永久切换模型的产品决策。

## 2. 本分支新增 / 修改

新增：

```text
src/rules_beyond/mimo_rule_provider.py
tests/test_mimo_rule_provider.py
docs/MIMO_RULE_PROVIDER_V0.1.md
docs/handoffs/2026-09-08-mimo-token-plan-provider.md
```

修改：

```text
src/rules_beyond/natural_language_benchmark.py
src/rules_beyond/__init__.py
tests/test_natural_language_benchmark.py
.github/workflows/live-natural-language-benchmark.yml
.env.example
docs/LIVE_NL_BENCHMARK_RUNBOOK.md
```

## 3. 当前 Provider 默认

```text
provider = mimo
model = mimo-v2.5-pro
base_url = https://token-plan-cn.xiaomimimo.com/v1
secret = MIMO_API_KEY
```

Base URL 可通过：

```text
MIMO_BASE_URL
```

覆盖，以 Token Plan 控制台实际展示为最终准则。

## 4. 请求契约

Chat Completions 请求使用：

```text
POST {base_url}/chat/completions
header: api-key
response_format: json_object
thinking: disabled
stream: false
max_completion_tokens: 1024
```

Provider 只返回模型 message content 字符串。

## 5. 不变的安全边界

MiMo 没有任何 Engine 权限。

完整链路仍然是：

```text
Natural Language
→ MiMo raw JSON envelope
→ NaturalLanguageRuleAdapter
→ RuleValidator
→ DynamicRuleController 再验证
→ active_rule
```

任何 `NO_CANDIDATE`、格式错误、Validator reject 都不能进入 Engine。

## 6. Benchmark 变化

命令现在支持：

```text
python -m rules_beyond.natural_language_benchmark \
  --provider mimo \
  --model mimo-v2.5-pro
```

也仍支持：

```text
--provider zhipu --model glm-5.1
```

18-case corpus 未改变。

## 7. Manual GitHub Action

`live-natural-language-benchmark` 现在有：

```text
provider choice: mimo | zhipu
model string
```

默认：

```text
mimo / mimo-v2.5-pro
```

MiMo 运行只需要仓库 Secret：

```text
MIMO_API_KEY
```

普通 PR/push 不会自动调用 live API。

## 8. 其他 AI / 开发者不要重复做

本 PR 合并前不要同时修改：

```text
mimo_rule_provider.py
natural_language_benchmark provider selection
live-natural-language-benchmark.yml
```

不要删除：

```text
zhipu_rule_provider.py
```

因为它仍是未来对照 Provider。

可以并行：

- 独立 review；
- Replay/API schema 草案；
- 竞赛材料整理；
- 前端信息架构草图（不要正式产品开发）。

## 9. 明确未完成

- 没有真实 `MIMO_API_KEY`；
- 没有 live `mimo-v2.5-pro` 18-case 结果；
- 没有 MiMo vs GLM 对比；
- 没有自然语言动态完整对局；
- 没有正式红蓝 LLM Agent；
- 没有正式 MVP UI。

## 10. 下一 Gate

```text
PR CI PASS + merge
→ 用户配置 GitHub Secret MIMO_API_KEY
→ 手动运行 mimo-v2.5-pro benchmark
→ 读取 result.json
→ 重点检查 false_accepts
→ 再决定是否直接进入 NL dynamic match，或先修 prompt/provider
```

在 live benchmark 通过前，项目仍是 Validation 阶段。
