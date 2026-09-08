# 《规则之外》验证历史与决策证据链

> 本文不是原始日志合集，而是**项目验证证据总索引**。
>
> 目的：让开发者、AI、评审或后续研究者快速回答：
>
> 1. 我们验证过什么？
> 2. 哪些测试失败过？
> 3. 失败导致了什么架构修改？
> 4. 当前哪些结论可以依赖，哪些仍只是实验候选？
>
> 原始实验细节保留在 `docs/experiments/`、`docs/handoffs/`、PR 和 GitHub Actions 中；本文只保留对设计和开发有长期决策价值的内容。

---

# 1. 如何阅读本文

本文中的状态分为：

```text
PASS        达到预先定义的 Gate，可作为当前工程依据
FAIL        未达到 Gate，必须永久保留，不得事后改写成 PASS
REGRESSION  已暴露问题修复后的已知集回归，不等于新的泛化证明
EXPERIMENT  有信息价值，但不足以成为产品默认
NORMATIVE   已进入当前规则 / 架构基线
```

重要原则：

- **失败结果不能删除或淡化。**
- Prompt / verifier 调优后，同一题库只能叫 regression set，不能重新称为 unseen。
- 安全误拒绝（false reject）与危险误接收（false accept）必须区分。
- 实验配置不能自动升级为产品默认。
- GitHub Actions 绿色只说明 workflow 成功；真正 Gate 必须查看 Artifact 中的指标。

---

# 2. 当前总状态

截至 2026-09-08：

```text
核心机制 / 工程可行性验证  → 已完成主要 Gate
正式 MVP 产品开发          → 已开始
```

阶段切换依据：

```text
docs/MVP_DEVELOPMENT_START_2026-09-08.md
```

最后一道触发 Gate：

```text
live-agent-planner-match
```

真实运行结果：

```text
model = mimo-v2.5-pro
seed = 1270000
result = RED_WIN
rounds = 5
gate_passed = true
gate_failures = []
planner_snapshot_errors = 0
PLAYER_RULE_REPLACED = 2
```

真实 Agent 策略决策：

```text
Phase 0:
RED  -> PRESSURE
BLUE -> KITE

Phase 1:
RED  -> PRESSURE
BLUE -> HOLD
```

对应记录：

```text
docs/experiments/LIVE_AGENT_PLANNER_GATE_PASS_2026-09-08.md
```

---

# 3. 验证阶段时间线

## V-01 外部深度研究审计

状态：`EXPERIMENT / REVIEW`

目的：

- 不依赖项目作者主观判断，重新审视游戏机制、AI 价值、架构和竞赛适配度；
- 识别 README / 设计草案中的未定义语义和高风险假设。

关键输出：

```text
docs/RESEARCH_AUDIT_DECISIONS_2026-09-07.md
```

被采纳的重要方向：

- 必须先解决 liveness；
- terminal utility 必须显式定义；
- movement occupancy 不能靠实现者猜；
- Rule DSL 必须成为可执行规范；
- symmetry 不能只靠“不写 RED/BLUE”；
- LLM 不应直接控制游戏状态；
- 先用确定性 bot / simulation 验证核心，再增加复杂 Agent；
- seed、event log、replay 必须成为工程基础。

该阶段没有证明“游戏好玩”。

---

## V-02 P0 Rule Freeze

状态：`NORMATIVE`

目的：冻结阻断 Engine 实现的核心语义。

对应：

```text
docs/P0_RULE_FREEZE_V0.1.md
docs/P0_RULE_FREEZE_ERRATA_2026-09-07.md
```

冻结范围：

- Agent terminal utility；
- anti-stall / Hard Liveness 基础语义；
- 同步移动 occupancy；
- V0.1 Rule DSL；
- faction neutrality + symmetry；
- RuleAST 最小执行语义。

产品基线包括：

```text
5×5
1v1
HP4
knife_damage=2
max_rounds=30
rule duration=UNTIL_REPLACED
```

注意：后续 HP5 实验没有覆盖这里的产品默认。

---

## V-03 Deterministic Engine

状态：`PASS`

目的：证明不调用 LLM 也能确定性运行基础战斗。

验证内容：

