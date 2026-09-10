# MVP 下一里程碑执行基线 — 2026-09-10

状态：**CURRENT EXECUTION BASELINE**  
前置工程纵向切片：**DONE**  
玩法 / Contract：`V0.2 / mvp-v0.2`

> 本文件从 2026-09-10 起负责回答：**A0–A3、B0–B4 都完成以后，项目下一步做什么。**
>
> `docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md` 保留为第二轮审计历史与原始行动依据；其中关于“尚未有 FastAPI / React / Match Service”以及旧 Phase 0 / Round 3 cadence 的描述已经是历史状态，不再代表当前执行进度。

---

# 1. 当前已经完成什么

截至 B4 merge：

```text
Gameplay Flow V0.2                         DONE
API / Replay Contract V0.2                DONE
DynamicRuleController V0.2                DONE — A0
MatchApplicationService                   DONE — A1
Repository / revision / lock / idempotency DONE — A2
FastAPI five-route vertical slice         DONE — A3 / PR #59
React/Vite product UI                     DONE — B0/B1
Replay UI                                 DONE — B3
OpenAPI generated TypeScript + API seam   DONE
real HTTP frontend integration            DONE — B4 / PR #61
```

正式运行链已经存在：

```text
Browser React
→ HttpMatchApiAdapter
→ FastAPI V0.2
→ MatchRepository
→ MatchApplicationService
→ DynamicRuleController
→ isolated RED / BLUE strategy agents
→ deterministic planner
→ Engine
→ authoritative MatchSnapshot / ReplaySnapshot
```

因此当前项目的主要风险已经从“工程能不能接起来”转为：

1. 一个不了解代码的人能否稳定完成一局；
2. LLM Agent 是否真的产生玩家可感知、可证明的价值；
3. “延长战斗”是否能形成足够丰富的策略空间，而不是迅速收敛成单一拖延套路。

---

# 2. 下一阶段唯一主顺序

```text
M1 — Integrated Playable Acceptance
↓ GATE 1
M2 — Agent A/B/C Evidence
↓ GATE 2
M3 — Human Playtest
↓
根据证据决定 Agent / 玩法 / UI 下一轮改动
```

这三步跑通前，默认不增加新的玩法系统。

---

# 3. M1 — Integrated Playable Acceptance

目标：**证明当前仓库真的已经是一条可由真人完成的纵向产品闭环，而不只是各层分别通过单元测试。**

## 必须验证的真实流程

至少完整跑通一次：

```text
启动 backend
启动 frontend
浏览器打开游戏
→ 开始游戏
→ create match
→ Round 1 前规则输入不可用
→ continue / advance Round 1
→ PLAYER_DECISION
→ 提交一条 rejected 或 MODEL_UNAVAILABLE 规则并可重试
→ 提交一条 accepted 规则
→ accepted 后不自动 advance
→ continue 下一回合
→ 至少再完成一个完整 Round
→ 继续直至 terminal，或使用受控短局配置完成 terminal smoke
→ 打开 Replay
→ Replay 能看到 authoritative round / intermission 历史
```

## 必须观察的异常路径

至少确认：

- 网络 / recoverable 失败不会让 UI 私自推进；
- 409 revision conflict 不自动重放旧 mutation；
- 同一次未知结果重试复用 Idempotency-Key；
- strategy fallback 是 200 正常 round，而不是整局失败；
- rule `MODEL_UNAVAILABLE` 是 200 可重试业务结果；
- terminal 后 submit / advance 被禁用；
- 未出现 raw provider error / private memory / chain-of-thought / API key / stack。

## M1 不做什么

M1 不增加：

```text
新 DSL
新武器
回血
多单位
地形
账号
排行榜
数据库
WebSocket
复杂动效重构
Agent richer plan
```

发现 bug 可以修；发现“想要的新功能”先记录，不在 M1 顺手加入。

## GATE 1 — M1 通过条件

只有同时满足以下条件，才进入 A/B/C：

