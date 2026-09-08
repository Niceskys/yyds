# 《规则之外》V0.2 双人并行开工准入

状态：**PASS — Developer A 与 Developer B 可以立即并行开发**  
基线：`main@f5a72e9b41e7f5cf23bbe763ece88aba82f6a4c9`  
日期：2026-09-08

本文件只回答一个问题：**现在 A、B 是否都已经具备独立开工条件，且不会因为缺少对方产物而被迫等待？**

结论：**是。**

执行任务：

```text
Developer A → Issue #37
Developer B → Issue #38
```

---

## 1. 为什么现在允许同时开工

当前 `main` 已具备四个共享前提：

1. `docs/GAMEPLAY_FLOW_V0.2.md` 已冻结当前玩法；
2. `docs/MVP_API_CONTRACT_V0.2.md` 已冻结公共 API / Replay / UI 所需字段；
3. `src/rules_beyond/api_contract.py` 已是 V0.2 Pydantic canonical source；
4. `contracts/fixtures/mvp-v0.2/` 已提供前端可直接使用的 schema-validated fixture。

PR #36 合并前，以下 CI 已全部通过：

```text
tests
behavior-diagnostics
dynamic-rule-replacement
```

因此当前共享合同足以让前后端分离开发。

---

# 2. Developer A — 可以立即开工

对应 GitHub Issue：**#37 — `[Developer A] 迁移 DynamicRuleController 到 V0.2 回合间状态机`**

## 当前任务

```text
A0 — DynamicRuleController V0.2 intermission migration
```

建议分支：

```text
backend/controller-v02-intermission
```

A 当前不需要等待任何前端代码。

A 的输入已经齐全：

```text
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_API_CONTRACT_V0.2.md
src/rules_beyond/dynamic_rule_controller.py
src/rules_beyond/rule_engine.py
现有 controller / engine / rule tests
```

A 负责把旧：

```text
Phase 0 before Round 1
Round 3 / 6 / 9 ... rule phase
```

迁移为：

```text
Round 1 无玩家规则直接执行
每个非终局回合后进入玩家决策阶段
失败规则可重试
同一决策阶段最多成功替换一次规则
成功后仍等待 continue
continue 后才能执行下一回合
terminal 后不再进入玩家决策阶段
```

A 的首批主要修改路径：

```text
src/rules_beyond/dynamic_rule_controller.py
tests/*controller* / 新增对应 controller tests
必要时低耦合新增 backend/domain helper
```

A **不要修改**：

```text
web/**
前端布局/样式
玩家中文文案
```

A0 完成后，A 可继续独立进入：

```text
A1 MatchApplicationService + in-memory repository
A2 revision / lock / idempotency
A3 FastAPI five-route vertical slice
```

---

# 3. Developer B — 可以立即开工

对应 GitHub Issue：**#38 — `[Developer B] 使用 V0.2 fixtures 开发 React/Vite 游玩界面`**

## 当前任务

```text
B0/B1 — React/Vite App Shell + Game Board / Status
```

建议分支：

```text
frontend/app-shell-v02
```

B 当前**不需要等待 A0、A1 或真实 FastAPI**。

B 的输入已经齐全：

```text
contracts/fixtures/mvp-v0.2/
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_API_CONTRACT_V0.2.md
src/rules_beyond/api_contract.py
OpenAPI generator
```

B 第一阶段直接用 fixture 开发：

```text
初始页：《规则之外》 + 开始游戏
5×5 棋盘
红方 / 蓝方面板
生命值
当前策略
实际行动
当前有效属性
当前公共规则
已完成回合数
规则制定次数
战局升温
本回合结果
规则输入
提交规则
继续下一回合
```

B 的主要修改路径：

```text
web/**
```

B **不要修改**：

```text
src/rules_beyond/engine.py
src/rules_beyond/rule_engine.py
src/rules_beyond/dynamic_rule_controller.py
src/rules_beyond/rule_validator.py
后端规则语义
```

