# Handoff — A3 V0.2 FastAPI 五路由真实 vertical slice

> 日期：2026-09-10
> 分支：`backend/fastapi-v02`
> 对应 Issue：#53
> 基线：`main@8d222217ac9e30f959b3fe8e8d76b0bba2c4312b`
> Gate：`DEVELOPER_A_GATE = READY`（`34df26d0`，2026-09-10 Shared Review 解除暂停）
> 状态：**A3 IMPLEMENTED — PR review。未合并、未自动 merge。**

## 1. 本轮范围

把 `openapi_contract.py` 的 contract-only 501 stub 变成可真实调用的 HTTP vertical slice，
同时保持五个冻结路由与 public DTO 不变：

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

Route 层没有重新实现 revision CAS、idempotency、per-match lock、strategy、planner、
Engine round、Replay assembly、battle escalation、effective stats 或 rule pipeline。

## 2. 核心文件

```text
新增 src/rules_beyond/api_app.py       build_app(repository) + 五个真实路由 + MatchRepositoryPort
新增 src/rules_beyond/api_errors.py    唯一 typed error / RequestValidationError → ErrorEnvelope 映射点
新增 src/rules_beyond/api_runtime.py   build_runtime_repository_from_env()
新增 src/rules_beyond/api_server.py    可执行 ASGI 入口（uvicorn）
改   src/rules_beyond/openapi_contract.py  contract_app 复用 api_app.build_app()，OpenAPI 冻结不变
改   src/rules_beyond/mimo_rule_provider.py / mimo_strategy_provider.py  transport hardening
改   pyproject.toml                    runtime uvicorn + dev httpx
新增 tests/test_fastapi_v02.py
新增 tests/test_api_error_mapping.py
新增 tests/test_mimo_transport_security.py
```

未改：`match_application_service.py`、`match_repository.py`、`api_contract.py`、
`openapi_contract.py` 的 OpenAPI 输出、`contract_fixtures.py`、`engine.py`、
`dynamic_rule_controller.py`、`rule_dsl.py`、`rule_validator.py`、`strategy_agent.py`、
`contracts/**`、`web/**`。

## 3. 路由实现

| 路由 | 行为 | 返回 |
|---|---|---|
| `POST /api/v1/matches` | `repository.create_match(seed=...)`；不执行 Round 1、不调用 provider | `201 MatchSnapshot` |
| `GET /api/v1/matches/{match_id}` | `repository.get_match_snapshot()`；零 mutation、零模型调用 | `200 MatchSnapshot` |
| `POST .../rules` | `repository.submit_public_rule(expected_revision, Idempotency-Key, player_text)` | `200 RuleSubmissionResult` |
| `POST .../advance` | `repository.advance_match(expected_revision, Idempotency-Key)`；一次调用即完整 mutation | `200 AdvanceResult` |
| `GET .../replay` | `repository.get_replay()`；零模型调用、零 revision 变化 | `200 ReplaySnapshot` |

规则业务拒绝（`NO_CANDIDATE` / `RULE_REJECTED` / `FAITHFULNESS_REJECTED` /
`MODEL_UNAVAILABLE`）仍然是 `200 RuleSubmissionResult`，不会被错误转成 ErrorEnvelope。

## 4. ErrorEnvelope 单一映射点