- 同步移动；
- 刀 / 弓攻击；
- 射程与命中率；
- simultaneous settlement；
- mutual death；
- seed 驱动确定性 bow RNG；
- terminal result。

重要工程结论：

> Engine 是最终裁判，LLM 不是 authoritative state writer。

---

## V-04 初始 liveness / bot artifact 诊断

状态：`EXPERIMENT`

目的：判断长局 / 拖局问题到底来自游戏机制还是测试 bot 本身。

重要发现：

- Passive / Passive 等 naive bot 会显著放大停滞；
- 不能仅根据一个 bot profile 的长局就认定棋盘 / 数值设计失败；
- liveness 必须做 adversarial policy 测试，而不是只跑随机 bot。

对应记录包括：

```text
docs/experiments/ADVERSARIAL_LIVENESS_2026-09-07.md
```

---

## V-05 Combat pace sweep

状态：`EXPERIMENT`

目的：比较 HP / knife damage 对基础节奏的影响。

实验曾覆盖：

```text
HP4 / HP5 / HP6
×
knife damage 2 / 1
```

关键决策：

- `HP5/K2` 只保留为工程实验候选；
- **产品默认仍为 HP4/K2**。

不要从测试文件里的 HP5 反向推断产品规则已修改。

---

## V-06 Rule DSL + Validator

状态：`PASS / NORMATIVE IMPLEMENTATION`

目的：让自然语言规则只能进入封闭、有限、确定性可验证的执行空间。

主要验证：

- schema；
- condition / effect allowlist；
- 数值边界；
- faction neutrality；
- symmetry；
- no-effect；
- capability safety；
- liveness safety。

对应：

```text
docs/RULE_DSL_VALIDATOR_IMPLEMENTATION_V0.1.md
```

关键结论：

> Natural Language 可以开放，但 executable semantics 必须封闭。

---

## V-07 Rule Evaluator + Public History

状态：`PASS`

目的：让 RuleAST 对公开状态产生确定性 modifier，并允许历史条件。

公开历史包括：

```text
has_previous_round
moved_last_round
last_attack_weapon
consecutive_bow_miss
consecutive_same_weapon_use
```

对应：

```text
docs/PUBLIC_RULE_HISTORY_V0.1.md
```

关键决策：

- PublicRuleHistory 在规则替换后继续保留；
- 新规则可以使用规则发布前已经发生的公开历史；
- private Agent memory 不属于 Rule public history。

---

## V-08 Rule-aware Engine integration

状态：`PASS`

目的：证明 RuleAST modifier 真正进入 Engine 结算，而不是停留在解释层。

确定的执行层次：

```text
Base stats
→ player rule modifier
→ ordinary safety clamp
→ system anti-stall minimum / override
→ final safety
```

Hard Liveness 不能被普通玩家规则关闭。

---

## V-09 Public Rule Core Signal

状态：`PASS WITH BLOCKER`

目的：验证公共规则是否真的足以改变战局，而不是“规则存在但策略 / 结果基本不变”。

结论：

- 规则机制存在可观测的战局信号；
- 但 liveness robustness 仍是 blocker，因此继续进入 adversarial liveness。

这一步证明的是“机制有信号”，不是“玩家一定觉得好玩”。

---

## V-10 Adversarial Liveness

状态：`PASS AFTER REVISION`

对比过：

```text
CURRENT
PRESSURE_12
ROLLING_10_LOW_DAMAGE
HARD_AT_ROUND_24
```

随后又测试 hybrid 方案。

关键结论：

- 已知拖延 exploit 需要绝对 late-game fallback；
- hybrid 没有形成足够优势；
- 最终采用 Round24 absolute Hard Liveness fallback。

Normative amendment：

```text
docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md
```

当前 Hard Liveness：

```text
previous latch
OR no_damage_streak >= 12
OR round_no >= 24
```

触发后保持到终局。

---

## V-11 Dynamic Public Rule Controller

状态：`PASS`

目的：验证规则不是开局一次性 modifier，而是能够在对局中被真人阶段性替换。

V0.1 cadence：

```text
phase 0: Round1 前
phase 1: Round3 结算后
phase 2: Round6 结算后
...
```

关键语义：

