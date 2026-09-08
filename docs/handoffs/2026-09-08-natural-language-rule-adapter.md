# Handoff — Natural Language Rule Adapter V0.1

> 日期：2026-09-08  
> 分支：`feat/natural-language-rule-adapter`  
> 状态：Adapter 边界实现完成；等待 PR CI。

## 1. 前置状态

PR #14 已合并，`main` 已具备确定性 DynamicRuleController：

```text
开局前规则阶段
→ Round 1-3
→ Round 3 后规则阶段
→ 新合法规则从 Round 4 生效
→ 无合法新规则则旧规则继续
```

因此现在开始建立自然语言输入层。

## 2. 本分支新增

```text
src/rules_beyond/natural_language_rule_adapter.py
tests/test_natural_language_rule_adapter.py
docs/NATURAL_LANGUAGE_RULE_ADAPTER_V0.1.md
```

并更新：

```text
src/rules_beyond/__init__.py
```

## 3. 核心边界

```text
Natural Language
→ RuleCandidateModel
→ raw string
→ strict JSON decode
→ RuleValidator
→ accepted / rejected
```

模型没有 Engine / GameState / DynamicRuleController 写权限。

Prompt 不是安全边界，RuleValidator 才是确定性边界。

## 4. Provider-neutral

当前只定义：

```python
RuleCandidateModel.generate_candidate(...)->str
```

没有引入任何真实 LLM SDK、API key 或厂商依赖。

因此下一位开发者不要把本 PR 描述成“GLM 已接入”。

## 5. 严格失败策略

当前不会自动修复：

- Markdown fenced JSON；
- JSON 前后解释文字；
- array；
- unknown fields；
- faction target；
- bounds violation。

模型返回结果只要不满足严格契约，就明确失败。

## 6. 测试覆盖

当前测试覆盖：

- 合法精确 JSON；
- 空输入不调用模型；
- Provider exception；
- Provider 返回非字符串；
- Markdown fenced JSON；
- JSON array；
- RED faction target；
- `winner=RED` prompt-injection 型未知字段；
- 数值越界；
- 超大输出；
- System Prompt 包含最小权限边界。

## 7. 并行开发边界

本 PR 合并前，其他 AI / 开发者不要同时修改：

```text
natural_language_rule_adapter.py
Natural Language -> Candidate JSON trust boundary
provider protocol
```

可以低冲突并行：

- 真实 Provider 选型/接口研究，但不要直接合入本分支；
- UI 草图；
- Replay 数据需求；
- 独立安全 review。

## 8. 明确未完成

- 真实 GLM API；
- Provider retry / timeout policy；
- semantic accuracy benchmark；
- 端到端自然语言动态对局；
- 两个真实 LLM Agent；
- 正式产品 UI。

## 9. 下一 Gate

只有本 PR CI 通过并合并后，才进入：

```text
真实 LLM Provider adapter
+
固定自然语言测试语料集
+
合法/非法/注入/模糊输入评测
```

该阶段重点是测“模型结构化自然语言是否可靠”，而不是让模型获得更多权限。
