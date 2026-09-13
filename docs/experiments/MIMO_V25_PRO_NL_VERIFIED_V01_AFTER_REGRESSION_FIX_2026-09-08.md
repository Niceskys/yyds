# MiMo V2.5 Pro Verified Natural-Language V0.1 Known-Set Regression — After Fix

> 日期：2026-09-08  
> Provider：MiMo China Token Plan  
> Model：`mimo-v2.5-pro`  
> Workflow run：`34176498461`  
> Head：`e6041d92cffc45deaf010688c4a0f1677d83c5d7`

## 1. 性质

这是已经暴露过的 V0.1 holdout 的**已知集回归**，不是新的泛化测试。

PR #23 只针对已知回归类别修正 translator/verifier guidance，并将 verified benchmark 改为比较 RuleAST 语义而不是 AND 条件的 JSON 顺序。

## 2. 结果

```text
total                    40
legal_total              20
legal_semantic_correct   20/20
legal_blocked             0
no_candidate_total       20
no_candidate_blocked     20/20
false_accepts             0
wrong_legal_candidates    0
semantic_rejections       1
verifier_errors           0
```

## 3. 关键结论

已知集回归目标全部达到：

- 原 OR 语义丢失漏洞不再进入执行链；
- NOT 语义丢失仍被 faithfulness verifier 拦截；
- 合法负向 modifier、history/cooldown 和双 AND 条件不再被误杀；
- 没有错误但 validator-legal 的规则被执行；
- verifier 没有协议/模型错误。

因此：

```text
Known V0.1 regression = PASS
Generalization = NOT PROVEN
```

## 4. 下一 Gate

不再修改 V0.1 已知题。

创建一个在当前 translator/verifier guidance 冻结后才生成的全新 V0.2 unseen holdout，并在第一次 live run 前冻结验收标准。
