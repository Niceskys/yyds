# Handoff — InMemoryMatchRepository / 多对局并发与幂等（A2）

> 日期：2026-09-09
> 分支：`backend/repository-concurrency-v02`
> 对应 Issue：#51
> 基线：`main@a932100ac543904f6dea17d459689ef5eae62d3f`
> 状态：**A2 IMPLEMENTED；等待 PR CI 与 review。未合并、未自动 merge。**

## 1. 本轮目标

把 A1 的「一个 `MatchApplicationService` 实例拥有一个 match」扩展为 A3 可直接调用的
多对局应用层：

```text
match_id lookup
per-match lock
expected_revision / CAS
Idempotency-Key replay
multi-match isolation
```

本轮**不**实现 FastAPI route / HTTP status / Header parsing / ErrorEnvelope（A3），
也不引入 DB / Redis / WebSocket / Celery / 分布式锁。

## 2. 核心文件

```text
src/rules_beyond/match_repository.py     新增：A2 多对局 repository
tests/test_match_repository.py           新增：22 个测试
docs/handoffs/2026-09-09-match-repository-concurrency-v02.md
```

未修改：

```text
src/rules_beyond/match_application_service.py   A1 原样复用
src/rules_beyond/strategy_agent.py
src/rules_beyond/api_contract.py                公开 schema 未改
src/rules_beyond/openapi_contract.py            仍是 contract-only 501 stub
src/rules_beyond/engine.py / rule_dsl.py / rule_validator.py
docs/GAMEPLAY_FLOW_V0.2.md                      normative gameplay 未改
web/**                                          未改
```

## 3. A2 architecture

```text
A3 (later)
   ↓
InMemoryMatchRepository            ← A2：registry / lock / revision / idempotency
   ↓  one per match
MatchApplicationService            ← A1：orchestration + public projection
   ↓
DynamicRuleController / Engine / IsolatedStrategyAgent / Planner
```

A2 只负责 registry 关注点，不复制任何 gameplay：

- match_id 分配与唯一性；
- `match_id -> _MatchRecord`；
- 每个 match 一个 `threading.Lock`；
- 对 A1 authoritative `MatchSnapshot.revision` 做 CAS；
- Idempotency-Key → 第一次 public result 的重放。

## 4. Repository ownership 与 per-match 隔离

`MatchServiceFactory` 每个 match 调用一次，内部创建：

```text
一个 MatchApplicationService
一个 RED IsolatedStrategyAgent（独立 private memory）
一个 BLUE IsolatedStrategyAgent（独立 private memory）
一条 verified NL rule pipeline（独立 rule model wrapper）
```

因此每个 match 拥有独立的 controller state、Replay、revision、idempotency records 和 lock。
provider 若本身是无状态 transport 可由 factory 闭包共享；**stateful strategy session 不共享**。

测试用 `CountingStrategyModel.observations` 证明：

```text
Match A 第二次决策的 private_memory 含 Round 1
Match B 第一次决策的 private_memory 为空
```

## 5. match_id

- `create_match(seed=None)` 由服务端生成 match_id（默认 `match_<16 hex>`）；
- 注册前先创建 service，再在 registry lock 内检查碰撞；碰撞则丢弃并换新 id 重试
  （最多 16 次），**绝不覆盖已有 match**；
- 测试注入 scripted `match_id_factory` 验证碰撞不会覆盖旧比赛。

## 6. Revision 语义

完全复用 A1 authoritative revision，A2 不维护第二套计数：

```text
create              -> revision 0
successful advance  -> revision +1
accepted rule       -> revision +1
rejected rule       -> revision 不变
```

mutation 在 per-match lock 内：

```text
current = service.get_match_snapshot()
if expected_revision != current.revision:
    raise RevisionConflictError(error_code=REVISION_CONFLICT)
```

`RevisionConflictError` 继承 A1 `MatchApplicationError`，携带冻结 `ErrorCode.REVISION_CONFLICT`；
A2 不映射 HTTP 409。

revision mismatch 保证：

```text
零 strategy provider 调用
零 rule model 调用
零 Planner / Engine mutation
零 Replay 修改
零 private memory 修改
```

## 7. Idempotency 顺序（关键）

每个 mutation 的临界区：

```text
acquire per-match lock
→ Idempotency-Key lookup
   → 已存在且 match_id + operation + fingerprint 完全一致：
        返回第一次保存 result 的 deep copy
        不检查新的 current revision
        不调用 provider / Planner / Engine
        不写 Replay
   → 已存在但 operation / payload 不同：IdempotencyConflictError(INVALID_REQUEST)
→ expected_revision check
→ 调 A1 完整 mutation
→ 保存 caller-safe public result
→ release lock
```

**lookup 必须在 revision check 之前**：第一次成功后 revision 已前进，网络重试携带旧的
`expected_revision` 仍必须返回第一次结果，而不是 `REVISION_CONFLICT`。

### 7.1 request fingerprint

```text
ADVANCE:          (expected_revision,)
RULE_SUBMISSION:  (expected_revision, player_text)
```

record 另存 `match_id` 与 `operation`；任一不一致即 `INVALID_REQUEST`，未新增 public enum。

### 7.2 缓存哪些结果

