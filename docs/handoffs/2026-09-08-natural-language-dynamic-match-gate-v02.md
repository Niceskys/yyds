# Handoff — Natural-Language Dynamic Match Gate V0.2

> 日期：2026-09-08

## 背景

第一次 live Dynamic Match Gate V0.1（run `34184281670`）FAIL。失败不是 Engine/Secret/HTTP 崩溃，而是同一句自然语言在不同 combat seed 中被重复调用 MiMo 后出现不同安全判定：一次 phase0 被 semantic verifier 误拒绝，一次 phase4 被 translator false reject。

V0.1 已永久记录为 FAIL，不得重跑挑结果改判。

## 本分支做什么

新增 V0.2 evaluation runner：

```text
src/rules_beyond/live_natural_language_dynamic_match_v02.py
```

核心原则：

```text
one player semantic request
-> one live provider decision
-> frozen semantic result
-> multiple deterministic combat seeds
```

通过 evaluation-only memoization 按 `(system_prompt, player_text)` 复用第一次模型输出。

新增独立 manual workflow：

```text
live-natural-language-dynamic-match-v02
```

## V0.2 固定阶段

```text
0 弓射程 +1                  legal
1 移动距离 +1                legal
2 HP<=2 OR 上回合没移动      explicit OR, must reject
3 距离>=3 时弓命中率 x0.5    legal recovery after rejection
```

不再需要 phase4。Phase 0/1/2/3 已覆盖完整产品链需要的四种行为：初始合法规则、合法替换、非法拒绝并沿用、拒绝后的再次合法替换。

## 明确没有做

- 没改 translator prompt；
- 没改 faithfulness prompt；
- 没改 Intent Guard；
- 没改 RuleValidator / DSL；
- 没改 Engine / DynamicRuleController；
- 没把 memoization 引入产品代码路径；
- 没开始真正 Agent/Planner 实现。

## 冲突热点

该分支主要新增 evaluation 文件。不要并行再做另一套 live dynamic-match gate。若需要开发 Engine/Agent，请等此 Gate 结果明确后再开始。

## Merge Gate

PR 合并前必须：

```text
pytest PASS
behavior-diagnostics PASS
dynamic-rule-replacement PASS
```

合并后用户手动运行：

```text
Actions -> live-natural-language-dynamic-match-v02
model = mimo-v2.5-pro
```

若 PASS，下一步进入真实 Agent/Planner Integration Gate；仍不宣布正式 MVP 开发开始。