- rule phase due 时必须先处理，不能直接 advance；
- accepted candidate 替换旧规则；
- no submission 沿用旧规则；
- invalid submission 拒绝并沿用旧规则；
- terminal round 不再打开下一 phase；
- PublicRuleHistory 不因 replacement 清空。

动态规则 paired experiment 曾显示不同规则序列能显著改变 outcome / match length，且测试集合中 TIMEOUT 为 0。

对应：

```text
docs/experiments/DYNAMIC_RULE_REPLACEMENT_2026-09-08.md
```

---

# 4. 自然语言规则验证链

## V-12 Strict Natural-Language Adapter

状态：`PASS`

最初链路：

```text
Natural Language
→ provider-neutral model
→ raw untrusted string
→ strict JSON decode
→ RuleValidator
```

原则：

- Prompt compliance 不是 security boundary；
- 不自动修 JSON；
- 不允许 model 直接写 Engine / GameState；
- Controller 再验证。

---

## V-13 Semantic Laundering 风险发现

状态：`FAILURE DISCOVERY`

发现的问题：

玩家可能输入：

```text
只让红方伤害 +1
```

模型为了满足“必须输出合法规则”，可能偷偷变成：

```text
双方伤害 +1
```

生成结果本身可以通过 deterministic Validator，但已经不是玩家原意。

架构修复：增加明确 envelope：

```text
CANDIDATE
or
NO_CANDIDATE
```

并明确：

> 不可表达 / 不允许 / 模糊的意图必须拒绝，不能静默“洗成”另一条合法规则。

这一步是后续自然语言 safety architecture 的基础。

---

## V-14 MiMo Provider + fixed benchmark

状态：`PASS INFRASTRUCTURE`

由于当时 GLM API Key 不可用，live provider 临时切到 MiMo China Token Plan；Zhipu provider 保留，未删除。

原则：

- provider 可切换；
- 同一 corpus 才能横向比较模型；
- secret 只通过环境 / GitHub Actions Secret 注入；
- CI mock provider，不消耗真实 token。

当前 MiMo 默认：

```text
mimo-v2.5-pro
```

---

## V-15 MiMo 第一轮 18-case baseline

状态：`FAIL`

结果摘要：

```text
LEGAL semantic correct = 1/8
NO_CANDIDATE safely rejected = 9/10
false_accepts = 0
false_rejects = 7
```

主要失败不是中文理解完全错误，而是 RuleAST JSON 形状不稳定，例如把：

```text
{"type":"BOW_RANGE_ADD","delta":1}
```

写成简写形式。

对应：

```text
docs/experiments/MIMO_V25_PRO_NL_LIVE_BASELINE_2026-09-08.md
```

决策：

- 不改 corpus；
- 不放宽 Validator；
- 只把 condition / effect 的 exact JSON shape 在 Prompt 中写清。

---

## V-16 Prompt schema fix regression

状态：`REGRESSION PASS`

同一 18-case corpus 修 Prompt 后：

```text
LEGAL = 8/8
NO_CANDIDATE = 10/10
false_accepts = 0
false_rejects = 0
```

其中个别 exact error 只是 rejection reason_code 不同，安全决策仍正确。

对应：

```text
docs/experiments/MIMO_V25_PRO_NL_LIVE_AFTER_PROMPT_FIX_2026-09-08.md
```

重要：

> 这不能作为新的泛化证明，因为 Prompt 已经针对该 corpus 暴露的问题做过修正。

因此建立新的 holdout。

---

## V-17 Holdout V0.1

状态：`FAIL`

40 条新题：

```text
20 LEGAL
20 NO_CANDIDATE
```

冻结 Gate 后 live 测试暴露关键问题：

- `false_accepts = 1`；
- 合法规则也有 false reject；
- 最危险例子是 `A OR B` 被翻译成 `A` 后仍能通过 Validator。

对应：

```text
docs/experiments/MIMO_V25_PRO_NL_HOLDOUT_V01_FAIL_2026-09-08.md
```

架构决策：

```text
Translator
→ RuleValidator
→ Faithfulness Verifier
```

Verifier 只允许：

```text
FAITHFUL
REJECT
```

**不能自动修 Candidate。**

