# Hybrid Liveness Experiment — 2026-09-08

## 结论

本轮测试：

```text
HYBRID = pressure >= 12 OR round >= 24
```

使用与上一轮一致的 1,000 paired seeds / cell、相同 exploit + healthy 场景。

结论：

```text
Hybrid: REJECT as normative candidate
Round-24: preferred next normative proposal
```

原因不是 Hybrid 无效，而是它没有提供单独候选之外的收益，却增加了 healthy distortion。

---

## 1. Exploit

四类已知 exploit 下：

```text
PRESSURE_12 timeout = 0%
ROUND_24 timeout    = 0%
HYBRID timeout      = 0%
```

因此 Hybrid 在最关键的 timeout 指标上没有比单独候选更好。

## 2. Healthy distortion

### No rule / Attack-first mirror

三者均：

```text
trigger 0%
outcome change 0%
```

### No rule / Attack-first vs Kite

| Policy | Trigger | Outcome change | Mean round delta |
|---|---:|---:|---:|
| Pressure-12 | 4.5% | 2.2% | -0.193 |
| Round-24 | 5.5% | 2.4% | -0.100 |
| Hybrid | 6.9% | 3.3% | -0.222 |

Hybrid 明显没有产生组合优势。

### Low HP Damage / Attack-first vs Kite

| Policy | Trigger | Outcome change | Mean round delta |
|---|---:|---:|---:|
| Pressure-12 | 3.8% | 3.2% | -0.124 |
| Round-24 | 2.0% | 1.5% | -0.037 |
| Hybrid | 4.1% | 3.3% | -0.127 |

这里 Round-24 的 healthy distortion 明显最低。

### Bow cooldown / Attack-first vs Kite

- Pressure-12: 0% trigger / 0% outcome change
- Round-24: 0.2% / 0.1%
- Hybrid: 0.2% / 0.1%

---

## 3. 为什么当前更偏向 Round-24

### 设计目标一致性

真人玩家目标是尽可能延长战斗。

Pressure-12 会把“长期低输出”本身视为需要强制终局的信号，典型在约第20~22回合触发。这可能惩罚玩家正在追求的核心目标。

Round-24 的语义更清楚：

```text
你可以合法延长战斗
但第24回合后系统进入不可绕过的最终决战阶段
```

它约束的是“无限/超长拖延”，而不是“低输出”本身。

### 实现风险

Pressure-12 需要新增并长期维护一套 pressure 状态语义。

Round-24 可以作为现有 anti-stall 的额外绝对 fallback：

```text
保留当前 no_damage_streak escalation
+
Round >= 24 → Hard Liveness
```

无需重写原来的 anti-stall 阶梯。

### 数据

在当前已知 exploit 中，Round-24 与 Pressure-12 同样把 timeout 降到 0%，同时在 Low-HP healthy 场景中的干扰更低。

---

## 4. 下一步

提出一个**单独的 normative PR**：

```text
Current anti-stall semantics
+
Absolute late-game fallback:
Round >= 24 → Hard Liveness
```

该 PR 必须同时修改：

- normative 规则文档；
- Engine / RuleAwareEngine；
- tests；
- paired regression；
- handoff。

正式修改前不把本实验分支本身当产品实现。
