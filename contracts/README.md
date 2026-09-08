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

Developer B 可使用该 OpenAPI 生成 TypeScript 类型。不要手写另一套长期维护的 API 类型。

## 生成完整 fixture 集

```bash
python -m rules_beyond.contract_fixtures --output-dir /tmp/rules-beyond-fixtures-v0.2
```

仓库内 `contracts/fixtures/mvp-v0.2/` 固定保存前端最重要的代表性 fixture：

```text
match_player_decision.json
rule_accepted.json
rule_rejected.json
match_terminal.json
error_revision_conflict.json
```

完整生成器还会产生：

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

## 约束

- fixture 必须能够通过 Pydantic canonical schema 校验；
- `private_memory`、`raw_model_output`、system prompt、provider key、chain-of-thought 等不得进入本目录；
- 修改公共 enum、字段名或字段语义前先判断是否属于 breaking change；
- Engine / Rule DSL 的真实 enum 与公共 enum 由 contract tests 做一致性检查；
- API 内部值可以是英文稳定 enum，但普通玩家 UI 尽量使用中文映射。