---

## V-18 Verified pipeline V0.1

状态：`FAIL → REGRESSION PASS`

第一版 Faithfulness Verifier 成功把 dangerous false accept 降为 0，但过于保守，导致大量合法规则被误拒绝。

修复方向：

- 明确负向 modifier / history / cooldown 等合法 DSL 能力；
- 让 verifier 理解语义等价表达；
- benchmark 按 AND 语义比较，不把条件数组顺序差异当错误。

已知 V0.1 regression 最终达到：

```text
20/20 LEGAL correctly passed
20/20 illegal blocked
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
```

这仍是 regression，不是 unseen。

---

## V-19 Unseen Holdout V0.2

状态：`FAIL → REGRESSION PASS`

50 条新题：

```text
25 LEGAL
25 NO_CANDIDATE
```

第一次 unseen 结果：

```text
LEGAL = 24/25
wrong_legal_candidates = 0
verifier_errors = 0
false_accepts = 1
```

唯一 hard blocker：

```text
A OR B
→ A AND B
```

两个条件都被保留，因此早期 verifier 只检查“条件是否出现”时没有识别逻辑关系已经改变。

架构修复：

```text
Deterministic Intent Guard
→ Translator
→ RuleValidator
→ Faithfulness Verifier
```

明确 OR/disjunction 在进入 Translator 前直接拒绝；Verifier 同时继续检查 logical relation。

修复后的 V0.2 regression：

```text
LEGAL = 24/25
NO_CANDIDATE blocked = 25/25
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
```

对应记录包括：

```text
docs/experiments/MIMO_V25_PRO_NL_VERIFIED_V02_FAIL_2026-09-08.md
docs/experiments/MIMO_V25_PRO_NL_VERIFIED_V02_REGRESSION_PASS_2026-09-08.md
```

---

## V-20 Unseen Holdout V0.3

状态：`PASS`

新的 50 条未见题：

```text
25 LEGAL
25 NO_CANDIDATE
```

冻结 Gate：

```text
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
legal_semantic_correct >= 24/25
```

第一次 unseen live 结果：

```text
legal_semantic_correct = 24/25
NO_CANDIDATE blocked = 25/25
false_accepts = 0
wrong_legal_candidates = 0
verifier_errors = 0
```

判定：`PASS`

对应：

```text
docs/experiments/NATURAL_LANGUAGE_HOLDOUT_GATE_V0.3.md
docs/experiments/MIMO_V25_PRO_NL_VERIFIED_V03_PASS_2026-09-08.md
```

重要限制：

- V0.3 自第一次 live run 后永久视为 exposed；
- 后续 Prompt / verifier 如果再改，不能拿 V0.3 重新证明 unseen 泛化。

---

# 5. 自然语言进入真实动态对局

## V-21 Dynamic NL Match V0.1

状态：`FAIL`

目的：验证：

```text
真实中文规则
→ verified pipeline
→ DynamicRuleController
→ Rule-aware bots
→ Engine
→ 完整终局
```

3 个 combat seed 实际都完成了比赛且无 TIMEOUT，但旧 Gate 把同一玩家文本为了不同 combat seed 重复调用 MiMo，导致同一句规则出现不同语义判断。

问题本质：

> combat randomness 不应该重新采样玩家规则的语义编译。

因此 V0.1 永久记为 FAIL。

对应：

```text
docs/experiments/MIMO_V25_PRO_NL_DYNAMIC_MATCH_V01_FAIL_2026-09-08.md
```

修复：

```text
一次玩家提交
→ natural-language pipeline 只执行一次
→ 冻结编译结果
→ 多个 combat seed 复用
```

---

## V-22 Dynamic NL Match V0.2

状态：`FAIL — SAFE USABILITY FALSE REJECT`

V0.2 修复了重复语义采样问题。

实际结果：

- phase0 合法“弓射程 +1”成功；
- phase2 非法 OR 被 Intent Guard 正确拒绝；
- phase3 后续合法规则仍可重新替换；
- 多个 combat seed 完整结束；
- **phase1 合法“双方移动距离 +1”被 MiMo 单次返回 NO_CANDIDATE。**

因此 Gate 正式判 FAIL。

