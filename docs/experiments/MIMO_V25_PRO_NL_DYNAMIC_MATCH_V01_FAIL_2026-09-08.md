# MiMo V2.5 Pro Natural-Language Dynamic Match Gate V0.1 — FAIL

> 日期：2026-09-08  
> Workflow run：`34184281670`  
> Head：`9239cfa876f5a7fb3d050ad960ceacf851e43324`  
> Model：`mimo-v2.5-pro`

## 结论

V0.1 Gate 按冻结标准判定 **FAIL**。不得通过重跑挑选偶然成功结果来改判。

三个 combat seed 均完成终局：

```text
1260000 -> RED_WIN, 16 rounds
1260001 -> DRAW_MUTUAL_DEATH, 12 rounds
1260002 -> RED_WIN, 10 rounds
TIMEOUT = 0
```

Engine、DynamicRuleController 和 Intent Guard 没有崩溃；失败来自重复自然语言模型判定的不稳定性。

## Gate failures

```text
seed 1260002: phase-0 natural-language rule did not change round-1 behavior
seed 1260000: reached legal phase 4 but it was not accepted (BASE_REJECTED)
seed 1260002: legal phase 0 was not accepted and replaced (SEMANTIC_REJECTED)
```

### seed 1260002 phase 0

同一条：

```text
双方弓的最大射程增加1格。
```

Translator 生成合法 candidate，但 Faithfulness Verifier 返回 REJECT，因此没有提交给 Controller。其他两个 seed 对同一文本均 ACCEPTED。

### seed 1260000 phase 4

```text
连续2回合使用同一种武器后，弓冷却1回合。
```

Translator 返回 NO_CANDIDATE，表现为安全 false reject。

### 安全路径

Phase 2 的显式 OR 规则在三个 seed 中均：

```text
INTENT_GUARD_REJECTED
controller_replaced = false
previous legal rule carried forward = true
```

没有非法规则进入 Engine。

## 对 Gate 设计的诊断

V0.1 runner 为每个 combat seed 重新调用一次相同自然语言语义链，导致一个“战斗随机种子测试”同时变成了“重复 LLM 采样一致性测试”。

当前 verified adapter 不读取 GameState；同一个规则阶段的 player text 对不同 combat seed 的语义输入完全相同。因此下一版 Gate 应把职责分开：

```text
一次真实 NL semantic compile
-> 冻结该语义结果
-> 多个 deterministic combat seeds 复用
```

这不是把 V0.1 改判 PASS。V0.1 永久保留为 FAIL 记录。

## 下一步

创建 Dynamic Match Gate V0.2：

- 不修改 translator / verifier Prompt；
- 不修改 Rule DSL / Validator / Engine；
- evaluation-only memoization，按 `(system_prompt, player_text)` 只调用 Provider 一次；
- 仅保留 phase 0/1/2/3，分别验证合法替换、再次合法替换、非法 OR 拒绝+沿用、拒绝后的恢复替换；
- 继续使用 3 个固定 combat seed。
