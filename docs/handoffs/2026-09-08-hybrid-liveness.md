# Handoff — Hybrid Liveness Experiment

> 日期：2026-09-08  
> 分支：`experiment/hybrid-liveness`  
> 状态：实验完成；**Hybrid 被否决，正式/normative anti-stall 仍未修改。**

## 1. 前置结论

上一轮 1,000 paired seeds / cell 已得到：

- CURRENT：已知 exploit TIMEOUT 11.0%~32.4%；
- PRESSURE_12：四类 exploit TIMEOUT 均为 0%；
- HARD_AT_ROUND_24：四类 exploit TIMEOUT 均为 0%；
- ROLLING_10_LOW_DAMAGE：残留 1.7%~2.7% TIMEOUT，已降级。

## 2. 本轮测试

```text
HYBRID:
pressure >= 12
OR
round >= 24
→ Hard Liveness
```

仍使用 1,000 paired seeds / cell、相同 exploit + healthy 场景。

## 3. 结果

### Exploit

Hybrid 与 Pressure / Round24 一样，四类已知 exploit：

```text
TIMEOUT = 0%
```

因此它没有在最关键指标上提供额外收益。

### Healthy distortion

无规则 Attack-first vs Kite：

```text
Pressure-12: trigger 4.5%, outcome change 2.2%
Round-24:    trigger 5.5%, outcome change 2.4%
Hybrid:      trigger 6.9%, outcome change 3.3%
```

Low-HP Damage：

```text
Pressure-12: trigger 3.8%, outcome change 3.2%
Round-24:    trigger 2.0%, outcome change 1.5%
Hybrid:      trigger 4.1%, outcome change 3.3%
```

Bow cooldown：Hybrid 与 Round24 基本一致，约 0.2% trigger / 0.1% outcome change。

完整记录：

```text
docs/experiments/HYBRID_LIVENESS_2026-09-08.md
```

## 4. 结论

```text
Hybrid = REJECT
```

原因：

- 没有比单独候选进一步降低 timeout；
- 在部分 healthy 场景中反而叠加了干扰；
- 增加规则复杂度却没有对应收益。

## 5. 当前推荐的下一 normative 候选

优先测试/提出：

```text
保留现有 no_damage_streak anti-stall
+
Round >= 24 → Hard Liveness
```

而不是 Pressure-12。

理由：

1. 四类 exploit timeout 同样降到 0%；
2. 不需要新增长期 pressure 状态；
3. 不重写现有 anti-stall 阶梯；
4. 对 Low-HP healthy 场景干扰更低；
5. 更符合玩家“尽量延长战斗”的目标——允许长局存在，只在晚局设置不可绕过的最终决战。

## 6. 并行开发边界

其他 AI / 开发者现在不要：

- 把 Hybrid 写进正式 Engine；
- 把 Pressure-12 写进正式 Engine；
- 擅自修改 P0 anti-stall；
- 开始每3回合规则替换 controller。

下一步应单独创建 normative PR，明确只增加 Round24 absolute fallback，并同时更新 Engine、RuleAwareEngine、规则文档和回归测试。
