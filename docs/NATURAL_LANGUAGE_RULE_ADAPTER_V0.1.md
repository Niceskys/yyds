# Natural Language Rule Adapter V0.1

> 状态：实现基线 / 进入真实 LLM Provider 前的安全边界  
> 日期：2026-09-08

## 1. 这一层解决什么问题

玩家未来输入的是自然语言，例如：

```text
生命值不高于 2 时，弓射程增加 1 格。
```

但 Game Engine 不能执行自然语言，也不能信任 LLM。

因此 V0.1 固定链路为：

```text
玩家自然语言
→ LLM Provider
→ 原始文本输出（不可信）
→ NaturalLanguageRuleAdapter
→ 严格 JSON envelope
→ RuleValidator
→ accepted RuleAST / rejected result
```

LLM 永远不拥有以下权限：

- 修改 GameState；
- 修改 HP；
- 决定胜负；
- 修改最大回合；
- 修改 anti-stall / Round-24；
- 修改 AI 目标；
- 直接替换 DynamicRuleController.active_rule。

## 2. Prompt 不是安全边界

System Prompt 会告诉模型允许的 Condition / Effect 和输出协议。

但是：

> 模型是否遵守 Prompt，不参与最终安全判断。

即使模型返回看似合理的 JSON，Candidate 仍必须经过 `RuleValidator`。

## 3. 为什么必须有 NO_CANDIDATE

真实玩家可能输入：

```text
只给红方伤害 +1
```

如果协议强迫模型“必须生成一条合法规则”，模型可能把它偷偷改成：

```text
双方伤害 +1
```

这在格式上合法，但已经改变了玩家意图。

因此 V0.1 明确允许模型说：

```json
{
  "decision": "NO_CANDIDATE",
  "reason_code": "DISALLOWED_INTENT"
}
```

禁止把不合法/不支持/模糊意图静默改写成另一条合法规则。

允许的 `reason_code` 只有：

```text
DISALLOWED_INTENT
UNSUPPORTED_CAPABILITY
AMBIGUOUS
CANNOT_MAP_SAFELY
```

## 4. 严格输出协议

模型只能返回两种 envelope 之一。

### 4.1 Candidate

```json
{
  "decision": "CANDIDATE",
  "candidate": {
    "version": "v0.1",
    "target": "ALL_UNITS",
    "conditions": [],
    "effect": {},
    "duration": "UNTIL_REPLACED"
  }
}
```

### 4.2 No Candidate

```json
{
  "decision": "NO_CANDIDATE",
  "reason_code": "AMBIGUOUS"
}
```

以下均拒绝：

- Markdown fenced JSON；
- JSON 前后附解释；
- JSON array；
- 未知 decision；
- envelope 多余字段；
- 未知 reason_code；
- 非字符串 Provider 返回值；
- JSON 解析失败；
- 超过输出大小上限。

本阶段不做自动 JSON repair 或语义猜测。

## 5. Provider 抽象

核心层只定义：

```python
RuleCandidateModel.generate_candidate(
    system_prompt: str,
    player_text: str,
) -> str
```

因此后续可以接 GLM、其他模型、本地模型或测试 Stub，而 Engine 不依赖厂商 SDK。

## 6. TranslationStatus

```text
ACCEPTED
NO_CANDIDATE
INPUT_REJECTED
MODEL_ERROR
MODEL_PROTOCOL_ERROR
OUTPUT_TOO_LARGE
JSON_DECODE_ERROR
CANDIDATE_NOT_OBJECT
RULE_REJECTED
```

只有 `ACCEPTED` 会包含已通过 Validator 的 `RuleAST`。

`NO_CANDIDATE` 表示模型明确选择不生成规则，不等于模型故障。

## 7. 与 DynamicRuleController 的边界

Adapter 不负责比赛状态机，不直接写 `active_rule`。

后续 Orchestration 层负责把 Candidate 交给合法 rule phase；Controller 仍应自行再次 deterministic validate，避免把上层 Adapter 当成新的信任点。

## 8. 当前明确未完成

- 真实 GLM API；
- API Key / Secret 配置；
- Provider retry；
- JSON repair；
- 20 秒 UI timer；
- 自然语言语义准确率评测；
- 正式 Agent；
- 前端。

所以当前仍不能说“自然语言规则功能已经可用”。

## 9. 下一 Gate

下一阶段接真实 Provider，并建立固定语料集测试：

- 明确合法规则；
- 明确非法规则；
- 模糊规则；
- 阵营偏置；
- Prompt Injection；
- 超出 DSL 能力范围；
- 数值越界；
- 历史条件规则。

特别要测：

> 对非法/模糊输入，模型是否选择 `NO_CANDIDATE`，而不是擅自改写玩家意图。

只有真实 Provider 的结构化与语义表现都达到可接受水平，同时 deterministic safety gate 始终有效，才进入端到端自然语言动态对局。
