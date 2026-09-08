# MiMo V2.5 Pro Verified Natural-Language Holdout V0.2 — FAIL

> 日期：2026-09-08  
> Provider：MiMo China Token Plan  
> Model：`mimo-v2.5-pro`  
> Workflow run：`34178489427`  
> Head：`943d0a7ed92283bc4e2bbb086a24a76fb58dffbd`  
> Suite：`holdout-v02`  
> Pipeline：`verified`

## 1. 冻结 Gate

第一次 live 之前冻结：

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 23/25
```

任何 `false_accepts > 0` 直接 FAIL。

## 2. 实际结果

```text
total                    50
legal_total              25
legal_semantic_correct   24/25
legal_blocked             1
no_candidate_total       25
no_candidate_blocked     24/25
false_accepts             1
wrong_legal_candidates    0
semantic_rejections       3
verifier_errors           0
```

结论：**FAIL**。

虽然合法规则可用性达到 24/25，超过最低要求，但 `false_accepts=1` 违反零容忍安全门槛。

## 3. 安全失败：OR 被改成 AND

玩家原文：

```text
生命值不超过2或者上一回合没移动时，弓射程增加1格。
```

V0.1 DSL 只支持 AND，因此正确行为必须是安全拒绝。

Translator 生成：

```text
SELF_HP_LTE(2)
AND DID_NOT_MOVE_LAST_ROUND
-> BOW_RANGE_ADD(+1)
```

该 Candidate 本身 validator-legal，所以 RuleValidator 无法知道原始 OR 被改写。Faithfulness Verifier 又错误返回：

```text
FAITHFUL
```

因此最终进入 executable pipeline，形成：

```text
false_accept = 1
```

这是语义逻辑关系被改变，而不是简单漏掉一个条件。

## 4. 合法规则误杀

唯一合法 false reject：

```text
上一轮使用了弓的单位，本轮弓需要冷却1回合。
```

Translator 正确生成：

```text
LAST_ATTACK_WEAPON_IS(BOW)
-> WEAPON_COOLDOWN(BOW, 1)
duration=UNTIL_REPLACED
```

RuleValidator 接受，但 Faithfulness Verifier 返回：

```text
REJECT / DROPPED_INTENT
```

这里需要明确：

- `UNTIL_REPLACED` 是公共规则自身的寿命；
- `WEAPON_COOLDOWN(..., rounds=1)` 是每次条件成立后产生的一回合 cooldown；
- 二者不矛盾。

## 5. 架构结论

仅使用：

```text
translator LLM
-> RuleValidator
-> faithfulness LLM
```

仍然不足以把所有显式不可表达逻辑从风险面中移除。

对于当前 DSL 明确不支持、且可从输入文本可靠识别的逻辑结构，应增加窄范围 deterministic intent guard，而不是继续要求另一个 LLM 每次重新判断。

首个 guard 只处理显式 OR：

```text
或者
或是
要么
English word: or
```

它不尝试成为通用自然语言解析器。

## 6. 后续规则

V0.2 已暴露，不能再作为 unseen 泛化证明。

修复后可以重跑 V0.2 作为**已知回归测试**，目标至少：

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 24/25
```

若已知回归通过，下一次正式泛化验收必须建立新的 V0.3 unseen corpus，并在第一次 live 前重新冻结 Gate。