`api_errors.py` 是唯一映射点，五个 route 不复制任何 try/except：

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
RuntimeNotConfiguredError     -> 503 INTERNAL_ERROR（contract-only app 未接线）
未映射的 MatchApplicationError 子类 -> 500 INTERNAL_ERROR（不静默继承别的 status）
unexpected exception          -> 500 INTERNAL_ERROR，清洗后 message
```

- `error_code` / `retryable` 直接取异常携带的 authoritative 值，A3 不再推导业务语义；
- status 按异常 MRO 查表，新的子类不会静默拿到别的错误的 status；
- message 来自封闭表（不从 `str(exc)` 取），`REVISION_CONFLICT` 与
  `contracts/fixtures/mvp-v0.2/error_revision_conflict.json` 完全一致；
- provider body / api-key / header / system prompt / private memory / stack 无法进入 response。

## 5. RequestValidationError

FastAPI 默认 `{"detail":[...]}` 不会返回给前端：

```text
缺 Idempotency-Key header -> 400 IDEMPOTENCY_KEY_REQUIRED retryable=true
其他 body/path 校验失败    -> 400 INVALID_REQUEST       retryable=false
```

`Idempotency-Key` 仍按冻结 OpenAPI 定义为 required header，没有为了手工判断改成 optional。

## 6. 同步阻塞代码与 ASGI event loop

五个 endpoint 全部写成普通 `def`（不是 `async def`），由 Starlette 在线程池执行，
同步 `urllib` / `threading.Lock` / A1/A2 同步调用不会阻塞 event loop。证据：

```text
tests/test_fastapi_v02.py::test_all_five_endpoints_are_synchronous
tests/test_fastapi_v02.py::test_blocking_repository_calls_do_not_block_the_asgi_event_loop
```

后者用 `httpx.ASGITransport` 在同一个 event loop 内并发发两个请求：match A 的 advance
阻塞在 strategy provider 内部时，match B 的 GET 仍然返回 200（若 route 是 `async def`
直接调用同步阻塞代码，该断言会超时失败）。

## 7. Runtime wiring 与启动

```text
build_runtime_repository_from_env()
  MIMO_API_KEY     必填；缺失 -> RuntimeError
  MIMO_RULE_MODEL  可选
  MIMO_BASE_URL    可选；非 HTTPS -> ValueError（启动即失败）
  -> MatchServiceFactory（每 match 独立 RED/BLUE session）-> InMemoryMatchRepository
```

启动命令（已在本机实测）：

```bash
python -m rules_beyond.api_server --host 127.0.0.1 --port 8000
uvicorn rules_beyond.api_server:create_runtime_app --factory --host 127.0.0.1 --port 8000
```

本机 smoke 实测（`MIMO_API_KEY=dummy`，create/read/replay 不需要 provider）：

```text
POST /api/v1/matches              -> 201, revision 0, lifecycle RUNNING
GET  /api/v1/matches/{id}         -> 200
GET  /api/v1/matches/{id}/replay  -> 200, timeline []
POST .../advance  (无 Idempotency-Key) -> 400 IDEMPOTENCY_KEY_REQUIRED retryable=true
POST .../advance  (stale revision)     -> 409 REVISION_CONFLICT "对局状态已经变化，请刷新后重试。"
GET  /api/v1/matches/missing      -> 404 MATCH_NOT_FOUND retryable=false
```

`import rules_beyond.openapi_contract` / `export_openapi()` / `import rules_beyond.api_server`
都不需要 `MIMO_API_KEY`，也不触网；provider 只在真正启动 runtime 时构建。没有新增
health route 或第六个业务 route。

## 8. Provider transport hardening

```text
ensure_https_url()               base_url / endpoint 必须是 https；构造 provider 与
                                 transport.post_json 都会拒绝 cleartext
CredentialSafeRedirectHandler    urllib 默认会跟随 3xx 并重放请求头（含 api-key）；
                                 现在只允许同源且仍为 https 的 redirect，
                                 跨主机 / scheme 降级 -> MimoTransportSecurityError
