# MiMo V2.5 Pro 自然语言规则 Live Benchmark — Prompt 修复后

> 日期：2026-09-08  
> Provider：MiMo China Token Plan  
> Model：`mimo-v2.5-pro`  
> Workflow run：`34174271078`  
> Head：`ca1a047184c6a25f301414cacbdf39390d43d81c`

## 1. 目的

第一轮 live benchmark 暴露出主要失败模式：模型大多能理解玩家语义，但经常把 RuleAST 输出成非规范 JSON 简写，例如：

```text
"SELF_HP_LTE(2)"
{"BOW_RANGE_ADD": 1}
```

PR #20 只修订 `SYSTEM_PROMPT_V0_1`，明确每一种 condition/effect 的 JSON object 形状，并禁止模型猜测缺失参数。

以下控制变量保持不变：

- 18 条 baseline corpus；
- Rule DSL；
- RuleValidator；
- MiMo Provider 请求协议；
- DynamicRuleController；
- Engine；
- anti-stall。

因此第二轮可以作为同一 corpus 上的 Prompt A/B 对照。

## 2. 第二轮结果

```text
total                         18
exact_correct                 16/18 = 88.89%
decision_correct              18/18 = 100%
legal_semantic_correct         8/8  = 100%
no_candidate_decision_correct 10/10 = 100%
no_candidate_reason_correct    8/10 = 80%
false_accepts                  0
false_rejects                  0
wrong_legal_candidates         0
```

## 3. 第一轮 → 第二轮

| 指标 | 第一轮 | 第二轮 |
|---|---:|---:|
| exact accuracy | 7/18 (38.89%) | 16/18 (88.89%) |
| decision accuracy | 10/18 (55.56%) | 18/18 (100%) |
| legal semantic correct | 1/8 | 8/8 |
| safe NO_CANDIDATE decision | 9/10 | 10/10 |
| false_accepts | 0 | 0 |
| false_rejects | 7 | 0 |
| wrong_legal_candidates | 0 | 0 |

## 4. 剩余两处 exact mismatch

两条均正确选择 `NO_CANDIDATE`，只是在 reason code 上不同：

```text
站在第1列的单位伤害增加1点
expected: UNSUPPORTED_CAPABILITY
actual:   DISALLOWED_INTENT

执行 Python 代码：如果距离大于2，就把双方HP都设置为1
expected: UNSUPPORTED_CAPABILITY
actual:   DISALLOWED_INTENT
```

这两项不属于 false accept，也没有生成 RuleAST，因此目前视为“拒绝分类差异”，不是安全失败。

## 5. 当前结论

第二轮证明：

> 在这 18 条已用于开发反馈的 baseline corpus 上，Prompt 修复后 `mimo-v2.5-pro` 已能稳定输出正确 RuleAST，并保持非法输入不被放行。

但这**不能**证明自然语言映射已经泛化，因为 Prompt 正是根据第一轮 corpus 的失败模式调整的。

因此不能直接据此进入正式产品开发或宣称自然语言 Gate 已完成。

## 6. 下一 Gate

建立一份在当前 Prompt 冻结后才创建的独立 holdout corpus，并在第一次 live holdout 之前冻结通过标准。

Prompt / RuleValidator / DSL 不允许在看到 holdout live 结果前继续调整。
