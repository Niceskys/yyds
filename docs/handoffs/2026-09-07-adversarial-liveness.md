# Handoff — Adversarial Liveness Experiment

> 日期：2026-09-07  
> 分支：`experiment/adversarial-liveness`  
> 状态：候选 anti-stall 实验；**尚未修改正式/normative liveness 规则**。

## 1. 为什么做这一步

上一轮 public-rule paired-seed 实验已经证明：

```text
Core mechanic signal = PASS
```

公共规则可以明显改变动作、武器使用和终局。

但同时发现：

```text
Liveness robustness = BLOCKER
```

低命中/远程规则可以偶尔造成一点伤害，反复把 `no_damage_streak` 清零，从而长期避免触发 Hard Liveness，最终把 TIMEOUT 推到 10%~33%。

因为真人玩家目标就是延长战斗，这不是边缘问题，而是与玩家激励同方向的可利用漏洞。

## 2. 本分支只比较候选方案

正式 `GameEngine` / `RuleAwareGameEngine` 的 anti-stall 语义暂时不改。

实验层比较：

### CURRENT

现有方案，无额外干预。

### PRESSURE_12

维护实验压力值：

```text
无伤害回合：pressure += 1
有伤害回合：pressure = max(0, pressure - 1)
pressure >= 12：进入 Hard Liveness
```

与当前“任意伤害直接清零”相比，零星伤害只能减缓压力，而不能完全洗掉长期拖延记录。

### ROLLING_10_LOW_DAMAGE

查看最近 10 个完整回合：

```text
总实际伤害 <= 1
→ 进入 Hard Liveness
```

测试“滚动窗口低 DPS”是否比连续无伤害更能识别稀疏攻击。

### HARD_AT_ROUND_24

绝对晚局兜底：

```text
Round >= 24 且仍未终局
→ 进入 Hard Liveness
```

优点是简单、可解释；风险是可能机械截断本来合理的长局。

## 3. 实验方法

使用上一轮同一候选参数：

```text
HP=5
Knife Damage=2
```

不会修改正式默认 HP=4。

对两类场景同时测试。

### 已知 exploit 场景

- Bow Range +1 / Attack-first mirror；
- Distance>=3, Bow Hit×0.5 / Attack-first vs Kite；
- 同规则 / Kite vs Attack-first；
- 同规则 / Kite mirror。

### healthy 对照

- 无规则 / Attack-first mirror；
- 无规则 / Attack-first vs Kite；
- HP<=2, Bow Damage+1 / Attack-first vs Kite；
- repeat Bow cooldown / Attack-first vs Kite。

目的：不能只看谁最能压 TIMEOUT，还要看它是否过度干扰原本正常的比赛。

## 4. 主要指标

每个候选与 CURRENT 使用相同 seed 比较：

- Timeout rate；
- 平均回合；
- outcome change rate vs CURRENT；
- 候选触发率；
- 平均触发回合；
- Hard Liveness 实际进入率；
- FORCED_BOW 数量。

## 5. 当前代码边界

新增：

```text
src/rules_beyond/liveness_experiment.py
tests/test_liveness_experiment.py
.github/workflows/adversarial-liveness.yml
```

实验策略通过在回合开始前对实验 state 设置 `hard_liveness_active=True` 来模拟候选方案。

这只是实验控制器，不代表产品 Engine 已采用该方案。

## 6. 并行开发注意

在实验结果出来前，其他 AI / 开发者不要：

- 直接把 pressure/rolling/round24 任一方案写进 normative P0 文档；
- 直接改 `engine.py` 的 no_damage_streak 语义；
- 开始每3回合规则替换 controller；
- 因为 core signal PASS 就开始 GLM Prompt 定稿。

可以低冲突并行：

- 对本实验设计做独立 code review；
- 分析更多 stall exploit 思路；
- 整理比赛/Replay/日志需求；
- 提出候选 liveness 指标，但不要未经数据直接改正式规则。

## 7. 下一步 Gate

```text
候选方案实验
↓
找到能显著压低 exploit TIMEOUT、且 healthy distortion 可接受的方案？

YES
→ 做更大样本回归
→ 再考虑 normative liveness 修订

NO
→ 不强行选一个
→ 扩展方案/必要时做针对性深度研究
```
