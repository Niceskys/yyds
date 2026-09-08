# Handoff — Natural Language Holdout V0.3

> 日期：2026-09-08

## 1. 这次做了什么

在已知 V0.2 修复回归通过后，建立新的 unseen V0.3 评测层：

```text
evals/natural_language_rule_holdout_v0.3.json
```

规模：

```text
25 LEGAL
25 NO_CANDIDATE
```

同时：

- 新增 `tests/test_natural_language_holdout_v03.py`；
- 在 live benchmark workflow 中新增 `holdout-v03` 选择项；
- 冻结 `docs/experiments/NATURAL_LANGUAGE_HOLDOUT_GATE_V0.3.md`；
- 记录 PR #25 后 V0.2 已知回归 PASS。

## 2. 为什么这样做

V0.2 首次 live run 已经暴露过，并触发了真实的 OR→AND 语义安全修复，因此修复后的 V0.2 只能做 regression，不能继续承担 unseen 泛化证明。

V0.3 重新提供一套从未参与 translator / guard / verifier 调优的语料，用来回答：

```text
当前 verified pipeline 在新表达和新边界组合上，能否继续保持 fail-closed 安全性和 >=96% 的合法语义映射率？
```

## 3. 明确没有做什么

本 PR **没有修改任何生产翻译/验证逻辑**：

```text
rule_intent_guard.py
natural_language_rule_adapter.py
rule_faithfulness.py
verified_natural_language_rule_adapter.py
Rule DSL
RuleValidator
Engine
DynamicRuleController
MiMo provider protocol
```

也没有新增 DSL 能力。

## 4. 当前证据 / 测试状态

已确认 PR #25 合并后的 V0.2 regression run：

```text
workflow = 34180183182
head = bbfda89c163d31df57c440bd93b115e5ea48a6d3
legal_semantic_correct = 24/25
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
```

V0.3 corpus 的 LEGAL expected candidates 均按当前 RuleValidator V0.1 边界设计；CI 测试会再次机械验证：

- 50 条、25/25 平衡；
- ID/text 唯一；
- 所有 expected legal RuleAST 可被 RuleValidator 接受；
- oracle verified pipeline 能得到满分。

## 5. 并发热点

本 PR 唯一修改的现有热点文件：

```text
.github/workflows/live-natural-language-benchmark.yml
```

其余均为新增 eval/test/doc 文件。

在第一次 V0.3 live run 完成前，不要并行修改 V0.3 corpus/Gate，也不要为了猜测 V0.3 结果提前调整 translator、guard 或 faithfulness verifier。

## 6. 后续开发者不要重复做什么

不要：

- 再创建另一套“V0.3”语料；
- 用 V0.2 regression PASS 当成新的 unseen 证明；
- 第一次 V0.3 live run 后改题/降阈值再称 unseen；
- 因某个 case 失败直接在同一 V0.3 上迭代到通过。

V0.3 一旦第一次 live run 开始即永久 exposed。

## 7. 下一步

PR CI 通过并合并后，运行一次：

```text
provider = mimo
model = mimo-v2.5-pro
suite = holdout-v03
pipeline = verified
```

冻结 Gate：

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 24/25
```

若 PASS：停止静态 corpus 扩张，进入“真实中文规则 -> verified pipeline -> DynamicRuleController -> 完整比赛/replay/log”的端到端动态 Gate。

若 FAIL：原样记录，V0.3 永久 exposed；修复后如需新的 unseen 泛化证明，另建 V0.4。

正式 MVP 开发仍未开始。
