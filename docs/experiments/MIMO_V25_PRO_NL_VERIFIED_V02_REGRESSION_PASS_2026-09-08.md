# MiMo V2.5 Pro — V0.2 verified 回归通过

> 日期：2026-09-08  
> 模型：`mimo-v2.5-pro`  
> Workflow run：`34180183182`  
> Head：`bbfda89c163d31df57c440bd93b115e5ea48a6d3`  
> Suite：`holdout-v02`  
> Pipeline：`verified`

## 1. 结论

PR #25 合并后的已知 V0.2 回归测试通过。

结果：

```text
legal_semantic_correct = 24/25
legal_blocked = 1
no_candidate_blocked = 25/25
false_accepts = 0
wrong_legal_candidates = 0
intent_guard_rejections = 1
semantic_rejections = 1
verifier_errors = 0
```

满足最新 handoff 中冻结的修复回归 Gate：

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 24/25
```

## 2. 唯一合法 false reject

```text
把双方弓的最远射程缩短2格。
```

期望：

```json
{"effect":{"type":"BOW_RANGE_ADD","delta":-2}}
```

实际：基础 translator 返回 `NO_CANDIDATE`，因此规则被安全阻断。

这是可用性损失，不是安全错误；没有错误规则进入可执行链。

## 3. 这次结果不能证明什么

V0.2 已在第一次 live run 中暴露，并直接触发了 OR→AND 修复，因此这次回归通过只证明：

```text
已知 V0.2 失败已被修复，且没有破坏冻结 Gate。
```

它不能作为新的 unseen 泛化证明。

因此停止针对 V0.2 调整，下一步建立全新的 V0.3 unseen Gate。
