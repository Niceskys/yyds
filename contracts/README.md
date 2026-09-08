# MVP V0.1 generated contract assets

本目录只保存**公共前后端契约资产**，不保存 Engine 内部对象或 Agent 私有数据。

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
python -m rules_beyond.openapi_contract --output /tmp/rules-beyond-openapi-v0.1.json
```

Developer B 可使用该 OpenAPI 生成 TypeScript 类型。不要手写另一套长期维护的 API 类型。

## 生成完整 fixture 集

```bash
python -m rules_beyond.contract_fixtures --output-dir /tmp/rules-beyond-fixtures-v0.1
```

仓库内 `contracts/fixtures/mvp-v0.1/` 只固定保存前端开工所需的代表性 fixture：

```text
rule_accepted.json
rule_rejected.json
match_terminal.json
error_revision_conflict.json
```

完整生成器还会产生 running match、advance result 和 replay 样例。

## 约束

- fixture 必须能够通过 Pydantic canonical schema 校验；
- `private_memory`、`raw_model_output`、system prompt、provider key、chain-of-thought 等不得进入本目录；
- 修改公共 enum、字段名或字段语义前先判断是否属于 breaking change；
- Engine / Rule DSL 的真实 enum 与公共 enum 由 contract tests 做一致性检查。