对应：

```text
docs/experiments/MIMO_V25_PRO_NL_DYNAMIC_MATCH_V02_FAIL_2026-09-08.md
```

为什么允许项目继续进入 Agent Gate：

- 没有 unsafe accept；
- 错误规则没有进入 Engine；
- Controller / Engine / dynamic replacement 链路没有失控；
- 失败属于玩家体验上的合法规则误拒绝。

当前产品决策：

> 该问题进入 MVP usability debt；通过清晰拒绝反馈、重新措辞和后续安全重试策略解决，**不得通过放松 Validator / Faithfulness safety boundary 解决**。

**不要把 V0.2 改写成 PASS。**

---

# 6. Agent / Planner 验证链

## V-23 Isolated Agent + Deterministic Planner offline Gate

状态：`PASS AFTER GATE CORRECTION`

目标：验证真正的双 Agent 架构：

```text
RED private Agent session
BLUE private Agent session
→ closed StrategyIntent
→ deterministic Planner
→ Controller
→ Engine
```

闭合 Intent：

```text
PRESSURE
KITE
EVADE
HOLD
```

LLM 不能直接输出具体 move path / coordinate / damage / winner / GameState mutation。

### CI 暴露的一个重要 Gate 定义错误

初始 Gate 曾要求：

```text
INVALID_ATTACK = 0
```

offline oracle CI 失败。

分析 Engine 后发现：

- Planner 根据提交时公开快照生成动作；
- 双方移动是 simultaneous；
- same-destination / swap conflict 或对手移动会改变最终位置；
- 攻击合法性是在移动结算后的真实位置上检查；
- 因此原本合理的提交可能在 settlement 时变成 INVALID_ATTACK。

这不是 Planner 一定规划非法。

Gate 修正为检查：

```text
planner_snapshot_errors = 0
INVALID_MOVE_PATH = 0
```

并新增 independent planner snapshot audit。

这个修正不是降低要求，而是把：

```text
submission-time planning correctness
```

与：

```text
simultaneous-game uncertainty
```

正确分开。

对应：

```text
docs/experiments/AGENT_PLANNER_INTEGRATION_GATE_V0.1.md
```

---

## V-24 Live Agent / Planner Gate

状态：`PASS`

首次真实 MiMo Agent Gate：

```text
workflow = live-agent-planner-match
model = mimo-v2.5-pro
seed = 1270000
result = RED_WIN
rounds = 5
gate_passed = true
gate_failures = []
planner_snapshot_errors = 0
PLAYER_RULE_REPLACED = 2
```

真实策略决策：

```text
Phase 0:
RED  -> PRESSURE
BLUE -> KITE

Phase 1:
RED  -> PRESSURE
BLUE -> HOLD
```

证明：

- RED / BLUE 使用独立 Agent session；
- private strategy memory 隔离；
- 两边在 rule change 后都能重新做真实模型决策；
- Planner 负责 concrete actions；
- Engine 负责 settlement；
- match 可以进入 terminal；
- Planner snapshot audit 无错误。

对应：

```text
docs/experiments/LIVE_AGENT_PLANNER_GATE_PASS_2026-09-08.md
```

该 PASS 触发：

```text
正式 MVP 开发开始
```

---

# 7. 这些验证目前可以证明什么

当前工程证据支持：

1. deterministic Engine 可以执行同步 1v1 战斗；
2. Rule DSL / Validator / Evaluator 可以成为 authoritative semantic layer；
3. 动态公共规则真的可以替换并改变战局；
4. 已知拖延策略受到 Hard Liveness 约束；
5. 自然语言规则存在 fail-closed verified pipeline；
6. unseen V0.3 上未观察到 false accept；
7. unsafe semantic laundering 风险已经被架构层专门处理；
8. RED / BLUE Agent 可以隔离 private strategy memory；
9. LLM 可以只负责高层 intent，具体动作仍由 deterministic Planner 生成；
10. 真正的 MiMo Agent + Planner + Controller + Engine 能完成完整终局对战；
11. 当前核心工程风险已经足够低，可以进入真人可玩 MVP 的产品开发。

---

# 8. 这些验证**不能**证明什么

当前不能据此声称：

