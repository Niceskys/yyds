# Handoff — MVP API Contract V0.1 implementation

日期：2026-09-08  
分支：`backend/api-contract-v01`

## 本次完成

把 Sprint 0 的文字合同真正落成了代码级 canonical source：

```text
src/rules_beyond/api_contract.py
src/rules_beyond/openapi_contract.py
src/rules_beyond/contract_fixtures.py
```

并增加：

```text
contracts/fixtures/mvp-v0.1/
contracts/README.md
tests/test_api_contract.py
tests/test_contract_fixture_files.py
```

## 现在具备什么

1. Pydantic DTO 可以直接校验 Match / Rule / Strategy / Event / Replay / Error 公共结构；
2. FastAPI contract app 可以生成五个冻结 `/api/v1` 路由的 OpenAPI；
3. `rules` 和 `advance` 的 OpenAPI 强制声明 `Idempotency-Key`；
4. 公共模型使用 `extra=forbid`，避免 private/internal 字段悄悄泄漏；
5. contract tests 检查 public enum 与真实 domain enum 一致；
6. 已有规则通过、规则拒绝、终局、revision conflict 四个静态前端 fixture；
7. 完整 fixture 集可由 `contract_fixtures.py` 生成；
8. OpenAPI 可由 `openapi_contract.py` 生成。

## 重要澄清

实现时发现合同文字有两处不一致，已记录在：

```text
docs/MVP_API_CONTRACT_V0.1_IMPLEMENTATION_NOTES.md
```

核心是：

```text
MOVE_RANGE_ADD    ← 正确现有 DSL enum
MOVE_RANGE_DELTA  ← 旧合同示例笔误，不得新增到 DSL
```

以及：

```text
RULE_PHASE_REQUIRED
```

属于 `ErrorEnvelope`，不是规则提交 public code。

## 明确没有做

本分支没有实现：

- MatchApplicationService；
- MatchRepository；
- revision 实际状态更新；
- per-match lock；
- idempotency 存储；
- 真实 FastAPI route body；
- Engine/Controller/Agent 的应用层编排；
- React 前端。

`openapi_contract.py` 的 route body 故意返回 501；它当前只承担**冻结 HTTP/OpenAPI 形状**的职责。

## 本地验证

在隔离环境中针对新增 contract 代码执行了 9 项 contract tests，全部通过。

最终是否允许合并，以 GitHub Actions 在完整仓库中执行的全量 pytest 为准。

## 下一步

Developer A：

```text
MatchApplicationService
→ in-memory MatchRepository
→ revision check
→ per-match lock
→ idempotency
→ 将 contract-only routes 接到真实 service
```

Developer B：

```text
使用 contracts/fixtures/mvp-v0.1/
→ React/Vite mock shell
→ Board / Status / Rule Panel
→ generated OpenAPI types
```

不要让 Developer B 等待 MatchApplicationService 完成才开始 UI。
