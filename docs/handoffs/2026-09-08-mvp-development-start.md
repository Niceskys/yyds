# Handoff — 2026-09-08 正式 MVP 开发启动

## 1. 发生了什么

首个真实 `live-agent-planner-match` workflow PASS。

运行：

```text
run_number: 1
head_sha: 5c1aeccc7d9ef1727c01f416695415f5a9c9477f
model: mimo-v2.5-pro
seed: 1270000
result: RED_WIN
rounds: 5
gate_passed: true
planner_snapshot_errors: 0
```

真实策略决策：

```text
Phase 0
RED  PRESSURE
BLUE KITE

Phase 1
RED  PRESSURE
BLUE HOLD
```

因此项目从“核心验证阶段”正式进入“MVP 产品开发阶段”。

## 2. 已经存在且不要重复实现的核心

不要重新实现：

```text
Game Engine
Rule-aware Engine
Rule DSL / Validator
Rule Evaluator
Public Rule History
Round24 Hard Liveness
DynamicRuleController
Natural-language strict adapter
NO_CANDIDATE envelope
Intent Guard
Faithfulness Verifier
MiMo China Token Plan provider
fixed NL benchmark / holdout infrastructure
IsolatedStrategyAgent
DeterministicIntentPlanner
Planner submission snapshot audit
```

如果需要改这些核心，必须说明为什么现有能力不满足 MVP，并单独开 PR。

## 3. 必须保留的结论

### Agent / Planner Gate

PASS。

可以进入正式 MVP 开发。

### Natural-Language Dynamic Match V0.2

仍然是 FAIL。

原因是合法规则：

```text
双方移动距离增加1格。
```

被 MiMo 单次安全 false reject。

这不是 unsafe accept，但必须作为 MVP 可用性问题保留。不要通过放松 deterministic safety boundaries 来“修绿”。

### 产品数值

产品 baseline 仍 HP4/K2。

HP5/K2 只是若干 engineering Gate / experiment 配置。

## 4. 新的默认开发分工

### Developer A

```text
Python backend
application service
FastAPI
API contract
Agent / LLM integration
Replay serialization
backend tests
```

### Developer B

```text
React + TypeScript
Vite
5x5 board
rule input
match status
strategy/event visualization
replay timeline
frontend tests
```

详细见：

```text
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
```

## 5. 第一个共同依赖

先冻结：

```text
docs/MVP_API_CONTRACT_V0.1.md
```

建议由 Developer A 负责 PR。

Developer B 在 contract 草案出现后使用 fixtures/mock 并行实现 UI，不等待完整 FastAPI。

## 6. 热点文件冲突风险

以下文件不要由两个开发者/AI 同时修改：

```text
src/rules_beyond/engine.py
src/rules_beyond/rule_engine.py
src/rules_beyond/dynamic_rule_controller.py
src/rules_beyond/strategy_agent.py
src/rules_beyond/natural_language_rule_adapter.py
src/rules_beyond/rule_faithfulness.py
src/rules_beyond/rule_validator.py
```

前端原则上不修改这些文件。

## 7. 下一步

按顺序：

```text
1. API Contract V0.1
2. React/Vite frontend mock shell
3. backend Match Application Service
4. FastAPI vertical slice
5. frontend real API integration
6. Replay
7. E2E
8. UX / animation / competition demo polish
```

不要在此时优先扩充 DSL、账号、排行榜、多单位、地形或 3D。

## 8. 新窗口 / 新 AI 最低读取

```text
README.md
docs/MVP_DEVELOPMENT_START_2026-09-08.md
docs/MVP_PARALLEL_DEVELOPMENT_PLAN.md
docs/AI_COLLABORATION_PROTOCOL.md
本 handoff
相关 P0 normative docs
当前 open PR
```
