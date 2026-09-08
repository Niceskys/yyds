# AI / 多人并行开发协作约定

> 目的：让新 ChatGPT/Codex/MiMo/DeepSeek 会话、其他 AI 和人类开发者快速继承当前状态，减少重复实现、覆盖修改、接口漂移和把实验结果说得比证据更强。

## 1. 当前必须先读的行动基线

2026-09-08 第二轮审计后的当前行动文件：

```text
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
docs/MVP_API_CONTRACT_V0.1.md
```

其中：

- `SECOND_AUDIT_ACTION_PLAN...` 回答“现在先做什么”；
- `MVP_API_CONTRACT_V0.1.md` 是前后端公共数据/API/Replay 的 normative source。

---

## 2. 每次提交 / PR 前先判断是否需要 Handoff

不是每个小改动都创建新文档。

### 必须说明 / 建议建立 Handoff 的情况

满足任一项时，应在 PR Body 中明确交接；若影响跨模块、规范或后续路线，再新增 `docs/handoffs/` 文档：

- 修改架构或模块职责；
- 修改规则/协议/DSL 等规范语义；
- 修改 API/OpenAPI/PublicStrategy/Replay schema；
- 同时涉及多个核心模块；
- 引入新的实验结论，后续开发要依赖该结论；
- 当前工作尚未全部完成，需要下一窗口继续；
- 很可能与其他开发者/AI 的并行任务冲突；
- 有意“不修改某文件/不实现某功能”，且后续容易被误认为遗漏。

### 一般不需要单独 Handoff 文档

- 拼写/排版修复；
- 很小且自解释的单元测试补充；
- 不改变行为的局部重构；
- PR Body 已足以完整说明、且没有并行冲突风险的单文件小改动。

---

## 3. 有协作价值的 PR 至少写清

```text
1. 这次做了什么
2. 为什么这样做
3. 明确没有做什么
4. 当前证据 / 测试状态
5. 与其他分支可能冲突的文件或模块
6. API/OpenAPI/Replay schema 是否变化
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

## 4. 证据等级纪律

第二轮审计后，历史 `live-agent-planner-match` Gate 的后续正式定位是：

```text
connectivity evidence
```

它支持“真实 provider + 两个隔离 Agent + Planner + Controller + Engine 可以连通并完成终局”。

它不支持：

- LLM Agent 比 heuristic 更好；
- 四个 StrategyIntent 是最终策略结构；
- memory 已经形成学习；
- 游戏已经好玩；
- 当前 Agent schema 可以永久冻结。

历史 PASS 记录不删除、不改写，但新文档/PR 不得把它升级叙述成 value evidence。

Sprint 1 的 LLM value 需要独立 A/B/C 证据。

---

## 5. 并行开发原则

- 优先新分支 + PR，不直接在 `main` 上做大范围修改；
- 开始工作前读取最新 `main` 和相关 `docs/handoffs/`；
- 不覆盖无关修改；
- 尽量通过新增低耦合文件减少热点文件冲突；
- 如果必须修改热点文件（如 `engine.py`），PR 中明确说明；
- 实验代码与正式产品代码分层，避免实验结论未经验证直接进入默认规则；
- 一个任务只指定一个主要实现 AI，不让两个 AI 同时编辑同一分支的热点文件；
- 前后端通过冻结 contract 对接，不把 Engine 规则逻辑复制到前端；
- Replay 是 shared product contract，不是后端私有日志格式。

---

## 6. Contract / schema ownership

Canonical source：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

实现责任：

```text
Developer A：Pydantic / OpenAPI 生成源
Developer B：generated/validated TypeScript types 的消费方
Shared review：PublicStrategyDecision / Replay / privacy boundary
```

硬规则：

- `api-types.ts` 等前端类型不得长期手改形成第二套真相；
- fixture 必须通过同一 schema 校验；
- breaking change 必须升级版本；
- enum 值、字段含义不能静默改变；
- `schema_version` / `plan_version` / `replay_version` 由规范管理；
- 修改公共 contract 时 A/B 都必须知情。

---

## 7. 当前项目阶段

项目已经从“只做核心机制验证”进入：

```text
正式 MVP 产品开发（GO WITH CONDITIONS）
```

“可以开始 MVP”不等于“当前 Agent 架构已经证明有价值”。

当前 P0 是：

```text
公共 contract
→ MatchApplicationService
→ revision/lock/idempotency
→ frontend mock / real integration
→ Replay
→ Agent A/B/C
```

---

## 8. MVP 双人并行责任域

默认分工：

```text
Developer A：Python 后端 / Engine integration / Agent / LLM / FastAPI / OpenAPI / Match Service
Developer B：React + TypeScript / Board / Rule UI / Replay / Visualization
```

默认热点文件由 Developer A 管理：

```text
src/rules_beyond/engine.py
src/rules_beyond/rule_engine.py
src/rules_beyond/dynamic_rule_controller.py
src/rules_beyond/strategy_agent.py
src/rules_beyond/rule_dsl.py
src/rules_beyond/rule_validator.py
未来 canonical schemas.py
未来 replay event mapping
```

Developer B 不为了 UI 需求直接修改这些文件；需要新能力时先提出 contract 变更。

---

## 9. Public / private boundary

公开 API/Replay 可以包含：

- public rule；
- accepted RuleAST projection；
- effective stats；
- public strategy decision；
- concrete Action；
- Engine public events；
- HP/position/result；
- Hard Liveness；
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

## 10. AI 接手项目时最低读取顺序

建议至少读取：

```text
README.md
AI_DEVELOPER_START_HERE.md
docs/SECOND_AUDIT_ACTION_PLAN_2026-09-08.md
docs/MVP_API_CONTRACT_V0.1.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/MVP_FIRST_TASKS.md
最新 P0 / normative 规则文档
相关模块代码
最新 docs/handoffs/
当前 open PR（若有）
```

不要只根据旧聊天摘要、某一个 experiment 或旧 README 猜当前状态。

---

## 11. 当前必须保留的已知问题

Natural-Language Dynamic Match V0.2 因一条合法规则被 MiMo 安全误拒绝而正式记录为 FAIL。

不能把它改写成 PASS，也不能通过放松 Validator / Faithfulness Verifier 来掩盖。

MVP 中应通过：

```text
清晰拒绝反馈
suggested rephrase
玩家确认后重新提交
受控 retry（仅网络/协议类错误）
```

解决可用性问题。

---

## 12. 当前禁止 AI 擅自做的事

禁止：

- 扩 OR/NOT/multi-effect 只为了让 Demo 看起来更强；
- 因为 UI 方便绕过 Controller/Validator；
- 让 LLM 直接修改 GameState；
- 让两个 Agent 共用 private memory；
- 把 private memory/hidden reasoning 放进 Replay；
- 把四个 StrategyIntent 固化为永久前端合同；
- 在没有 A/B/C 证据时声称 LLM Agent 必要；
- 一开始引入 WebSocket/Redis/Celery/微服务；
- 为“顺手完善”加入多人、职业、地形、装备、账号、排行榜等 Non-goals。
