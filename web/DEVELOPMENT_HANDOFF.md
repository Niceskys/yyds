# Developer B Handoff

## 当前基线

- integration baseline: `main@873000a1c0c6b55835905bcaa94a5de07b60b581`
- A3 merge: `b79b1da08a3ff5801b286b5f970f7e371fd85a08`（PR #59）
- current Developer B state: **B4 CURRENT**
- B4 Issue: #60
- contract version: `mvp-v0.2`
- B0 App Shell: DONE（PR #43）
- B1 fixture UI: DONE（PR #43）
- B3 selectable Replay: DONE（PR #47）
- Issue #45 npm audit: DONE（PR #54）
- Shared OpenAPI snapshot: DONE（Issue #56 / PR #57）
- B4-prep generated TS + API adapter seam: DONE（Issue #55 / PR #58）
- B4 real HTTP integration: **CURRENT — 可以开始**

## 公共契约权威链

```text
src/rules_beyond/api_contract.py
        ↓
src/rules_beyond/openapi_contract.py
        ↓
contracts/openapi/mvp-v0.2.json
        ↓ openapi-typescript 7.13.0
web/src/contract/generated/api.ts
        ↓
web/src/contract/types.ts
        ↓
MatchApiAdapter / ViewModel / React
```

不要手写第二套 DTO；OpenAPI/generated TS 仍由现有 parity / `contract:check` 守卫。

## A3 已完成能力

真实 backend 已合并：

```text
POST /api/v1/matches
GET  /api/v1/matches/{match_id}
POST /api/v1/matches/{match_id}/rules
POST /api/v1/matches/{match_id}/advance
GET  /api/v1/matches/{match_id}/replay
```

本地启动：

```bash
python -m rules_beyond.api_server --host 127.0.0.1 --port 8000
```

或：

```bash
uvicorn rules_beyond.api_server:create_runtime_app --factory --host 127.0.0.1 --port 8000
```

A3 最终 CI / Shared Review：

```text
308 tests PASS
behavior-diagnostics PASS
dynamic-rule-replacement-v02 PASS
OpenAPI snapshot parity unchanged
```

## Provider failure 的最终 B4 语义

**不要把“模型失败”统一当成 HTTP 503。**

### Strategy provider/model failure

```text
HTTP 200 AdvanceResult
round 正常完成并提交
失败方 PublicStrategyDecision.status = FALLBACK_MODEL_ERROR
degraded = true
```

前端可显示非阻断的“模型降级策略”提示，但对局继续正常展示。

### Rule provider/model failure

```text
HTTP 200 RuleSubmissionResult
accepted = false
public_code = MODEL_UNAVAILABLE
revision 不增加
rule_change_count 不增加
仍处于 PLAYER_DECISION
can_submit_rule = true
```

前端提示“模型暂时不可用，可稍后重新提交”，不要当 503。

### 真正的 RecoverableMatchFailure

```text
HTTP 503
ErrorEnvelope.error.code = INTERNAL_ERROR
retryable = true
```

前端保留原 authoritative snapshot，不自行推进；同一次未知结果的用户意图重试必须复用原 Idempotency-Key。

## B4 当前任务

正式 Issue：#60。

建议分支：

```text
frontend/real-api-v02
```

实现真实 `HttpMatchApiAdapter`，复用 #55 的 transport-neutral `MatchApiAdapter`：

```text
createMatch(seed?)
getMatch(matchId)
submitRule({ matchId, expectedRevision, idempotencyKey, playerText })
advanceMatch({ matchId, expectedRevision, idempotencyKey })
getReplay(matchId)
```

主流程从：

```text
fixtures/mock → ViewModel → React
```

切到：

```text
FastAPI V0.2 → HttpMatchApiAdapter → generated DTO → existing ViewModel → React
```

## Revision / Idempotency-Key

