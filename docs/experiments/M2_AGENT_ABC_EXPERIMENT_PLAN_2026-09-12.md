# M2 Agent A/B/C Evidence — Experiment Design Freeze

状态：**FROZEN FOR REVIEW / IMPLEMENTATION NOT YET AUTHORIZED**  
日期：2026-09-12  
前置 Gate：M1、B5A 均已通过

## 1. 决策问题

M2 只回答两个问题：

1. 当前四意图 LLM（B）相对纯确定性启发式（A）是否产生可测量的规则适应价值；
2. 更丰富但仍封闭的高层计划（C）是否值得替换当前四意图结构。

M2 必须支持一个结论：KEEP B、UPGRADE TO C、REDESIGN AI ROLE、SIMPLIFY / REMOVE LLM STRATEGY LAYER。

## 2. 冻结比较组

所有组使用相同 GameConfig、RuleAwareGameEngine、战局升温、规则日程、combat seed 和确定性合法动作枚举。LLM 永远不能直接写 Action、坐标、HP、伤害、RNG、胜负或 GameState。

### A — Deterministic Heuristic

只读取 B/C 可见的同一 public observation，不调用模型、不使用隐藏对手信息。启发式优先级冻结为：

1. 存在本回合可完成击杀的合法候选时选择 PRESSURE；
2. 自身 HP 低于对手且当前没有正期望伤害候选时选择 EVADE；
3. 弓可用且存在正期望伤害候选时选择 KITE；
4. 刀可用且能进入刀范围时选择 PRESSURE；
5. 否则选择 HOLD。

A 仍通过当前 DeterministicIntentPlanner 生成具体动作。

### B — Current Four-intent LLM

保持当前生产 prompt、IsolatedStrategyAgent、private-memory 上限、provider 配置和 DeterministicIntentPlanner。输出仍为 PRESSURE、KITE、EVADE、HOLD。不得为了让 B 得分更高而改 prompt。

### C — Richer-plan Candidate

C 使用与 B 相同的 public observation 和隔离原则，实验输出冻结为：

~~~json
{
  "mode": "PRESSURE|KITE|EVADE|HOLD",
  "target_distance": 1,
  "weapon_preference": "KNIFE|BOW|ANY",
  "risk_budget": "LOW|MEDIUM|HIGH",
  "short_term_goal": "DAMAGE|SURVIVE|CONTROL_DISTANCE",
  "horizon_rounds": 1,
  "contingency": "CLOSE|SEPARATE|HOLD"
}
~~~

target_distance 为 1–5，horizon_rounds 为 1–3；其他字段均为封闭 enum。缺字段、额外字段、越界或协议错误时整份 fallback，不做部分接受。具体 Action 仍由确定性 planner 生成。C 仅存在于实验命名空间，Gate 2 决策前不修改生产 API、Replay contract 或 UI。

C planner 在现有合法候选集合上按固定顺序评分：合法性 → 生存硬约束 → weapon preference → target distance → mode 原有评分 → 确定性 tie-break。contingency 只在其公开触发条件满足时选择对应的封闭评分分支。

## 3. 场景与配对

使用 4 个固定场景，每个规则 candidate 直接来自已验证的 closed Rule DSL，M2 不测试自然语言编译器：

| 场景 | 规则日程 | 测量重点 |
|---|---|---|
| S0 control | 全局无玩家规则 | 基线行为、终局、延迟 |
| S1 mobility | Round 1 后 MOVE_RANGE_ADD +1 | 是否使用新增移动能力 |
| S2 range | Round 1 后 BOW_RANGE_ADD +1 | 是否捕获新增远程攻击机会 |
| S3 replacement | R1 BOW_RANGE_ADD +1；R2 MOVE_RANGE_ADD +1；R3 条件弓命中倍率 | 连续替换后的适应与稳定性 |

combat seeds：

~~~text
pilot:   1_280_000 .. 1_280_002（每场景 3 个）
confirm: 1_280_000 .. 1_280_009（每场景累计 10 个）
~~~

同一个 seed × scenario 必须跑完 A、B、C；执行顺序按 seed 做确定性轮换（ABC、BCA、CAB），降低 provider 时间漂移偏差。RED / BLUE 始终使用不同 Agent 实例。

最大规模为 4 scenarios × 10 seeds × 3 arms = 120 matches。B+C 最多 80 场；按 30 回合、每回合双方各一次决策计算，provider 硬上限为 4,800 次调用。达到运行前登记的金额上限或调用上限立即停止并标记 BUDGET_STOP，不得丢弃已完成失败样本。

