# Handoff — Round-24 Normative Hard-Liveness Amendment

> 日期：2026-09-08  
> 分支：`feat/round24-hard-liveness`  
> 状态：**Normative 候选实现；等待 PR CI / regression 后才能合并。**

## 1. 这次与前面实验的区别

前面的 PR #11 / #12 只比较候选，没有修改产品规则。

本分支第一次把实验结论落实到正式 V0.1 Engine 语义：

```text
保留现有 no_damage_streak anti-stall
+
Round >= 24 → Hard Liveness
```

这仍然属于核心机制验证/Engine MVP 阶段，不代表玩家产品 UI 已进入正式开发。

## 2. 为什么选择 Round-24，而不是 Pressure / Hybrid

1,000 paired seeds / cell 的实验结果：

- Pressure-12：四类已知 exploit TIMEOUT = 0%；
- Round-24：四类已知 exploit TIMEOUT = 0%；
- Hybrid：同样 0%，但部分 healthy distortion 更高；
- Rolling Window：仍残留 TIMEOUT，已降级。

Round-24 被优先采用的原因：

- 与 Pressure 的 exploit 防护效果相同；
- 不需要增加新的长期 pressure 状态；
- 不重写已有 3/6/9/12 阶梯；
- 部分 healthy 场景干扰更低；
- 更符合“真人尽可能延长战斗”的玩家目标：允许长局存在，但给超长局设置绝对终局阶段。

证据：

```text
docs/experiments/ADVERSARIAL_LIVENESS_2026-09-07.md
docs/experiments/HYBRID_LIVENESS_2026-09-08.md
```

## 3. 正式语义

产品默认：

```text
GameConfig.late_game_hard_round = 24
```

每个 Round Start：

```text
hard_liveness =
    previous_hard_liveness
    OR no_damage_streak >= 12
    OR round_no >= late_game_hard_round
```

默认情况下：

```text
Round 23：仅凭回合数不会触发
Round 24：移动/攻击结算前进入 Hard Liveness
```

进入后沿用原来的 Level 4 / FORCED_BOW 语义并锁存。

## 4. 修改文件

正式代码：

```text
src/rules_beyond/model.py
src/rules_beyond/engine.py
src/rules_beyond/rule_engine.py
```

历史实验可复现性：

```text
src/rules_beyond/rule_experiment.py
```

旧实验配置显式使用：

```text
late_game_hard_round = 31
max_rounds = 30
```

因此此前实验报告的 `CURRENT` baseline 不会因为产品默认变化而被悄悄改写。

测试 / 回归：

```text
tests/test_liveness.py
tests/test_rule_engine.py
src/rules_beyond/round24_regression.py
.github/workflows/round24-regression.yml
```

Normative 文档：

```text
docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md
```

## 5. 为什么使用 Amendment，而不是偷偷重写原 Freeze

`docs/P0_RULE_FREEZE_V0.1.md` 是 2026-09-07 的历史冻结基线。

本次是有实验依据的规则变更，因此新增明确的 Normative Amendment，并规定它只在 `Absolute late-game Hard Liveness fallback` 范围内拥有更高优先级。

这样新窗口/其他 AI 可以区分：

```text
最初冻结了什么
vs
后来基于数据正式修订了什么
```

## 6. 并行开发注意

在本 PR 合并前，其他 AI / 开发者不要：

- 再修改 `model.py` 的 liveness 配置；
- 再修改 `engine.py` / `rule_engine.py` 的 Hard Liveness 入口；
- 把 Pressure-12 或 Hybrid 另行写进正式 Engine；
- 开始依赖 Round-24 已合并的 dynamic-rule controller。

可以低冲突并行：

- UI / Replay 需求设计（不实现依赖 Engine 的正式客户端）；
- 技术栈与目录规划；
- 比赛材料整理；
- 独立 code review。

## 7. 合并 Gate

必须同时满足：

```text
普通 pytest = PASS
behavior diagnostics = PASS
historical experiment compatibility = PASS
round24-regression = PASS
```

其中 `round24-regression` 使用实际 `RuleAwareGameEngine` + 产品 Round24 配置，对四类已知 exploit 各跑 1,000 seeds；任何 TIMEOUT 都使 CI 失败。

## 8. 合并后的下一步

只有本 PR 合并后，才进入：

```text
动态公共规则替换 controller
```

先用确定性规则序列验证“每 N 回合替换规则”本身，再考虑 GLM 自然语言接入。
