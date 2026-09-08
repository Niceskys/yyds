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
→ JSON decode
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

System Prompt 会要求模型只输出一份 V0.1 JSON，并列出允许的 Condition / Effect。

但是：

> 模型是否遵守 Prompt，不参与安全判断。

即使模型返回看似合理的 JSON，仍必须经过 `RuleValidator`。

## 3. 严格输出协议

V0.1 Adapter 要求模型返回：

```text
恰好一个 JSON object
```

以下均拒绝：

- Markdown fenced JSON；
- JSON 前后附解释；
- JSON array；
- 非字符串 Provider 返回值；
- JSON 解析失败；
- 超过输出大小上限。

本阶段不做“自动提取 JSON”“自动修复字段”“猜测玩家真正想表达什么”。

原因：这些容错行为会模糊信任边界，并可能把模型错误转换成合法规则。

后续若要增加一次重试/纠错，必须作为独立、可测试的策略增加，不能绕过 Validator。

## 4. Provider 抽象

核心层只定义：

```python
RuleCandidateModel.generate_candidate(
    system_prompt: str,
    player_text: str,
) -> str
```

因此后续可以接：

- GLM；
- 其他兼容模型；
- 本地模型；
- 测试 Stub。

核心 Engine 不依赖任何厂商 SDK。

## 5. TranslationStatus

Adapter 只产生以下状态：

```text
ACCEPTED
INPUT_REJECTED
MODEL_ERROR
MODEL_PROTOCOL_ERROR
OUTPUT_TOO_LARGE
JSON_DECODE_ERROR
CANDIDATE_NOT_OBJECT
RULE_REJECTED
```

其中只有：

```text
ACCEPTED
```

会包含一个已经通过 Validator 的 `RuleAST`。

## 6. 与 DynamicRuleController 的边界

Adapter 不负责比赛状态机。

它不会：

- 判断现在是不是规则阶段；
- 自动 carry previous rule；
- 自动开始下一回合；
- 直接写入 active_rule。

后续 Orchestration 层应遵循：

```text
NaturalLanguageRuleAdapter
→ 得到 candidate / translation result
→ DynamicRuleController 在合法 rule phase 中处理 candidate
```

即使 Adapter 已经验证一次，Controller 仍然可以再次通过自己的 `RuleValidator` 进行 deterministic validation，避免信任调用方。

## 7. 当前明确未完成

本阶段没有：

- 调用真实 GLM API；
- API Key / Secret 配置；
- Provider retry；
- JSON repair；
- 20 秒 UI timer；
- 自然语言语义准确率评测；
- 多语言评测；
- 正式 Agent；
- 前端。

所以“Adapter 已完成”不能被描述为“自然语言功能已经可用”。

目前证明的只是：

> 模型输出已经被放进一个严格、可测试、不可直接越权的信任边界。

## 8. 下一 Gate

下一阶段应接一个真实 Provider，但仍然只做：

```text
真实自然语言样例
→ Provider
→ Candidate JSON
→ Adapter
→ RuleValidator
```

需要建立一个固定测试语料集，至少覆盖：

- 明确合法规则；
- 明确非法规则；
- 模糊规则；
- 阵营偏置；
- Prompt Injection；
- 超出 DSL 能力范围；
- 数值越界；
- 含历史条件的规则。

只有真实 Provider 在该 Gate 下达到可接受的结构化成功率，且所有非法输出都被确定性边界拦截后，才进入端到端自然语言动态对局。