- `expected_revision` 永远取当前服务端 snapshot；
- 新用户意图生成新 Idempotency-Key；
- 同一次用户意图因网络错误/结果未知而 retry，必须复用原 key；
- 前端禁止本地 `revision + 1`；
- 409 `REVISION_CONFLICT` 后重新 GET authoritative snapshot，不自动重放旧 mutation。

## ErrorEnvelope UX

集中处理，不要在组件里分散解析：

```text
MATCH_NOT_FOUND
REVISION_CONFLICT
IDEMPOTENCY_KEY_REQUIRED
INVALID_REQUEST
MATCH_TERMINAL
RULE_SUBMISSION_NOT_ALLOWED
ADVANCE_NOT_ALLOWED
INTERNAL_ERROR
```

不得把 raw body、stack、provider raw error、system prompt、private memory、API key 显示到 UI。

## 正式游玩流程

```text
开始游戏
→ createMatch
→ RUNNING / revision 0
→ 用户继续
→ advance Round 1
→ PLAYER_DECISION
→ rejected rule 可重试
→ MODEL_UNAVAILABLE 可重试
→ accepted 后锁规则输入，但不自动 advance
→ 用户继续
→ advance 下一完整 Round
→ ...
→ terminal
```

第一回合前规则输入仍不可用。前端不模拟 Engine、命中率、规则合法性、effective stats、battle escalation 或 terminal。

## Replay

正式 Replay 使用：

```text
GET /api/v1/matches/{match_id}/replay
```

继续复用现有 B3：

```text
ReplaySnapshot → Replay Adapter → Replay ViewModel → Replay UI
```

不要从当前 UI 反推 Replay，也不要重新计算 round/events。

## Mock 收口

B4 完成后，正式游玩路径不得继续依赖：

```text
advance_round.json
rule_accepted.json
rule_rejected.json
match_terminal.json
MockScenarioBar
```

但 `contracts/fixtures/mvp-v0.2/**` 继续保留作为 contract / ViewModel regression 资产。

## 本地连接

优先使用 Vite dev proxy / 同源风格连接 `/api/v1`，不要为了本地开发擅自在后端放开 `CORS *`。

API base 必须可配置；production 不应硬编码 `127.0.0.1:8000`。

## Loading / duplicate action

mutation 进行中：

- 对应按钮 loading；
- 阻止重复点击生成多个不同 key；
- 不锁死无关只读 UI；
- 网络结果未知时保留原 snapshot，并用同 key retry。

terminal 后 submit/advance 全禁用，Replay / 状态查看保持可用。

## 最低验证

至少通过：

```text
npm ci
npm run contract:check
npm run typecheck
npm run test
npm run build
```

测试至少覆盖：create、Round 1、accepted/rejected、MODEL_UNAVAILABLE、FALLBACK_MODEL_ERROR、503、Idempotency-Key retry、409 resync、Replay、terminal、unknown event fallback、privacy、loading duplicate guard、正式主流程不再由 fixture 推进。

不得执行 `npm audit fix --force`。

## Developer A 当前状态

根目录 `DEVELOPER_A_GATE.md`：

```text
DEVELOPER_A_GATE = PAUSED_BY_OWNER
LAST_COMPLETED_TASK = A3 FastAPI V0.2 five-route vertical slice
DO_NOT_START = true
```

A0/A1/A2/A3 全部 DONE。Developer A 当前不应开始旧 Day 4/Day 5 或任何新后端任务，直到 Shared Review 明确批准新的 Issue。

## 下一位 Developer B 必须先读

1. `DEVELOPER_A_GATE.md`
2. Issue #60
3. PR #59 / A3 handoff
4. `docs/GAMEPLAY_FLOW_V0.2.md`
5. `docs/MVP_API_CONTRACT_V0.2.md`
6. `contracts/README.md`
7. `contracts/openapi/mvp-v0.2.json`
8. `web/DEVELOPMENT_HANDOFF.md`
9. `web/NPM_AUDIT_2026-09-09.md`
10. 最近 5–10 个 main commits
