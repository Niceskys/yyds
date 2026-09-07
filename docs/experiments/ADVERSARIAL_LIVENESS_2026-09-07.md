# Adversarial Liveness Experiment — 2026-09-07

## 结论摘要

上一轮已经确认公共规则存在明显 core signal，但也发现当前 `no_damage_streak` 可被“低 DPS + 偶尔命中”规避。

本实验在 **1,000 paired seeds / cell** 下比较：

- CURRENT
- PRESSURE_12
- ROLLING_10_LOW_DAMAGE
- HARD_AT_ROUND_24

结论：

```text
CURRENT              = 已确认存在 stall exploit
PRESSURE_12          = 强候选
HARD_AT_ROUND_24     = 强候选
ROLLING_10_LOW_DAMAGE= 降级，不推荐进入下一轮主候选
```

这仍然是实验结论，**没有修改 normative anti-stall 规则**。

---

## 1. Exploit 场景

| 场景 | CURRENT timeout | PRESSURE_12 | ROLLING_10 | ROUND_24 |
|---|---:|---:|---:|---:|
| Bow Range +1 / Attack-first mirror | 32.4% | 0% | 2.7% | 0% |
| Hit×0.5 / Attack-first vs Kite | 26.6% | 0% | 2.3% | 0% |
| Hit×0.5 / Kite vs Attack-first | 28.3% | 0% | 2.3% | 0% |
| Hit×0.5 / Kite mirror | 11.0% | 0% | 1.7% | 0% |

### PRESSURE_12

典型触发：约第 20~22 回合。

它能识别“长期低输出但偶尔造成伤害”的对局，因为伤害只让 pressure -1，而不是把长期拖延历史完全清空。

### HARD_AT_ROUND_24

四类 exploit 同样全部降到 0% TIMEOUT。

它的优点是语义简单、绝对可靠；缺点是它不识别行为，只是晚局硬兜底。

### ROLLING_10_LOW_DAMAGE

虽然明显降低 TIMEOUT，但仍残留 1.7%~2.7%，同时通常在第 16~17 回合介入，比另外两个候选更早改变比赛。

因此当前不再把它作为主候选。

---

## 2. Healthy distortion

### 无规则 / Attack-first mirror

所有候选均无影响：

```text
trigger = 0%
outcome change = 0%
mean round delta = 0
```

### 无规则 / Attack-first vs Kite

| 候选 | trigger | outcome change | mean round delta |
|---|---:|---:|---:|
| PRESSURE_12 | 4.5% | 2.2% | -0.193 |
| ROLLING_10 | 9.6% | 3.7% | -0.590 |
| ROUND_24 | 5.5% | 2.4% | -0.100 |

### Low HP Bow Damage +1 / Attack-first vs Kite

| 候选 | trigger | outcome change | mean round delta |
|---|---:|---:|---:|
| PRESSURE_12 | 3.8% | 3.2% | -0.124 |
| ROLLING_10 | 6.7% | 5.9% | -0.346 |
| ROUND_24 | 2.0% | 1.5% | -0.037 |

### Repeat Bow Cooldown / Attack-first vs Kite

- PRESSURE_12：0% trigger，0% outcome change
- ROLLING_10：0% trigger，0% outcome change
- ROUND_24：0.2% trigger，0.1% outcome change

---

## 3. 当前判断

### 为什么不直接选 PRESSURE_12

它是自适应的，能根据长期拖延行为在约第 20~22 回合进入 Hard Liveness；但 healthy distortion 略高于 Round-24 的部分场景。

### 为什么不直接选 ROUND_24

它在 healthy 场景中的干扰非常低，而且能绝对消灭当前已知 exploit TIMEOUT；但它只是“时间到了强制终局”，缺乏对拖延行为本身的识别。

### 下一轮最合理候选

不把两者当互斥方案，而测试：

```text
Pressure-12 = 自适应主机制
Round-24    = 绝对晚局 failsafe
```

即：

```text
pressure >= 12
OR
round >= 24
→ Hard Liveness
```

这能验证是否同时获得：

1. 对真实拖延行为的自适应识别；
2. 无法被绕过的最终上限；
3. 可接受的 healthy distortion。

---

## 4. 不能从本实验推出什么

本实验不能证明：

- 游戏已经“好玩”；
- Pressure-12 已经应写入正式 P0；
- Round-24 已经应写入正式 P0；
- Hybrid 一定更好；
- 正式 AI Agent 会有与 probe bots 相同的分布。

正式规则修订必须等待下一轮 hybrid 回归。
