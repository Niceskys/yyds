# MiMo Rule Provider V0.1

> 状态：Current live-validation provider baseline  
> 日期：2026-09-08  
> 背景：当前 GLM API Key 暂不可用，因此使用用户已有的 MiMo China Token Plan 暂时代替 live natural-language benchmark。

## 1. 定位

MiMo 只替代：

```text
Natural Language
→ LLM candidate translation
```

不替代也不修改：

```text
RuleValidator
DynamicRuleController
RuleAwareGameEngine
Game Engine
anti-stall / Round-24
Agent objective
```

所以 Provider 更换不会改变游戏规则。

---

## 2. China Token Plan API 基线

当前默认：

```text
Base URL:
https://token-plan-cn.xiaomimimo.com/v1

Chat Completions:
POST /chat/completions

API key env:
MIMO_API_KEY

Default model:
mimo-v2.5-pro
```

Token Plan 控制台实际显示的 Base URL 优先。如果未来账号控制台给出不同地址，可通过：

```text
MIMO_BASE_URL
```

覆盖默认值。

---

## 3. 结构化输出

当前 Provider 请求固定：

```json
{
  "response_format": {"type": "json_object"},
  "thinking": {"type": "disabled"},
  "stream": false,
  "max_completion_tokens": 1024
}
```

原因：Rule translation 是受限结构化任务，本阶段关注稳定 JSON 与语义映射，不需要深度思考输出。

当前只计划 live benchmark：

```text
mimo-v2.5-pro
```

如需比较，再使用完全相同 corpus 测：

```text
mimo-v2.5
```

不能为某个模型换题后比较。

---

## 4. Secret 边界

真实 Token Plan Key：

```text
MIMO_API_KEY
```

禁止：

- 提交到 GitHub；
- 写入测试；
- 写入 README / Issue / PR；
- 发到普通 AI 聊天；
- 打进日志。

`.env` 继续被 `.gitignore` 排除。

`.env.example` 只包含空值和变量名。

---

## 5. Provider-neutral benchmark

`natural_language_benchmark.py` 现在支持：

```text
--provider mimo
--provider zhipu
```

当前默认：

```text
provider = mimo
model = mimo-v2.5-pro
```

智谱实现不删除，GLM API 恢复后可以：

```text
provider = zhipu
model = glm-5.1
```

使用同一 18-case corpus 比较。

---

## 6. 安全边界没有变化

MiMo 输出仍然只是：

```text
untrusted raw string
```

必须继续经过：

```text
NaturalLanguageRuleAdapter
→ strict envelope decode
→ NO_CANDIDATE / CANDIDATE
→ RuleValidator
→ DynamicRuleController 再验证
```

MiMo 不获得：

- GameState 写权限；
- active_rule 写权限；
- Engine 调用权限；
- 胜负修改权限。

---

## 7. 当前 Gate

离线 CI 只能证明：

```text
MiMo request contract / provider isolation / benchmark integration
```

不能证明：

```text
MiMo 对 18 条中文规则的真实语义准确率
```

因此本阶段完成后仍需要：

```text
GitHub Secret MIMO_API_KEY
→ manual live benchmark
→ result.json
→ inspect false_accepts / wrong_legal_candidates / false_rejects
```

在 live benchmark 数据通过前，仍不宣布正式 MVP 开发开始。
