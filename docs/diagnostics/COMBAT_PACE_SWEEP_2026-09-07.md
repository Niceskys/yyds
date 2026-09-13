# 战斗节奏参数实验：HP × Knife Damage

> 日期：2026-09-07  
> 状态：Experimental evidence / 非最终平衡结论  
> 数据：6 个参数组合 × 6 个策略配对 × 每格 1,000 局 = 36,000 局。  
> 执行：GitHub Actions `combat-pace-sweep`。

## 1. 为什么做这个实验

前一轮诊断已经说明：

> `Aggressive vs Aggressive` 的 100% 双杀主要是 naive bot heuristic 与同步规则耦合，不应因此直接修改同步移动规则。

新的风险是战斗节奏。

部分对局：

```text
3 ~ 6 回合就结束
```

而玩家规则窗口暂定每 3 回合一次。如果大量比赛过快结束，核心循环：

```text
玩家改规则
→ AI 适应
→ 玩家观察
→ 再改规则
```

可能没有充分展开的时间。

本轮只改变：

- 初始 HP；
- Knife Damage。

不改变地图、Bow、移动、anti-stall 或 Bot 行为。

---

## 2. 参数组合

| Variant | HP | Knife Damage |
|---|---:|---:|
| baseline | 4 | 2 |
| hp5_k2 | 5 | 2 |
| hp6_k2 | 6 | 2 |
| hp4_k1 | 4 | 1 |
| hp5_k1 | 5 | 1 |
| hp6_k1 | 6 | 1 |

代表性配对：

```text
Attack-first vs Attack-first
Aggressive vs Attack-first
Attack-first vs Aggressive
Attack-first vs Kite
Kite vs Attack-first
Kite vs Kite
```

`Aggressive vs Aggressive` 没放入本轮节奏平均，因为上一轮已经确认它是一个特殊的 naive collision stress case，不适合拿来代表普通节奏。

---

## 3. 六个组合的总体对比

下面的“总体”是把 6 个策略配对等权合并，仅用于比较参数敏感性，不代表未来正式 Agent 的真实分布。

| 参数 | 六组平均回合 | <=6 回合比例 | Timeout 比例 |
|---|---:|---:|---:|
| HP4 / Knife2 | 7.47 | 49.1% | 0.00% |
| HP5 / Knife2 | 9.67 | 37.2% | 0.12% |
| HP6 / Knife2 | 11.86 | 34.1% | 1.07% |
| HP4 / Knife1 | 7.78 | 49.5% | 0.00% |
| HP5 / Knife1 | 10.23 | 37.4% | 0.15% |
| HP6 / Knife1 | 12.62 | 25.5% | 1.10% |

### 第一结论：单独降低 Knife Damage 效果很有限

同 HP 比较：

```text
HP4: Knife2 -> Knife1
平均回合 7.47 -> 7.78
短局率 49.1% -> 49.5%

HP5: Knife2 -> Knife1
平均回合 9.67 -> 10.23
短局率 37.2% -> 37.4%
```

因此：

> `Knife Damage 2 -> 1` 不是当前最有效的节奏调节手段。

尤其对主要使用 Bow 的 Attack-first / Kite 对局几乎没有直接作用。

### 第二结论：HP 对节奏影响明显

典型 Attack-first vs Attack-first：

| HP / Knife | 平均回合 | <=6 回合 |
|---|---:|---:|
| 4 / 2 | 6.29 | 61.0% |
| 5 / 2 | 8.13 | 19.0% |
| 6 / 2 | 9.84 | 4.0% |

增加 HP 能明显减少这一类过短对局。

### 第三结论：HP=6 开始把远程对局推向过长区域

Attack-first vs Kite：

| HP / Knife | 平均回合 | >=12 回合 | Timeout |
|---|---:|---:|---:|
| 4 / 2 | 11.38 | 43.7% | 0.0% |
| 5 / 2 | 14.84 | 72.7% | 0.3% |
| 6 / 2 | 17.93 | 89.2% | 2.6% |

反向 Kite vs Attack-first 在 HP6 / Knife2 下 Timeout 为 3.2%。

因此：

> 继续简单增加全局 HP 会同时拖慢原本已经足够长的远程战斗。

### 第四结论：全局数值不能解决所有短局

Aggressive vs Attack-first：

```text
HP4 / Knife2: 3.0 回合，100% <=6
HP5 / Knife2: 3.514 回合，100% <=6
HP6 / Knife2: 4.0 回合，100% <=6
HP6 / Knife1: 6.256 回合，74.4% <=6
```

说明：

> 通过全局加 HP / 降 Knife Damage，很难同时解决近战爆发型短局，又不把远程对局拖得过长。

这也是为什么当前不应继续无止境做数值微调。

---

## 4. 当前最合理的实验候选

如果下一阶段必须选择一个单一测试值：

> **HP=5 / Knife Damage=2 是目前更合理的“下一阶段实验候选”，不是最终平衡值。**

理由：

- 相比 HP4，明显减少 Attack-first 镜像短局；
- Attack-first/Kite 对局进入约 14~15 回合；
- Timeout 仍然非常低（约 0~0.4% 的这些代表性配对）；
- 不需要同时改变 Knife 的基础身份；
- 比 HP6 更少把远程对局推向 18+ 回合与 2~3% Timeout。

但目前**不建议立刻把仓库正式默认值永久改为 HP5**。

原因是下一阶段真正需要验证的是动态公共规则，而不是继续把 simple-bot baseline 调到某个漂亮数字。

---

## 5. 对开发顺序的影响

这一轮数据已经足够支持停止纯基础数值调参。

下一步应进入：

```text
Rule DSL + Validator
→ deterministic Rule Evaluator
→ 用预定义规则做动态规则 simulation
```

暂时仍然：

```text
不接 GLM
不接正式 Agent
不做 UI polish
```

先回答项目最核心的问题：

> 同一组求胜 Bot/Planner，在公共规则发生变化以后，行为和结果是否真的发生可解释、可重复的变化？

如果动态规则本身不能稳定改变策略，那么继续优化 HP、动画或 LLM 接口都没有意义。

---

## 6. 当前结论

### 可以接受

- Engine liveness 兜底目前能工作；
- 不同简单策略确实产生不同结果；
- HP 是明显的节奏旋钮；
- HP5 是值得继续实验的中间值。

### 仍不能声称

- HP5 是最终值；
- Knife Damage2 已平衡；
- 正式 Agent 会呈现相同分布；
- 基础战斗已经好玩；
- 玩家动态规则一定能把过短比赛变成有意义的长局。

最后一项正是下一阶段要验证的内容。