前端不得自己计算：

```text
规则是否合法
规则是否触发
弓箭命中率
有效属性
战局升温等级
终局结果
```

这些全部由后端 authoritative state 提供；Mock 阶段按 fixture 展示即可。

---

# 4. A/B 现在不会互相阻塞

当前并行关系：

```text
Developer A
DynamicRuleController V0.2
        │
        │ 不依赖 B
        ▼
MatchApplicationService

Developer B
React/Vite + V0.2 fixtures
        │
        │ 不依赖 A0/A1
        ▼
Board / Rule / Status / Event / Replay UI
```

双方第一次真正需要再次同步，是：

```text
A 的真实 FastAPI vertical slice 可调用
+
B 的 fixture UI 已基本完成
↓
Frontend real API integration
```

在这之前，两边不应因为“等对方”停工。

---

# 5. 当前冻结的共享接口

A/B 并行期间，以下内容视为冻结共享面：

```text
GAMEPLAY_FLOW_V0.2
MVP_API_CONTRACT_V0.2
schema_version = mvp-v0.2
replay_version = replay-v0.2
五个 /api/v1 路由
MatchSnapshot
PlayerDecisionSnapshot
BattleEscalationSnapshot
RuleSubmissionResult
PublicStrategyDecision
ReplaySnapshot
ErrorEnvelope
```

如果任何一方发现字段不够：

```text
先提出 contract change
→ A/B 共同确认
→ 修改 canonical schema + fixture
→ 再继续消费
```

禁止：

- A 静默改公共字段；
- B 在 TypeScript 中自行发明永久字段；
- 为了临时 UI 方便复制一套游戏规则逻辑到前端。

---

# 6. 文件冲突规避

### A 默认拥有

```text
src/rules_beyond/**
Python backend tests
后端 service / repository / API 实现
```

### B 默认拥有

```text
web/**
frontend tests
frontend assets
```

### Shared — 暂时不要未经协调并行修改

```text
docs/GAMEPLAY_FLOW_V0.2.md
docs/MVP_API_CONTRACT_V0.2.md
src/rules_beyond/api_contract.py
src/rules_beyond/openapi_contract.py
src/rules_beyond/contract_fixtures.py
contracts/fixtures/mvp-v0.2/**
```

---

# 7. Developer A 开工完成条件

A0 合并前至少证明：

- Round 1 前无规则提交入口；
- Round 1 可直接执行；
- 每个非终局完整回合后进入 intermission；
- rejected submission 可重试；
- accepted submission 后本 intermission 禁止第二次成功替换；
- accepted 后仍需 continue；
- 换规则不重置 `no_damage_streak` / public history；
- terminal 不再开放 intermission；
- 原 Engine / RuleValidator 行为未被意外改变；
- CI 全绿。

---

# 8. Developer B 开工完成条件

B 第一阶段不以“接上真后端”为完成条件。

B0/B1 合并前至少做到：

- 初始页可进入游戏页；
- 5×5 棋盘可按 fixture 渲染；
- 红蓝状态与中文策略名称可渲染；
- 当前公共规则、已完成回合、规则制定次数、战局升温可渲染；
- `PLAYER_DECISION` 下规则输入 / 提交 / 继续按钮状态正确；
- accepted fixture 会锁定本轮规则输入，但继续按钮仍可用；
- rejected fixture 允许修改后再次提交；
- terminal fixture 禁止继续提交/推进；
- UI 不展示 chain-of-thought/private memory；
- 不在前端实现游戏裁判逻辑。

---

# 9. 当前并行开发口令

从本文件合并起，项目状态正式记为：

```text
PARALLEL START GATE = PASS

Developer A: START
Developer B: START
```

当前推荐同时进行：

```text
A → Issue #37 → backend/controller-v02-intermission
B → Issue #38 → frontend/app-shell-v02
```

除非出现 V0.2 contract blocker，否则任何一方都不应以“等待另一方完成”为理由停止当前任务。
