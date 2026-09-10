# Handoff — A3 V0.2 FastAPI 五路由真实 vertical slice

> 日期：2026-09-10  
> 分支：`backend/fastapi-v02`  
> 对应 Issue：#53  
> PR：#59  
> 基线：`main@8d222217ac9e30f959b3fe8e8d76b0bba2c4312b`  
> 状态：**A3 IMPLEMENTED — Shared Review 收尾中，未合并。**

## 1. 本轮范围

把 `openapi_contract.py` 的 contract-only 501 stub 变成可真实调用的 HTTP vertical slice，同时保持五个冻结路由与 public DTO 不变：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

架构保持：

```text
FastAPI route
→ InMemoryMatchRepository        （A2：lookup / per-match lock / revision CAS / Idempotency-Key）
→ MatchApplicationService        （A1：orchestration + public projection）
→ Controller / Agents / Planner / Engine
```

Route 层没有重新实现 revision CAS、idempotency、per-match lock、strategy、planner、Engine round、Replay assembly、battle escalation、effective stats 或 rule pipeline。

## 2. 核心文件

```text
新增 src/rules_beyond/api_app.py
新增 src/rules_beyond/api_errors.py
新增 src/rules_beyond/api_runtime.py
新增 src/rules_beyond/api_server.py
改   src/rules_beyond/openapi_contract.py
改   src/rules_beyond/mimo_rule_provider.py
改   src/rules_beyond/mimo_strategy_provider.py
改   pyproject.toml
新增 tests/test_fastapi_v02.py
新增 tests/test_api_error_mapping.py
新增 tests/test_mimo_transport_security.py
新增 tests/test_fastapi_provider_fallbacks.py   # Shared Review 收尾
```

未修改 `match_application_service.py`、`match_repository.py`、`api_contract.py`、Engine/gameplay、`contracts/**` 或 `web/**`。

## 3. 五个路由

| 路由 | 行为 | 返回 |
|---|---|---|
| `POST /api/v1/matches` | `repository.create_match(seed=...)`；不执行 Round 1、不调用 provider | `201 MatchSnapshot` |
| `GET /api/v1/matches/{match_id}` | `repository.get_match_snapshot()`；零 mutation、零模型调用 | `200 MatchSnapshot` |
| `POST .../rules` | `repository.submit_public_rule(expected_revision, Idempotency-Key, player_text)` | `200 RuleSubmissionResult` 或 typed ErrorEnvelope |
| `POST .../advance` | `repository.advance_match(expected_revision, Idempotency-Key)`；一次调用即完整 mutation | `200 AdvanceResult` 或 typed ErrorEnvelope |
| `GET .../replay` | `repository.get_replay()`；零模型调用、零 revision 变化 | `200 ReplaySnapshot` |

规则业务拒绝（`NO_CANDIDATE` / `RULE_REJECTED` / `FAITHFULNESS_REJECTED` / `MODEL_UNAVAILABLE`）属于正常 `200 RuleSubmissionResult`，不会被错误转成 generic HTTP error。

## 4. Provider failure 的 authoritative HTTP 语义

这是 B4 必须按此实现的最终语义，不能把“模型失败”统一理解为 503。

### 4.1 Strategy provider/model failure

```text
strategy provider/model failure
→ IsolatedStrategyAgent fallback
→ HTTP 200 AdvanceResult
→ round 正常完成并提交
→ 失败方 PublicStrategyDecision.status = FALLBACK_MODEL_ERROR
→ degraded = true
```

前端可以显示“模型降级策略”之类的非阻断提示，但不能把这一回合当成服务器失败。

### 4.2 Rule provider/model failure

```text
rule provider/model failure
→ HTTP 200 RuleSubmissionResult
→ accepted = false
→ public_code = MODEL_UNAVAILABLE
→ revision 不增加
→ rule_change_count 不增加
→ lifecycle 仍为 PLAYER_DECISION
→ can_submit_rule = true
```

玩家可以稍后重新提交；不能显示成 503，也不能本地推进 revision。

### 4.3 真正的 503

只有真正的 `RecoverableMatchFailure`，即完整 mutation / round 无法安全完成时，才映射：

```text
503 INTERNAL_ERROR
retryable = true
```

这种情况下前端应保留原 authoritative snapshot，不自行推进，然后允许同一用户意图使用原 Idempotency-Key 重试。

Shared Review 在 `tests/test_fastapi_provider_fallbacks.py` 增加了 HTTP regression，专门锁定 4.1 / 4.2 并验证 raw provider exception 不会进入响应。

## 5. ErrorEnvelope 单一映射点

`api_errors.py` 是唯一映射点，route 不复制 try/except：

```text
MatchNotFoundError            -> 404 MATCH_NOT_FOUND            retryable=false
RevisionConflictError         -> 409 REVISION_CONFLICT          retryable=true
MatchTerminalError            -> 409 MATCH_TERMINAL
RuleSubmissionNotAllowedError -> 409 RULE_SUBMISSION_NOT_ALLOWED
AdvanceNotAllowedError        -> 409 ADVANCE_NOT_ALLOWED
IdempotencyKeyRequiredError   -> 400 IDEMPOTENCY_KEY_REQUIRED   retryable=true
IdempotencyConflictError      -> 400 INVALID_REQUEST            retryable=false
InvalidRequestError           -> 400 INVALID_REQUEST            retryable=false
RecoverableMatchFailure       -> 503 INTERNAL_ERROR             retryable=true
RuntimeNotConfiguredError     -> 503 INTERNAL_ERROR
unexpected exception          -> 500 INTERNAL_ERROR
```

