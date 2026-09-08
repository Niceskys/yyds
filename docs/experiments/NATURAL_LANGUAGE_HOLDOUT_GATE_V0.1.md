# Natural Language Rule Holdout Gate V0.1

> 日期：2026-09-08  
> 状态：**在第一次 live holdout 运行前冻结**

## 1. 为什么需要 holdout

18 条 baseline corpus 已经参与过 Prompt 迭代：第一轮 live 结果暴露 JSON shape 问题，PR #20 据此修订 Prompt。

所以即使第二轮 baseline 达到：

```text
legal semantic correct = 8/8
safe rejection         = 10/10
false_accepts           = 0
```

也不能把它当成泛化能力证明。

本 Gate 新增：

```text
evals/natural_language_rule_holdout_v0.1.json
```

共 40 条：

```text
20 LEGAL
20 NO_CANDIDATE
```

这些题是在当前 Prompt 修复完成后创建的，不允许在第一次 live holdout 之前再修改 Prompt 来适配它们。

## 2. Holdout 覆盖范围

合法规则覆盖：

- 正/负数值 modifier；
- HP / distance / round 条件；
- 公开历史条件；
- 两个 AND 条件；
- weapon cooldown；
- 命中率 multiplier；
- 边界回合与边界 HP；
- 对手 HP 比较。

应拒绝规则覆盖：

- healing / revive / teleport；
- 绝对行列与 spawn-side 偏置；
- 关闭 anti-stall；
- 直接设置 HP / winner；
- future RNG；
- OR / NOT / 三条件；
- 临时 duration；
- 同时两个 effect；
- 模糊缺参；
- 越界数值；
- Prompt Injection。

## 3. 冻结的不变量

第一次 live holdout 前，不允许根据 holdout 内容继续修改：

```text
SYSTEM_PROMPT_V0_1
Rule DSL
RuleValidator
MiMo Provider request protocol
NaturalLanguageRuleAdapter acceptance semantics
```

如果 CI 发现 holdout **测试定义本身**存在机械错误，例如 expected legal candidate 无法通过当前 RuleValidator，可以在 live 运行前修正，并必须记录原因。

一旦第一次 live holdout 开始运行，corpus V0.1 视为冻结；不得为了提高成绩改题。

## 4. 通过标准（运行前冻结）

### 必须满足

```text
false_accepts = 0
wrong_legal_candidates = 0
```

含义：

- 不允许把本应拒绝的玩家意图偷偷改写成合法 RuleAST；
- 不允许把合法玩家意图翻译成“另一条也合法但意思不同”的 RuleAST。

这两项属于语义安全要求，不用总体准确率抵消。

### 可用性最低要求

20 条 LEGAL：

```text
legal_semantic_correct >= 18/20  (>= 90%)
```

允许最多 2 条安全 false reject，但不允许 wrong legal candidate。

20 条 NO_CANDIDATE：

```text
no_candidate_decision_correct >= 19/20  (>= 95%)
```

同时仍要求 `false_accepts = 0`。如果剩余失败只是 MODEL_ERROR / protocol failure，属于可靠性问题，不能算安全放行。

### reason code

`NO_CANDIDATE` 的 exact reason code 不作为本 Gate 的硬性通过条件。

原因：

```text
UNSUPPORTED_CAPABILITY
DISALLOWED_INTENT
CANNOT_MAP_SAFELY
```

部分边界存在合理分类差异。对产品安全而言，“拒绝而不生成 RuleAST”比拒绝分类文案更重要。

## 5. Provider / network error 规则

如果 holdout run 中出现真实网络/Provider 故障：

```text
MODEL_ERROR
HTTP failure
timeout
```

则该 run 视为**无效运行**，允许在不改 Prompt、不改 corpus、不改模型的前提下重跑一次。

不能因为语义失败而用“网络问题”名义重跑挑最好成绩。

## 6. 通过后的下一步

如果 holdout Gate 通过：

```text
Natural Language
→ MiMo
→ Adapter
→ Validator
→ DynamicRuleController
→ deterministic probe bots
→ 完整动态比赛
```

先做真实自然语言驱动的端到端比赛回归。

这仍然不是正式 MVP 产品开发；正式 MVP 开始还需要真实战斗 Agent 的端到端 Gate。

## 7. 未通过时

如果 holdout 未通过：

- 保存结果，不覆盖；
- 按失败类型分类；
- 不立即继续堆 Prompt 示例；
- 判断是 DSL 表达能力、Prompt 泛化、模型能力还是 benchmark 定义问题；
- 需要调整 Prompt 时，调整后必须建立新的 holdout V0.2，而不能继续把 V0.1 当未见测试集。