- 游戏已经“好玩”；
- 玩家愿意长期玩；
- 3 回合一次改规则就是最终最佳节奏；
- 5×5 是最终最优棋盘尺寸；
- HP4 / 当前伤害就是最终平衡；
- StrategyIntent 四分类足够体现最终大模型价值；
- MiMo 的合法规则 false reject 已解决；
- 当前 Prompt 对所有中文表达都鲁棒；
- Replay / Explainability 已达到玩家体验要求；
- 项目一定适合比赛或能获奖；
- 当前 API / 前端架构已经验证。

这些属于 MVP 阶段下一轮验证对象。

---

# 9. 当前已知技术 / 产品债务

## P0 / P1 债务

### 1. Natural-language safe false reject

已知简单合法规则存在偶发 NO_CANDIDATE。

处理方向：

- 对玩家显示明确、可理解的拒绝原因；
- 允许重新措辞；
- 后续评估有限、安全、可观测的 retry 策略；
- 不放松 deterministic Validator / semantic fidelity。

### 2. StrategyIntent 空间较小

当前：

```text
PRESSURE / KITE / EVADE / HOLD
```

足以验证架构，不足以证明 LLM 在最终产品里具有足够深的策略价值。

后续需要通过真人 MVP 和策略行为分析判断是否扩展 intent / planner abstraction。

### 3. Planner 仍是 MVP baseline

当前 Planner 不是全局搜索器，也不是最终博弈算法。

### 4. Product fun 尚未验证

需要真人试玩数据，而不是继续仅靠离线 simulation。

### 5. API / Replay / Frontend vertical slice 尚待正式实现

这是当前 MVP 主线。

---

# 10. MVP 阶段接下来的验证重点

从现在开始，不应把主要时间继续花在静态自然语言 benchmark 上。

优先验证：

```text
1. 真人能否在浏览器完成完整对局闭环
2. 前后端 API contract 是否稳定
3. rule rejection UX 是否可理解
4. strategy intent / rule effect 是否能被玩家看懂
5. Replay 是否能解释“规则改变后为什么战局变了”
6. 两个 Agent 的策略差异是否足够明显
7. 3-round rule cadence 是否给玩家足够观察与决策时间
8. 游戏是否真正产生“机制设计者”体验
9. 竞赛 Demo 是否能在短时间内展示 AI 的必要性
```

当这些问题需要新的实验时，应建立新的 Gate / experiment 文档，而不是修改历史结论。

---

# 11. 关键文档索引

## Normative / architecture

```text
docs/P0_RULE_FREEZE_V0.1.md
docs/P0_RULE_FREEZE_V0.1_ROUND24_AMENDMENT.md
docs/RULE_DSL_VALIDATOR_IMPLEMENTATION_V0.1.md
docs/PUBLIC_RULE_HISTORY_V0.1.md
docs/SEMANTIC_FAITHFULNESS_GATE_V0.1.md
```

## MVP phase

```text
docs/MVP_DEVELOPMENT_START_2026-09-08.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/MVP_FIRST_TASKS.md
```

## Collaboration

```text
AI_DEVELOPER_START_HERE.md
docs/AI_COLLABORATION_PROTOCOL.md
docs/handoffs/
```

## Raw / detailed evidence

```text
docs/experiments/
GitHub Actions artifacts
relevant PR descriptions
```

---

# 12. 新实验写入规范

以后任何会影响架构或产品路线的实验，至少记录：

```text
名称
日期
要回答的问题
固定配置
模型 / provider
样本 / seed
运行前冻结的 PASS / FAIL Gate
实际结果
失败样例
结论
导致的架构 / 产品决策
不能推出什么
关联 PR / workflow / artifact
```

不要只写：

```text
“测试通过了”
```

也不要只保存原始日志而没有决策结论。

---

## 最终原则

这个项目的验证历史应该像一条**可审计的证据链**：

```text
假设
→ 测试
→ 失败/通过
→ 架构修正
→ 新的未见验证
→ 当前结论
```

而不是把失败隐藏掉，只保留最终成功截图。

这条证据链既服务于开发，也将直接服务于后续竞赛答辩、技术说明和第二轮独立深度研究。
