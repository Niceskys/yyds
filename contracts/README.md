# MVP V0.2 generated contract assets

本目录只保存**公共前后端契约资产**，不保存 Engine 内部对象或 Agent 私有数据。

当前玩法基线：

```text
docs/GAMEPLAY_FLOW_V0.2.md
```

当前公共 API 规范：

```text
docs/MVP_API_CONTRACT_V0.2.md
```

`mvp-v0.1/` 保留为历史合同样例，不再作为新前端开发依据。

## Canonical source

唯一代码生成源：

```text
src/rules_beyond/api_contract.py
```

FastAPI / OpenAPI 入口：

```text
src/rules_beyond/openapi_contract.py
```

Fixture 生成器：

```text
src/rules_beyond/contract_fixtures.py
```

## 生成 OpenAPI

```bash
python -m rules_beyond.openapi_contract --output /tmp/rules-beyond-openapi-v0.2.json
```

Developer B 可使用该 OpenAPI 生成 TypeScript 类型。不要手写另一套长期维护的 API schema。

当前仓库**不要求 checked-in OpenAPI JSON 作为 B0/B1/B2/B3 的开工前提**。Mock 阶段允许使用：

```text
checked-in V0.2 fixtures
→ frontend adapter
→ UI ViewModel
→ React components
```

但 UI ViewModel 只是展示投影，不得复制完整 Python/Pydantic schema，也不得承载游戏裁判逻辑。真实 API 接入阶段应切换到 OpenAPI 生成类型。

## 完整 V0.2 fixture 集

重新生成：

```bash
python -m rules_beyond.contract_fixtures --output-dir /tmp/rules-beyond-fixtures-v0.2
```

仓库内 `contracts/fixtures/mvp-v0.2/` 现在固定保存完整 8 个代表性 fixture：

```text
match_initial.json
match_player_decision.json
rule_accepted.json
rule_rejected.json
match_terminal.json
error_revision_conflict.json
advance_round.json
replay_terminal.json
```

`tests/test_contract_fixture_files.py` 同时保证：

```text
checked-in fixture 能通过 canonical schema
checked-in fixture == contract_fixtures.py 生成结果
fixture 中的示例事件来自当前 Engine event vocabulary
```

因此修改 `contract_fixtures.py` 后如果忘记重新导出入库文件，CI 必须失败。

## V0.2 关键变化

```text
无 Round 1 前规则阶段
第 1 回合自动无规则开始
每个非终局完整回合后进入 PLAYER_DECISION
每个回合间最多成功替换一次规则
规则成功后仍需点击继续下一回合
rule_change_count 只统计成功生效规则
战局升温作为公共可解释状态
Replay 从 Round 1 开始，不再有 pre-game phase 0
```

## 前端消费规范

### 坐标

公共坐标是 **1-based**：

```text
row: 1..rows
col: 1..cols
row = 1 位于棋盘顶部
```

V0.2 的 5×5 棋盘中，前端若使用 0-based 数组索引，只允许在渲染边界做：

```text
arrayRow = row - 1
arrayCol = col - 1
```

禁止把转换后的 0-based 坐标重新写回公共状态或 Mock contract。

### 普通玩家界面隐藏字段

下列字段属于公共 contract 的机器可用状态，但 **V0.2 普通玩家 UI 不直接展示内部英文名或内部机制名**：

```text
effective_stats.*.conflict_level
effective_stats.*.hard_liveness
battle_escalation.hard_liveness_active
```

玩家只看到产品层统一概念：

```text
战局升温
```

以及允许展示的有效属性结果。前端只做过滤/中文映射，不修改 schema。

### Event kind

`RoundEventPublicView.kind` 当前仍是开放字符串，而不是冻结 enum。这是有意保留的兼容边界，不代表前端可以假设任意字符串都有专用 UI。

前端处理规则：

```text
已知 kind → 中文专用渲染
未知 kind → 通用安全 fallback
```

未知事件不得导致页面崩溃，也不得显示 provider 原始错误、私有推理或内部异常栈。

Fixture 中的事件必须来自当前 Engine 实际 vocabulary；测试会阻止再次把类似 `BOW_HIT` 这种 Engine 不产生的示例事件提交进仓库。

### 中文映射基线

```text
PRESSURE → 逼近进攻
KITE     → 保持距离
EVADE    → 躲避保命
HOLD     → 原地应对
RED      → 红方
BLUE     → 蓝方
BOW      → 弓箭
KNIFE    → 刀
BattleEscalationSnapshot → 战局升温
```

不要把四分类 intent 固化成不可扩展的永久页面结构；它们是当前 V0.2 公共策略值。

## 约束

- fixture 必须能够通过 Pydantic canonical schema 校验；
- checked-in fixture 必须与 `build_fixtures()` 生成结果一致；
- `private_memory`、`raw_model_output`、system prompt、provider key、chain-of-thought 等不得进入本目录；
- 修改公共 enum、字段名或字段语义前先判断是否属于 breaking change；
- Engine / Rule DSL 的真实 enum 与公共 enum 由 contract tests 做一致性检查；
- 前端不得自行计算规则是否合法、命中率、有效属性、战局升温等级或终局；
- API 内部值可以是英文稳定 enum，但普通玩家 UI 优先使用中文产品文案。
