# AI / 多人并行开发协作约定

> 目的：让新 ChatGPT 窗口、其他 AI、其他开发者可以快速继承当前状态，减少重复实现、覆盖修改和语义漂移。

## 1. 每次提交 / PR 前先判断是否需要 Handoff

不是每个小改动都创建新文档。

### 必须说明 / 建议建立 Handoff 的情况

满足任一项时，应在 PR Body 中明确交接；若影响跨模块、规范或后续路线，再新增 `docs/handoffs/` 文档：

- 修改架构或模块职责；
- 修改规则/协议/DSL 等规范语义；
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

## 2. 有协作价值的 PR 至少写清

```text
1. 这次做了什么
2. 为什么这样做
3. 明确没有做什么
4. 当前证据 / 测试状态
5. 与其他分支可能冲突的文件或模块
6. 后续开发者不要重复做什么
7. 下一步是什么
```

如果存在临时结论，要明确写：

```text
实验候选 / 暂定
```

不得写成：

```text
最终规则 / 已证明
```

除非证据真的足够。

## 3. 并行开发原则

- 优先新分支 + PR，不直接在 `main` 上做大范围修改；
- 开始工作前读取最新 `main` 和相关 `docs/handoffs/`；
- 不覆盖无关修改；
- 尽量通过新增低耦合文件减少热点文件冲突；
- 如果必须修改热点文件（如 `engine.py`），PR 中明确说明；
- 实验代码与正式产品代码尽量分层，避免实验结论未经验证直接进入默认规则；
- 一个任务只指定一个主要实现 AI，不让两个 AI 同时编辑同一分支的热点文件；
- 前后端通过冻结 API contract 对接，不把 Engine 规则逻辑复制到前端。

## 4. AI 接手项目时的最低读取顺序

建议至少读取：

```text
README.md
docs/MVP_DEVELOPMENT_START_2026-09-08.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
最新 P0 / normative 规则文档
相关模块代码
最新的 docs/handoffs/
当前 open PR（若有）
```

不要只根据旧聊天摘要或单个 README 猜测当前状态。

## 5. 当前项目阶段（2026-09-08 起）

《规则之外》已经结束“只做核心机制验证”的阶段，进入：

```text
正式 MVP 产品开发
```

阶段转换依据是首个真实 `live-agent-planner-match` Gate PASS：两个隔离 MiMo Agent 在动态公共规则下通过闭合 StrategyIntent + deterministic Planner 完成终局对战，且 Planner submission snapshot audit 为 0 错误。

这不代表以下内容已经被证明：

- 核心玩法已经好玩；
- 当前 Planner 是最终版本；
- 当前 HP / 伤害是最终平衡；
- MiMo 是最终模型选择；
- 自然语言规则不存在 false reject；
- 当前 UI / API 已经定型；
- 项目一定能在竞赛中获奖。

## 6. MVP 双人并行责任域

默认分工：

```text
开发者 A：Python 后端 / Engine integration / Agent / LLM / FastAPI / API contract
开发者 B：React + TypeScript / Board / Rule UI / Replay / Visualization
```

默认热点文件由开发者 A 管理：

```text
src/rules_beyond/engine.py
src/rules_beyond/rule_engine.py
src/rules_beyond/dynamic_rule_controller.py
src/rules_beyond/strategy_agent.py
src/rules_beyond/rule_validator.py
```

开发者 B 不为了 UI 需求直接修改这些文件；需要新能力时先提出 API contract 变更。

完整分工与当前优先级见：

```text
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
```

## 7. 当前必须保留的已知问题

Natural-Language Dynamic Match V0.2 因一条合法规则被 MiMo 安全误拒绝而正式记录为 FAIL。

不能把它改写成 PASS，也不能通过放松 Validator / Faithfulness Verifier 来掩盖。

MVP 中应通过：

```text
清晰的拒绝反馈
可重新措辞
后续评估安全重试策略
```

解决该可用性问题。