`error_code` / `retryable` 取 typed error authoritative 值；public message 来自封闭表，不从 `str(exc)` 透传 provider body、API key、header、system prompt、private memory 或 stack。

## 6. RequestValidationError

FastAPI 默认 `{"detail":[...]}` 不返回给前端：

```text
缺 Idempotency-Key header -> 400 IDEMPOTENCY_KEY_REQUIRED retryable=true
其他 body/path 校验失败   -> 400 INVALID_REQUEST       retryable=false
```

Header 仍按冻结 OpenAPI 定义为 required。

## 7. 同步阻塞与 ASGI

五个 endpoint 都是普通 `def`，由 Starlette 在线程池执行，避免同步 `urllib` / `threading.Lock` / A1/A2 调用直接阻塞 event loop。

已有测试：

```text
test_all_five_endpoints_are_synchronous
test_blocking_repository_calls_do_not_block_the_asgi_event_loop
```

## 8. Runtime wiring / 启动

```text
build_runtime_repository_from_env()
  MIMO_API_KEY     必填
  MIMO_RULE_MODEL  可选
  MIMO_BASE_URL    可选；必须 HTTPS
  → MatchServiceFactory
  → 每 match 独立 RED/BLUE strategy session
  → InMemoryMatchRepository
```

启动：

```bash
python -m rules_beyond.api_server --host 127.0.0.1 --port 8000
uvicorn rules_beyond.api_server:create_runtime_app --factory --host 127.0.0.1 --port 8000
```

`import rules_beyond.openapi_contract`、`export_openapi()`、`import rules_beyond.api_server` 都不需要 `MIMO_API_KEY`，provider 只在真正 runtime app 构建时创建。

## 9. MiMo transport hardening

- `MIMO_BASE_URL` / endpoint 必须 HTTPS；
- urllib 只允许同源 HTTPS redirect；
- 跨 host 或 scheme downgrade redirect 被拒绝；
- 错误信息不包含 API key、header 或 provider raw body。

## 10. 依赖变化

```text
runtime: + uvicorn>=0.30,<1
dev:     + httpx>=0.27,<1
```

## 11. OpenAPI / 前端 generated contract

```text
contract_app.openapi() == contracts/openapi/mvp-v0.2.json
```

五个 path / method / request body / success model / required `Idempotency-Key` / schema version 均未改变；`web/**` 与 `contracts/**` 未改，没有 `CONTRACT CHANGE REQUIRED`。

已知遗留：OpenAPI description 仍有旧文案 `Route bodies are implemented by MatchApplicationService later.`。它属于冻结 snapshot，本轮不单独改。

## 12. 测试 / CI

A3 原 HEAD 正式 CI 已确认：

```text
306 passed
behavior-diagnostics                 PASS
dynamic-rule-replacement-v02         PASS
```

Shared Review 新增 2 条 provider fallback HTTP regression 后，最终测试数量与 CI 状态以 PR #59 最新 HEAD 的 GitHub Actions 为准。

重点覆盖：

```text
create / get / replay
Round 1 advance
accepted / rejected rule
idempotency replay
revision conflict
missing / whitespace Idempotency-Key
terminal / not-allowed
RecoverableMatchFailure -> 503
strategy provider failure -> 200 degraded fallback
rule provider failure -> 200 MODEL_UNAVAILABLE
malformed request
privacy / secret non-leakage
OpenAPI parity
runtime import without MIMO_API_KEY
ASGI blocking boundary
full create -> R1 -> rule -> R2 -> replay vertical flow
MiMo HTTPS / redirect protection
```

## 13. 主要提交

```text
f148ae4 feat(backend): wire V0.2 FastAPI routes to match repository
f07ee90 feat(backend): add runtime MiMo wiring and harden provider transport
7446f1c test(backend): cover the real HTTP vertical slice and idempotent retries
4a00dfe docs(backend): record A3 FastAPI vertical-slice handoff
1bba921 docs(backend): sync A3 status in active start-here and task board
bfa091b docs(backend): sync V0.2 API contract section 14 with A2 merge and A3 status
8cc1b7f docs(backend): list the real A3 commit hashes in the handoff
9752fab test(backend): lock HTTP provider fallback semantics
```

## 14. 留给 Developer B B4

B4 正式 Issue：#60。

```text
Developer B B4 real HTTP integration
- backend 启动：python -m rules_beyond.api_server --host 127.0.0.1 --port 8000
- 优先 Vite dev proxy / 同源方式，无需求不扩大 CORS
- in-memory repository，进程重启会丢失
- create/get/replay 不调用模型
- strategy provider failure 是 200 degraded fallback
- rule provider failure 是 200 MODEL_UNAVAILABLE
- 503 仅代表 RecoverableMatchFailure
```

## 15. 当前风险 / 后续

1. in-memory repository：进程重启即丢失；多进程/持久化不在当前 MVP 范围。
2. 真实 MiMo 调用仍可能超时/失败，但其 HTTP 语义必须按 §4 区分，而不是统一 503。
3. OpenAPI 未新增所有 4xx/5xx response documentation；保持 snapshot 稳定，如未来补齐需 Shared Review。
4. app description 仍为旧文案，后续若改需同步 snapshot + generated TS。
5. CORS 未开启；B4 优先使用 Vite dev proxy / 同源部署。

---

**注意：2026-09-10 Shared Review 已接管 PR #59 最后 review-fix。Developer A 在 `DEVELOPER_A_GATE = REVIEW_FIX_IN_PROGRESS_BY_SHARED_REVIEW` 期间不要向本分支继续 push。**