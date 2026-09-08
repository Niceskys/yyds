# MiMo V2.5 Pro Verified Pipeline — V0.1 已知集回归

> 日期：2026-09-08  
> Provider：MiMo China Token Plan  
> Model：`mimo-v2.5-pro`  
> Workflow run：`34175838599`  
> Head：`c86160a2fb9f25ac2b8310274f06f4758368ffa3`

## 1. 性质

本次运行使用已经暴露过的 V0.1 holdout，因此**不是未见泛化测试**。目的只是检查新增 semantic faithfulness gate 能否拦住已知的语义删减问题，并测量误杀。

## 2. 结果

```text
total                         40
legal_total                   20
legal_semantic_correct        12/20
legal_blocked                  8
no_candidate_total            20
no_candidate_blocked          20/20
false_accepts                  0
wrong_legal_candidates         0
semantic_rejections            5
verifier_errors                0
```

## 3. 安全回归

原 V0.1 translator-only holdout 的关键失败：

```text
A OR B -> A -> ACCEPTED
```

verified pipeline 中该规则变为：

```text
base_status = ACCEPTED
faithfulness = REJECT(ALTERED_INTENT)
pipeline = SEMANTIC_REJECTED
```

新的 NOT 语义删减也被 verifier 拦截。

因此已知 false accept 从：

```text
1 -> 0
```

## 4. 可用性问题

8 条合法规则被挡住，其中：

```text
5 条：translator 自己 NO_CANDIDATE
3 条：faithfulness verifier 误杀
```

Translator 主要误拒：

- 明确负向 modifier；
- `LAST_ATTACK_WEAPON_IS(NONE)`；
- 合法 1 回合 cooldown；
- history + cooldown 组合。

Verifier 主要误杀：

- `75% -> multiplier 0.75`；
- `第12回合起 + 上回合未移动`；
- `连续3回合同武器 -> 刀冷却1回合`。

## 5. 结论

Semantic gate 方向成立：它确实阻断了 deterministic Validator 无法发现的“合法但不忠实”候选。

但当前 pipeline 只有 12/20 合法可用率，不能进入新 holdout 或端到端游戏 Gate。

下一步只能针对这些**已知回归**修正 translator guidance / verifier equivalence rules；修正后先重跑已知 V0.1 regression。只有安全仍为 0 false accept 且合法可用率恢复后，才创建全新 V0.2 未见 holdout。
