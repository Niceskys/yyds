# AI / 多人并行开发协作约定

> 目的：让新 ChatGPT/Codex/MiMo/DeepSeek 会话、其他 AI 和人类开发者快速继承当前状态，减少重复实现、覆盖修改、接口漂移和把实验结果说得比证据更强。

---

## 1. 当前必须先读的行动基线

```text
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_API_CONTRACT_V0.2.md
docs/MVP_FIRST_TASKS.md
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
```

其中：

- `GAMEPLAY_FLOW_V0.2.md` 回答“玩家现在到底怎么玩”；
- `MVP_API_CONTRACT_V0.2.md` 是当前前后端公共数据/API/Replay normative source；
- `MVP_FIRST_TASKS.md` 回答“下一步先做什么”；
- 第二轮审计文档继续提供架构和证据纪律。

旧 V0.1 contract / Phase0 / 3回合 cadence 文档保留为历史证据，不再作为新产品实现依据。

---

## 2. 当前最重要的状态机变化

旧产品流程：

```text
Phase0 before Round1
Round3 / 6 / 9 ... rule phase
```

当前 V0.2：

```text
Round1 前不能制定规则
Round1 无玩家规则自动开始
每个非终局完整回合后进入 PLAYER_DECISION
玩家可直接继续或尝试提交规则
同一 intermission 最多成功替换一次规则
规则成功后仍需点击继续下一回合
```

因此任何新 AI / 开发者看到旧 `DynamicRuleController` 时，都必须知道：

> 当前 Controller 实现尚待 cadence migration，不能反过来把产品规范改回旧流程。

---

## 3. 每次提交 / PR 前先判断是否需要 Handoff

### 必须说明 / 建议建立 Handoff

满足任一项时，应在 PR Body 中明确交接；若影响跨模块、规范或后续路线，再新增 `docs/handoffs/`：

- 修改玩法状态机；
- 修改架构或模块职责；
- 修改规则/协议/DSL 语义；
- 修改 API/OpenAPI/PublicStrategy/Replay schema；
- 同时涉及多个核心模块；
- 引入新的实验结论，后续开发要依赖；
- 当前工作尚未全部完成，需要下一窗口继续；
- 很可能与其他开发者/AI 的并行任务冲突；
- 有意“不修改某文件/不实现某功能”，且后续容易被误认为遗漏。

### 一般不需要单独 Handoff

- 拼写/排版修复；
- 很小且自解释的单元测试补充；
- 不改变行为的局部重构；
- PR Body 已足以完整说明、且没有并行冲突风险的单文件小改动。

---

## 4. 有协作价值的 PR 至少写清

```text
1. 这次做了什么
2. 为什么这样做
3. 明确没有做什么
4. 当前证据 / 测试状态
5. 与其他分支可能冲突的文件或模块
6. Gameplay/API/OpenAPI/Replay 是否变化
7. 后续开发者不要重复做什么
8. 下一步是什么
```

如果存在临时结论，要明确写：

```text
实验候选 / 暂定 / connectivity evidence
```

不得写成：

```text
最终规则 / 已证明 LLM 必要 / 已证明好玩
```

除非证据真的足够。

---

## 5. 证据等级纪律

历史 `live-agent-planner-match` Gate 的后续正式定位：

```text
connectivity evidence
```

它支持“真实 provider + 两个隔离 Agent + Planner + Controller + Engine 可以连通并完成终局”。

它不支持：

- LLM Agent 比 heuristic 更好；
- 四个 StrategyIntent 是最终策略结构；
- memory 已形成学习；
- 游戏已经好玩；
- V0.2 新玩法已经验证；
- 当前 Agent schema 可以永久冻结。

历史 PASS 不删除、不改写，但新文档/PR 不得把它升级成 value evidence。

Sprint 1 的 LLM value 需要独立 A/B/C 证据。

---

## 6. 并行开发原则

- 优先新分支 + PR，不直接在 `main` 做大范围修改；
- 开始工作前读取最新 `main`、当前 normative 文档和相关 handoff；
- 不覆盖无关修改；
- 尽量通过新增低耦合文件减少热点冲突；
- 如果必须修改热点文件，PR 中明确说明；
- 实验代码与正式产品代码分层；
- 一个任务只指定一个主要实现 AI，不让两个 AI 同时编辑同一热点文件；
- 前后端通过冻结 contract 对接，不把 Engine 规则逻辑复制到前端；
- Replay 是 shared product contract，不是后端私有日志格式。

---

## 7. Contract / schema ownership

当前 canonical source：

```text
docs/MVP_API_CONTRACT_V0.2.md
src/rules_beyond/api_contract.py
```

实现责任：

```text
Developer A：Pydantic / OpenAPI 生成源
Developer B：generated/validated TypeScript types 的消费方
Shared review：PlayerDecision / BattleEscalation / PublicStrategyDecision / Replay / privacy boundary
```

硬规则：

- 前端类型不得长期手改形成第二套真相；
- fixture 必须通过同一 schema 校验；
- breaking change 必须升级 schema/replay version；
- enum 值、字段含义不能静默改变；
- 修改公共 contract 时 A/B 都必须知情；
- 当前新前端只使用 `contracts/fixtures/mvp-v0.2/`。

---

## 8. 当前项目阶段与 P0

```text
正式 MVP 产品开发（GO WITH CONDITIONS）
```