只要 mutation 正常返回 public result 就缓存第一次结果：

```text
ACCEPTED rule
NO_CANDIDATE / RULE_REJECTED / FAITHFULNESS_REJECTED / MODEL_UNAVAILABLE（rejected rule 也缓存）
successful AdvanceResult
```

原因：rejected rule 也会写一条 Replay RULE_ATTEMPT 并调用 rule model；同 key 重试必须直接
返回第一次结果，不能重复写 Replay、不能重复调用模型。

### 7.3 哪些异常不缓存

```text
RevisionConflictError
MatchNotFoundError
RecoverableMatchFailure
InvalidRequestError / IdempotencyConflictError
```

异常不写入 success cache；故障恢复后同 key 可真正 retry（有测试）。

## 8. Per-match lock 与并发

- 每个 match 一个 `threading.Lock`；
- provider / Planner / Engine 全程在该 match 的 lock 内，绝不在 registry lock 内；
- registry lock 只保护 `match_id -> record` 的注册与查找（极短）；
- 不同 match 可并发：测试用两个 `threading.Event` 证明 Match A 阻塞在 provider 时
  Match B 仍能进入自己的临界区（若存在 global lock 会死锁并超时失败）；
- 同 match 不同 key、相同 expected_revision 并发：只执行一个完整 round，另一个
  `REVISION_CONFLICT`；
- 同 match 同 key 并发：只实际执行一次，两个 caller 得到等价结果。

所有并发测试使用 `threading.Event` / blocking fake，无 `sleep` 猜时序、无真实网络。

## 9. Public-copy 边界

A1 已保证 public DTO deep copy。A2：

```text
cache 保存 result.model_copy(deep=True)
每次 cache 命中返回 model_copy(deep=True)
```

调用方篡改第一次 idempotent 返回值不会污染 cache（有测试）。

## 10. 测试

```text
tests/test_match_repository.py   22 tests
```

覆盖：

```text
create 两个 match：id 不同、revision 均 0
match_id 碰撞不覆盖旧 match
unknown match_id -> MatchNotFoundError
空 Idempotency-Key -> INVALID_REQUEST
两 match advance / rule / replay 完全隔离
per-match RED/BLUE strategy session 与 private memory 隔离（observation 断言）
wrong expected_revision -> REVISION_CONFLICT 且零 provider/零 Replay
advance -> revision +1
accepted rule -> revision +1；rejected rule -> revision 不变
same advance key 重试：结果相同、零重复模型调用、ROUND 只有 1 条
same accepted-rule key 重试：rule_id 相同、rule_change_count 不重复、Replay 不重复
same rejected-rule key 重试：不新增第二条 INTERMISSION、不重新调用模型
same key + 不同 player_text -> INVALID_REQUEST、零额外 side effect
same key 跨 operation -> INVALID_REQUEST
caller 篡改缓存返回 DTO 不污染 cache
同 match 不同 key 并发：一个 success、一个 REVISION_CONFLICT，只执行一个 round
同 match 同 key 并发：只执行一次，两结果等价
不同 match blocking provider 可并发进入（非 global lock）
RecoverableMatchFailure 不写 success cache，同 key 可真正 retry
GET snapshot/replay 零 mutation、零模型调用
public/cached response 不含 private_memory / raw_model_output / system_prompt / stack
```

全部使用 deterministic fake / counting fake / blocking fake。

## 11. 验证

```text
pytest -o addopts="" -q                                                 245 passed
python -m rules_beyond.dynamic_rule_experiment_v02 --matches-per-pair 500   PASS
python -m rules_beyond.diagnostics --matches-per-pair 2000                  PASS
```

（A1 基线 223 passed；本 PR 新增 22 个测试。）

## 12. 留给 A3

```text
FastAPI 五路由 adapter：
  POST /api/v1/matches
  GET  /api/v1/matches/{match_id}
  POST /api/v1/matches/{match_id}/rules
  POST /api/v1/matches/{match_id}/advance
  GET  /api/v1/matches/{match_id}/replay
HTTP status / ErrorEnvelope mapping：
  RevisionConflictError -> 409 REVISION_CONFLICT
  MatchNotFoundError    -> 404 MATCH_NOT_FOUND
  IdempotencyConflictError / InvalidRequestError -> 400 INVALID_REQUEST
  RecoverableMatchFailure -> 503 MODEL_UNAVAILABLE / INTERNAL_ERROR
Idempotency-Key Header 解析
```

A3 只需注入 `InMemoryMatchRepository(service_factory=...)`，不得再实现 revision / lock /
idempotency。

## 13. 风险 / 需要审核

1. A2 与 A3 的边界：A2 已提供纯 Python API，A3 只做 HTTP adapter；若 A3 需要不同的异常
   → HTTP 映射策略，请在 A3 设计时确认。
2. in-memory idempotency records 无上限、无 TTL，仅适用于 MVP 单进程；多进程/持久化
   属于后续独立议题。
3. `create_match` 的 match_id 碰撞重试上限 16 次，超过抛 `InvalidRequestError`。
4. A2 不提供 match 删除/过期；A1 单 aggregate 的 API 变更（加入 match_id 参数）尚未发生，
   A3 通过 repository 调用即可。
