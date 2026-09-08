# Handoff — MiMo Live Benchmark Baseline + RuleAST Prompt Fix

> 日期：2026-09-08  
> 分支：`fix/nl-rule-json-schema-prompt`  
> 状态：第一轮真实 MiMo benchmark 已完成；Prompt 修复已实现；等待 CI / 第二轮 live benchmark。

## 1. 第一轮真实结果

Provider：

```text
mimo
mimo-v2.5-pro
China Token Plan
```

GitHub Actions run：

```text
34173798527
```

结果：

```text
18 total
exact accuracy               7/18 = 38.89%
decision accuracy           10/18 = 55.56%
legal semantic correct       1/8
safe NO_CANDIDATE decision   9/10
false_accepts                0
false_rejects                7
wrong_legal_candidates       0
```

完整分析见：

```text
docs/experiments/MIMO_V25_PRO_NL_LIVE_BASELINE_2026-09-08.md
```

## 2. 客观判断

```text
安全信号：正向
自然语言 RuleAST 可用性：未过 Gate
```

不要把绿色 workflow 描述为“MiMo 已验证可用”。

最主要失败不是 Engine/Validator，而是模型生成了 JSON shorthand：

```text
"SELF_HP_LTE(2)"
{"BOW_RANGE_ADD": 1}
```

而当前 V0.1 DSL 要求：

```text
{"type":"SELF_HP_LTE","value":2}
{"type":"BOW_RANGE_ADD","delta":1}
```

## 3. 本分支修改

只修改自然语言契约 Prompt 和 Prompt contract tests。

没有修改：

```text
RuleValidator
Rule DSL
18-case corpus
Engine
DynamicRuleController
MiMo Provider request protocol
anti-stall
```

这是有意的控制变量。

## 4. Prompt 修复

现在逐一列出每种 Condition / Effect 的 exact JSON object shape，并明确禁止：

```text
condition string shorthand
effect key/value shorthand
renamed fields
invented fields
```

同时增加 faithfulness 约束：

```text
玩家没有明确给出数字 -> 不猜
玩家没有明确给出阈值 -> 不猜
“残血 / 更灵活 / 更强 / 更远”缺必要参数 -> AMBIGUOUS
unsupported intent -> NO_CANDIDATE，不近似改写
```

这个约束很重要，因为第一轮 `残血的时候更灵活一点` 曾被模型自行猜成 HP<=3 + move+1，只是因为 schema 错误才被 Validator 拦下。

## 5. 并发开发边界

本 PR 合并前，其他 AI / 开发者不要同时修改：

```text
SYSTEM_PROMPT_V0_1
Natural Language -> RuleAST semantic mapping policy
18-case live benchmark interpretation
```

可以并行：

```text
Engine review
Replay event design review
frontend-only mockup
competition material整理
```

不要为了提高 benchmark 分数修改 18-case corpus 或放松 Validator。

## 6. 下一步

```text
CI PASS
→ merge
→ 再次手动运行 live-natural-language-benchmark
   provider=mimo
   model=mimo-v2.5-pro
→ 与 run 34173798527 直接比较
```

第二轮重点：

```text
false_accepts 必须继续为 0
legal_semantic_correct 应显著高于 1/8
false_rejects 应显著下降
ambiguous case 不得因 schema 修好而变成 false accept
```

第二轮 live 数据出来前，不进入自然语言动态完整对局，不宣布正式 MVP 开发开始。