error message                    只含 HTTP code / 固定文案，不含 api-key、header、body
```

## 9. 依赖变化

```text
[project].dependencies        + uvicorn>=0.30,<1     （可执行 ASGI server）
[project.optional-dependencies].dev  + httpx>=0.27,<1 （FastAPI TestClient）
```

CI 仍用 `python -m pip install -e '.[dev]'`，因此不再依赖 runner 恰好预装 httpx。

## 10. OpenAPI / 前端 generated contract

```text
contract_app.openapi() 与 contracts/openapi/mvp-v0.2.json 逐字节相同（未漂移）
```

- 五个 path / method / request body / response model / required `Idempotency-Key`
  header / `schema_version = mvp-v0.2` / `replay_version = replay-v0.2` 全部未变；
- 未新增错误 response documentation，避免 checked-in snapshot 变化触发前端
  `contract:check` 漂移；
- `web/**` 与 `contracts/**` 未改，**没有** `CONTRACT CHANGE REQUIRED`；
- 已知遗留：OpenAPI 的 app description 仍是旧文案
  "Route bodies are implemented by MatchApplicationService later."。它属于冻结
  snapshot 的一部分，本轮刻意不改；如需更新，应由 Shared Review 同时更新
  snapshot + generated TS。

## 11. 测试

```text
新增 3 个测试文件 / 57 个测试
pytest -o addopts="" -q        306 passed（A3 前基线 249 passed）
```

覆盖（Issue #53 §11 的 1-20 与 HTTP vertical flow 全部覆盖）：

```text
create 201 / revision 0 / 零 provider 调用
GET 200 / unknown 404 MATCH_NOT_FOUND
first advance -> Round 1 / revision +1 / PLAYER_DECISION
accepted rule -> 仍 PLAYER_DECISION / 不自动 advance / rule_change_count +1
rejected rule -> 正常 RuleSubmissionResult（非 ErrorEnvelope）
same advance Idempotency-Key -> 第一次结果，round/model 只执行一次
same rule Idempotency-Key -> 不重复 Replay / 不重复模型调用
wrong revision -> 409 REVISION_CONFLICT retryable=true
missing / whitespace Idempotency-Key -> 400 IDEMPOTENCY_KEY_REQUIRED
same key + changed payload -> 400 INVALID_REQUEST
terminal advance -> 409 MATCH_TERMINAL
rule before Round 1 -> 409 RULE_SUBMISSION_NOT_ALLOWED
recoverable advance failure -> 503 清洗后的 INTERNAL_ERROR，无 raw provider 文本
GET replay -> 200，零 provider 调用、零 revision 变化
malformed body -> 400 INVALID_REQUEST（无 FastAPI detail）
所有 ErrorEnvelope schema_version == mvp-v0.2
response 不含 private_memory / raw_model_output / system_prompt / api-key / stack
runtime app OpenAPI == checked-in snapshot，且只有五个业务 path
import/export 不需要 MIMO_API_KEY；runtime app 只在启动时构建 provider
五个 endpoint 均为同步函数；blocking 调用不阻塞 event loop
HTTP vertical flow: create -> advance R1 -> accepted rule -> advance R2 -> snapshot -> replay
MiMo transport: https-only、跨主机/scheme 降级 redirect 拒绝、错误信息不含 key
```

全部测试使用 deterministic fake provider + in-memory repository，无真实 MiMo 网络。
vertical flow 测试额外 patch `OpenerDirector.open` 抛错，证明整条 HTTP 链路不触网。

## 12. 验证

```text
python -m pytest -o addopts="" -q                                            306 passed
python -m rules_beyond.dynamic_rule_experiment_v02 --matches-per-pair 500     PASS
python -m rules_beyond.diagnostics --matches-per-pair 2000                    PASS
OpenAPI snapshot parity                                                      identical
手动 uvicorn（python -m / --factory 两种入口）                    实际 HTTP 200/201/400/404/409
```

## 13. 提交

```text
f148ae4 feat(backend): wire V0.2 FastAPI routes to match repository
f07ee90 feat(backend): add runtime MiMo wiring and harden provider transport
7446f1c test(backend): cover the real HTTP vertical slice and idempotent retries
<docs>  docs(backend): record A3 FastAPI handoff and status
```

## 14. 留给 B4 / 未完成

```text
Developer B B4 real API integration
- 启动：python -m rules_beyond.api_server --host 127.0.0.1 --port 8000
- 目前无 CORS / 无鉴权 / 无持久化（in-memory，重启丢失）
- 真实 provider 需要 MIMO_API_KEY；create/get/replay 不需要
```

## 15. 风险 / 需要审核

1. in-memory repository：进程重启即丢失；多进程/持久化仍不在 MVP 范围。
2. `/advance`、`/rules` 会真实调用 MiMo；失败时 HTTP 返回 503 INTERNAL_ERROR，
   前端需要提示“稍后重试”，但不能展示内部原因。
3. OpenAPI 未新增 4xx/5xx response documentation（刻意保持 snapshot 稳定）；
   如需补齐需走 Shared Review。
4. app description 文案仍为旧文案（见 §10）。
5. CORS 未开启：B4 建议用 Vite dev proxy / 同源部署，不要在本轮扩大安全配置。