## 4. 冻结指标

### Primary：rule-opportunity capture rate

当规则使一个候选动作首次成为合法或提高其可计算效果时，记录一个 opportunity。若实际 Action 使用该新增移动距离、新增射程或被修改武器能力，则记为 captured。

capture_rate = captured opportunities / eligible opportunities。

机会与捕获均由规则前后 authoritative effective stats、planner 合法候选和实际 Action 确定，不由 LLM 自评，也不根据胜负倒推。

### Secondary

- 规则替换后两回合内的高层决策变化率；
- action signature 的 Shannon entropy 与唯一签名数；
- intent/mode 分布与转移矩阵；
- match result、terminal round、score_rounds，三者分别报告；
- provider accepted / protocol fallback / model fallback rate；
- planner snapshot issue count、Engine invalid event count；
- 每次决策端到端 p50 / p95 latency；
- prompt、completion、total token 与实际费用；provider 不返回 usage 时必须记录 usage 缺失，并单列 UTF-8 字符估算；
- 从公开 Replay 能否指出“规则变化 → 策略/行动变化”。

### Replay 可解释性抽样

从 confirm 阶段按 arm/scenario 分层抽取 12 段规则替换窗口，隐藏 arm 名称，由至少 2 名评审独立判断：是否识别能力变化、是否指出随后两回合内相关变化、变化是否与规则一致。三题全是为 1 个 explainable sample。分歧保留原评分并由第三人裁决；不得只挑成功案例。

## 5. 完整性 Gate

任一项失败，相关 arm 不能进入价值比较：

~~~text
planner_snapshot_issues == 0
cross_team_private_memory_leaks == 0
public_contract_drift == 0
replay_reconstructability == 100%
completed samples include provider failures
fallback samples remain in assigned arm
~~~

若 B 或 C 的 provider fallback rate > 10%，该 arm 标为 PROVIDER_INCONCLUSIVE，不声称模型结构优劣。

## 6. 分析方法

- 以 seed × scenario 为 paired unit；
- Primary 报告每 arm 比率、B−A、C−B 的 paired bootstrap 95% CI（10,000 resamples）；
- latency 与费用报告 median、p95、总量；
- match result、rounds、diversity 和 explainability 作为 secondary；
- pilot 只检查 harness、数据完整性和费用，不观察后改阈值；
- confirm 包含 pilot seeds，但只有在 pilot 未改变 protocol 时才能合并。

这是 MVP 决策实验，40 场/arm 只用于识别较大产品效应；小差异视为证据不足。

## 7. Gate 2 判定规则

1. 完整性 Gate 失败 → REDESIGN AI ROLE；
2. B 相对 A 的 Primary 提升至少 10 个百分点，且 paired bootstrap 95% CI 下界 > 0 → B 有保留证据；
3. B 未满足第 2 条，且 B−A 的 95% CI 上界 < 10 个百分点 → SIMPLIFY / REMOVE LLM STRATEGY LAYER；
4. C 相对 B 的 Primary 提升至少 10 个百分点且 CI 下界 > 0，并且 fallback 不更差超过 2 个百分点、p95 latency 与单局费用均不高于 B 的 1.5 倍 → UPGRADE TO C；
5. B 满足保留条件而 C 不满足升级条件 → KEEP B；
6. 其余混合、预算停止或区间过宽结果 → REDESIGN AI ROLE，并明确下一次要减少的不确定性，不追加有利样本。

## 8. 运行产物

正式运行保存 manifest.json、matches.jsonl、decisions.jsonl、rounds.jsonl、summary.json、report.md。禁止保存 API key、system prompt、raw provider error、chain-of-thought 或跨队 private memory。raw model output 仅可在本地受限调试中短暂存在，不进入提交产物。

## 9. 实现前 Gate

本文件冻结的是设计，不授权后端实现。开工前必须：

1. 创建新的 Developer A Issue，列出 harness、A、C、usage/latency instrumentation 和验证范围；
2. 明确 public contract change，默认应为 NO；
3. 更新 DEVELOPER_A_GATE.md 为该 Issue 的 READY；
4. 在 Issue 留下 READY — 可以开始；
5. 从最新 main 新建分支；
6. 运行前登记 provider、model、金额上限和 Replay 评审人员。