当前 P0：

```text
Gameplay/API Contract V0.2
→ DynamicRuleController cadence migration
→ MatchApplicationService
→ revision / lock / idempotency
→ frontend mock / real integration
→ Replay
→ 追逃实验 + Agent A/B/C
→ 真人试玩
```

Developer B 可以在 Controller migration 时并行完成 V0.2 Mock UI。

---

## 9. 当前双人责任域

### Developer A

```text
src/rules_beyond/**
Python tests
DynamicRuleController V0.2 migration
Pydantic / OpenAPI
MatchApplicationService
MatchRepository
FastAPI
Replay public projection
provider integration
```

### Developer B

```text
web/**
React + TypeScript + Vite
初始页
5×5 board
红蓝状态
rule_change_count
战局升温
规则输入 / 拒绝 / suggested rephrase
公开策略 / concrete action
Event feed
Replay timeline
```

### 默认热点文件由 Developer A 管理

```text
src/rules_beyond/engine.py
src/rules_beyond/rule_engine.py
src/rules_beyond/dynamic_rule_controller.py
src/rules_beyond/strategy_agent.py
src/rules_beyond/rule_dsl.py
src/rules_beyond/rule_validator.py
src/rules_beyond/api_contract.py
replay event mapping
```

Developer B 不为了 UI 需求直接修改这些文件；需要新能力时先提出 contract 变更。

---

## 10. Public / private boundary

公开 API/Replay 可以包含：

- public rule；
- accepted RuleAST projection；
- effective stats；
- public strategy decision；
- concrete Action；
- Engine public events；
- HP/position/result；
- completed_rounds / score_rounds；
- rule_change_count；
- PlayerDecision 状态；
- BattleEscalation 状态；
- public rejection code。

永远不能进入 public API/Replay：

```text
provider key
raw chain-of-thought
hidden reasoning
RED/BLUE private strategy memory
完整 system prompt
未经清洗的 provider error/body
stack trace
```

任何新增 schema 字段先做 privacy review。

---

## 11. 玩家 UI 中文化原则

内部 enum 可保持英文稳定值，但普通玩家界面尽量中文。

至少映射：

```text
PRESSURE → 逼近进攻
KITE → 保持距离
EVADE → 躲避保命
HOLD → 原地应对
RED → 红方
BLUE → 蓝方
BOW → 弓箭
KNIFE → 刀
```

工程字段：

```text
Hard Liveness / conflict_level
```

在玩家 UI 统一表达为：

```text
战局升温
```

不要向普通玩家展示 schema/provider/CoT 等工程概念。

---

## 12. V0.2 玩法硬规则，AI 不得擅自改变

```text
Round1 前不能制定规则
Round1 无玩家规则
每个非终局完整回合后暂停
每个 intermission 都可尝试提交规则
同一 intermission 最多成功替换一次
规则 accepted 后仍需手动继续
始终最多一条 active rule
rule_change_count 只统计成功规则
规则替换不重置 no_damage_streak
暂时没有回血
玩家主成绩 = completed_rounds
```

`max_rounds = 30` 暂保留。

达到 30 回合时，AI match result 可以是 `TIMEOUT`，但玩家 UI 应视为达到本局最高回合数。

---

## 13. 当前必须保留的 anti-stall 语义

当前 Engine 已有：

```text
3 / 6 / 9 / 12 连续无实际伤害阈值
Round24 hard-liveness 兜底
```

V0.2 产品名：

```text
战局升温
```

不要在没有实验和规范变更的情况下自行删掉或改阈值。

尤其禁止：

```text
换规则 → no_damage_streak 清零
```

只有实际伤害才重置连续无伤害。

---

## 14. 当前必须保留的已知问题

Natural-Language Dynamic Match V0.2 因一条合法规则被 MiMo 安全误拒而正式记录为 FAIL。

不能改写成 PASS，也不能通过放松 Validator / Faithfulness Verifier 掩盖。

MVP 中通过：

```text
清晰拒绝反馈
suggested rephrase
玩家确认后重新提交
受控 retry（仅网络/协议错误）
```

解决可用性问题。

---

## 15. 当前禁止 AI 擅自做的事

禁止：

- 把旧 Phase0 / 3回合 cadence 当当前产品规则；
- Round1 前允许玩家制定规则；
- accepted 后自动推进下一回合；
- 同一 intermission 成功替换多次；
- rule change 重置战局升温；
- 加回血；
- 扩 OR/NOT/multi-effect 只为 Demo；
- 因 UI 方便绕过 Controller/Validator；
- 让 LLM 直接修改 GameState；
- 让两个 Agent 共用 private memory；
- 把 private memory/hidden reasoning 放进 Replay；
- 把四个 StrategyIntent 固化为永久前端合同；
- 在没有 A/B/C 证据时声称 LLM Agent 必要；
- 一开始引入 WebSocket/Redis/Celery/微服务；
- 为“顺手完善”加入多人、职业、地形、装备、账号、排行榜等 Non-goals。

---

## 16. AI 接手项目时最低读取顺序

```text
README.md
AI_DEVELOPER_START_HERE.md
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_API_CONTRACT_V0.2.md
docs/MVP_FIRST_TASKS.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
最新相关 handoff
当前 open PR
相关模块源码/测试
```

不要只根据旧聊天摘要、某一个 experiment 或旧 README 猜当前状态。
