# Developer A Execution Gate

> **Developer A / 后端 AI 在进行任何非 trivial 开发前必须先检查本文件。**
>
> 本文件只决定“现在允许 Developer A 做什么”，不替代 `AI_DEVELOPER_START_HERE.md`、Issue、contract 或 handoff。

## CURRENT STATUS

```text
DEVELOPER_A_GATE = REVIEW_FIX_ONLY
CURRENT_TASK = A3 PR #59 review-fix only
ISSUE = #53
PR = #59
WORKING_BRANCH = backend/fastapi-v02
DO_NOT_START_NEW_TASK = true
```

## 当前授权

A3 主体已经实现并进入 PR #59。Developer A **不得重新开始 A3，也不得开始旧 Day 4 / Day 5 或其他新的后端产品任务**。

当前只允许：

```text
读取最新 main / Issue #53 / PR #59 / Shared Review 评论
继续已有 backend/fastapi-v02
修复 PR #59 明确列出的 review blocker
运行测试 / CI
更新 A3 handoff 与 PR 描述
push 到原 PR #59
```

禁止：

```text
新建另一个 A3 分支或 PR
开始新的 backend feature
开始旧 Day 4 / Day 5
修改 Developer B web/**
扩大 public schema / OpenAPI
重写 A1/A2 revision / lock / idempotency
修改 gameplay / Engine / Controller cadence / Rule DSL / Validator
引入 DB / Redis / Celery / WebSocket / 账号 / leaderboard
```

## 当前唯一 review-fix

PR #59 的 A3 主体已经通过 Shared Review。当前只剩一个 **B4-facing provider failure 语义收尾**：

### 1. Strategy provider failure

Authoritative 语义：

```text
strategy provider/model failure
→ IsolatedStrategyAgent fallback
→ HTTP 200 AdvanceResult
→ round 正常完成并提交
→ 失败方 PublicStrategyDecision.status = FALLBACK_MODEL_ERROR
→ degraded = true
```

这不是 503。

必须新增 HTTP regression test，且 response 不得泄露 raw provider exception。

### 2. Rule provider failure

Authoritative 语义：

```text
rule provider/model failure
→ HTTP 200 RuleSubmissionResult
→ accepted = false
→ public_code = MODEL_UNAVAILABLE
→ revision 不增加
→ rule_change_count 不增加
→ intermission 保持可继续提交
```

这不是 503。

必须新增 HTTP regression test，且 response 不得泄露 raw provider exception。

### 3. 真正的 503

只有真正的：

```text
RecoverableMatchFailure
```

即完整 round / mutation 无法安全完成时，才映射：

```text
503 INTERNAL_ERROR
retryable = true
```

### 4. 文档修正

必须修正：

```text
docs/handoffs/2026-09-09-fastapi-vertical-slice-v02.md
PR #59 描述
```

不得再写成“`/advance`、`/rules` 真实 provider 失败都会 503”。

## A3 已通过的边界，不要重做

Shared Review 已确认以下主体方向成立：

- 五个 FastAPI 路由只调用 A2 repository；
- ErrorEnvelope / RequestValidationError 集中映射；
- route 使用同步 `def`，同步 provider/repository 不直接阻塞 ASGI event loop；
- runtime ASGI server 入口存在；
- OpenAPI snapshot 无漂移；
- `MIMO_BASE_URL` HTTPS-only；
- 防止携带 `api-key` 的跨主机 / scheme downgrade redirect；
- `uvicorn` runtime dependency 与 `httpx` dev dependency 已显式声明；
- import / OpenAPI export 不要求 `MIMO_API_KEY`。

不要为了 review-fix 重构这些已经通过的部分。

## 验证要求

review-fix 后至少运行：

```text
python -m pytest -o addopts="" -q
python -m rules_beyond.dynamic_rule_experiment_v02 --matches-per-pair 500
python -m rules_beyond.diagnostics --matches-per-pair 2000
```

GitHub Actions：

```text
tests
behavior-diagnostics
dynamic-rule-replacement-v02
```

必须全部 success。

不得改变：

```text
contracts/openapi/mvp-v0.2.json
web/src/contract/generated/api.ts
public paths / schema / required Idempotency-Key header
```

如果发现必须改 public contract：

```text
CONTRACT CHANGE REQUIRED
```

停止自行扩 schema，等待 Shared Review。

## 当前项目位置

```text
A0 DynamicRuleController V0.2                         DONE
A1 MatchApplicationService                            DONE
A2 Repository / revision / lock / idempotency         DONE
A3 FastAPI five-route vertical slice                   REVIEW FIX ONLY — PR #59
B4 Developer B real HTTP integration                  BLOCKED — Issue #60
```

B4 只有在：

```text
PR #59 review-fix 完成
→ Shared Review 复审
→ PR #59 merge
```

之后才解除 Issue #60 的 BLOCKED。

---

维护规则：PR #59 合并后，本文件必须再次更新，明确 Developer A 下一步是暂停还是进入新的已批准任务；不得长期保留 `REVIEW_FIX_ONLY`。