1. 一条真实浏览器闭环可重复跑通；
2. 不需要手工修改数据库 / Match state 才能完成；
3. 规则 accepted / rejected / model unavailable 都不会破坏对局；
4. Replay 不依赖再次调用模型；
5. frontend / backend hosted CI 继续全绿；
6. 有一份明确 smoke 记录：环境、provider、seed（若有）、关键步骤、结果、已知问题。

---

# 4. M2 — Agent A/B/C Evidence

目标：**回答 LLM Agent 是否真的值得保留，以及当前四分类结构是否足够。**

必须比较三组：

## A — Deterministic Heuristic

不使用 LLM 做策略决策。

## B — Current Four-Intent LLM

```text
PRESSURE
KITE
EVADE
HOLD
```

保持当前产品实现。

## C — Richer-plan Candidate

只有在实验设计冻结后才允许实现。候选 public/high-level structure 可以包含：

```text
mode
target_distance
weapon_preference
risk_budget
short_term_goal
horizon_rounds
contingency
```

具体 Action 仍必须由 deterministic planner / Engine 决定。

## 最低指标

至少记录：

- rule change 后策略/行为响应差异；
- strategy/provider 成功率与 fallback rate；
- planner/settlement invalid rate；
- 行为/策略多样性；
- match utility / result；
- 玩家目标 `score_rounds`；
- latency；
- token / API cost；
- 是否能从公开 Replay 看出“AI 对规则作出了合理适应”。

## 实验纪律

- 同组使用可比较 seed / scenario；
- 不只挑成功案例；
- provider 失败必须进入统计；
- 不允许仅用 README / prompt / 单局录屏证明 AI 有价值；
- A/B/C 结果允许得出“LLM 没有明显优势”。

## GATE 2 — Agent 决策

结果必须支持下列之一：

```text
KEEP B
UPGRADE TO C
REDESIGN AI ROLE
SIMPLIFY / REMOVE LLM STRATEGY LAYER
```

没有证据时不默认“因为是 AI 比赛，所以 LLM 越多越好”。

---

# 5. M3 — Human Playtest

目标：**确认玩家是否真的理解规则影响、AI 适应和“延长战斗”的乐趣。**

优先找不了解代码的人试玩，而不是只由开发者自测。

最低记录：

- 玩家是否理解自己的目标；
- 是否理解“规则同时作用双方”；
- 是否知道 accepted 后还要点继续；
- 是否能从策略 / 行动 / Replay 看懂规则影响；
- 规则输入失败时是否知道如何改写；
- 是否出现明显最优拖延套路；
- 哪一时刻开始觉得无聊；
- 是否愿意主动再开一局；
- 最想修改/新增的一个东西是什么。

不要把“玩家提出的功能”直接视为需求。先聚类问题，再判断根因是：

```text
规则机制
AI 行为
信息表达
节奏
目标设计
UI
```

---

# 6. 当前明确 Non-goals

在 M1–M3 得出结论前，继续推迟：

```text
OR / NOT / multi-effect DSL
回血
WebSocket
Redis
Celery
Event Bus
微服务
复杂数据库
多人房间
账号 / 排行 / 商城
MCTS
多单位
地形
职业 / 技能
自由代码规则
移动 App
3D
```

如果出现新的功能建议，默认进入候选清单，不直接开工。

---

# 7. Developer A / B 调度规则

## Developer A

当前仍受根目录：

```text
DEVELOPER_A_GATE.md
```

约束。没有新的批准 Issue 前保持 `PAUSED_BY_OWNER`。

M2 若需要实现实验 harness / deterministic A / richer C，必须先创建新的 Developer A Issue，并按 gate 解锁协议放行。

## Developer B

B0–B4 已完成。新的前端工作必须建立新 Issue。

M1 可以由 Shared / Developer B 执行 integration smoke 与必要的前端 integration bug 修复，但不能借 M1 扩大玩法范围。

---

# 8. 当前第一任务

**现在先做 M1 Integrated Playable Acceptance。**

在 M1 通过以前：

- 不解锁 Developer A 做新 Agent feature；
- 不实现 C richer plan；
- 不做 UI 大改版；
- 不提前做真人玩法扩展。

M1 完成后，Shared Review 再决定 M2 的具体实验任务拆分。
