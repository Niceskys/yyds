# Handoff — Hybrid Liveness Experiment

> 日期：2026-09-08  
> 分支：`experiment/hybrid-liveness`  
> 状态：实验中；**没有修改正式/normative anti-stall**。

## 1. 前置结论

`docs/experiments/ADVERSARIAL_LIVENESS_2026-09-07.md` 已记录 1,000 paired seeds / cell 的结果：

- CURRENT 存在 11.0%~32.4% 的已知 exploit TIMEOUT；
- PRESSURE_12 在四类 exploit 中均把 TIMEOUT 降到 0%；
- HARD_AT_ROUND_24 同样均降到 0%；
- ROLLING_10_LOW_DAMAGE 仍残留 1.7%~2.7% TIMEOUT，且 healthy distortion 更高，已降级。

## 2. 为什么测试 Hybrid

PRESSURE_12 与 ROUND_24 解决的是两个不同问题：

```text
PRESSURE_12
= 根据长期低输出/拖延行为自适应触发

ROUND_24
= 无论行为如何，提供绝对不可绕过的晚局 failsafe
```

本轮测试：

```text
pressure >= 12
OR
round >= 24
→ Hard Liveness
```

## 3. 本分支改动

只修改实验层：

```text
src/rules_beyond/liveness_experiment.py
tests/test_liveness_experiment.py
```

新增：

```text
LivenessPolicy.HYBRID_PRESSURE_12_ROUND_24
```

并把实验主比较收敛为：

```text
CURRENT
PRESSURE_12
HARD_AT_ROUND_24
HYBRID_PRESSURE_12_ROUND_24
```

Rolling Window 的实现保留用于历史复现，但不再进入默认主比较。

## 4. 保持不变

没有修改：

- `engine.py`
- `rule_engine.py`
- P0 normative anti-stall 文档
- 默认 HP / Damage
- GLM / Agent / rule replacement controller

## 5. 判定重点

Hybrid 不能只做到 TIMEOUT=0；因为单独 Pressure / Round24 已经能做到。

真正要看：

1. exploit 是否仍保持 0% TIMEOUT；
2. 触发是否优先由 Pressure 在真实拖延局中提前识别；
3. Round24 是否只承担尾部 failsafe；
4. healthy outcome distortion 是否没有明显高于单独候选。

## 6. 并行边界

其他 AI / 开发者当前不要：

- 把 Hybrid 写进正式 Engine；
- 修改 normative P0；
- 开始每3回合规则替换；
- 重复实现另一套 hybrid benchmark。

可以并行：

- 正式产品技术栈方案；
- Replay/日志需求；
- 独立 review；
- 更多 adversarial 场景设计。

## 7. 下一步 Gate

```text
Hybrid 1,000-seed regression PASS
↓
形成 normative anti-stall 修订提案
↓
单独 PR 修改正式规则 + Engine + 文档 + 回归测试
```

如果 Hybrid 没有明显价值，则不因为已经实现而强行采用。
