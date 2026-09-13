# Handoff — Natural Language Rule Adapter V0.1

> 日期：2026-09-08  
> 最新修订分支：`fix/natural-language-rejection-envelope`  
> 状态：Adapter 已增加显式 `NO_CANDIDATE` 语义安全出口；等待 PR CI。

## 1. 当前已完成

主分支已具备：

```text
DynamicRuleController
+
NaturalLanguageRuleAdapter
```

本次修订解决真实 Provider 接入前发现的语义安全缺口。

## 2. 为什么修订

原协议只允许模型输出 Candidate。

风险：玩家明确要求非法/偏置规则时，模型可能为了满足系统限制，把玩家原意“洗白”为另一条合法规则，例如：

```text
玩家：只给红方伤害 +1
模型：双方伤害 +1
```

Validator 会接受后者，但语义已经被改变。

因此必须允许模型明确拒绝映射。

## 3. 新输出 envelope

合法且可忠实映射：

```json
{
  "decision": "CANDIDATE",
  "candidate": { ...V0.1 Rule Candidate... }
}
```

不能安全映射：

```json
{
  "decision": "NO_CANDIDATE",
  "reason_code": "DISALLOWED_INTENT"
}
```

`reason_code` 只允许：

```text
DISALLOWED_INTENT
UNSUPPORTED_CAPABILITY
AMBIGUOUS
CANNOT_MAP_SAFELY
```

## 4. 不变量

- `NO_CANDIDATE` 不会产生 RuleAST；
- Candidate 仍必须经过 deterministic RuleValidator；
- DynamicRuleController 仍会再次验证 forwarded candidate；
- Prompt 仍不是安全边界；
- Adapter 不写 GameState / active_rule。

## 5. 测试新增

覆盖：

- 正常 CANDIDATE envelope；
- 正常 NO_CANDIDATE；
- 非法 reason_code；
- envelope 多余字段；
- unknown decision；
- candidate 非 object；
- 原有 faction / injection / bounds 防护；
- Controller defense-in-depth。

## 6. 并行开发边界

在本修订合并前，其他 AI 不要同时修改：

```text
natural_language_rule_adapter.py
natural-language output envelope
NO_CANDIDATE reason codes
```

`feat/zhipu-rule-provider` 分支已经创建但尚未实现 Provider；应等待本修订合并后再从最新 main 继续，避免基于旧 bare-candidate 协议开发。

## 7. 下一步

本修订通过并合并后：

```text
真实智谱 Provider
→ response_format=json_object
→ GLM-5.1 baseline（model name configurable）
→ 固定自然语言语料集 benchmark
```

不要在没有 benchmark 数据时直接把产品模型切到更新模型。
