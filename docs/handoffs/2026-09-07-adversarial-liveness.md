# Handoff — Adversarial Liveness Experiment

> 日期：2026-09-07  
> 分支：`experiment/adversarial-liveness`  
> 状态：候选 anti-stall 实验完成；**尚未修改正式/normative liveness 规则**。

## 1. 背景

上一轮 public-rule paired-seed 实验已经得到：

```text
Core mechanic signal = PASS
Liveness robustness = BLOCKER
```

低命中/远程规则可以偶尔造成一点伤害，反复把 `no_damage_streak` 清零，从而长期避免 Hard Liveness。由于真人玩家目标就是延长战斗，这个漏洞与玩家激励同方向。

## 2. 本轮比较的候选

### CURRENT

现有逻辑，无额外干预。

### PRESSURE_12

```text
无伤害回合：pressure += 1
有伤害回合：pressure = max(0, pressure - 1)
pressure >= 12：进入 Hard Liveness
```

### ROLLING_10_LOW_DAMAGE

```text
最近10个完整回合总实际伤害 <= 1
→ Hard Liveness
```

### HARD_AT_ROUND_24

```text
Round >= 24 且仍未终局
→ Hard Liveness
```

所有候选都只存在于实验控制器中，正式 `GameEngine` / `RuleAwareGameEngine` 未改。

## 3. 最终样本

CI 已扩大到：

```text
1,000 paired seeds / cell
```

普通 tests、behavior diagnostics、adversarial-liveness workflow 全部通过。

完整结果见：

```text
docs/experiments/ADVERSARIAL_LIVENESS_2026-09-07.md
```

## 4. 主要结果

四类已知 exploit 的 CURRENT timeout：

```text
32.4%
26.6%
28.3%
11.0%
```

### PRESSURE_12

四类全部：

```text
TIMEOUT = 0%
```

典型在约第20~22回合识别并触发。

Healthy 对照中：

- 无规则 Attack-first mirror：0% 干扰；
- 无规则 Attack-first vs Kite：4.5% trigger，2.2% outcome change；
- Low HP Damage 规则：3.8% trigger，3.2% outcome change；
- Bow cooldown：0% trigger，0% outcome change。

### HARD_AT_ROUND_24

四类 exploit 同样：

```text
TIMEOUT = 0%
```

Healthy 对照中：

- 无规则 Attack-first mirror：0% 干扰；
- 无规则 Attack-first vs Kite：5.5% trigger，2.4% outcome change；
- Low HP Damage：2.0% trigger，1.5% outcome change；
- Bow cooldown：0.2% trigger，0.1% outcome change。

### ROLLING_10_LOW_DAMAGE

Exploit TIMEOUT 仍残留约：

```text
1.7%~2.7%
```

且通常第16~17回合就介入；healthy distortion 也整体更高。

因此它从主候选降级。

## 5. 当前结论

不能简单说 PRESSURE_12 或 ROUND_24 已经胜出。

更合理的下一步是测试组合：

```text
pressure >= 12
OR
round >= 24
→ Hard Liveness
```

设计意图：

```text
Pressure-12 = 自适应识别真正的长期拖延
Round-24    = 无法绕过的绝对晚局 failsafe
```

## 6. 并行开发边界

其他 AI / 开发者现在不要：

- 把 PRESSURE_12 写进正式 P0；
- 把 ROUND_24 写进正式 P0；
- 改 `engine.py` / `rule_engine.py` 正式 anti-stall；
- 因为 exploit 已有候选解就直接进入 GLM Prompt 定稿；
- 再实现一套重复的 liveness benchmark。

可以低冲突并行：

- 独立 review 实验设计；
- 研究 Replay / 日志需求；
- 整理正式产品技术栈；
- 分析更多可能的 adversarial stall 策略。

## 7. 下一步 Gate

```text
Hybrid: Pressure-12 OR Round-24
↓
paired regression（exploit + healthy）
↓
结果稳定且 healthy distortion 可接受？

YES
→ 才提出 normative anti-stall 修订 PR

NO
→ 不修改正式规则，继续实验
```
